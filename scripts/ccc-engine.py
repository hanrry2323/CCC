#!/usr/bin/env python3
"""ccc-engine.py — CCC 多 workspace 并行执行引擎 (v0.28.1+)

替代「每 workspace 一个 engine 进程」模式。
单进程扫描 ~/program/* 下所有含 .ccc/board/ 的项目，全局 MAX_CONCURRENT=3 共享并发池。

使用方式:
  python3 ccc-engine.py

退出:
  Ctrl+C 或 SIGTERM → 优雅关闭
"""

import argparse
import atexit
import json
import os
import signal
import subprocess
import sys
import threading
import time
import traceback as _traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

# 确保当前目录在 path 中
_script_dir = Path(__file__).resolve().parent
if str(_script_dir) not in sys.path:
    sys.path.insert(0, str(_script_dir))

from _config import Config, get_logger
from _executor import _sanitized_env
from _logger import add_file_handler
from _board_store import FileBoardStore
from _utils import now_iso as _utils_now_iso
from _stats_aggregator import aggregate_stats, load_summary
from _cost_telemetry import check_abnormal_traffic as _check_abnormal_traffic
from _capability_evolver import record_failure_pattern as _record_failure_pattern

_log = get_logger("engine")

_engine_shutdown = False
_engine_start_ts: float = time.time()
_restart_log_written: bool = False
_RESTART_LOG_PATH: Path = Path.home() / ".ccc" / "logs" / "engine-restarts.jsonl"

# ccc-board 在 import 时会 eager 绑定 ROOT；默认 workspace 供首次加载
os.environ.setdefault("CCC_WORKSPACE", str(_script_dir.parent))

# v0.28.2: Stats HTTP 默认端口（plan: engine-stats-endpoint）
_STATS_PORT = 7776

import importlib.util as _importlib_util

_ccc_board_path = str(_script_dir / "ccc-board.py")
_spec = _importlib_util.spec_from_file_location("ccc_board", _ccc_board_path)
ccc_board = _importlib_util.module_from_spec(_spec)
_spec.loader.exec_module(ccc_board)

dev_role_launch = ccc_board.dev_role_launch
dev_role_relaunch = ccc_board.dev_role_relaunch
dev_role_check_complete = ccc_board.dev_role_check_complete
reviewer_role = ccc_board.reviewer_role
tester_role = ccc_board.tester_role
kb_role = ccc_board.kb_role
MAX_RETRY = ccc_board.MAX_RETRY

_load_phases = ccc_board._load_phases
_resolve_phase_dependencies = ccc_board._resolve_phase_dependencies
_apply_phase_status_updates = ccc_board._apply_phase_status_updates
_check_phase_failures = ccc_board._check_phase_failures
_current_running_phase = ccc_board._current_running_phase

cfg = Config()


# 日志轮转：engine.log + daily rotate + keep 7 days
_log_dir = Path(os.environ.get("HOME", str(Path.home()))) / ".ccc" / "logs"
_log_dir.mkdir(parents=True, exist_ok=True)
_log_file = str(_log_dir / "engine.log")
add_file_handler("engine", _log_file, when="midnight", interval=1, backup_count=7)


_log.info(
    "ccc-engine config: phase_timeout=%ds, exec_timeout=%ds, engine_tick_interval=%ds",
    cfg.phase_timeout,
    cfg.exec_timeout,
    cfg.engine_tick_interval,
)

_engine_shutdown = False
_MAX_PRODUCT_RETRIES = 3
MAX_CONCURRENT = 3

# v0.35: degraded mode — 引擎自我保护
_degraded_mode = False
_degraded_since: float | None = None
_DEGRADED_QUARANTINE_THRESHOLD = 10   # 30min 内 quarantine > 此值 → degraded
_DEGRADED_FAIL_THRESHOLD = 10         # 30min 内 product_fail > 此值 → degraded
_DEGRADED_RECOVERY_SECONDS = 600      # 10min 无异常 → 自动恢复

# v0.36: 熔断 — upstream 不可用时暂停 abnormal 自动重试
_breaker_open: bool = False
_breaker_since: float = 0.0
_BREAKER_RECOVERY_SECONDS = 120

# v0.36: abnormal 重试（指数退避）
_RETRY_BASE_INTERVAL = 120    # 2min
_RETRY_MAX_INTERVAL = 3600    # 1h
_RETRY_BACKOFF_FACTOR = 2.0
_ABNORMAL_RETRY_KEYWORDS = [
    "重试", "all_failed", "失败", "failed", "超时", "timeout",
    "unhealthy", "不可用", "quarantine", "异常", "exception",
    "stale", "stalled", "exit code", "opencode",
    "product_role", "dev_role", "reviewer", "tester",
]
_TRANSIENT_KEYWORDS = [
    "timeout", "超时", "network", "网络", "upstream", "hang", "hung",
    "连接", "unavailable", "不可用", "econnreset", "temporary",
    "transient", "unhealthy", "opencode", "rate limit", "429",
    "502", "503", "504", "connection", "reset by peer",
]
_PERMANENT_KEYWORDS = [
    "syntaxerror", "importerror", "typeerror", "nameerror",
    "indentationerror", "modulenotfounderror", "attributeerror",
    "语法错误", "编码错误", "invalid syntax", "cannot import",
    "compile failed", "assertionerror",
]

# v0.36: 内存阈值（MB）— 与 Config 默认对齐；cfg 覆盖优先
_MEM_WARN_MB = 400
_MEM_DEGRADED_MB = 800
_MEM_KILL_MB = 1500

# v0.30.0: 全局 opencode 并发计数 — F-CON-01 线程锁 + Phase 2 跨进程 flock
_GLOBAL_OPENCODE_MAX = 6  # ∑ (MAX_CONCURRENT × PHASE_PARALLEL_MAX_WORKERS)


def _opencode_slots_path() -> Path:
    """共享槽位状态文件（测试可设 CCC_OPENCODE_SLOTS_FILE）。"""
    from board.slots import default_state_path

    return default_state_path()


def _global_opencode_count() -> int:
    from board.slots import snapshot

    return int(snapshot(_opencode_slots_path()).get("count") or 0)


class _OpenCodeCountProxy:
    """日志友好的实时计数代理（跨进程快照）。"""

    def __int__(self) -> int:
        return _global_opencode_count()

    def __index__(self) -> int:
        return _global_opencode_count()

    def __format__(self, spec: str) -> str:
        return format(_global_opencode_count(), spec)

    def __repr__(self) -> str:
        return str(_global_opencode_count())

    def __str__(self) -> str:
        return str(_global_opencode_count())

    def __eq__(self, other: object) -> bool:
        return _global_opencode_count() == other

    def __lt__(self, other: object) -> bool:
        return _global_opencode_count() < other  # type: ignore[operator]


_GLOBAL_OPENCODE_COUNT = _OpenCodeCountProxy()

# v0.28.2: Phase 并行调度（plan: engine-phase-parallel-dispatch）
PHASE_PARALLEL_MAX_WORKERS = 2


def _try_acquire_opencode_slot(task_key: str) -> bool:
    """F-CON-01 + Phase 2: 跨进程/线程安全获取 1 个 opencode 槽位。"""
    from board.slots import try_acquire

    return try_acquire(
        task_key,
        max_slots=_GLOBAL_OPENCODE_MAX,
        state_path=_opencode_slots_path(),
    )


def _release_opencode_slot(task_key: str, n: int | None = None) -> int:
    """F-CON-01/02 + Phase 2: 释放 task 持有的槽位。n=None 表示全部释放。"""
    from board.slots import release

    return release(task_key, n, state_path=_opencode_slots_path())


def _drop_active_task_and_slots(
    active_tasks: dict[str, dict] | None, task_key: str
) -> None:
    """F-CON-02: quarantine/完成时统一释放槽位并从 active_tasks 移除。"""
    released = _release_opencode_slot(task_key)
    if active_tasks is not None and task_key in active_tasks:
        active_tasks.pop(task_key, None)
        _save_active_tasks(active_tasks)
    if released:
        engine_log(f"[slot] released {released} opencode slot(s) for {task_key}")


# ---------- 上游健康检测 ----------
_upstream_health_cache: dict = {}  # {"healthy": bool, "checked_at": float}


def _get_relay_url() -> str:
    """复刻 ccc-board.py._get_relay_url：取 AGENT_PLANNER_BASE_URL 或默认 :4000"""
    return os.environ.get("AGENT_PLANNER_BASE_URL", "http://127.0.0.1:4000")


def _is_upstream_healthy() -> bool:
    """检查 relay/proxy 是否可达，30s 缓存。

    v0.40.1: 4xx 视为 proxy 在线（鉴权失败 ≠ 进程宕机）。
    仅连接失败 / 5xx / 超时才判 unhealthy。
    CCC_UPSTREAM_STRICT=1 时恢复旧行为（仅 HTTP 200 = healthy）。
    """
    now = time.time()
    cached = _upstream_health_cache.get("healthy")
    cached_at = _upstream_health_cache.get("checked_at", 0)
    if cached is not None and now - cached_at < 30:
        return cached

    relay = _get_relay_url()
    messages_url = relay.rstrip("/") + "/v1/messages"
    strict = (os.environ.get("CCC_UPSTREAM_STRICT") or "").strip() in ("1", "true", "yes")
    status_code: int | None = None
    err_msg = ""
    try:
        import urllib.error
        import urllib.request

        data = json.dumps({
            "model": "flash",
            "messages": [{"role": "user", "content": "ok"}],
            "max_tokens": 1,
        }).encode()
        req = urllib.request.Request(
            messages_url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "x-api-key": "health-check",
                "anthropic-version": "2023-06-01",
            },
            method="POST",
        )
        try:
            resp = urllib.request.urlopen(req, timeout=8)
            status_code = getattr(resp, "status", None) or resp.getcode()
        except urllib.error.HTTPError as http_exc:
            status_code = http_exc.code
            err_msg = str(http_exc.reason or http_exc)[:120]
    except Exception as exc:
        status_code = None
        err_msg = str(exc)[:120]

    if status_code is None:
        healthy = False
    elif strict:
        healthy = status_code == 200
    else:
        # proxy 可达：2xx/4xx；5xx 或无响应 → 不健康
        healthy = 200 <= status_code < 500

    _upstream_health_cache["healthy"] = healthy
    _upstream_health_cache["checked_at"] = now
    _upstream_health_cache["status_code"] = status_code
    _upstream_health_cache["error"] = err_msg
    # 状态变化写全局 probe 事件（~/.ccc/stats/upstream-probe.jsonl）
    prev = _upstream_health_cache.get("_last_logged")
    sig = (healthy, status_code)
    if prev != sig:
        _upstream_health_cache["_last_logged"] = sig
        try:
            probe_dir = Path.home() / ".ccc" / "stats"
            probe_dir.mkdir(parents=True, exist_ok=True)
            with (probe_dir / "upstream-probe.jsonl").open("a", encoding="utf-8") as fh:
                fh.write(
                    json.dumps(
                        {
                            "ts": now_iso(),
                            "healthy": healthy,
                            "status": status_code,
                            "error": err_msg or None,
                            "relay": relay,
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
        except Exception:
            pass
    if not healthy:
        engine_log(
            f"[health] upstream 不可用 status={status_code} err={err_msg or '-'} "
            f"— 跳过 product_role（缓存 30s）"
        )
    elif status_code and status_code != 200:
        engine_log(
            f"[health] upstream proxy 可达 status={status_code}（视为 healthy）"
        )
    return healthy


def _set_parallel_disabled(val: bool) -> None:
    """Set the global PHASE_PARALLEL_DISABLED toggle (module-level)."""
    global PHASE_PARALLEL_DISABLED
    PHASE_PARALLEL_DISABLED = val


def _write_engine_restart(status: str, reason: str | None = None) -> None:
    """写入结构化重启日志到 ~/.ccc/logs/engine-restarts.jsonl。

    Args:
        status: "started" | "shutdown" | "stopped"
        reason: 描述原因，如 "SIGTERM" | "KeyboardInterrupt" | None（started 时为 None）
    """
    global _restart_log_written
    if _restart_log_written:
        return
    _restart_log_written = True
    uptime = max(0.001, time.time() - _engine_start_ts)
    entry = {
        "ts": _utils_now_iso(),
        "pid": os.getpid(),
        "uptime_sec": round(uptime, 3),
        "status": status,
        "reason": reason,
    }
    try:
        _RESTART_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _RESTART_LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass


PHASE_PARALLEL_DISABLED = False  # 故障 fallback 时设为 True（仅当次 Engine tick）

_stores: dict[str, FileBoardStore] = {}

# Per-task 并行 phase 状态：
#   task_key -> {
#     "groups": [[phase_num, ...], ...],   # 待执行的 group 列表（每组内并行）
#     "current_group": [phase_num, ...] | None,  # 当前正在跑的 group
#     "phase_meta": {phase_num: {subid, pid, started_at}}
#   }
_parallel_phases: dict[str, dict] = {}

# v0.33: product_role 异步 inflight 表（task_key -> {tid, started_at}）
_product_inflight: dict[str, dict] = {}

# backlog+planned 为空时的补充冷却（per-workspace，单位秒）
_last_empty_replenish: dict[str, float] = {}

# v0.31+: hang 自动重启（plan: executor-auto-restart）
_MAX_HANG_RETRY = 2  # 单个 task 最多自动重启 hung 的次数
_hang_retry_counter: dict[str, int] = {}  # task_key -> retry count
_HANG_COUNTER_FILE = Path.home() / ".ccc" / "engine-hang-retries.json"


def _load_hang_retry_counter() -> None:
    """F-ARCH-01: 从磁盘恢复 hang 重试计数。"""
    global _hang_retry_counter
    try:
        if _HANG_COUNTER_FILE.is_file():
            data = json.loads(_HANG_COUNTER_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                _hang_retry_counter = {str(k): int(v) for k, v in data.items()}
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        _hang_retry_counter = {}


def _save_hang_retry_counter() -> None:
    """F-ARCH-01: 持久化 hang 重试计数。"""
    try:
        _HANG_COUNTER_FILE.parent.mkdir(parents=True, exist_ok=True)
        _HANG_COUNTER_FILE.write_text(
            json.dumps(_hang_retry_counter, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError:
        pass


# v0.31+: hang 检测（plan: executor-hang-detection）
# Phase 4 of the pipeline: detect → write .hung → Phase 5 consumes it.
_HANG_CHECK_INTERVAL_SEC = 300  # 5 分钟无活动判定为 hung
# F-FLOW-04: busy-loop 互补 — CPU>0 但超过此秒数仍视为 hung（stale 默认已缩短至 2h）
_HANG_BUSY_MAX_SEC = 3600


def now_iso() -> str:
    return _utils_now_iso()


def engine_log(msg: str, *args: str) -> None:
    if args:
        msg = msg % args
    _log.info("%s", msg)


# ── Stats 日志（结构化 JSONL，供 AI 分析用）──
_STATS_DIR: Path | None = None


def _stats_dir(ws: Path) -> Path:
    global _STATS_DIR
    if _STATS_DIR is None:
        _STATS_DIR = ws / ".ccc" / "stats"
        _STATS_DIR.mkdir(parents=True, exist_ok=True)
    return _STATS_DIR


def _log_stats(ws: Path, event: str, tid: str, **extra) -> None:
    """写一条结构化事件到 .ccc/stats/events.jsonl。"""
    sf = _stats_dir(ws) / "events.jsonl"
    record = {
        "t": now_iso(),
        "event": event,
        "task": tid,
        "workspace": ws.name,
    }
    record.update(extra)
    try:
        with sf.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        pass


_NOTIFY_SCRIPT = _script_dir / "ccc-notify.sh"


def _ccc_notify(title: str, message: str) -> None:
    """非阻塞 macOS 桌面通知（Engine 主循环不等待）。"""
    if not _NOTIFY_SCRIPT.is_file():
        engine_log(f"notify 跳过: {_NOTIFY_SCRIPT} 不存在")
        return
    try:
        subprocess.Popen(
            ["bash", str(_NOTIFY_SCRIPT), title, message],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            env=_sanitized_env(),
        )
    except OSError as exc:
        engine_log(f"notify 失败: {exc}")


def _quarantine_with_notify(
    ws: Path,
    tid: str,
    reason: str,
    store: FileBoardStore | None = None,
    phase: int = 1,
    active_tasks: dict[str, dict] | None = None,
    *,
    role: str | None = None,
    exit_code: int | None = None,
    from_col: str | None = None,
) -> None:
    """移入 abnormal 并触发桌面通知。F-CON-02: 同时释放 opencode 槽位。"""
    _activate_workspace(ws)
    if store is None:
        store = _get_store(ws)
    store.quarantine(tid, reason)
    _log_stats(ws, "quarantine", tid, reason=reason)
    # v0.40: 统一失败账本（写失败必须可见，禁止静默）
    try:
        from _failure_ledger import infer_role_from_reason, record_failure

        record_failure(
            ws,
            task_id=tid,
            role=role or infer_role_from_reason(reason or ""),
            reason=reason or "unknown",
            phase=phase,
            from_col=from_col,
            to_col="abnormal",
            exit_code=exit_code,
            related_stats_event="quarantine",
        )
    except Exception:
        engine_log(f"[failures] record_failure failed for {tid}: {_traceback.format_exc()[:500]}")
    _ccc_notify("CCC", f"任务 {tid} 进入异常状态，原因：{reason}")
    store.update_index()
    # F-CON-02: 释放该 task 全部槽位
    _drop_active_task_and_slots(active_tasks, _task_key(ws, tid))
    # v0.31: 记录教训
    try:
        from _lessons import record_failure as _lesson_fail

        _lesson_fail(ws, tid, phase, reason or "unknown", "")
    except Exception as exc:
        engine_log(f"[lessons] record_failure failed for {tid}: {exc}")
    # v0.32: 自动追加到 docs/lessons.md
    try:
        from _lessons import auto_append_lesson_md

        auto_append_lesson_md(ws, tid, phase, reason or "unknown")
    except Exception as exc:
        engine_log(f"[lessons] auto_append failed for {tid}: {exc}")


def _discover_workspaces() -> list[Path]:
    """发现 Engine 管辖的 workspace（v0.40：默认不再扫全 ~/program）。

    优先级：
      1. CCC_WORKSPACES=name:path,name:path 或 path,path
      2. ~/.ccc/workspaces.json → {"workspaces":[{"path":"..."}]}
      3. 仅 CCC 自身（cfg.ccc_home / 本仓库）
    显式全扫：CCC_DISCOVER_ALL=1（兼容旧行为，不推荐）
    """
    import os as _os

    seen: set[str] = set()
    workspaces: list[Path] = []

    def _add(p: Path) -> None:
        if not p.is_dir():
            return
        if not (p / ".ccc" / "board").is_dir():
            return
        key = str(p.resolve())
        if key in seen:
            return
        workspaces.append(p.resolve())
        seen.add(key)

    env = _os.environ.get("CCC_WORKSPACES", "").strip()
    if env:
        for part in env.split(","):
            part = part.strip()
            if not part:
                continue
            path_s = part.split(":", 1)[-1] if ":" in part else part
            _add(Path(path_s).expanduser())
        if workspaces:
            return workspaces

    registry = Path.home() / ".ccc" / "workspaces.json"
    if registry.is_file():
        try:
            data = json.loads(registry.read_text(encoding="utf-8"))
            for item in data.get("workspaces") or []:
                if isinstance(item, str):
                    _add(Path(item).expanduser())
                elif isinstance(item, dict) and item.get("path"):
                    _add(Path(item["path"]).expanduser())
        except (OSError, json.JSONDecodeError) as exc:
            engine_log(f"[workspace] registry parse failed: {exc}")
        if workspaces:
            return workspaces

    if _os.environ.get("CCC_DISCOVER_ALL", "").strip() in ("1", "true", "yes"):
        program_dir = Path.home() / "program"
        if program_dir.is_dir():
            for p in sorted(program_dir.iterdir()):
                if p.is_dir():
                    _add(p)
            projects_dir = program_dir / "projects"
            if projects_dir.is_dir():
                for p in sorted(projects_dir.iterdir()):
                    if p.is_dir():
                        _add(p)
        return workspaces

    # 默认：仅 CCC 自身
    home = getattr(cfg, "ccc_home", None)
    if home:
        _add(Path(home))
    if not workspaces:
        _add(Path(__file__).resolve().parent.parent)
    return workspaces


def _queue_has_consumable_work(store: FileBoardStore) -> bool:
    """enabled 模式可消费列（不含 abnormal — 回灌需 invent）。"""
    for col in ("backlog", "planned", "in_progress", "testing", "verified"):
        if store.list_tasks(col):
            return True
    return False


def _may_invent() -> bool:
    try:
        from _ccc_control import may_invent

        return may_invent()
    except ImportError:
        return False


def _ws_label(ws: Path, program_dir: Path | None = None) -> str:
    program_dir = program_dir or (Path.home() / "program")
    try:
        return ws.relative_to(program_dir).as_posix()
    except ValueError:
        return ws.name


def _task_key(ws: Path, tid: str) -> str:
    return f"{ws.resolve()}|{tid}"


_workspace_switch_lock = threading.RLock()


def _activate_workspace(ws: Path) -> Path:
    """切换当前 workspace：env + ContextVar + lazy 缓存重置。

    F-CON-03 Phase 2: workspace 经 set_workspace()（废除模块级 ROOT 补丁）。
    """
    ws = ws.resolve()
    with _workspace_switch_lock:
        ccc_board.set_workspace(ws)
        ccc_board._reset_lazy()
    return ws


def _get_store(workspace: Path) -> FileBoardStore:
    key = str(workspace.resolve())
    if key not in _stores:
        _stores[key] = FileBoardStore(workspace)
    return _stores[key]


_BOARD_COLUMNS = (
    "backlog",
    "planned",
    "in_progress",
    "testing",
    "verified",
    "released",
    "abnormal",
)


def _verdict_file(ws: Path, tid: str) -> Path:
    return ws / ".ccc" / "verdicts" / f"{tid}.verdict.md"


def _verdict_is_valid(ws: Path, tid: str) -> bool:
    """verdict 文件必须存在且非空（空文件视为未产出）。"""
    vf = _verdict_file(ws, tid)
    if not vf.is_file():
        return False
    try:
        return bool(vf.read_text(encoding="utf-8").strip())
    except OSError:
        return False


def _find_task_column(store: FileBoardStore, tid: str) -> str | None:
    for col in _BOARD_COLUMNS:
        if any(t["id"] == tid for t in store.list_tasks(col)):
            return col
    return None


def _ensure_task_in_testing(store: FileBoardStore, tid: str) -> None:
    """reviewer 可能提前挪 verified；拉回 testing 以便 tester/pytest 门禁。"""
    if _find_task_column(store, tid) == "verified":
        store.move_task(tid, "verified", "testing")


def _run_pytest(ws: Path) -> tuple[int, str]:
    """在 workspace 跑 pytest tests/；有 .venv 则走 .venv/bin/pytest。"""
    venv_pytest = ws / ".venv" / "bin" / "pytest"
    if venv_pytest.is_file():
        cmd = [str(venv_pytest), "tests/", "-q", "--tb=line"]
    else:
        cmd = ["python3", "-m", "pytest", "tests/", "-q", "--tb=line"]
    try:
        r = subprocess.run(
            cmd,
            cwd=ws,
            capture_output=True,
            text=True,
            timeout=cfg.phase_timeout,
        )
        stdout = r.stdout if isinstance(r.stdout, str) else (r.stdout.decode("utf-8", errors="replace") if r.stdout else "")
        stderr = r.stderr if isinstance(r.stderr, str) else (r.stderr.decode("utf-8", errors="replace") if r.stderr else "")
        output = stdout + stderr
        return r.returncode, output
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else (exc.stdout.decode("utf-8", errors="replace") if exc.stdout else "")
        stderr = exc.stderr if isinstance(exc.stderr, str) else (exc.stderr.decode("utf-8", errors="replace") if exc.stderr else "")
        output = stdout + stderr
    except OSError as exc:
        return 1, str(exc)


def _record_pytest_failure(ws: Path, tid: str, exit_code: int, output: str) -> None:
    """pytest 失败时写 verdict + pids 摘要（供 OpenCode relaunch 回灌）。"""
    vf = _verdict_file(ws, tid)
    vf.parent.mkdir(parents=True, exist_ok=True)
    snippet = output[-2000:] if output else "(无输出)"
    section = (
        f"\n\n## Engine pytest 检查\n\n"
        f"- **退出码**: {exit_code}\n\n"
        f"```\n{snippet}\n```\n"
    )
    try:
        if vf.is_file():
            vf.write_text(vf.read_text(encoding="utf-8") + section, encoding="utf-8")
        else:
            vf.write_text(
                f"# Verdict: {tid}\n\n**FAIL** (engine pytest)\n{section}",
                encoding="utf-8",
            )
    except OSError as exc:
        engine_log(f"写入 pytest 失败记录到 verdict 失败: {exc}")
    # v0.41.1: 独立摘要供 dev prompt 注入
    try:
        pids = ws / ".ccc" / "pids"
        pids.mkdir(parents=True, exist_ok=True)
        (pids / f"{tid}.pytest_fail.md").write_text(
            f"exit_code={exit_code}\n\n{snippet}\n",
            encoding="utf-8",
        )
    except OSError as exc:
        engine_log(f"写入 pytest_fail.md 失败: {exc}")


def _verdict_is_timeout(ws: Path, tid: str) -> bool:
    """检查 verdict 文件是否标记为 TIMEOUT（reviewer LLM 超时但未 quarantine）。"""
    vf = _verdict_file(ws, tid)
    if not vf.is_file():
        return False
    try:
        content = vf.read_text(encoding="utf-8")
        return "**Verdict:** TIMEOUT" in content
    except OSError:
        return False


def _revert_task_commit(ws: Path, tid: str) -> bool:
    """Verdict FAIL 时回滚 task 的最后一个 commit。

    读取 phases.json 拿到 commit hash → git revert → 退回 planned。
    失败仅日志记录，不阻断 engine 主循环。

    Returns:
        True = 回滚成功；False = 失败
    """
    phases_file = ws / ".ccc" / "phases" / f"{tid}.phases.json"
    if not phases_file.exists():
        return False
    try:
        phases_data = _load_phases(tid, ws)
        commits = [
            p.get("commit", "")
            for p in phases_data
            if p.get("commit") and p.get("commit") not in ("null", "None", "")
        ]
        if not commits:
            return False
        last_commit = commits[-1]
    except (OSError, json.JSONDecodeError) as exc:
        engine_log(f"[verdict-gate] {tid} 读 commit hash 失败: {exc}")
        return False

    try:
        result = subprocess.run(
            ["git", "revert", "--no-edit", last_commit],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(ws),
            env=_sanitized_env(),
        )
        if result.returncode != 0:
            engine_log(
                f"[verdict-gate] {tid} revert {last_commit[:12]} 失败: "
                f"{result.stderr[:200]}"
            )
            return False
        engine_log(f"[verdict-gate] {tid} 已 revert commit {last_commit[:12]}")
        return True
    except Exception as exc:
        engine_log(f"[verdict-gate] {tid} revert 异常: {exc}")
        return False


def _clear_verdict(ws: Path, tid: str) -> None:
    """删除 verdict 文件，使 _verdict_is_valid 返回 False，触发 engine 重试。"""
    vf = _verdict_file(ws, tid)
    try:
        vf.unlink(missing_ok=True)
    except OSError:
        pass


_PYTEST_FAIL_MAX = 3  # F-FLOW-01: pytest 连续失败上限 → abnormal


def _parse_verdict_status(content: str) -> str | None:
    """F-FLOW-03: 从 verdict 文件解析 **Verdict:** 字段，不使用裸子串。"""
    for line in content.splitlines():
        stripped = line.strip()
        low = stripped.lower()
        if low.startswith("**verdict:**") or low.startswith("verdict:"):
            raw = stripped.split(":", 1)[1].strip().strip("*").strip()
            return raw.split()[0].upper() if raw else None
    return None


def _run_reviewer_tester_gate(ws: Path, tid: str) -> bool:
    """reviewer verdict + tester + engine pytest 双门禁。通过才移 verified。

    v0.31+: 超时情形 engine 层自动重试（不 quarantine），
    reviewer_retry_on_timeout 次超时后再 quarantine。
    F-FLOW-02: complexity=small 跳过 reviewer+tester，直通 verified（写简短 verdict）。
    """
    _activate_workspace(ws)
    store = _get_store(ws)
    label = _ws_label(ws)

    # F-FLOW-02: small complexity → skip LLM gate
    task_meta = next((t for t in store.list_tasks("testing") if t["id"] == tid), None)
    if task_meta and task_meta.get("complexity") == "small":
        verdict_dir = ws / ".ccc" / "verdicts"
        verdict_dir.mkdir(parents=True, exist_ok=True)
        (verdict_dir / f"{tid}.verdict.md").write_text(
            f"# {tid} Verdict\n\n**Verdict:** PASS\n\n"
            f"complexity=small: skipped reviewer+tester per STARTUP-BRIEF\n",
            encoding="utf-8",
        )
        col = _find_task_column(store, tid)
        if col == "testing":
            store.move_task(tid, "testing", "verified")
            _log_stats(ws, "move", tid, from_col="testing", to_col="verified")
        store.update_index()
        engine_log(f"[{label}] {tid} complexity=small → verified (skip gate)")
        return _find_task_column(store, tid) == "verified"

    timeout_retries = cfg.reviewer_retry_on_timeout
    timeout_count = 0
    verdict_ok = False
    max_attempts = max(2, timeout_retries)

    for attempt in range(max_attempts):
        reviewer_role()
        if _verdict_is_valid(ws, tid):
            if _verdict_is_timeout(ws, tid):
                timeout_count += 1
                if timeout_count >= timeout_retries:
                    engine_log(
                        f"[{label}] {tid} reviewer 超时重试 {timeout_count}/{timeout_retries} 耗尽 → abnormal"
                    )
                    cur_phase = _current_running_phase(tid)
                    _quarantine_with_notify(
                        ws, tid, "reviewer 超时重试耗尽", store, phase=cur_phase
                    )
                    return False
                _clear_verdict(ws, tid)
                _ensure_task_in_testing(store, tid)
                engine_log(
                    f"[{label}] {tid} reviewer 超时，等待重试 (attempt {attempt + 1}/{timeout_retries})"
                )
                time.sleep(30)
                continue
            verdict_ok = True
            break

        engine_log(
            f"[{label}] {tid} reviewer 未产出有效 verdict (attempt {attempt + 1}/{max_attempts})"
        )
        _ensure_task_in_testing(store, tid)
        if attempt == max_attempts - 1 and not verdict_ok:
            engine_log(f"[{label}] {tid} reviewer verdict 重试耗尽 → abnormal")
            cur_phase = _current_running_phase(tid)
            _quarantine_with_notify(
                ws, tid, "reviewer 未产出 verdict", store, phase=cur_phase
            )
            store.update_index()
            return False

    _ensure_task_in_testing(store, tid)

    try:
        tester_role()
    except Exception as exc:
        engine_log(f"[{label}] {tid} tester_role 异常: {exc}")

    _ensure_task_in_testing(store, tid)

    tests_dir = ws / "tests"
    if tests_dir.is_dir():
        exit_code, output = _run_pytest(ws)
        _log_stats(ws, "pytest", tid, exit_code=exit_code, output_len=len(output))
        if exit_code != 0:
            _record_pytest_failure(ws, tid, exit_code, output)
            # F-FLOW-01: 连续失败计数 → abnormal
            pids_dir = ws / ".ccc" / "pids"
            pids_dir.mkdir(parents=True, exist_ok=True)
            fail_marker = pids_dir / f"{tid}.pytest_fails"
            try:
                fails = int(fail_marker.read_text().strip() or "0")
            except (OSError, ValueError):
                fails = 0
            fails += 1
            fail_marker.write_text(str(fails))
            if fails >= _PYTEST_FAIL_MAX:
                engine_log(
                    f"[{label}] {tid} pytest 连续失败 {fails}/{_PYTEST_FAIL_MAX} → abnormal"
                )
                cur_phase = _current_running_phase(tid)
                _quarantine_with_notify(
                    ws,
                    tid,
                    f"pytest 连续失败 {fails} 次 (exit={exit_code})",
                    store,
                    phase=cur_phase,
                )
                try:
                    fail_marker.unlink(missing_ok=True)
                except OSError:
                    pass
                return False
            engine_log(
                f"[{label}] {tid} pytest 失败 (exit={exit_code}) "
                f"count={fails}/{_PYTEST_FAIL_MAX}，留在 testing"
            )
            _ccc_notify(
                "CCC",
                f"任务 {tid} pytest 未通过 (exit={exit_code}) "
                f"{fails}/{_PYTEST_FAIL_MAX}",
            )
            store.update_index()
            return False
        # 成功则清计数 + 失败摘要
        fail_marker = ws / ".ccc" / "pids" / f"{tid}.pytest_fails"
        fail_summary = ws / ".ccc" / "pids" / f"{tid}.pytest_fail.md"
        try:
            fail_marker.unlink(missing_ok=True)
            fail_summary.unlink(missing_ok=True)
        except OSError:
            pass
    else:
        engine_log(f"[{label}] {tid} 无 tests/ 目录，跳过 engine pytest")

    # F-FLOW-03: 结构化 Verdict 字段，禁止裸子串
    if _verdict_is_valid(ws, tid):
        _vf = _verdict_file(ws, tid)
        try:
            _vcontent = _vf.read_text()
            status = _parse_verdict_status(_vcontent)
            if status in ("FAIL", "FALLBACK", "QUARANTINED"):
                engine_log(
                    f"[verdict-gate] [{_ws_label(ws)}] {tid} "
                    f"verdict={status} — 触发回滚"
                )
                _reverted = _revert_task_commit(ws, tid)
                store.move_task(tid, "testing", "planned")
                _clear_verdict(ws, tid)
                return False  # 跳过 verified 推进
        except OSError:
            pass

    if verdict_ok:
        col = _find_task_column(store, tid)
        if col == "testing":
            store.move_task(tid, "testing", "verified")
            _log_stats(ws, "move", tid, from_col="testing", to_col="verified")
        store.update_index()
        return _find_task_column(store, tid) == "verified"

    store.update_index()
    return False


def _run_verified_kb_gate(ws: Path) -> None:
    """v0.38: 扫 verified → kb_role → released（补齐 7 角色闭环）。"""
    _activate_workspace(ws)
    store = _get_store(ws)
    verified = store.list_tasks("verified")
    if not verified:
        return
    label = _ws_label(ws)
    engine_log(f"[{label}] verified 列有 {len(verified)} 个任务，跑 kb_role")
    try:
        result = kb_role()
        moved = (result or {}).get("moved") or []
        for tid in moved:
            _log_stats(ws, "move", tid, from_col="verified", to_col="released")
            engine_log(f"[{label}] {tid} ✓ kb → released")
        store.update_index()
    except Exception as exc:
        engine_log(f"[{label}] kb_role 异常: {exc}")


def _run_testing_tasks_gate(ws: Path) -> None:
    """对 testing 列每个 task 跑 reviewer/tester 门禁。"""
    _activate_workspace(ws)
    store = _get_store(ws)
    label = _ws_label(ws)
    for task in store.list_tasks("testing"):
        tid = task["id"]
        engine_log(f"[{label}] testing 门禁: {tid}")
        try:
            _run_reviewer_tester_gate(ws, tid)
        except Exception as exc:
            engine_log(f"[{label}] {tid} reviewer/tester 门禁异常: {exc}")


def _handle_task_result(ws: Path, tid: str, result: dict) -> bool:
    """处理 dev_role_check_complete 结果。返回 True 表示从 active_tasks 移除。"""
    _activate_workspace(ws)
    store = _get_store(ws)
    label = _ws_label(ws)
    status = result.get("status", "unknown")

    if status == "phase_done":
        # v0.38: 当前 phase 完成，仍有后续 phase → relaunch，留在 active_tasks
        next_phase = result.get("next_phase")
        engine_log(
            f"[{label}] {tid} phase {result.get('phase')} done → relaunch phase {next_phase}"
        )
        try:
            relaunch = dev_role_relaunch(tid)
        except Exception as exc:
            engine_log(f"[{label}] {tid} phase relaunch 异常: {exc}")
            return False
        if relaunch.get("ok") or relaunch.get("status") in ("launched", "ok", "running"):
            return False
        # relaunch 失败：留给下一 tick / hang 恢复
        engine_log(
            f"[{label}] {tid} phase relaunch 未成功: {relaunch}，保留 active_tasks"
        )
        return False

    if status == "success":
        # v0.33/v0.38: dev_role_check_complete 可能已移到 testing，避免双重 move
        col = _find_task_column(store, tid)
        if col == "in_progress":
            store.move_task(tid, "in_progress", "testing")
            _log_stats(ws, "move", tid, from_col="in_progress", to_col="testing")
        elif col == "testing":
            _log_stats(ws, "move", tid, from_col="in_progress", to_col="testing")
        else:
            engine_log(
                f"[{label}] {tid} success 但列={col}，跳过 in_progress→testing"
            )
        store.update_index()
        return True

    if status == "failed":
        retry = result.get("retry", 0)
        failure_summary = _check_phase_failures(tid)
        # v0.31 (P0.1): phase 图无法解析 → 删旧 phases.json + 回 backlog 重生成
        if failure_summary.get("unresolvable"):
            # 读 regen 计数器，cap 2 次
            _regen_count = _read_regen_count(ws, tid)
            if _regen_count >= 2:
                engine_log(
                    f"[{label}] {tid} phase 图无法解析，regen {_regen_count} 次 ≥ 2 → abnormal"
                )
                _record_failure_pattern("phase-graph-regen")
                store.move_task(tid, "in_progress", "abnormal")
                store.update_index()
                return True
            # 删旧 phases.json（product_role 据此判断是否需要重新生成）
            _phases_file = ws / ".ccc" / "phases" / f"{tid}.phases.json"
            if _phases_file.exists():
                _phases_file.unlink()
                engine_log(f"[{label}] {tid} 删旧 phases.json，触发 regen #{_regen_count + 1}")
            # v0.37: 写 .regen 标记，防止 _process_backlog 因残留/竞态 phases.json 跳过 product
            try:
                _regen_mark = ws / ".ccc" / "pids" / f"{tid}.regen"
                _regen_mark.parent.mkdir(parents=True, exist_ok=True)
                _regen_mark.write_text(str(_regen_count + 1))
            except OSError:
                pass
            # reset 靠删除新 plan 自然归零，不调 _write_engine_iter_meta（文件已删=no-op）
            _record_regen(ws, tid)
            # 回 backlog（删 phases.json 后 product_role 会看到无 phases.json → 重生成）
            store.move_task(tid, "in_progress", "backlog")
            store.update_index()
            return True
        if failure_summary.get("all_failed_or_skipped"):
            engine_log(
                f"[{label}] {tid} 所有 phase failed/skipped "
                f"(skipped={failure_summary.get('skipped')})"
            )
            store.update_index()
            return True
        cur = _current_running_phase(tid)
        engine_log(f"[{label}] {tid} 失败 (retry={retry}), relaunch phase {cur}")
        dev_role_relaunch(tid)
        return False

    if status == "quarantined":
        failure_summary = _check_phase_failures(tid)
        # v0.31 (P0.1): phase 图无法解析 → 删旧 phases.json + 回 backlog 重生成
        if failure_summary.get("unresolvable"):
            # 读 regen 计数器，cap 2 次
            _regen_count = _read_regen_count(ws, tid)
            if _regen_count >= 2:
                engine_log(
                    f"[{label}] {tid} phase 图无法解析（隔离中），regen {_regen_count} 次 ≥ 2 → abnormal"
                )
                store.move_task(tid, "in_progress", "abnormal")
                store.update_index()
                return True
            _phases_file = ws / ".ccc" / "phases" / f"{tid}.phases.json"
            if _phases_file.exists():
                _phases_file.unlink()
                engine_log(f"[{label}] {tid} 删旧 phases.json（隔离），触发 regen #{_regen_count + 1}")
            _record_regen(ws, tid)
            store.move_task(tid, "in_progress", "backlog")
            store.update_index()
            return True
        if failure_summary.get("all_failed_or_skipped"):
            engine_log(
                f"[{label}] {tid} 所有 phase failed/skipped → abnormal "
                f"(skipped_downstream={failure_summary['skipped']})"
            )
        else:
            engine_log(f"[{label}] {tid} 重试耗尽, 已隔离, 移向下一个")
        store.update_index()
        return True

    if status == "not_found":
        engine_log(f"[{label}] {tid} 不在 in_progress (可能已被外部移走)")
    else:
        engine_log(f"[{label}] {tid} 未知状态: {status}")
    return True


_ACTIVE_TASKS_FILE = Path.home() / ".ccc" / "engine-active-tasks.json"


def _read_regen_count(ws: Path, tid: str) -> int:
    """读 phase_graph_unresolvable regen 计数器（来自 warnings.json）"""
    try:
        _wf = ws / ".ccc" / "warnings.json"
        if not _wf.exists():
            return 0
        import json as _json
        _data = _json.loads(_wf.read_text())
        if not isinstance(_data, list):
            return 0
        _regen = [w for w in _data if w.get("type") == "phase_graph_regen" and w.get("task_id") == tid]
        return len(_regen)
    except Exception:
        return 0


def _record_regen(ws: Path, tid: str) -> None:
    """记录一次 phase_graph_regen 到 warnings.json（复用 failed+quarantined 分支）"""
    try:
        _regen_count = _read_regen_count(ws, tid) + 1
        _wf = ws / ".ccc" / "warnings.json"
        _existing = []
        if _wf.exists():
            try:
                import json as _json
                _existing = _json.loads(_wf.read_text())
                if not isinstance(_existing, list):
                    _existing = []
            except Exception:
                _existing = []
        _existing.append({
            "type": "phase_graph_regen",
            "task_id": tid,
            "regen_count": _regen_count,
            "detected_at": datetime.now(timezone.utc).isoformat(),
        })
        _wf.write_text(json.dumps(_existing, ensure_ascii=False, indent=2))
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════
# v0.35: degraded mode — 引擎自我保护
# ═══════════════════════════════════════════════════════════════

def _recent_events(ws: Path, event_type: str, window_sec: int) -> list[dict]:
    """从 events.jsonl 读最近指定类型事件（滑动窗口）。"""
    ev_file = ws / ".ccc" / "stats" / "events.jsonl"
    if not ev_file.exists():
        return []
    now = time.time()
    events = []
    try:
        for line in ev_file.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            if ev.get("event") == event_type:
                ts = ev.get("t", 0)
                if isinstance(ts, (int, float)) and ts > now - window_sec:
                    events.append(ev)
    except OSError:
        pass
    return events


def _check_degraded(ws: Path) -> None:
    """检查是否需要进入/退出 degraded 模式。

    degraded 模式下:
    - 停 backlog→planned intake（新 task 不进 pipeline）
    - 现有 in_progress/testing 继续跑完
    - 维护任务照跑（audit, stale check, cleanup）

    v0.36: upstream 不可用时同步开熔断，暂停 abnormal 自动重试。
    """
    global _degraded_mode, _degraded_since, _breaker_open, _breaker_since

    # v0.36: upstream 熔断
    recovery = getattr(cfg, "breaker_recovery_seconds", _BREAKER_RECOVERY_SECONDS)
    if not _is_upstream_healthy():
        if not _breaker_open:
            _breaker_open = True
            _breaker_since = time.time()
            engine_log("[breaker] upstream 不可用 → 开熔断，暂停 abnormal 重试")
            _ccc_notify("CCC", "engine 熔断：upstream 不可用")
    elif _breaker_open:
        elapsed = time.time() - _breaker_since
        if elapsed >= recovery:
            _breaker_open = False
            _breaker_since = 0.0
            engine_log(f"[breaker] upstream 已恢复（熔断 {elapsed:.0f}s）→ 关熔断")

    q_count = len(_recent_events(ws, "quarantine", 1800))
    f_count = len(_recent_events(ws, "product_fail", 1800))
    _any_success = len(_recent_events(ws, "product_done", 1800)) + len(_recent_events(ws, "auto_fixed", 1800))

    should_degrade = (
        q_count > _DEGRADED_QUARANTINE_THRESHOLD
        or f_count > _DEGRADED_FAIL_THRESHOLD
        or (q_count > 0 and _any_success == 0)
    )

    if should_degrade and not _degraded_mode:
        _degraded_mode = True
        _degraded_since = time.time()
        engine_log(
            f"[degraded] 30min 异常过高 (q={q_count}, f={f_count}, ok={_any_success}), "
            f"进入 degraded 模式 — 暂停 intake"
        )
        _ccc_notify("CCC", "engine 进入 degraded 模式（异常率过高，暂停 intake）")

    if _degraded_mode and not should_degrade:
        elapsed = time.time() - (_degraded_since or time.time())
        if elapsed > _DEGRADED_RECOVERY_SECONDS:
            _degraded_mode = False
            _degraded_since = None
            engine_log(
                f"[degraded] 异常率已恢复 (q={q_count}, f={f_count}), 退出 degraded 模式"
            )
            _ccc_notify("CCC", "engine 退出 degraded 模式（指标恢复正常）")


def _save_active_tasks(active_tasks: dict[str, dict]) -> None:
    """持久化 active_tasks 到 ~/.ccc/engine-active-tasks.json，Engine 重启后恢复。"""
    try:
        _ACTIVE_TASKS_FILE.parent.mkdir(parents=True, exist_ok=True)
        serializable = {}
        for k, v in active_tasks.items():
            item = dict(v)
            ws = item.get("workspace")
            if isinstance(ws, Path):
                item["workspace"] = str(ws)
            serializable[k] = item
        _ACTIVE_TASKS_FILE.write_text(
            json.dumps(serializable, ensure_ascii=False, indent=2, default=str)
        )
    except (OSError, TypeError) as exc:
        engine_log(f"[persist] save active_tasks 失败: {exc}")


def _load_active_tasks() -> dict[str, dict]:
    """从持久化文件恢复 active_tasks。返回 dict（可能是空的）。

    加载后立即删除持久化文件（避免下次重启用过期数据）。
    加载时校验每个 task 的进程是否存活，死的排除（防止僵尸任务占满并发槽）。
    """
    if not _ACTIVE_TASKS_FILE.exists():
        return {}
    try:
        raw = json.loads(_ACTIVE_TASKS_FILE.read_text())
        if not isinstance(raw, dict):
            return {}
        restored = {}
        for k, v in raw.items():
            ws_str = v.get("workspace", "")
            ws_path = Path(ws_str).resolve() if ws_str else None
            if not ws_path or not ws_path.is_dir() or not (ws_path / ".ccc" / "board").is_dir():
                engine_log(f"[persist] 忽略 {k}: workspace 不存在")
                continue
            v["workspace"] = ws_path

            # 校验进程存活：检查 pids 目录下该 task 的 PID 文件
            tid = v.get("task_id", "")
            alive = False
            if tid:
                import subprocess as _sp
                pids_dir = ws_path / ".ccc" / "pids"
                for pidf in sorted(pids_dir.glob(f"{tid}*.pid")):
                    if pidf.name.endswith(".done"):
                        continue
                    try:
                        pid = int(pidf.read_text().strip())
                        r = _sp.run(
                            ["ps", "-p", str(pid), "-o", "state="],
                            capture_output=True, text=True, timeout=3,
                            env=_sanitized_env(),
                        )
                        state = r.stdout.strip()
                        if state and state != "Z":
                            alive = True
                            break
                    except (ValueError, OSError):
                        continue
            if not alive:
                engine_log(
                    f"[persist] 排除僵尸 active_task {k}: "
                    f"进程不存活 (tid={tid})"
                )
                continue
            restored[k] = v

        if restored:
            engine_log(f"[persist] 恢复 {len(restored)} 个 active_tasks (存活)")
        return restored
    except (json.JSONDecodeError, OSError, TypeError) as exc:
        engine_log(f"[persist] load active_tasks 失败: {exc}")
        return {}
    finally:
        # 加载后立即删除，避免下次启动用过期数据
        try:
            _ACTIVE_TASKS_FILE.unlink(missing_ok=True)
        except OSError:
            pass


def _recover_tasks(ws: Path, active_tasks: dict[str, dict]) -> None:
    """Engine 启动后扫描 board，恢复 in_progress/testing 列的 task 上下文。

    验收点：
      - in_progress 列 task: 调 dev_role_check_complete 恢复 phase 执行状态
      - testing 列 task: 调 reviewer_role + tester_role 恢复验收流程
      - 每恢复一个 task 间隔 5s，避免并发重启风暴
      - board 为空时静默跳过，无日志噪声

    Args:
        ws: workspace 路径
        active_tasks: 引擎活跃 task 表（恢复后的 task 会填充到此 dict）
    """
    _activate_workspace(ws)
    store = _get_store(ws)
    label = _ws_label(ws)

    in_prog = store.list_tasks("in_progress")
    testing = store.list_tasks("testing")

    if not in_prog and not testing:
        engine_log(f"[{label}] board 为空，跳过 task 恢复")
        return

    if in_prog:
        engine_log(
            f"[recover] [{label}] 恢复 {len(in_prog)} 个 in_progress task "
            f"（间隔 5s 避免并发）"
        )

    for idx, task in enumerate(in_prog):
        tid = task["id"]
        complexity = task.get("complexity", "medium")
        cur_phase = _current_running_phase(tid)
        engine_log(
            f"[recover] [{label}] Recovered task {tid} at phase {cur_phase} "
            f"（in_progress → dev 检查）"
        )
        try:
            result = dev_role_check_complete(tid)
            status = result.get("status", "unknown")
            key = _task_key(ws, tid)
            if status == "running":
                active_tasks[key] = {
                    "workspace": ws,
                    "task_id": tid,
                    "complexity": complexity,
                    "started_at": now_iso(),
                }
                engine_log(f"[recover] [{label}] {tid} PID 仍存活，继续监控")
            else:
                _handle_task_result(ws, tid, result)
        except Exception as exc:
            engine_log(f"[recover] [{label}] {tid} in_progress 恢复异常: {exc}")

        if idx < len(in_prog) - 1:
            time.sleep(5)

    if testing:
        engine_log(
            f"[recover] [{label}] 恢复 {len(testing)} 个 testing task "
            f"（间隔 5s 避免并发）"
        )

    for idx, task in enumerate(testing):
        tid = task["id"]
        engine_log(f"[recover] [{label}] Recovered task {tid} at phase reviewing")
        try:
            try:
                reviewer_role()
            except Exception as exc:
                engine_log(f"[recover] [{label}] {tid} reviewer 异常: {exc}")
            try:
                tester_role()
            except Exception as exc:
                engine_log(f"[recover] [{label}] {tid} tester 异常: {exc}")
        except Exception as exc:
            engine_log(f"[recover] [{label}] {tid} testing 恢复异常: {exc}")

        if idx < len(testing) - 1:
            time.sleep(5)


def _startup_scan_workspace(ws: Path, active_tasks: dict[str, dict]) -> None:
    _activate_workspace(ws)
    store = _get_store(ws)
    label = _ws_label(ws)
    in_prog = store.list_tasks("in_progress")
    if in_prog:
        engine_log(f"[{label}] 发现 {len(in_prog)} 个 in_progress 任务，恢复检查")
    for task in in_prog:
        tid = task["id"]
        key = _task_key(ws, tid)
        complexity = task.get("complexity", "medium")
        result = dev_role_check_complete(tid)
        status = result.get("status", "unknown")
        if status == "running":
            active_tasks[key] = {
                "workspace": ws,
                "task_id": tid,
                "complexity": complexity,
                "started_at": now_iso(),
            }
            engine_log(f"[{label}] {tid} 检查 PID 存活")
        elif status in ("success", "failed"):
            engine_log(f"[{label}] {tid} 已完成 (status={status}), 继续链")
            if not _handle_task_result(ws, tid, result):
                active_tasks[key] = {
                    "workspace": ws,
                    "task_id": tid,
                    "complexity": complexity,
                    "started_at": now_iso(),
                }
        else:
            _handle_task_result(ws, tid, result)


def _process_backlog(ws: Path) -> bool:
    """消费 backlog 首条 task。返回 True 表示做了操作。

    v0.33: 异步 product_role — 不阻塞引擎 tick。Popen 后返回，后续 tick 检查完成。
    v0.35: degraded mode 下暂停 intake。
    """
    # v0.35: degraded mode → 暂停 backlog intake
    global _degraded_mode
    if _degraded_mode:
        return False

    _activate_workspace(ws)
    store = _get_store(ws)
    label = _ws_label(ws)
    backlog = store.list_tasks("backlog")
    if not backlog:
        return False

    tid = backlog[0]["id"]
    key = _task_key(ws, tid)
    phases_file = ws / ".ccc" / "phases" / f"{tid}.phases.json"
    _task_data = backlog[0]

    # v0.37: regen 标记强制重跑 product（即使残留 phases.json）
    _regen_mark = ws / ".ccc" / "pids" / f"{tid}.regen"
    if _regen_mark.exists():
        if phases_file.exists():
            try:
                phases_file.unlink()
                engine_log(
                    f"[product] [{label}] {tid} 发现 .regen 标记，删残留 phases.json 强制重生成"
                )
            except OSError as exc:
                engine_log(f"[product] [{label}] {tid} 删 phases.json 失败: {exc}")
        try:
            _regen_mark.unlink()
        except OSError:
            pass

    plan_file = ws / ".ccc" / "plans" / f"{tid}.plan.md"
    # v0.42.1: description 已引用现成 plan → 收养，跳过 LLM product
    if not (phases_file.exists() and plan_file.exists()):
        try:
            from _plan_adopt import try_adopt_referenced_plan

            adopted = try_adopt_referenced_plan(ws, tid, _task_data)
            if adopted.get("ok") and adopted.get("reason") in (
                "adopted",
                "already_present",
            ):
                engine_log(
                    f"[product] [{label}] {tid} 收养现有 plan: {adopted.get('source') or adopted.get('reason')}"
                )
        except Exception as exc:
            engine_log(f"[product] [{label}] {tid} plan adopt 跳过: {exc}")

    # 1. plan+phases 齐全（手动拆分 / 收养），直通 planned；残缺则清掉走 product
    if phases_file.exists() and plan_file.exists():
        engine_log(
            f"[product] [{label}] {tid} plan+phases 已存在，跳过 product_role，移入 planned"
        )
        if not store.move_task(tid, "backlog", "planned"):
            engine_log(f"[product] [{label}] move {tid} backlog→planned 失败，跳过")
            return False
        _log_stats(ws, "move", tid, from_col="backlog", to_col="planned")
        return True
    if phases_file.exists() and not plan_file.exists():
        try:
            phases_file.unlink()
            engine_log(
                f"[product] [{label}] {tid} 有 phases 无 plan，删孤儿 phases 走 product"
            )
        except OSError as exc:
            engine_log(f"[product] [{label}] {tid} 删孤儿 phases 失败: {exc}")

    # v0.35: 任务分类 — auto/quick 不走 product_role
    try:
        _pipeline_class = ccc_board._classify_task_intake(_task_data)
    except Exception:
        _pipeline_class = "full"  # fallback 安全
    if _pipeline_class in ("auto", "quick"):
        _log.info(
            f"[intake] [{label}] {tid} 分类={_pipeline_class}，不走 product_role"
        )
        if _pipeline_class == "auto":
            result = ccc_board._run_auto_fix(_task_data)
            if result.get("ok"):
                _log_stats(ws, "auto_fixed", tid, commit=result.get("commit", "")[:12])
                # 不放到 released（避免污染统计），直接移 abnormal+标记已修
                store.move_task(tid, "backlog", "released")
            else:
                _log.warning(
                    f"[intake] [{label}] {tid} auto-fix 失败: {result.get('error')}"
                )
                store.move_task(tid, "backlog", "abnormal")
            store.update_index()
            return True
        else:  # quick
            result = ccc_board._run_quick_fix(_task_data)
            if result.get("ok"):
                # quick-fix 完成后进入 testing，走 reviewer/tester 门禁（勿卡在 in_progress）
                store.move_task(tid, "backlog", "testing")
            else:
                store.move_task(tid, "backlog", "abnormal")
            store.update_index()
            return True

    # 2. 上游健康检测（避免 upstream 宕机 + fail_counter 永久锁死）
    if not _is_upstream_healthy():
        engine_log(
            f"[product] [{label}] {tid} 跳过 — upstream 不可用，下次 tick 重试（不计数）"
        )
        return False

    # 3. 失败计数器（含 15min 自动衰减）
    _COUNTER_DECAY_SEC = 900  # 15 分钟
    fail_counter_dir = ws / ".ccc" / ".product-fail-counter"
    fail_counter_path = fail_counter_dir / f"{tid}.json"
    fail_count = 0
    if fail_counter_path.exists():
        try:
            fail_data = json.loads(fail_counter_path.read_text())
            fail_count = fail_data.get("fail_count", 0)
            # 自动衰减：距上次失败超过 15 分钟 → 重置计数器
            last_failed = fail_data.get("last_failed_at", 0)
            if fail_count > 0 and last_failed:
                elapsed = time.time() - last_failed
                if elapsed > _COUNTER_DECAY_SEC:
                    engine_log(
                        f"[product] [{label}] {tid} fail_counter {fail_count} → 0 "
                        f"(距上次失败 {elapsed:.0f}s > {_COUNTER_DECAY_SEC}s 衰减窗口)"
                    )
                    fail_count = 0
                    fail_counter_path.write_text(
                        json.dumps({"fail_count": 0, "last_failed_at": 0}, indent=2)
                    )
        except (json.JSONDecodeError, OSError):
            fail_count = 0

    if fail_count >= _MAX_PRODUCT_RETRIES:
        engine_log(
            f"[product] [{label}] {tid} 已失败 {fail_count} 次 >= {_MAX_PRODUCT_RETRIES}，移入 abnormal"
        )
        _quarantine_with_notify(
            ws, tid, f"product_role 连续失败 {fail_count} 次", store, phase=0
        )
        _ccc_notify("CCC", f"product_role 拆分 {tid} 连续失败 {fail_count} 次")
        return True

    # 3. 检查 inflight 异步 product
    if key in _product_inflight:
        engine_log(f"[product] [{label}] {tid} 异步 product 检查...")
        result = ccc_board.check_product_async(tid)
        if result["status"] == "success":
            _product_inflight.pop(key, None)
            try:
                if fail_counter_path.exists():
                    fail_counter_path.unlink()
            except OSError:
                pass
            _log_stats(ws, "product_done", tid, fail_count=fail_count)
            engine_log(f"[product] [{label}] {tid} ✓ 异步 product 完成")
            return True
        elif result["status"] == "failed":
            _product_inflight.pop(key, None)
            fail_count += 1
            fail_counter_dir.mkdir(parents=True, exist_ok=True)
            fail_counter_path.write_text(
                json.dumps({"fail_count": fail_count, "last_failed_at": time.time()}, indent=2)
            )
            err = result.get("error", "")[:200]
            _log_stats(
                ws,
                "product_fail",
                tid,
                fail_count=fail_count,
                error=err,
            )
            try:
                from _failure_ledger import record_failure

                record_failure(
                    ws,
                    task_id=tid,
                    role="product",
                    reason=err or "product_fail",
                    phase=0,
                    from_col="backlog",
                    to_col=None,
                    related_stats_event="product_fail",
                )
            except Exception:
                engine_log(
                    f"[failures] product_fail ledger: {_traceback.format_exc()[:300]}"
                )
            engine_log(
                f"[product] [{label}] product_role({tid}) 异步失败 #{fail_count}: {result.get('error', '?')}"
            )
            if fail_count >= _MAX_PRODUCT_RETRIES:
                _quarantine_with_notify(
                    ws,
                    tid,
                    f"product_role 连续失败 {fail_count} 次",
                    store,
                    phase=0,
                    role="product",
                    from_col="backlog",
                )
                _ccc_notify("CCC", f"product_role 拆分 {tid} 连续失败 {fail_count} 次")
            return True
        # status == "running"
        engine_log(f"[product] [{label}] {tid} 异步 product 执行中...")
        return False

    # 4. 启动异步 product_role（不阻塞引擎 tick）
    engine_log(
        f"[product] [{label}] backlog 异步拆分: {tid} (此前失败 {fail_count} 次)"
    )
    _log_stats(ws, "product_start", tid, fail_count=fail_count)
    launch_r = ccc_board.launch_product_async(tid)
    if launch_r.get("ok"):
        _product_inflight[key] = {"tid": tid, "started_at": now_iso()}
        return True

    # 5. 启动失败
    fail_count += 1
    fail_counter_dir.mkdir(parents=True, exist_ok=True)
    fail_counter_path.write_text(json.dumps({"fail_count": fail_count, "last_failed_at": time.time()}, indent=2))
    err = launch_r.get("error", "")[:200]
    _log_stats(
        ws,
        "product_fail",
        tid,
        fail_count=fail_count,
        error=err,
    )
    try:
        from _failure_ledger import record_failure

        record_failure(
            ws,
            task_id=tid,
            role="product",
            reason=err or "product launch failed",
            phase=0,
            from_col="backlog",
            to_col=None,
            related_stats_event="product_fail",
        )
    except Exception:
        engine_log(f"[failures] product_fail ledger: {_traceback.format_exc()[:300]}")
    engine_log(
        f"[product] [{label}] product_role({tid}) 启动失败 #{fail_count}: {launch_r.get('error', '')}"
    )
    if fail_count >= _MAX_PRODUCT_RETRIES:
        _quarantine_with_notify(
            ws,
            tid,
            f"product_role 连续失败 {fail_count} 次",
            store,
            phase=0,
            role="product",
            from_col="backlog",
        )
        _ccc_notify("CCC", f"product_role 拆分 {tid} 连续失败 {fail_count} 次")
    return True


def _auto_replenish_backlog(ws: Path, store, program_dir: Path) -> bool:
    """backlog + planned 都为空时，立即触发 audit_role 补充新任务。

    绕过 _audit_should_run 的 2h 间隔，但有 5min per-workspace 冷却
    避免 audit_role 在无变更的项目上空转。

    v0.37: 默认关闭（cfg.auto_replenish / CCC_AUTO_REPLENISH=1）。
    v0.40: 另需 control=invent（may_invent）；enabled 禁止自造。

    Returns: True 表示触发了 audit_role
    """
    if not _may_invent():
        return False
    if not getattr(cfg, "auto_replenish", False):
        return False
    if store.list_tasks("backlog"):
        return False
    if store.list_tasks("planned"):
        return False

    now = time.time()
    ws_key = str(ws)
    last = _last_empty_replenish.get(ws_key, 0.0)
    if now - last <= 300:
        return False

    _last_empty_replenish[ws_key] = now
    label = _ws_label(ws, program_dir)
    engine_log(f"[{label}] backlog+planned 均为空，立即触发 audit_role 补充")
    try:
        ccc_board.audit_role(workspace=str(ws))
    except Exception as exc:
        engine_log(f"[{label}] audit_role 异常: {exc}")
    return True


# ═══════════════════════════════════════════════════════════════
# v0.28.2: Phase 并行调度（plan: engine-phase-parallel-dispatch）
# ═══════════════════════════════════════════════════════════════


def _phase_market_subid(tid: str, phase_num: int) -> str:
    """Per-phase marker subid，避免并行 phase 写在同 task_id.{done,pid,exitcode}。

    用「task_id__p{N}」双下划线，与 ccc-board 的「task_id-p{N}」区分。
    """
    return f"{tid}__p{phase_num}"


def _group_parallel_phases(phases: list[dict], executable: set[int]) -> list[list[int]]:
    """将 executable phases 分组：同组内 phase 之间无 depends_on 关系。

    Args:
        phases: 所有 phase dict（来自 _load_phases）
        executable: 当前可执行的 phase id 集合（来自 _resolve_phase_dependencies）

    Returns:
        list[list[int]]：每个内层 list 是一组可并行 phase（组内相位无依赖）。
        多组间必须先后顺序执行（前组全部完成才执行下一组）。

    算法：贪心。每个 phase 顺序遍历 — 能加入最后一个 group 当存在互不依赖，
    否则开新 group。
    """
    if not executable:
        return []
    by_id = {p.get("phase"): p for p in phases if p.get("phase") is not None}
    sorted_executable = sorted(executable)
    groups: list[list[int]] = []
    for pid in sorted_executable:
        phase_deps = set(by_id.get(pid, {}).get("depends_on") or [])
        placed = False
        # 尝试放入最后一个 group
        if groups:
            last_group = groups[-1]
            last_group_ids = set(last_group)
            # 若本 phase 与组内所有 phase 不互依赖（last_group_ids ∩ phase_deps == ∅）
            # 且组内其他 phase 也不依赖本 phase（避免环）
            conflicts = last_group_ids & phase_deps
            reverse_deps_conflict = any(
                pid in set(by_id.get(g, {}).get("depends_on") or []) for g in last_group
            )
            if not conflicts and not reverse_deps_conflict:
                last_group.append(pid)
                placed = True
        if not placed:
            groups.append([pid])
    return groups


def _phase_to_pgroup(p: int) -> str:
    """OpenCode pool / marker 用的 phase id（与 ccc-board 一致：task_id-pN）。"""
    # 注：当前 _try_launch_planned 调 dev_role_launch，里头 phase_id=task_id-pN。
    # 本 dispatcher 用 pgroup = task_id__pN 双下划线以隔离 task-level 标记。
    return f"p{p}"


def _build_phase_prompt(task_id: str, phase_num: int, plan_content: str) -> str:
    """构造单 phase 的 prompt（委托 board.prompt，与 ccc-board 共用）。"""
    from board.prompt import build_dev_phase_prompt

    scope: list[str] = []
    pytest_fail = ""
    skill_hints = ""
    try:
        for p in _load_phases(task_id):
            if int(p.get("phase", -1)) == int(phase_num):
                sc = p.get("scope") or []
                if isinstance(sc, list):
                    scope = [str(x) for x in sc if x]
                # v0.42.1: 空 scope 从 plan 回填，避免 OpenCode「未提供 scope」盲跑
                if not scope and plan_content:
                    try:
                        from _plan_adopt import backfill_scopes

                        filled = backfill_scopes([dict(p)], plan_content)
                        scope = list(filled[0].get("scope") or [])
                    except Exception:
                        pass
                break
    except Exception:
        pass
    try:
        from board.context import get_workspace as _gw

        pf = _gw() / ".ccc" / "pids" / f"{task_id}.pytest_fail.md"
        if pf.is_file():
            pytest_fail = pf.read_text(encoding="utf-8", errors="replace")[:4000]
    except Exception:
        pass
    try:
        from board.store_ops import list_tasks as _lt
        from _skills_catalog import format_skill_hints_block

        tid = str(task_id)
        for col in ("in_progress", "planned", "testing", "backlog"):
            task = next((t for t in _lt(col) if t.get("id") == tid), None)
            if not task:
                continue
            hints = task.get("hints") if isinstance(task.get("hints"), dict) else {}
            skills = hints.get("skills") if isinstance(hints.get("skills"), list) else []
            note = hints.get("note") if isinstance(hints.get("note"), str) else ""
            skill_hints = format_skill_hints_block(skills, note)
            break
    except Exception:
        pass
    return build_dev_phase_prompt(
        task_id,
        phase_num,
        plan_content,
        scope=scope,
        pytest_failure=pytest_fail,
        skill_hints=skill_hints,
    )


def _launch_parallel_phase(
    ws: Path,
    task_id: str,
    phase_num: int,
    plan_content: str,
    timeout_s: int,
    label: str,
) -> dict | None:
    """启单个 phase 的 opencode-runner.sh 后台进程，用 per-phase 命名空间隔离。

    Returns:
        {"subid": str, "pid": int, "proc": Popen} 或 None（失败）。
    """
    import subprocess as _sp

    subid = _phase_market_subid(task_id, phase_num)
    pids_dir = ws / ".ccc" / "pids"
    pids_dir.mkdir(parents=True, exist_ok=True)
    prompt_dir = Path.home() / ".ccc" / "prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    prompt_file = prompt_dir / f"{subid}.prompt.md"
    prompt_file.write_text(
        _build_phase_prompt(task_id, phase_num, plan_content),
        encoding="utf-8",
    )
    try:
        # 用 phase_id = subid 命名 opencode-runner.sh 的输出 marker
        # opencode-runner.sh 内部会写 ${PID_DIR}/${TASK_ID}.{done,exitcode}
        # 这里 TASK_ID 用 subid，故 marker 也隔离。
        tkey = _task_key(ws, task_id)
        if not _try_acquire_opencode_slot(tkey):
            engine_log(
                f"[engine] 全局 opencode 已达上限 "
                f"({_GLOBAL_OPENCODE_COUNT}/{_GLOBAL_OPENCODE_MAX})，等待"
            )
            return None
        try:
            proc = _sp.Popen(
                [
                    "bash",
                    str(_script_dir / "opencode-runner.sh"),
                    subid,
                    str(_script_dir.parent),  # CCC_HOME
                    str(ws),  # ROOT_DIR
                    "--phase",
                    f"{task_id}-p{phase_num}",  # 与 ccc-board 一致 phase_id 命名
                    "--prompt",
                    str(prompt_file),
                    "--timeout",
                    str(timeout_s),
                    "--cwd",
                    str(ws),
                ],
                cwd=ws,
                start_new_session=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=_sanitized_env(),
            )
        except Exception:
            _release_opencode_slot(tkey, 1)
            raise
        pids_dir.joinpath(f"{subid}.pid").write_text(str(proc.pid))
        engine_log(
            f"[{label}] {task_id}-p{phase_num} launched PID={proc.pid} "
            f"(subid={subid}, retry 0/{cfg.DEFAULT_RETRY}, timeout {timeout_s}s)"
        )
        return {"subid": subid, "pid": proc.pid, "proc": proc}
    except Exception as exc:
        engine_log(f"[{label}] {task_id}-p{phase_num} launch failed: {exc}")
        return None


def _check_parallel_phase_done(ws: Path, subid: str) -> dict:
    """检查单个并行 phase 完成状态。

    Returns:
        {"status": "running" | "success" | "failed", "exit_code": int}
    """
    pids_dir = ws / ".ccc" / "pids"
    done_file = pids_dir / f"{subid}.done"
    if not done_file.exists():
        # 检查 PID 是否存活
        pid_file = pids_dir / f"{subid}.pid"
        if pid_file.exists():
            try:
                pid = int(pid_file.read_text().strip())
                os.kill(pid, 0)
                return {"status": "running", "exit_code": -1}
            except (ValueError, OSError, ProcessLookupError):
                pass
        return {"status": "running", "exit_code": -1}
    exit_file = pids_dir / f"{subid}.exitcode"
    try:
        exit_code = int(exit_file.read_text().strip()) if exit_file.exists() else 1
    except ValueError:
        exit_code = 1
    return {
        "status": "success" if exit_code == 0 else "failed",
        "exit_code": exit_code,
    }


def _launch_parallel_group(
    ws: Path,
    task_id: str,
    phase_nums: list[int],
    plan_content: str,
    timeout_s: int,
    label: str,
) -> tuple[bool, dict[int, dict]]:
    """并行启一组 phase（max_workers 个线程）。返回 (success, phase_meta)。

    Args:
        phase_nums: 这组 phase 编号列表
        plan_content: 完整 plan 文本（每个 phase 都用同一份 prompt）
        timeout_s: 超时秒数

    Returns:
        (True, {phase_num: {"subid": ..., "pid": ...}}) 全部成功
        (False, {...}) 部分/全部失败
    """
    if not phase_nums:
        return True, {}

    max_w = min(PHASE_PARALLEL_MAX_WORKERS, len(phase_nums))
    engine_log(
        f"[parallel] [{label}] {task_id} 并行启动 "
        f"phase {' + '.join(f'phase-{n}' for n in phase_nums)} "
        f"(max_workers={max_w})"
    )
    phase_meta: dict[int, dict] = {}
    try:
        with ThreadPoolExecutor(max_workers=max_w) as ex:
            futures = {
                ex.submit(
                    _launch_parallel_phase,
                    ws,
                    task_id,
                    pn,
                    plan_content,
                    timeout_s,
                    label,
                ): pn
                for pn in phase_nums
            }
            for fut, pn in futures.items():
                try:
                    res = fut.result(timeout=15)
                except Exception as exc:
                    engine_log(
                        f"[{label}] {task_id}-p{pn} parallel submit exception: {exc}"
                    )
                    res = None
                if res is None:
                    engine_log(
                        f"[parallel][warn] {task_id}-p{pn} 启动失败，"
                        f"此 phase 将被跳过（其他 phase 继续）"
                    )
                    continue
                phase_meta[pn] = res
        success = len(phase_meta) > 0
        if success:
            engine_log(
                f"[parallel] [{label}] {task_id} 并行 phase 已启动: "
                f"{[(pn, phase_meta[pn]['pid']) for pn in sorted(phase_meta)]}"
            )
        return success, phase_meta
    except Exception as exc:
        engine_log(
            f"[parallel][warn] {task_id} ThreadPoolExecutor 异常: {exc}，"
            f"fallback 串行模式"
        )
        _set_parallel_disabled(True)
        return False, {}


def _try_launch_planned(ws: Path, active_tasks: dict[str, dict]) -> bool:
    """从 planned 启动一个 task。返回 True 表示已启动。

    v0.28.2: 当 executable phase 数 >= 2 且未禁用并行时，走并行分支；
    失败时 fallback 到单 phase 串行 dev_role_launch。
    """
    _activate_workspace(ws)
    store = _get_store(ws)
    label = _ws_label(ws)
    planned = store.list_tasks("planned")
    for task in planned:
        tid = task["id"]
        key = _task_key(ws, tid)
        if key in active_tasks:
            continue
        plan_file = ws / ".ccc" / "plans" / f"{tid}.plan.md"
        phases_file = ws / ".ccc" / "phases" / f"{tid}.phases.json"
        if not plan_file.exists() or not phases_file.exists():
            continue

        phases = _load_phases(tid, ws)
        executable: set[int] = set()
        if phases:
            executable, blocked, skipped = _resolve_phase_dependencies(phases)
            if blocked or skipped:
                _apply_phase_status_updates(tid, blocked, skipped)
                engine_log(
                    f"[{label}] {tid} phase 依赖解析: executable={sorted(executable)} "
                    f"blocked={sorted(blocked)} skipped={sorted(skipped)}"
                )
            if phases and all(
                p.get("status") in ("skipped", "failed") or (p.get("phase") in skipped)
                for p in phases
            ):
                engine_log(
                    f"[{label}] {tid} 所有 phase 被跳过（依赖失败链），跳过 task 启动"
                )
                continue

        complexity = task.get("complexity", "medium")
        # F-FLOW-05: task 级 depends_on_tasks — 依赖未 released 则跳过
        deps = task.get("depends_on_tasks") or []
        if isinstance(deps, str):
            deps = [deps]
        if deps:
            released_ids = {t["id"] for t in store.list_tasks("released")}
            blocked = [d for d in deps if d not in released_ids]
            if blocked:
                engine_log(
                    f"[{label}] {tid} 等待 task 依赖: {blocked}（未 released）"
                )
                continue
        engine_log(f"[{label}] 取新 task: {tid} (complexity={complexity})")

        # ── v0.28.2: 并行分支 ──
        # 条件：executable phase >= 2 + 未被全局禁用
        # 不满足则直接走单 phase dev_role_launch（原有路径）
        if (
            phases
            and executable
            and len(executable) >= 2
            and not PHASE_PARALLEL_DISABLED
        ):
            groups = _group_parallel_phases(phases, executable)
            if groups and len(groups[0]) >= 2:
                plan_content = plan_file.read_text(encoding="utf-8")
                timeout_s = _lookup_phase_timeout(tid, phases)
                ok = _try_launch_planned_parallel(
                    ws, tid, groups, plan_content, timeout_s
                )
                if ok:
                    if not store.move_task(tid, "planned", "in_progress"):
                        engine_log(
                            f"[engine] [{_ws_label(ws)}] move {tid} planned→in_progress 失败，"
                            "不注册 active_task"
                        )
                        continue  # 作用于外层 for task in planned
                    active_tasks[key] = {
                        "workspace": ws,
                        "task_id": tid,
                        "complexity": complexity,
                        "started_at": now_iso(),
                        "mode": "parallel",
                    }
                    _save_active_tasks(active_tasks)
                    store.update_index()
                    return True
                # 并行启动失败 → 回退串行
                engine_log(f"[{label}] {tid} 并行启动失败，回退 dev_role_launch 串行")

        # v0.34: 系统性失败检测 — 同类 task 在 abnormal 过多则直接熔断
        _abnormal_tasks = store.list_tasks("abnormal")
        # 取 task id 前缀（前 3 段）做同类匹配：audit-review-20260716 → 匹配 audit-review-*
        _prefix = "-".join(tid.split("-")[:3])
        _similar_failures = sum(1 for t in _abnormal_tasks if isinstance(t.get("id"), str) and t["id"].startswith(_prefix))
        if _similar_failures >= 5:
            engine_log(
                f"[{label}] {tid} 同类任务已有 {_similar_failures} 个在 abnormal，"
                f"系统性失败 → 直接熔断，不重试"
            )
            store.move_task(tid, "planned", "abnormal")
            store.update_index()
            continue

        # v0.34 (Phase2): 异常流量检测 — 单 task 单角色 1h 内 > 20 次 → 跳闸隔离
        if _check_abnormal_traffic(tid, "executor"):
            engine_log(
                f"[{label}] {tid} executor 调用过于频繁（1h>20），疑似死循环 → abnormal"
            )
            _record_failure_pattern("abnormal-traffic-executor")
            store.move_task(tid, "planned", "abnormal")
            store.update_index()
            continue

        tkey = _task_key(ws, tid)
        if not _try_acquire_opencode_slot(tkey):
            engine_log(
                f"[engine] 全局 opencode 已达上限 "
                f"({_GLOBAL_OPENCODE_COUNT}/{_GLOBAL_OPENCODE_MAX})，等待"
            )
            continue
        launch_r = dev_role_launch(tid)
        if "error" in launch_r:
            _release_opencode_slot(tkey, 1)
            engine_log(f"[{label}] 启动 {tid} 失败: {launch_r['error']}")
            continue
        active_tasks[key] = {
            "workspace": ws,
            "task_id": tid,
            "complexity": complexity,
            "started_at": now_iso(),
        }
        _save_active_tasks(active_tasks)
        store.update_index()
        return True
    return False


def _lookup_phase_timeout(tid: str, phases: list[dict]) -> int:
    """查 phases 里 phase 1 的 timeout，单位秒；找不到走 cfg.default_timeout。

    engine-phase-retry-config: 缺省 600 → cfg.default_timeout（1800），
    与 ccc-board._load_timeout 默认值保持一致。
    """
    default_to = cfg.default_timeout
    for p in phases:
        if p.get("phase") == 1:
            try:
                return int(p.get("timeout", default_to))
            except (TypeError, ValueError):
                return default_to
    return default_to


def _store_atomic_write_phases(path: Path, payload: str) -> None:
    """原子写 phases.json：写 temp + os.replace。容错 fallback 直写。"""
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_text(payload, encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        try:
            path.write_text(payload, encoding="utf-8")
        except OSError:
            pass


def _try_launch_planned_parallel(
    ws: Path,
    task_id: str,
    groups: list[list[int]],
    plan_content: str,
    timeout_s: int,
) -> bool:
    """启并行 task 的首个 group，剩余 group 等当前 group 全部完成后再启。

    Args:
        ws: workspace 路径
        task_id: task 名
        groups: 分组后的并行 phase 列表（每组内无相互依赖）
        plan_content: 完整 plan 文本
        timeout_s: 单 phase 超时秒数

    Returns:
        True 至少启了一个 phase；False 全部失败。
    """
    global _parallel_phases

    label = _ws_label(ws)
    key = _task_key(ws, task_id)
    first_group = groups[0]
    engine_log(
        f"[parallel] [{label}] {task_id} 并行调度: {len(groups)} 个 group "
        f"(size={[len(g) for g in groups]}, max_workers={min(PHASE_PARALLEL_MAX_WORKERS, len(first_group))})"
    )
    success, phase_meta = _launch_parallel_group(
        ws, task_id, first_group, plan_content, timeout_s, label
    )
    if not success:
        engine_log(f"[parallel][error] [{label}] {task_id} 全部 phase 启动失败")
        return False
    _parallel_phases[key] = {
        "groups": groups,
        "current_group": first_group,
        "phase_meta": phase_meta,
        "any_group_fail": False,
        "ws_path": str(ws),
    }
    engine_log(
        f"[parallel] [{label}] {task_id} 当前 group={first_group} 启动 {len(phase_meta)} phase OK"
    )
    return True


def _on_parallel_group_complete(ws: Path, task_id: str, phase_nums: list[int]) -> str:
    """检一组并行 phase 是否都写完 marker。

    Returns:
        "still_running" — 仍有 phase 没标 done
        "group_done_ok" — 全部 phase 成功
        "group_done_fail" — 至少 1 条失败
    """
    ws = ws.resolve()
    pids_dir = ws / ".ccc" / "pids"
    exitcodes: dict[int, int] = {}
    for pid in phase_nums:
        subid = _phase_market_subid(task_id, pid)
        done_path = pids_dir / f"{subid}.done"
        exit_path = pids_dir / f"{subid}.exitcode"
        if not done_path.exists():
            return "still_running"
        try:
            ec = int(exit_path.read_text().strip()) if exit_path.exists() else 1
        except (ValueError, OSError):
            ec = 1
        exitcodes[pid] = ec
    label = _ws_label(ws)
    any_fail = any(ec != 0 for ec in exitcodes.values())
    engine_log(
        f"[parallel][group-done] [{label}] {task_id} group {phase_nums} → "
        f"{'fail' if any_fail else 'ok'} (exitcodes={exitcodes})"
    )
    # 写回 phases.json：pending → done/failed
    phases_file = ws / ".ccc" / "phases" / f"{task_id}.phases.json"
    if phases_file.exists():
        try:
            raw = phases_file.read_text(encoding="utf-8")
            new_lines: list[str] = []
            changed = False
            for line in raw.splitlines():
                s = line.strip()
                if not s:
                    new_lines.append(line)
                    continue
                try:
                    obj = json.loads(s)
                except json.JSONDecodeError:
                    new_lines.append(line)
                    continue
                if not isinstance(obj, dict) or "phase" not in obj:
                    new_lines.append(line)
                    continue
                pid = obj.get("phase")
                if pid in exitcodes:
                    new_status = "done" if exitcodes[pid] == 0 else "failed"
                    if obj.get("status") != new_status:
                        obj["status"] = new_status
                        changed = True
                new_lines.append(json.dumps(obj, ensure_ascii=False))
            if changed:
                _store_atomic_write_phases(phases_file, "\n".join(new_lines) + "\n")
        except OSError as exc:
            engine_log(f"[parallel][status] 写 phases.json 失败: {exc}")
    return "group_done_fail" if any_fail else "group_done_ok"


def _check_parallel_task_complete(ws: Path, task_id: str) -> str:
    """Engine tick 调用：推进并行 task 状态。

    Returns:
        "still_running" — 当前 group 未完 / 等待下一 group
        "task_complete_ok" — 全部 group 完成且全成功
        "task_complete_fail" — 有 group 失败
    """
    global _parallel_phases

    ws = ws.resolve()
    key = _task_key(ws, task_id)
    state = _parallel_phases.get(key)
    if not state:
        return "still_running"

    current_group = state.get("current_group") or []
    if not current_group:
        return "still_running"

    group_state = _on_parallel_group_complete(ws, task_id, current_group)
    if group_state == "still_running":
        return "still_running"
    # v0.30.0: 本组 phase 已结束，释放本组 opencode 槽位（F-CON-01）
    n_launched = len(state.get("phase_meta") or {})
    if n_launched:
        _release_opencode_slot(_task_key(ws, task_id), n_launched)
    if group_state == "group_done_fail":
        state["any_group_fail"] = True

    # 推进到下一 group
    groups = state.get("groups") or [current_group]
    current_group_idx = groups.index(current_group) if current_group in groups else -1
    next_group = None
    for i in range(current_group_idx + 1, len(groups)):
        if groups[i]:
            next_group = groups[i]
            break
    if next_group and len(next_group) >= 2:
        # 启动下一 group
        plan_file = ws / ".ccc" / "plans" / f"{task_id}.plan.md"
        if plan_file.exists():
            plan_content = plan_file.read_text(encoding="utf-8")
            # 拿当前 timeout
            timeout_s = 600
            phases = _load_phases(task_id, ws)
            if phases:
                timeout_s = _lookup_phase_timeout(task_id, phases)
            label = _ws_label(ws)
            ok, meta = _launch_parallel_group(
                ws,
                task_id,
                next_group,
                plan_content,
                timeout_s,
                label,
            )
            if ok:
                state["current_group"] = next_group
                state["phase_meta"] = meta
                engine_log(
                    f"[parallel][next-group] {task_id} 下一 group {next_group} 启动"
                )
                return "still_running"
            engine_log(f"[parallel][warn] {task_id} 下一 group 启动失败，标 group fail")
            state["any_group_fail"] = True

    # 全部 group 完成（或后续 group 启不动）
    any_fail = bool(state.get("any_group_fail"))
    _parallel_phases.pop(key, None)
    pids_dir = ws / ".ccc" / "pids"
    try:
        (pids_dir / f"{task_id}.done").write_text("ok")
        (pids_dir / f"{task_id}.exitcode").write_text("1" if any_fail else "0")
    except OSError as exc:
        engine_log(f"[parallel][marker-write] {task_id} 写完成 marker 失败: {exc}")
    label = _ws_label(ws)
    engine_log(
        f"[parallel][task-done] [{label}] {task_id} 全部 group 完成 (any_fail={any_fail})"
    )
    return "task_complete_fail" if any_fail else "task_complete_ok"


def _parallel_task_marker_to_result(ws: Path, task_id: str) -> dict:
    """类似 dev_role_check_complete: 把并行 task 的 done/exitcode 映射成 status dict。"""
    ws = ws.resolve()
    pids_dir = ws / ".ccc" / "pids"
    done_path = pids_dir / f"{task_id}.done"
    exit_path = pids_dir / f"{task_id}.exitcode"
    if not done_path.exists():
        return {"status": "running", "retry": 0}
    try:
        ec = int(exit_path.read_text().strip()) if exit_path.exists() else 1
    except (ValueError, OSError):
        ec = 1
    if ec == 0:
        return {"status": "success", "retry": 0}
    return {"status": "failed", "retry": 0}


def _reset_parallel_disabled_after_tick() -> None:
    """tick 边界 reset PHASE_PARALLEL_DISABLED（fallback 只对当次 tick 生效）。"""
    global PHASE_PARALLEL_DISABLED
    PHASE_PARALLEL_DISABLED = False


def engine_loop(workspaces: list[Path]) -> None:
    global MAX_RETRY
    """引擎主循环：多 workspace 轮询，全局 MAX_CONCURRENT 共享。"""
    global _engine_shutdown

    # v0.39.2: 仅 control=enabled 才进业务循环；ui/disabled 均 idle
    try:
        from _ccc_control import get_mode, may_start_engine
    except ImportError:
        def may_start_engine() -> bool:
            return not (Path.home() / ".ccc" / "DISABLED").is_file()

        def get_mode() -> str:
            return "enabled" if may_start_engine() else "disabled"

    if not may_start_engine():
        engine_log(
            f"CCC control={get_mode()} — idle hold "
            f"(full: python3 scripts/_ccc_control.py enable)"
        )
        while not _engine_shutdown and not may_start_engine():
            time.sleep(60)
        if _engine_shutdown:
            return
        engine_log("CCC control=enabled — entering normal loop")

    program_dir = Path.home() / "program"
    labels = [_ws_label(w, program_dir) for w in workspaces]
    engine_log(f"CCC Engine 启动 ({len(workspaces)} workspace)")
    engine_log(f"  workspaces={labels}")
    engine_log(
        f"  poll_interval={cfg.engine_poll_interval}s, idle_sleep={cfg.engine_idle_sleep}s"
    )
    engine_log(f"  max_retry={MAX_RETRY}, max_concurrent={MAX_CONCURRENT}")

    _write_engine_restart("started")

    active_tasks: dict[str, dict] = {}
    iteration = 0

    # R4: 从持久化文件恢复 active_tasks，避免重启丢上下文
    active_tasks = _load_active_tasks()
    _load_hang_retry_counter()

    # v0.36: 启动时先采样内存（在 recover 之前，避免 recover 间隔拖慢 heartbeat）
    for ws in workspaces:
        try:
            _check_process_memory(ws)
            _cleanup_zombie_pid_refs(ws)
        except Exception as exc:
            engine_log(f"[mem] startup sample failed for {_ws_label(ws)}: {exc}")

    for ws in workspaces:
        _recover_tasks(ws, active_tasks)

    while not _engine_shutdown:
        iteration += 1
        tick_start = time.time()
        any_active = bool(active_tasks)

        first_task = next(iter(active_tasks.values()), {})
        first_task_id = first_task.get("task_id")
        first_task_ws = first_task.get("workspace")
        current_phase = None
        if first_task_id and first_task_ws:
            try:
                _activate_workspace(first_task_ws)
                current_phase = _current_running_phase(first_task_id)
            except Exception as exc:
                engine_log(f"stats phase lookup failed for {first_task_id}: {exc}")
        _update_stats(
            active_count=len(active_tasks),
            current_task=first_task_id,
            current_phase=current_phase,
            phase_status="running" if any_active else "done",
            workspace_name=first_task_ws.name if first_task_ws else None,
        )

        try:
            completed_tasks: list[str] = []
            if active_tasks:
                # v0.31+: hang 自动重启（Phase 4 + Phase 5 联合投递）
                # Phase 4 先检测并写 .hung marker，Phase 5 再消费 marker 触发
                # kill+stash+relaunch，最后再做完成判定。
                for ws in workspaces:
                    _activate_workspace(ws)
                    _check_and_mark_hung(ws, active_tasks)
                    _run_hang_auto_restart(ws, active_tasks)
                for key, info in list(active_tasks.items()):
                    ws = info["workspace"]
                    tid = info["task_id"]
                    label = _ws_label(ws, program_dir)
                    _activate_workspace(ws)
                    mode = info.get("mode", "serial")
                    if mode == "parallel":
                        # v0.28.2: 并行 task 走专用检查器
                        par_state = _check_parallel_task_complete(ws, tid)
                        if par_state == "still_running":
                            if iteration % 60 == 0:
                                engine_log(f"[parallel] [{label}] {tid} 执行中")
                            any_active = True
                            continue
                        # task_complete_ok / task_complete_fail → 包装成 result
                        if par_state == "task_complete_ok":
                            result = {"status": "success", "retry": 0}
                        else:
                            result = {"status": "failed", "retry": 0}
                    else:
                        result = dev_role_check_complete(tid)
                    status = result.get("status", "unknown")
                    complexity = info.get("complexity", "medium")

                    if status == "running":
                        if iteration % 60 == 0:
                            engine_log(f"[{label}] {tid} 执行中")
                        any_active = True
                        continue

                    if _handle_task_result(ws, tid, result):
                        # v0.30.0: 串行 task 结束时释放槽位（并行 path 已在 group 完成时递减）
                        if mode != "parallel":
                            _release_opencode_slot(key, 1)
                        completed_tasks.append(key)

                for key in completed_tasks:
                    active_tasks.pop(key, None)
                if completed_tasks:
                    _save_active_tasks(active_tasks)
                # tick 边界重置 fallback 标志
                _reset_parallel_disabled_after_tick()

            # 每 6 轮（~60s）跑一次 degraded 检测 + stale check + testing 流转 + 统计聚合
            if iteration % 6 == 0:
                for ws in workspaces:
                    _activate_workspace(ws)
                    _check_degraded(ws)
                    _store = _get_store(ws)
                    _check_stale(ws, active_tasks)
                    # v0.40: abnormal 自动回灌仅 invent
                    if _may_invent():
                        _retry_abnormal_failures(ws)
                    # v0.36: 每 36 tick (~6min) 内存监控 + 残影 PID 清理
                    if iteration % 36 == 0:
                        try:
                            _check_process_memory(ws)
                        except Exception as exc:
                            engine_log(f"[mem] {_ws_label(ws)} 异常: {exc}")
                        try:
                            _cleanup_zombie_pid_refs(ws)
                        except Exception as exc:
                            engine_log(f"[pids] {_ws_label(ws)} cleanup 异常: {exc}")
                    test_tasks = _store.list_tasks("testing")
                    if test_tasks:
                        label = _ws_label(ws)
                        engine_log(
                            f"[{label}] testing 列有 {len(test_tasks)} 个任务，跑 reviewer+tester 门禁"
                        )
                        _run_testing_tasks_gate(ws)
                    # v0.38: verified → kb → released
                    if _store.list_tasks("verified"):
                        _run_verified_kb_gate(ws)
                    # v0.30: 定期统计聚合（即使系统忙）
                    try:
                        aggregate_stats(ws)
                        # v0.31: 自适应调参（读 summary.json → 调整 timeout/retry）
                        try:
                            summary = load_summary(ws)
                            if summary and summary.get("total_events", 0) > 5:
                                task_stats = summary.get("task_stats", {})
                                total = task_stats.get("total", 0)
                                failed = task_stats.get("failed", 0)
                                if total > 0:
                                    fail_rate = failed / total
                                    if fail_rate > 0.4 and MAX_RETRY < 5:
                                        engine_log(
                                            f"[auto-tune] fail_rate={fail_rate:.0%}, "
                                            f"MAX_RETRY={MAX_RETRY} (adjusting)"
                                        )
                                        MAX_RETRY = min(MAX_RETRY + 1, 5)
                                        ccc_board.MAX_RETRY = MAX_RETRY  # F-ROLE-04
                                    elif fail_rate < 0.1 and MAX_RETRY > 2:
                                        engine_log(
                                            f"[auto-tune] fail_rate={fail_rate:.0%}, "
                                            f"MAX_RETRY={MAX_RETRY} (reducing)"
                                        )
                                        MAX_RETRY = max(MAX_RETRY - 1, 2)
                                        ccc_board.MAX_RETRY = MAX_RETRY  # F-ROLE-04
                        except Exception as exc:
                            engine_log(f"[auto-tune] error: {exc}")
                    except Exception as exc:
                        engine_log(
                            f"[stats] periodic aggregate error for {ws.name}: {exc}"
                        )
            ws_first_running: dict[str, str | None] = {}
            ws_active_counts: dict[str, int] = {}
            for info in active_tasks.values():
                ws_key = str(info["workspace"])
                if ws_key not in ws_first_running:
                    ws_first_running[ws_key] = info["task_id"]
                ws_active_counts[ws_key] = ws_active_counts.get(ws_key, 0) + 1
            for ws in workspaces:
                ws_key = str(ws)
                running_task_id = ws_first_running.get(ws_key)
                ws_count = ws_active_counts.get(ws_key, 0)
                ws_pids = _get_running_pids(ws) if running_task_id else []
                _write_heartbeat(ws, running_task_id, ws_count, ws_pids)

            # v0.33: 即使 active_tasks 满了，也要检查 inflight product 完成
            if _product_inflight:
                for ws in workspaces:
                    _activate_workspace(ws)
                    _process_backlog(ws)

            while len(active_tasks) < MAX_CONCURRENT and not _engine_shutdown:
                # v1.0: planned 优先（dev_role），无 planned 才 backlog（product_role）
                # 避免 60+ backlog 阻塞 dev_role 永远不启动（B1）
                did_something = False
                # 规则：保持 3 个任务同时进行（MAX_CONCURRENT）
                # 每次 tick 尽最大可能填充空槽位：先启动 planned（dev_role），再处理 backlog（product_role）
                for ws in workspaces:
                    if len(active_tasks) >= MAX_CONCURRENT:
                        break
                    if _try_launch_planned(ws, active_tasks):
                        did_something = True
                        any_active = True

                for ws in workspaces:
                    if len(active_tasks) >= MAX_CONCURRENT:
                        break
                    if _process_backlog(ws):
                        did_something = True
                        any_active = True

                if not did_something:
                    break

            if not active_tasks:
                for ws in workspaces:
                    _activate_workspace(ws)
                    _check_stale(ws, active_tasks)
                    # 空闲时立即处理 testing 任务
                    _store2 = _get_store(ws)
                    test_tasks = _store2.list_tasks("testing")
                    if test_tasks:
                        label = _ws_label(ws)
                        engine_log(
                            f"[{label}] idle: testing 列有 {len(test_tasks)} 个任务，跑 reviewer+tester 门禁"
                        )
                        _run_testing_tasks_gate(ws)
                    if _store2.list_tasks("verified"):
                        _run_verified_kb_gate(ws)
                    _write_heartbeat(ws, None, 0, [])

                    # v0.40: enabled=只消费；invent 才允许 audit/evolve/replenish/abnormal
                    _has_consumable = _queue_has_consumable_work(_store2)
                    if not _has_consumable and not _may_invent():
                        continue

                    if _may_invent() and _audit_should_run(str(ws)):
                        label = _ws_label(ws, program_dir)
                        engine_log(f"[{label}] 触发 audit_role（invent 模式）")
                        try:
                            ccc_board.audit_role(workspace=str(ws))
                        except Exception as exc:
                            engine_log(f"[{label}] audit_role 异常: {exc}")

                    if (
                        _may_invent()
                        and getattr(cfg, "evolve_on_idle", False)
                        and iteration % 36 == 0
                    ):
                        try:
                            ev_res = ccc_board._evolve_run_one(str(ws))
                            if ev_res.get("posted", 0) > 0:
                                label = _ws_label(ws, program_dir)
                                engine_log(
                                    f"[evolve] [{label}] posted {ev_res['posted']} findings"
                                )
                        except Exception as exc:
                            label = _ws_label(ws, program_dir)
                            engine_log(f"[evolve] [{label}] 异常: {exc}")

                    if _may_invent():
                        _auto_replenish_backlog(ws, _store2, program_dir)
                        _retry_abnormal_failures(ws)

                    _check_new_reviews(ws)

                    # v0.30: 空闲时聚合统计 → 反馈回路（学习飞轮）
                    try:
                        summary = aggregate_stats(ws)
                        if summary:
                            insights = summary.get("perf_insights", [])
                            recs = summary.get("recommendations", [])
                            for ins in insights:
                                if ins.get("severity") == "warning":
                                    engine_log(
                                        "[stats] %s — %s",
                                        ws.name,
                                        ins.get("label", ""),
                                    )
                            for rec in recs:
                                if rec.get("action") != "system_healthy":
                                    engine_log(
                                        "[stats-recommend] %s: %s",
                                        rec.get("action", "?"),
                                        rec.get("suggestion", ""),
                                    )
                    except Exception as exc:
                        engine_log(f"[stats] aggregate error for {ws.name}: {exc}")

            # v0.40: 无可消费队列 → 深睡（≥60s），避免空转造功
            any_consumable = False
            for ws in workspaces:
                try:
                    if _queue_has_consumable_work(_get_store(ws)):
                        any_consumable = True
                        break
                except Exception:
                    pass
            if not any_active and not any_consumable and not _may_invent():
                if iteration % 12 == 1:
                    engine_log(
                        f"CCC control={get_mode()} — queue empty, deep sleep 60s "
                        f"(wake: ~/.ccc/engine.wake)"
                    )
                # v0.41: 可被下任务 wake 文件打断
                if _sleep_until_wake(60):
                    engine_log("[wake] 收到 engine.wake，立即进入下一 tick")
                continue

            if not any_active:
                time.sleep(cfg.engine_tick_interval)
                continue

        except KeyboardInterrupt:
            engine_log("收到 SIGINT, 优雅关闭")
            break
        except Exception as e:
            engine_log(f"异常: {e}")
            engine_log(f"{_traceback.format_exc()[:2000]}")
            engine_log(f"  {_tb.format_exc().splitlines()[-2]}")
            time.sleep(cfg.engine_idle_sleep)
            continue

        _wait_tick(tick_start)

    engine_log("收到关闭信号，停止接收新任务")


def _sleep_until_wake(seconds: float) -> bool:
    """深睡可被 ~/.ccc/engine.wake 打断。返回 True=被唤醒。"""
    try:
        from _engine_wake import consume_wake

        end = time.time() + max(0.0, seconds)
        while time.time() < end:
            payload = consume_wake()
            if payload is not None:
                engine_log(
                    f"[wake] reason={payload.get('reason')} "
                    f"task={payload.get('task_id')}"
                )
                return True
            time.sleep(min(2.0, max(0.1, end - time.time())))
        # 超时前再看一眼
        return consume_wake() is not None
    except Exception:
        time.sleep(seconds)
        return False


def _wait_tick(tick_start: float) -> None:
    elapsed = time.time() - tick_start
    remaining = cfg.engine_poll_interval - elapsed
    if remaining > 0:
        time.sleep(min(remaining, cfg.engine_poll_interval))


def _audit_should_run(workspace: str, interval_hours: int = 2) -> bool:
    from datetime import datetime as _dt

    ws_slug = Path(workspace).name if workspace else "CCC"
    last_run_file = Path.home() / ".ccc" / f"audit-last-run.{ws_slug}.json"
    if not last_run_file.exists():
        old_file = Path.home() / ".ccc" / "audit-last-run.json"
        if old_file.exists():
            return _audit_check_old(old_file, interval_hours)
        return True
    try:
        data = json.loads(last_run_file.read_text())
        last = _dt.fromisoformat(data["last_run"].replace("Z", "+00:00"))
        now = _dt.now(timezone.utc)
        hours = (now - last).total_seconds() / 3600
        return hours >= interval_hours
    except (json.JSONDecodeError, KeyError, ValueError):
        return True


def _audit_check_old(old_file, interval_hours: int = 2) -> bool:
    from datetime import datetime as _dt

    try:
        data = json.loads(old_file.read_text())
        last = _dt.fromisoformat(data["last_run"].replace("Z", "+00:00"))
        now = _dt.now(timezone.utc)
        hours = (now - last).total_seconds() / 3600
        return hours >= interval_hours
    except (json.JSONDecodeError, KeyError, ValueError):
        return True


def _classify_failure(reason: str, tid: str, phase_note: str = "") -> str:
    """将失败原因分为 transient / permanent。

    不匹配任何关键词时按 transient（宁可错重试也不漏）。
    """
    blob = f"{reason} {phase_note} {tid}".lower()
    for kw in _PERMANENT_KEYWORDS:
        if kw.lower() in blob:
            return "permanent"
    for kw in _TRANSIENT_KEYWORDS:
        if kw.lower() in blob:
            return "transient"
    return "transient"


def _retry_cooldown_seconds(retry_count: int) -> int:
    """第 N 次重试冷却 = base × factor^N，上限 max。"""
    base = getattr(cfg, "retry_base_interval", _RETRY_BASE_INTERVAL)
    factor = getattr(cfg, "retry_backoff_factor", _RETRY_BACKOFF_FACTOR)
    max_iv = getattr(cfg, "retry_max_interval", _RETRY_MAX_INTERVAL)
    cool = base * (factor ** max(0, int(retry_count)))
    return min(int(cool), int(max_iv))


def _retry_abnormal_failures(ws: Path) -> None:
    """扫描 abnormal 任务，冷却后自动移回 planned 重试（全阶段）。

    v0.36:
      - 关键字放宽（不再仅限 "重试"）
      - transient/permanent 分类；permanent 不重试
      - 指数退避冷却
      - upstream 熔断期间跳过
    """
    from datetime import datetime as _dt
    import json as _json

    global _breaker_open, _breaker_since

    recovery = getattr(cfg, "breaker_recovery_seconds", _BREAKER_RECOVERY_SECONDS)
    if _breaker_open and time.time() - _breaker_since < recovery:
        engine_log(f"[{_ws_label(ws)}] 熔断中，跳过 abnormal 重试")
        return

    _activate_workspace(ws)
    store = _get_store(ws)
    label = _ws_label(ws)
    now = _dt.now(timezone.utc)
    retry_counter_file = ws / ".ccc" / ".dev_auto_retry.json"
    retry_counts: dict[str, int] = {}
    if retry_counter_file.exists():
        try:
            retry_counts = _json.loads(retry_counter_file.read_text())
        except (_json.JSONDecodeError, OSError):
            retry_counts = {}
    MAX_AUTO_RETRY = 3
    moved_tasks: list[str] = []

    for task in store.list_tasks("abnormal"):
        tid = task["id"]
        reason = task.get("note") or ""
        if not any(kw in reason for kw in _ABNORMAL_RETRY_KEYWORDS):
            continue

        kind = _classify_failure(reason, tid, task.get("note") or "")
        if kind == "permanent":
            engine_log(
                f"[{label}] skip auto-retry {tid}: 不可恢复错误（permanent）"
            )
            continue

        updated_str = task.get("updated_at", task.get("created_at", ""))
        if not updated_str:
            continue
        try:
            updated = _dt.fromisoformat(updated_str.replace("Z", "+00:00"))
            minutes_since = (now - updated).total_seconds() / 60
        except (ValueError, TypeError):
            continue

        auto_retried = retry_counts.get(tid, 0)
        if auto_retried >= MAX_AUTO_RETRY:
            continue
        needed_minutes = _retry_cooldown_seconds(auto_retried) / 60
        if minutes_since < needed_minutes:
            continue  # 冷却中

        try:
            task_json = _json.loads(
                (ws / ".ccc/board/abnormal" / f"{tid}.jsonl").read_text()
            )
            task_json["status"] = "planned"
            task_json["updated_at"] = now_iso()
            task_json["note"] = (
                f"auto-retry #{auto_retried + 1}/{MAX_AUTO_RETRY}: {reason[:80]}"
            )
            planned_dir = ws / ".ccc/board/planned"
            planned_dir.mkdir(parents=True, exist_ok=True)
            (planned_dir / f"{tid}.jsonl").write_text(
                _json.dumps(task_json, ensure_ascii=False) + "\n"
            )
            (ws / ".ccc/board/abnormal" / f"{tid}.jsonl").unlink()
            retry_counts[tid] = auto_retried + 1
            store.update_index()
            engine_log(
                f"[{label}] auto-retry #{auto_retried + 1}/{MAX_AUTO_RETRY}: {tid} "
                f"(冷却 {minutes_since:.0f}/{needed_minutes:.0f}min, {kind}) → planned"
            )
            moved_tasks.append(tid)
        except Exception as e:
            _log.warning("auto-retry failed for %s: %s", tid, e)

    try:
        retry_counter_file.write_text(
            _json.dumps(retry_counts, ensure_ascii=False) + "\n"
        )
    except OSError:
        pass

    try:
        from _lessons import get_recent_lessons

        recent = get_recent_lessons(ws)
        for task_id in moved_tasks:
            for lesson in recent:
                if lesson.get("task_id") == task_id and not lesson.get("fixed"):
                    _log.info(
                        "[lessons-reapply] %s: %s",
                        task_id,
                        lesson.get("error", "")[:80],
                    )
    except Exception:
        pass


# 兼容旧名（测试 / 外部引用）
_retry_abnormal_dev_failures = _retry_abnormal_failures


def _check_new_reviews(ws: Path) -> None:
    try:
        from _review_validator import scan_review_dir

        results = scan_review_dir(str(ws))
        label = _ws_label(ws)
        for r in results:
            if not r.get("valid"):
                fname = Path(r.get("file", "?")).name
                errs = "; ".join(r["errors"][:3])
                engine_log(f"[{label}] 🔴 报告格式错误 {fname}: {errs}")
    except ImportError as e:
        _log.warning("_review_validator unavailable, skipping review scan: %s", e)
    except Exception as exc:
        engine_log(f"review 校验异常: {exc}")


def _check_stale(ws: Path, active_tasks: dict[str, dict] | None = None) -> None:
    from datetime import datetime as _dt

    _activate_workspace(ws)
    store = _get_store(ws)
    label = _ws_label(ws)
    now = _dt.now(timezone.utc)
    for task in store.list_tasks("in_progress"):
        # v0.34 (P4): 优先 phase_last_advanced_ts（phase 级别停滞）
        updated_str = task.get("phase_last_advanced_ts", task.get("updated_at", task.get("created_at", "")))
        if not updated_str:
            continue
        try:
            updated = _dt.fromisoformat(updated_str.replace("Z", "+00:00"))
            hours_stale = (now - updated).total_seconds() / 3600
            if hours_stale > cfg.max_stale_hours:
                tid = task["id"]
                reason = (
                    f"engine: in_progress 滞留 {hours_stale:.1f}h "
                    f"(阈值 {cfg.max_stale_hours}h)"
                )
                cur_phase = _current_running_phase(tid)
                _quarantine_with_notify(
                    ws, tid, reason, store, phase=cur_phase, active_tasks=active_tasks
                )
                engine_log(
                    f"[{label}] stale: {tid} in_progress 滞留 "
                    f"{hours_stale:.1f}h → abnormal"
                )
        except (ValueError, TypeError) as e:
            _log.warning(
                "stale task timestamp parse failed for %s: %s", task.get("id"), e
            )
    try:
        store.cleanup_events(max_days=30)
    except Exception as e:
        _log.warning("events TTL cleanup failed: %s", e, exc_info=True)


def _collect_grandchildren(pid: int, acc: list[int]) -> None:
    """递归收集 pid 的全部子孙进程。"""
    import subprocess as _sp

    try:
        r = _sp.run(
            ["pgrep", "-P", str(pid)],
            capture_output=True,
            text=True,
            timeout=3,
        )
        if r.returncode == 0:
            for line in r.stdout.strip().splitlines():
                line = line.strip()
                if not line.isdigit():
                    continue
                child = int(line)
                if child not in acc:
                    acc.append(child)
                    _collect_grandchildren(child, acc)
    except (_sp.TimeoutExpired, FileNotFoundError, OSError, ValueError):
        pass


def _kill_process_tree(pid: int) -> bool:
    """发 SIGTERM→等→SIGKILL 递归子进程。返回 True 表示进程最终已死。"""
    import subprocess as _sp

    children: list[int] = []
    try:
        r = _sp.run(
            ["pgrep", "-P", str(pid)],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if r.returncode == 0:
            for line in r.stdout.strip().splitlines():
                line = line.strip()
                if line.isdigit():
                    child = int(line)
                    children.append(child)
                    _collect_grandchildren(child, children)
    except (_sp.TimeoutExpired, FileNotFoundError, OSError, ValueError):
        pass

    # 先杀子，再杀父（叶子优先）
    for child_pid in reversed(children):
        try:
            os.kill(child_pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError, OSError):
            pass
    if children:
        time.sleep(3)
    for child_pid in reversed(children):
        try:
            os.kill(child_pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError, OSError):
            pass

    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return True
    except PermissionError:
        _log.warning("kill tree %d permission denied", pid)
        return False
    except OSError as exc:
        _log.warning("kill tree %d SIGTERM failed: %s", pid, exc)
        return False

    time.sleep(5)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    except (PermissionError, OSError):
        return True

    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        return True
    except OSError as exc:
        _log.warning("kill tree %d SIGKILL failed: %s", pid, exc)
        return False

    time.sleep(1)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    except (PermissionError, OSError):
        return True
    return False


# 兼容旧名
_kill_pid = _kill_process_tree


def _git_stash_ws(ws: Path, tid: str, phase_num: int) -> bool:
    """cd ws && git stash push -m 'ccc-auto-stash: ...'。返回是否成功。"""
    try:
        result = subprocess.run(
            ["git", "stash", "push", "-m", f"ccc-auto-stash: {tid} phase {phase_num}"],
            cwd=str(ws),
            capture_output=True,
            timeout=30,
            text=True,
            env=_sanitized_env(),
        )
    except subprocess.TimeoutExpired:
        _log.warning("git stash timed out for %s", tid)
        return False
    except OSError as exc:
        _log.warning("git stash failed for %s: %s", tid, exc)
        return False
    if result.returncode != 0:
        _log.warning(
            "git stash non-zero exit for %s: rc=%d stderr=%s",
            tid,
            result.returncode,
            (result.stderr or "")[:200],
        )
        return False
    return True


def _check_and_mark_hung(ws: Path, active_tasks: dict[str, dict]) -> None:
    """扫描 active_tasks 中的 running phase，检测 hung 条件并写 .hung marker。

    Phase 4 of executor-hang-detection plan（与 Phase 5 `_run_hang_auto_restart`
    配对）。同一 tick 内 Phase 4 先跑、Phase 5 后跑：

      Phase 4 (本函数): 检测 → 写 `.ccc/pids/<subid>.hung`（JSON）
      Phase 5 (_run_hang_auto_restart): 读 .hung → kill + git stash + relaunch

    判定条件（全部满足才写 marker）：
      1. PID 存活（`os.kill(pid, 0)`，已退出抛 ProcessLookupError → 跳过）
      2. CPU 0%（`ps -p PID -o %cpu=`，非 0 → 跳过，进程仍在工作）
      3. 运行时长 > _HANG_CHECK_INTERVAL_SEC（`info["started_at"]`，不足 → 跳过）

    排除项：
      - 已存在 `.hung` → 不重复标记
      - 已存在 `.done` → 任务已正常完成（race-safe）
    """
    from datetime import datetime as _dt

    _activate_workspace(ws)
    label = _ws_label(ws)
    pids_dir = ws / ".ccc" / "pids"
    now = _dt.now(timezone.utc)

    store = _get_store(ws)
    for key, info in list(active_tasks.items()):
        if info.get("workspace") != ws:
            continue
        tid = info["task_id"]
        # v0.40.1: 已 quarantine 的任务不再刷 hang 事件
        if _find_task_column(store, tid) == "abnormal":
            continue
        try:
            cur_phase = _current_running_phase(tid)
        except Exception as exc:
            engine_log(f"[{label}] hang-detect: 读 {tid} current phase 失败: {exc}")
            continue
        if cur_phase is None or cur_phase <= 0:
            continue

        subid = _phase_market_subid(tid, cur_phase)
        hung_path = pids_dir / f"{subid}.hung"
        done_path = pids_dir / f"{subid}.done"
        pid_path = pids_dir / f"{subid}.pid"

        # 已标记或已完成 → 跳过
        if hung_path.is_file():
            continue
        if done_path.is_file():
            continue

        # 读 PID
        if not pid_path.is_file():
            continue
        try:
            pid = int(pid_path.read_text().strip())
        except (ValueError, OSError) as exc:
            engine_log(f"[{label}] hang-detect: {tid} 读 PID 失败: {exc}")
            continue
        if pid <= 0:
            continue

        # PID 存活检查
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            continue
        except PermissionError:
            # 进程存在但没权限（macOS root-owned），视为仍存活
            pass
        except OSError as exc:
            engine_log(f"[{label}] hang-detect: {tid} PID={pid} 检查异常: {exc}")
            continue

        # 运行时长检查
        started_str = info.get("started_at", "")
        if not started_str:
            continue
        try:
            started = _dt.fromisoformat(str(started_str).replace("Z", "+00:00"))
            elapsed = (now - started).total_seconds()
        except (ValueError, TypeError) as exc:
            engine_log(f"[{label}] hang-detect: {tid} started_at 解析失败: {exc}")
            continue
        if elapsed < _HANG_CHECK_INTERVAL_SEC:
            continue

        # CPU 检查（仅在存活 + 足够久的 phase 上跑）
        try:
            result = subprocess.run(
                ["ps", "-p", str(pid), "-o", "%cpu="],
                capture_output=True,
                text=True,
                timeout=5,
                env=_sanitized_env(),
            )
        except subprocess.TimeoutExpired:
            engine_log(f"[{label}] hang-detect: {tid} ps 超时，跳过本次")
            continue
        except OSError as exc:
            engine_log(f"[{label}] hang-detect: {tid} ps 异常: {exc}")
            continue
        if result.returncode != 0:
            # 进程刚退出，ps 返回非 0 → 不算 hung
            continue
        try:
            cpu = float(result.stdout.strip())
        except ValueError:
            engine_log(
                f"[{label}] hang-detect: {tid} ps 输出无法解析: {result.stdout!r}"
            )
            continue
        # v0.36: 即使 CPU 活跃，RSS 超单进程上限也直接标 hung
        rss_mb = _get_proc_rss_mb(pid)
        mem_kill = getattr(cfg, "mem_kill_mb", _MEM_KILL_MB)
        if rss_mb > mem_kill:
            engine_log(
                f"[{label}] hang-detect: {tid} RSS={rss_mb:.0f}MB > {mem_kill}MB，标记 hung"
            )
            marker = {
                "task_id": tid,
                "phase": cur_phase,
                "pid": pid,
                "cpu": cpu,
                "rss_mb": round(rss_mb, 1),
                "elapsed_sec": int(elapsed),
                "detected_at": now_iso(),
                "reason": "rss_over_limit",
            }
            try:
                hung_path.write_text(json.dumps(marker, ensure_ascii=False) + "\n")
            except OSError as exc:
                engine_log(f"[{label}] hang-detect: {tid} 写 .hung 失败: {exc}")
            continue

        if cpu > 0.0 and elapsed < _HANG_BUSY_MAX_SEC:
            # F-FLOW-04: CPU 忙但未超 busy 阈值 → 跳过；超时则仍可标 hung
            continue

        # v0.30.0: macOS ps %cpu 是生命周期均值，网络等待型进程可能 CPU≈0 但非 hung
        # 二次确认：检查 pids 目录下该 subid 附属文件的最后修改时间
        _latest = 0.0
        try:
            for _pf in sorted(
                pids_dir.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True
            ):
                if _pf.name.startswith(f"{subid}.") and _pf.name != hung_path.name:
                    _latest = _pf.stat().st_mtime
                    break
        except OSError:
            pass
        if _latest and (now.timestamp() - _latest) < 120 and cpu <= 0.0:
            # 最近 2 分钟有文件活动（如 stdout/result 持续写入）→ 进程活着
            continue

        # 全部条件满足 → 写 .hung marker
        marker = {
            "task_id": tid,
            "phase": cur_phase,
            "pid": pid,
            "cpu": cpu,
            "rss_mb": round(rss_mb, 1),
            "elapsed_sec": int(elapsed),
            "detected_at": now_iso(),
        }
        try:
            hung_path.write_text(json.dumps(marker, ensure_ascii=False) + "\n")
        except OSError as exc:
            engine_log(f"[{label}] hang-detect: {tid} 写 .hung 失败: {exc}")
            continue

        _log_stats(
            ws,
            "hang_detected",
            tid,
            phase=cur_phase,
            pid=pid,
            cpu=cpu,
            elapsed_sec=int(elapsed),
        )
        try:
            from _failure_ledger import record_failure

            record_failure(
                ws,
                task_id=tid,
                role="engine",
                reason=f"hang_detected pid={pid} cpu={cpu:.1f}% elapsed={int(elapsed)}s",
                phase=cur_phase,
                from_col="in_progress",
                to_col=None,
                exit_code=None,
                related_stats_event="hang_detected",
            )
        except Exception:
            engine_log(
                f"[failures] hang_detected ledger: {_traceback.format_exc()[:300]}"
            )
        engine_log(
            f"[{label}] hang-detect: {tid} phase {cur_phase} PID={pid} "
            f"CPU={cpu:.1f}% 运行时长={int(elapsed)}s → 标记 .hung"
        )


def _run_hang_auto_restart(ws: Path, active_tasks: dict[str, dict]) -> None:
    """扫描 active_tasks 中的 hung phase 并自动重启（v0.31+）。

    检测 active_tasks 中每个 task 的当前 phase 是否已被 Phase 4
    （executor-hang-detection）标记为 hung（.ccc/pids/<subid>.hung）。

    如标记存在：
      1. 解析 subid → 读 .pid 文件拿到 PID
      2. kill -TERM → 5s 后存活则 kill -KILL
      3. cd ws && git stash push -m 'ccc-auto-stash: <tid> phase <n>'
      4. 清理 .hung 文件
      5. dev_role_relaunch(tid) 用同一 plan 重启
      6. 更新 _hang_retry_counter，超限则 quarantine + notify
    """
    global _hang_retry_counter

    _activate_workspace(ws)
    label = _ws_label(ws)
    pids_dir = ws / ".ccc" / "pids"

    store = _get_store(ws)
    for key, info in list(active_tasks.items()):
        if info.get("workspace") != ws:
            continue
        tid = info["task_id"]
        # v0.40.1: 已 quarantine → 不再 hang-auto / 不再刷账本
        if _find_task_column(store, tid) == "abnormal":
            active_tasks.pop(key, None)
            _hang_retry_counter.pop(key, None)
            continue
        try:
            cur_phase = _current_running_phase(tid)
        except Exception as exc:
            engine_log(f"[{label}] hang-auto: 读 {tid} current phase 失败: {exc}")
            continue
        if cur_phase is None or cur_phase <= 0:
            continue

        subid = _phase_market_subid(tid, cur_phase)
        hung_path = pids_dir / f"{subid}.hung"
        if not hung_path.is_file():
            continue

        retries = _hang_retry_counter.get(key, 0)
        engine_log(
            f"[{label}] hang-auto: {tid} phase {cur_phase} 标记 hung "
            f"(auto-retry {retries + 1}/{_MAX_HANG_RETRY})"
        )

        # 1) 读 PID
        pid_path = pids_dir / f"{subid}.pid"
        pid: int | None = None
        if pid_path.is_file():
            try:
                pid = int(pid_path.read_text().strip())
            except (ValueError, OSError):
                pid = None
        else:
            engine_log(
                f"[{label}] hang-auto: {tid} 缺 {pid_path.name}（可能已退出），跳过 kill"
            )

        # 2) kill 进程树
        if pid is not None and pid > 0:
            if _kill_process_tree(pid):
                engine_log(f"[{label}] hang-auto: {tid} PID={pid} 进程树已 kill")
            else:
                engine_log(f"[{label}] hang-auto: {tid} PID={pid} kill 失败，继续")

        # 3) git stash
        if not _git_stash_ws(ws, tid, cur_phase):
            engine_log(f"[{label}] hang-auto: {tid} git stash 失败，跳过 restart")
            # 仍然清理 hung 标记避免无限循环
            try:
                hung_path.unlink()
            except OSError:
                pass
            continue

        # 4) 清理 .hung
        try:
            hung_path.unlink()
        except OSError as exc:
            engine_log(f"[{label}] hang-auto: 清理 {hung_path.name} 失败: {exc}")

        # 5) 重启或超限 quarantine
        if retries >= _MAX_HANG_RETRY:
            reason = f"hang auto-restart 耗尽（{_MAX_HANG_RETRY} 次）— {tid} phase {cur_phase}"
            engine_log(f"[{label}] hang-auto: {tid} 超限 → abnormal")
            _quarantine_with_notify(
                ws,
                tid,
                reason,
                phase=cur_phase,
                active_tasks=active_tasks,
                role="engine",
                from_col="in_progress",
            )
            # v0.40.1: quarantine 后清计数 + 移出 active，避免重复 hang 事件
            _hang_retry_counter.pop(key, None)
            _save_hang_retry_counter()
            active_tasks.pop(key, None)
            continue

        try:
            _activate_workspace(ws)
            result = dev_role_relaunch(tid)
        except Exception as exc:
            engine_log(f"[{label}] hang-auto: {tid} relaunch 异常: {exc}")
            result = {"ok": False}

        _hang_retry_counter[key] = retries + 1
        _save_hang_retry_counter()
        if result.get("ok"):
            engine_log(
                f"[{label}] hang-auto: {tid} phase {cur_phase} 已重启 "
                f"(retry {retries + 1}/{_MAX_HANG_RETRY})"
            )
        else:
            engine_log(f"[{label}] hang-auto: {tid} relaunch 返回非 ok: {result}")


def _get_running_pids(ws: Path) -> list[int]:
    """扫描 .ccc/pids/ 目录，返回没有对应 .done 标记的 PID 列表。"""
    pids_dir = ws / ".ccc" / "pids"
    if not pids_dir.is_dir():
        return []
    result: list[int] = []
    for f in sorted(pids_dir.iterdir()):
        if f.suffix != ".pid":
            continue
        subid = f.stem
        if (pids_dir / f"{subid}.done").exists():
            continue
        try:
            pid = int(f.read_text().strip())
            if pid > 0:
                result.append(pid)
        except (ValueError, OSError):
            pass
    return result


def _read_heartbeat(ws: Path) -> dict | None:
    hb_file = ws / ".ccc" / "engine-heartbeat.json"
    if hb_file.exists():
        try:
            return json.loads(hb_file.read_text())
        except (OSError, json.JSONDecodeError):
            pass
    return None


def _get_proc_rss_mb(pid: int) -> float:
    """取进程 RSS（MB），失败返回 0。"""
    import subprocess as _sp

    try:
        r = _sp.run(
            ["ps", "-o", "rss=", "-p", str(pid)],
            capture_output=True,
            text=True,
            timeout=3,
        )
        if r.returncode == 0 and r.stdout.strip().isdigit():
            return int(r.stdout.strip()) / 1024.0
    except (_sp.TimeoutExpired, FileNotFoundError, OSError, ValueError):
        pass
    return 0.0


def _cleanup_zombie_pid_refs(ws: Path) -> None:
    """扫描 .ccc/pids/*.pid，若进程已死且无 .done 标记 → 删残影。"""
    pids_dir = ws / ".ccc" / "pids"
    if not pids_dir.is_dir():
        return
    cleaned = 0
    for f in sorted(pids_dir.iterdir()):
        if f.suffix != ".pid":
            continue
        subid = f.stem
        if (pids_dir / f"{subid}.done").exists():
            continue
        try:
            pid = int(f.read_text().strip())
        except (ValueError, OSError):
            pid = 0
        if pid > 0:
            try:
                os.kill(pid, 0)  # 探活
                continue  # 进程活着 → 跳过
            except (ProcessLookupError, PermissionError):
                pass  # 已死或无权限
            except OSError:
                pass
        for sfx in (".pid", ".hung", ".exitcode", ".stdout"):
            marker = pids_dir / f"{subid}{sfx}"
            if marker.exists():
                try:
                    marker.unlink()
                    cleaned += 1
                except OSError:
                    pass
    if cleaned:
        engine_log(f"[{_ws_label(ws)}] 清理 {cleaned} 个残影 PID 标记")


def _check_process_memory(ws: Path) -> None:
    """抽样 CCC 相关进程 RSS → 告警 / degraded / 强杀。

    每 36 轮（~6min）执行一次。v0.37: 纳入 claude/radon/bandit/vulture/opencode，
    并按聚合 RSS 强杀最大非-engine 进程（此前心跳只看到 ~75MB 假象）。
    """
    import subprocess as _sp

    global _degraded_mode, _degraded_since

    warn_mb = getattr(cfg, "mem_warn_mb", _MEM_WARN_MB)
    degraded_mb = getattr(cfg, "mem_degraded_mb", _MEM_DEGRADED_MB)
    kill_mb = getattr(cfg, "mem_kill_mb", _MEM_KILL_MB)

    try:
        tracked: dict[int, str] = {}  # pid → label
        for pid in _get_running_pids(ws):
            tracked[pid] = "workspace-pid"
        tracked[os.getpid()] = "engine"

        # 补充：cmdline 含 ccc / claude / radon / bandit / vulture / opencode 的相关进程
        _MEM_KEYWORDS = (
            "ccc-",
            "ccc_",
            "claude",
            "radon",
            "bandit",
            "vulture",
            "opencode",
            "ccc-health-analyzer",
            "ccc-security-analyzer",
        )
        try:
            import platform as _plat

            if _plat.system() == "Darwin":
                ps_cmd = ["ps", "-axo", "rss=,pid=,args="]
            else:
                ps_cmd = ["ps", "-eo", "rss=,pid=,args=", "--sort=-rss"]
            r = _sp.run(ps_cmd, capture_output=True, text=True, timeout=5)
            for line in r.stdout.splitlines():
                parts = line.strip().split(None, 2)
                if len(parts) < 3:
                    continue
                try:
                    rss_kb = int(parts[0])
                    pid = int(parts[1])
                except ValueError:
                    continue
                args = parts[2].lower()
                if pid in tracked:
                    continue
                if any(k in args for k in _MEM_KEYWORDS):
                    tracked[pid] = args[:80]
                elif ("python" in args) and "ccc" in args:
                    tracked[pid] = args[:80]
        except (_sp.TimeoutExpired, FileNotFoundError, OSError):
            pass

        total = 0.0
        offenders: list[tuple[int, float, str]] = []
        for pid, label in tracked.items():
            rss_mb = _get_proc_rss_mb(pid)
            if rss_mb <= 0:
                continue
            total += rss_mb
            if rss_mb > warn_mb:
                offenders.append((pid, rss_mb, label))

        offenders.sort(key=lambda x: x[1], reverse=True)
        memory_mb = {
            "total": round(total, 1),
            "top_pid": [offenders[0][0], offenders[0][1]] if offenders else None,
            "warn_mb": warn_mb,
            "kill_mb": kill_mb,
        }

        # 写入 heartbeat（保留 running 等字段）
        prev = _read_heartbeat(ws) or {}
        _write_heartbeat(
            ws,
            prev.get("running"),
            int(prev.get("active_task_count") or 0),
            prev.get("running_pids") or [],
            memory_mb=memory_mb,
        )

        our_pids = set(_get_running_pids(ws))
        for pid, rss_mb, label in offenders:
            if rss_mb > kill_mb and (pid in our_pids or pid == os.getpid() or "claude" in label or "radon" in label or "bandit" in label or "vulture" in label or "opencode" in label):
                # 不杀 engine 自身
                if pid == os.getpid():
                    engine_log(
                        f"[mem] engine PID={pid} RSS={rss_mb:.0f}MB > {kill_mb}MB（仅告警，不自杀）"
                    )
                    continue
                engine_log(
                    f"[mem] PID={pid} RSS={rss_mb:.0f}MB > {kill_mb}MB，强杀进程树 ({label[:60]})"
                )
                _kill_process_tree(pid)
                _ccc_notify("CCC", f"[mem] 强杀 PID={pid}（RSS {rss_mb:.0f}MB）")

        # v0.37: 聚合超限 → 杀最大非-engine 进程
        if total > kill_mb:
            for pid, rss_mb, label in offenders:
                if pid == os.getpid():
                    continue
                engine_log(
                    f"[mem] 聚合 RSS={total:.0f}MB > {kill_mb}MB，强杀最大进程 PID={pid} ({rss_mb:.0f}MB)"
                )
                _kill_process_tree(pid)
                _ccc_notify(
                    "CCC",
                    f"[mem] 聚合超限 {total:.0f}MB，强杀 PID={pid}",
                )
                break

        if total > degraded_mb:
            if not _degraded_mode:
                _degraded_mode = True
                _degraded_since = time.time()
                engine_log(
                    f"[mem] 总RSS={total:.0f}MB > {degraded_mb}MB → degraded mode"
                )
                _ccc_notify("CCC", f"engine degraded：总 RSS {total:.0f}MB")

        for pid, rss_mb, label in offenders[:3]:
            if rss_mb > warn_mb:
                engine_log(
                    f"[mem] PID={pid} RSS={rss_mb:.0f}MB（warning阈值={warn_mb}MB） label={label[:40]}"
                )

    except (_sp.TimeoutExpired, FileNotFoundError, OSError) as e:
        _log.warning("[mem] 检查失败: %s", e)


def _write_heartbeat(
    ws: Path,
    running_task_id: str | None,
    active_task_count: int = 0,
    running_pids: list[int] | None = None,
    memory_mb: dict | None = None,
) -> None:
    ws = ws.resolve()
    # 保留上次 memory_mb，避免常规 heartbeat 覆盖掉内存采样
    if memory_mb is None:
        prev = _read_heartbeat(ws)
        if prev and isinstance(prev.get("memory_mb"), dict):
            memory_mb = prev["memory_mb"]
    hb = {
        "workspace": str(ws),
        "running": running_task_id or None,
        "active_task_count": active_task_count,
        "running_pids": running_pids or [],
        "timestamp": now_iso(),
    }
    if memory_mb is not None:
        hb["memory_mb"] = memory_mb
    hb_file = ws / ".ccc" / "engine-heartbeat.json"
    try:
        hb_file.write_text(json.dumps(hb, ensure_ascii=False) + "\n")
    except OSError as e:
        _log.warning("engine heartbeat write failed for %s: %s", ws, e)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="CCC Engine — multi-workspace scheduler"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=_STATS_PORT,
        help=f"Stats HTTP 端点端口（默认 {_STATS_PORT}）",
    )
    args = parser.parse_args(argv)

    program_dir = Path.home() / "program"
    workspaces = _discover_workspaces()
    if not workspaces:
        engine_log("未找到任何 workspace（需 ~/program/*/.ccc/board/）")
        sys.exit(1)

    labels = [_ws_label(w, program_dir) for w in workspaces]
    engine_log(f"发现 {len(workspaces)} 个 workspace: {labels}")

    def _handle_sigterm(signum, frame):
        global _engine_shutdown
        if _engine_shutdown:
            return
        _engine_shutdown = True
        engine_log("收到 SIGTERM, 优雅关闭中...")
        _write_engine_restart("shutdown", "SIGTERM")

    def _final_restart_log():
        if not _restart_log_written:
            _write_engine_restart("stopped", "exit/by_crash")

    atexit.register(_final_restart_log)

    signal.signal(signal.SIGTERM, _handle_sigterm)

    _run_stats_server(args.port)

    try:
        engine_loop(workspaces)
    except KeyboardInterrupt:
        engine_log("Engine 关闭")
        _write_engine_restart("shutdown", "KeyboardInterrupt")
    except SystemExit:
        _log.debug("engine exiting via SystemExit")
    _engine_shutdown = True
    engine_log("Engine 终止")


# ── Stats HTTP Endpoint（plan: engine-stats-endpoint） ──
def _read_engine_version() -> str:
    try:
        return (_script_dir.parent / "VERSION").read_text(encoding="utf-8").strip()
    except OSError:
        return "unknown"


_ENGINE_VERSION = _read_engine_version()
_stats_started_at: float | None = time.time()
_stats_lock = threading.Lock()
_stats_data: dict = {
    "uptime_sec": 0.001,
    "current_task": None,
    "current_phase": None,
    "phase_status": "pending",
    "in_progress_count": 0,
    "engine_version": _ENGINE_VERSION,
    "last_tick_at": None,
    "workspace": Path.cwd().name,
}


def _update_stats(
    active_count: int,
    current_task: str | None = None,
    current_phase: int | None = None,
    phase_status: str | None = None,
    workspace_name: str | None = None,
) -> None:
    global _stats_started_at
    now = now_iso()
    now_ts = time.time()
    with _stats_lock:
        if _stats_started_at is None:
            _stats_started_at = now_ts
            _stats_data["uptime_sec"] = 0
        else:
            _stats_data["uptime_sec"] = max(0.001, now_ts - _stats_started_at)
        _stats_data["current_task"] = current_task
        _stats_data["current_phase"] = current_phase
        _stats_data["phase_status"] = phase_status or (
            "running" if active_count else "done"
        )
        _stats_data["in_progress_count"] = active_count
        _stats_data["last_tick_at"] = now
        if workspace_name:
            _stats_data["workspace"] = workspace_name


class _StatsHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        engine_log(
            "[stats-api] %s - [%s] %s",
            self.address_string(),
            self.log_date_time_string(),
            format % args,
        )

    def do_GET(self):
        if self.path == "/api/stats":
            try:
                with _stats_lock:
                    payload = json.dumps(_stats_data, ensure_ascii=False).encode(
                        "utf-8"
                    )
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
            except Exception as exc:
                engine_log(f"[stats-api] 响应失败: {exc}")
                try:
                    self.send_response(500)
                    self.end_headers()
                except Exception:
                    pass
        else:
            self.send_response(404)
            self.end_headers()


def _stats_snapshot() -> dict:
    """HTTP 线程用的快照方法：与 _update_stats 共享锁。"""
    with _stats_lock:
        return dict(_stats_data)


def _run_stats_server(port: int) -> None:
    """在独立线程跑轻量 HTTP 服务，仅 127.0.0.1。"""
    try:
        server = HTTPServer(("127.0.0.1", port), _StatsHandler)
    except OSError as exc:
        engine_log(f"Stats HTTP 启动失败 (port={port}): {exc}")
        return
    engine_log(f"Stats HTTP 服务启动在 http://127.0.0.1:{port}/api/stats")

    def _serve():
        try:
            while not _engine_shutdown:
                server.handle_request()
        except Exception as exc:
            engine_log(f"Stats HTTP 服务异常: {exc}")
        finally:
            try:
                server.server_close()
            except Exception:
                pass
            engine_log("Stats HTTP 服务关闭")

    t = threading.Thread(target=_serve, name="ccc-stats-http", daemon=True)
    t.start()


if __name__ == "__main__":
    main()
