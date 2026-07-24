#!/usr/bin/env python3
"""ccc-engine.py — CCC 多 workspace 并行执行引擎 (v0.28.1+)

替代「每 workspace 一个 engine 进程」模式。
单进程扫描含 .ccc/board/ 的业务仓，全局 MAX_CONCURRENT 共享并发池
（默认 4；env ``CCC_MAX_CONCURRENT`` 可覆盖）。

使用方式:
  python3 ccc-engine.py
  CCC_MAX_CONCURRENT=6 python3 ccc-engine.py

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
from datetime import datetime, timezone
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
from _utils import get_relay_url as _utils_get_relay_url
from _stats_aggregator import aggregate_stats, load_summary
from _cost_telemetry import check_abnormal_traffic as _check_abnormal_traffic
from _capability_evolver import record_failure_pattern as _record_failure_pattern

_log = get_logger("engine")

_engine_shutdown = False
_engine_start_ts: float = time.time()
_restart_log_written: bool = False
_RESTART_LOG_PATH: Path = Path.home() / ".ccc" / "logs" / "engine-restarts.jsonl"

# board.roles / board.phase 在 import 时可能读 workspace；默认供首次加载
os.environ.setdefault("CCC_WORKSPACE", str(_script_dir.parent))

# v0.28.2: Stats HTTP 默认端口（plan: engine-stats-endpoint）
_STATS_PORT = 7776

import types as _types

from board.roles.dev import (  # noqa: E402
    dev_role_launch,
    dev_role_relaunch,
    dev_role_check_complete,
)
from board.roles.reviewer import (  # noqa: E402
    reviewer_role,
    clear_stale_review_locks,
)
from board.roles.tester import tester_role  # noqa: E402
from board.roles.kb import kb_role  # noqa: E402
from board.roles.product import (  # noqa: E402
    launch_product_async,
    check_product_async,
)
from board.roles.audit import (  # noqa: E402
    audit_role,
    _classify_task_intake,
    _run_auto_fix,
    _run_quick_fix,
    _evolve_run_one,
)
from board.roles.common import MAX_RETRY  # noqa: E402
from board.phase import (  # noqa: E402
    _load_phases,
    _resolve_phase_dependencies,
    _apply_phase_status_updates,
    _check_phase_failures,
    _current_running_phase,
)

# 兼容测试 monkeypatch：ccc_engine.ccc_board.X（不再 importlib 整文件加载 monolith）
ccc_board = _types.SimpleNamespace(
    dev_role_launch=dev_role_launch,
    dev_role_relaunch=dev_role_relaunch,
    dev_role_check_complete=dev_role_check_complete,
    reviewer_role=reviewer_role,
    tester_role=tester_role,
    kb_role=kb_role,
    MAX_RETRY=MAX_RETRY,
    clear_stale_review_locks=clear_stale_review_locks,
    launch_product_async=launch_product_async,
    check_product_async=check_product_async,
    audit_role=audit_role,
    _classify_task_intake=_classify_task_intake,
    _run_auto_fix=_run_auto_fix,
    _run_quick_fix=_run_quick_fix,
    _evolve_run_one=_evolve_run_one,
    _load_phases=_load_phases,
    _resolve_phase_dependencies=_resolve_phase_dependencies,
    _apply_phase_status_updates=_apply_phase_status_updates,
    _check_phase_failures=_check_phase_failures,
    _current_running_phase=_current_running_phase,
)

cfg = Config()

from engine.slots import (  # noqa: E402
    GLOBAL_OPENCODE_COUNT as _GLOBAL_OPENCODE_COUNT,
    OpenCodeCountProxy as _OpenCodeCountProxy,
    global_opencode_count as _global_opencode_count,
    opencode_slots_path as _opencode_slots_path,
    release_opencode_slot as _release_opencode_slot,
    try_acquire_opencode_slot as _try_acquire_opencode_slot,
    _GLOBAL_OPENCODE_MAX,
)
from engine import workspace as _engine_workspace  # noqa: E402
from engine.workspace import (  # noqa: E402
    _activate_workspace,
    _ensure_task_in_testing,
    _find_task_column,
    _get_store,
    _ws_label,
)
from engine.active_tasks import (  # noqa: E402
    ACTIVE_TASKS_FILE as _ACTIVE_TASKS_FILE,
    _drop_active_task_and_slots,
    _load_active_tasks,
    _register_active,
    _save_active_tasks,
    release_dev_slot as _release_dev_slot,
    workspace_blocks_new_opencode as _workspace_blocks_new_opencode,
)
from engine.hang import (  # noqa: E402
    _HANG_BUSY_MAX_SEC,
    _HANG_CHECK_INTERVAL_SEC,
    _HANG_COUNTER_FILE,
    _MAX_HANG_RETRY,
    _check_and_mark_hung,
    _hang_retry_counter,
    _load_hang_retry_counter,
    _run_hang_auto_restart,
    _save_hang_retry_counter,
)
from engine.gates import (  # noqa: E402
    _PYTEST_FAIL_MAX,
    _clear_verdict,
    _parse_verdict_status,
    _record_pytest_failure,
    _revert_task_commit,
    _run_pytest,
    _run_reviewer_tester_gate,
    _run_testing_tasks_gate,
    _run_verified_kb_gate,
    _verdict_file,
    _verdict_is_timeout,
    _verdict_is_valid,
)

_stores = _engine_workspace._stores

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
MAX_CONCURRENT = max(
    1,
    int(os.environ.get("CCC_MAX_CONCURRENT", "4") or "4"),
)  # cross-ws pool; same-ws OpenCode still 1
# product 异步并行：全局上限 / 每 workspace 上限（env 可降回串行）
MAX_PRODUCT_INFLIGHT = int(os.environ.get("CCC_MAX_PRODUCT_INFLIGHT", "3") or "3")
MAX_PRODUCT_PER_WS = int(os.environ.get("CCC_MAX_PRODUCT_PER_WS", "2") or "2")

# v0.35: degraded mode — 引擎自我保护
_degraded_mode = False
_degraded_since: float | None = None
_DEGRADED_QUARANTINE_THRESHOLD = 10   # 30min 内 quarantine > 此值 → degraded
_DEGRADED_FAIL_THRESHOLD = 10         # 30min 内 product_fail > 此值 → degraded
# v0.53+: 人下达 task_dispatch 可绕过 degraded intake（防 pending epic 饿死）
_intake_bypass_degraded = False
_intake_bypass_ticks_left = 0
_wake_priority_workspace: Path | None = None
_INTAKE_BYPASS_TICKS = 12  # ~2min @10s tick — enough for product launch
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

# H7: 主循环 tick 看门狗（卡死自愈 → exit → launchd KeepAlive）
_last_tick_mono: float = 0.0
_TICK_WATCHDOG_STALE_S = float(os.environ.get("CCC_ENGINE_TICK_STALE_S", "180") or "180")
_TICK_WATCHDOG_POLL_S = 30.0

# v0.28.2: Phase 并行调度（plan: engine-phase-parallel-dispatch）
PHASE_PARALLEL_MAX_WORKERS = 2


# ---------- 上游健康检测 ----------
_upstream_health_cache: dict = {}  # {"healthy": bool, "checked_at": float}


def _get_relay_url() -> str:
    """v0.51.0 P2-2: 委托 _utils.get_relay_url（SSOT）。"""
    return _utils_get_relay_url()


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
    # 仅做 TCP/HTTP 可达性探测，不发带假 key 的业务请求
    try:
        import ssl
        import urllib.error
        import urllib.request

        def _probe(ctx: ssl.SSLContext | None = None) -> tuple[int | None, str]:
            req = urllib.request.Request(
                messages_url,
                method="GET",
                headers={"User-Agent": "ccc-engine-health"},
            )
            try:
                # urlopen context= 仅 https 生效
                kwargs: dict = {"timeout": 5}
                if ctx is not None and messages_url.startswith("https://"):
                    kwargs["context"] = ctx
                resp = urllib.request.urlopen(req, **kwargs)
                code = getattr(resp, "status", None) or resp.getcode()
                return (int(code) if code is not None else None), ""
            except urllib.error.HTTPError as http_exc:
                # 4xx（如 401/405）仍说明上游在线
                return http_exc.code, str(http_exc.reason or http_exc)[:120]
            except urllib.error.URLError as url_exc:
                return None, str(url_exc.reason or url_exc)[:160]

        status_code, err_msg = _probe()
        # 本机 CA/中间人证书链常导致 verify 失败；健康检查只关心可达性
        if status_code is None and "CERTIFICATE" in (err_msg or "").upper():
            try:
                status_code, err_msg2 = _probe(ssl._create_unverified_context())
                if status_code is not None:
                    err_msg = f"tls_insecure_ok:{err_msg2 or err_msg}"[:160]
            except Exception as exc:
                err_msg = f"{err_msg}; insecure_retry={exc}"[:160]
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
            probe_path = probe_dir / "upstream-probe.jsonl"
            probe_record = {
                "ts": now_iso(),
                "healthy": healthy,
                "status": status_code,
                "error": err_msg or None,
                "relay": relay,
            }
            try:
                from _jsonl_rotate import append_jsonl
                append_jsonl(probe_path, probe_record)
            except ImportError:
                with probe_path.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(probe_record, ensure_ascii=False) + "\n")
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
    uptime = max(0.001, time.time() - _engine_start_ts)
    entry = {
        "ts": _utils_now_iso(),
        "pid": os.getpid(),
        "uptime_sec": round(uptime, 3),
        "status": status,
        "reason": reason,
        "source": "engine",
        "version": _ENGINE_VERSION,
    }
    try:
        from _jsonl_rotate import append_jsonl
        append_jsonl(_RESTART_LOG_PATH, entry)
    except ImportError:
        try:
            _RESTART_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            with _RESTART_LOG_PATH.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError:
            pass


def _check_last_exit_was_kill() -> bool:
    """检查上次退出是否为强制杀死（无正常日志）。返回 True=上次被强杀。"""
    try:
        if not _RESTART_LOG_PATH.exists():
            return False
        with _RESTART_LOG_PATH.open("r", encoding="utf-8") as f:
            lines = f.readlines()
            if not lines:
                return False
            last = json.loads(lines[-1].strip())
            last_status = last.get("status", "")
            if last_status == "started":
                return True
            return False
    except (json.JSONDecodeError, OSError):
        return False


def _loop_heartbeat_path() -> Path:
    return Path.home() / ".ccc" / "engine-loop-heartbeat.json"


_last_loop_hb_write_mono = 0.0
_LOOP_HB_WRITE_MIN_S = float(os.environ.get("CCC_ENGINE_LOOP_HB_WRITE_S", "30"))


def _mark_engine_tick() -> None:
    """记录主循环 tick 进度（H7 看门狗 + patrol 共用）。

    内存 mono 每 tick 更新；磁盘 heartbeat 节流写入（默认 30s），
    并用原子写避免半截 JSON。
    """
    global _last_tick_mono, _last_loop_hb_write_mono
    _last_tick_mono = time.monotonic()
    if (_last_tick_mono - _last_loop_hb_write_mono) < _LOOP_HB_WRITE_MIN_S:
        return
    _last_loop_hb_write_mono = _last_tick_mono
    try:
        from _board_store import _atomic_write

        p = _loop_heartbeat_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write(
            p,
            json.dumps(
                {
                    "pid": os.getpid(),
                    "timestamp": _utils_now_iso(),
                    "mono": _last_tick_mono,
                },
                ensure_ascii=False,
            )
            + "\n",
        )
    except OSError:
        pass


def _start_tick_watchdog() -> None:
    """若主循环超过 CCC_ENGINE_TICK_STALE_S 无 tick，exit 让 launchd 拉起。"""
    global _last_tick_mono
    _last_tick_mono = time.monotonic()

    def _watch() -> None:
        while not _engine_shutdown:
            time.sleep(_TICK_WATCHDOG_POLL_S)
            if _engine_shutdown:
                return
            age = time.monotonic() - _last_tick_mono
            if age > _TICK_WATCHDOG_STALE_S:
                engine_log(
                    f"[watchdog] no tick for {age:.0f}s "
                    f"(>{_TICK_WATCHDOG_STALE_S:.0f}s) — exit 0 for launchd SuccessfulExit restart"
                )
                try:
                    _RESTART_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
                    with _RESTART_LOG_PATH.open("a", encoding="utf-8") as f:
                        f.write(
                            json.dumps(
                                {
                                    "ts": _utils_now_iso(),
                                    "pid": os.getpid(),
                                    "status": "stopped",
                                    "reason": "tick_watchdog_stale",
                                    "stale_sec": round(age, 1),
                                    "exit_code": 0,
                                },
                                ensure_ascii=False,
                            )
                            + "\n"
                        )
                except OSError:
                    pass
                # Must be 0: plist KeepAlive SuccessfulExit only restarts on success.
                # Exit 78 (EX_CONFIG) left Engine dead after watchdog (pending epics starved).
                os._exit(0)

    t = threading.Thread(target=_watch, name="ccc-tick-watchdog", daemon=True)
    t.start()
    engine_log(
        f"[watchdog] tick watchdog on (stale={_TICK_WATCHDOG_STALE_S:.0f}s, "
        f"poll={_TICK_WATCHDOG_POLL_S:.0f}s)"
    )


PHASE_PARALLEL_DISABLED = False  # 故障 fallback 时设为 True（仅当次 Engine tick）

# Per-task 并行 phase 状态：
#   task_key -> {
#     "groups": [[phase_num, ...], ...],   # 待执行的 group 列表（每组内并行）
#     "current_group": [phase_num, ...] | None,  # 当前正在跑的 group
#     "phase_meta": {phase_num: {subid, pid, started_at}}
#   }
_parallel_phases: dict[str, dict] = {}

# v0.33: product_role 异步 inflight 表（task_key -> {tid, started_at, workspace}）
_product_inflight: dict[str, dict] = {}

# recover/失败后待补槽 relaunch（不立即超并发 launch）
# key = task_key -> {workspace, task_id, complexity, reason, enqueued_at}
_pending_relaunch: dict[str, dict] = {}

# relaunch 退避：key = f"{task_key}:p{phase}" -> {last_ts, count, last_head}
_relaunch_meta: dict[str, dict] = {}

# backlog+planned 为空时的补充冷却（per-workspace，单位秒）
_last_empty_replenish: dict[str, float] = {}


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
        from _jsonl_rotate import append_jsonl
        append_jsonl(sf, record)
    except ImportError:
        try:
            with sf.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError:
            pass
    except OSError:
        pass
    # 跨仓耗时 SSOT（小卡分钟数统计用）
    if event in ("opencode_start", "opencode_done"):
        try:
            gdir = Path.home() / ".ccc" / "stats"
            gdir.mkdir(parents=True, exist_ok=True)
            from _jsonl_rotate import append_jsonl as _aj

            _aj(gdir / "opencode-timings.jsonl", record)
        except Exception:
            try:
                with (Path.home() / ".ccc" / "stats" / "opencode-timings.jsonl").open(
                    "a", encoding="utf-8"
                ) as f:
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
            except OSError:
                pass


def _maybe_sample_host_resources(active_tasks: dict[str, dict]) -> None:
    """~60s Mac2017 CPU/内存曲线 → ~/.ccc/stats/host-resources.jsonl。"""
    try:
        from _host_resources import sample_and_append
        from engine.slots import global_opencode_count

        sample_and_append(
            active_dev=len(active_tasks),
            max_concurrent=MAX_CONCURRENT,
            opencode_slots=int(global_opencode_count()),
            interval_sec=60.0,
        )
    except Exception:
        pass


def _wall_seconds_from_started(started_at: str | None) -> float | None:
    """Parse active_tasks started_at → wall seconds; None if unparseable."""
    if not started_at:
        return None
    try:
        from datetime import datetime, timezone

        s = str(started_at).strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return round(max(0.0, (datetime.now(timezone.utc) - dt).total_seconds()), 2)
    except (TypeError, ValueError, OSError):
        return None


def _log_opencode_done(
    ws: Path,
    tid: str,
    *,
    status: str,
    complexity: str = "medium",
    started_at: str | None = None,
    result: dict | None = None,
) -> None:
    """埋点：小卡/阶段 OpenCode 墙钟 + result.duration_s。"""
    duration_s = None
    exit_code = None
    killed = None
    # result.json 优先（opencode-exec 写出）；容忍污染
    result_path = Path(ws) / ".ccc" / "reports" / f"{tid}.result.json"
    if result_path.is_file():
        try:
            from _result_json import parse_result_file

            raw_txt = result_path.read_text(encoding="utf-8", errors="replace")
            parsed, dirty = parse_result_file(result_path, raw=raw_txt)
            if dirty:
                _log_stats(ws, "dirty_result", tid, keys=list(parsed)[:20])
            if isinstance(parsed, dict) and parsed:
                if "duration_s" in parsed:
                    duration_s = float(parsed["duration_s"])
                if "exit_code" in parsed:
                    exit_code = parsed["exit_code"]
                if "killed" in parsed:
                    killed = bool(parsed["killed"])
        except (OSError, ValueError, TypeError):
            pass
    wall_s = _wall_seconds_from_started(started_at)
    # result dict 兜底（salvage / check_complete 可能未落盘 result.json）
    if duration_s is None and isinstance(result, dict):
        try:
            if result.get("duration_s") is not None:
                duration_s = float(result["duration_s"])
        except (TypeError, ValueError):
            pass
    # P2/KPI: 缺 duration_s 时用墙钟回填；双空则 0.0（保 fill_rate 可统计）
    duration_from_wall = False
    if duration_s is None and wall_s is not None:
        duration_s = wall_s
        duration_from_wall = True
    if duration_s is None:
        duration_s = 0.0
        duration_from_wall = True
    _log_stats(
        ws,
        "opencode_done",
        tid,
        status=status,
        complexity=complexity,
        duration_s=duration_s,
        wall_s=wall_s,
        duration_min=round(duration_s / 60.0, 3) if duration_s is not None else None,
        wall_min=round(wall_s / 60.0, 3) if wall_s is not None else None,
        exit_code=exit_code,
        killed=killed,
        result_status=(result or {}).get("status"),
        duration_from_wall=duration_from_wall,
    )


_NOTIFY_SCRIPT = _script_dir / "ccc-notify.sh"

# KPI R4: short-path fail budget — ban 1Hz planned↔in_progress storm
_SHORT_PATH_FAIL_MAX = 3


def _short_path_fail_file(ws: Path, tid: str) -> Path:
    return Path(ws) / ".ccc" / "pids" / f"{tid}.short_path_fails"


def _bump_short_path_fail(ws: Path, tid: str, path: str, why: str) -> int:
    """Increment fail counter; return new count."""
    p = _short_path_fail_file(ws, tid)
    p.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    try:
        if p.is_file():
            n = int((p.read_text(encoding="utf-8").strip().splitlines() or ["0"])[0])
    except (OSError, ValueError):
        n = 0
    n += 1
    try:
        p.write_text(
            f"{n}\npath={path}\nwhy={str(why)[:300]}\n",
            encoding="utf-8",
        )
    except OSError:
        pass
    return n


def _clear_short_path_fail(ws: Path, tid: str) -> None:
    p = _short_path_fail_file(ws, tid)
    try:
        if p.is_file():
            p.unlink()
    except OSError:
        pass


def _handle_short_path_failure(
    ws: Path,
    tid: str,
    store,
    *,
    label: str,
    path: str,
    why: str,
) -> bool:
    """On short-path fail: budgeted retry → abnormal. Returns True (tick consumed)."""
    n = _bump_short_path_fail(ws, tid, path, why)
    _log_stats(
        ws,
        "dev_path",
        tid,
        path=path,
        ok=False,
        why=str(why)[:200],
        short_path_fail_n=n,
    )
    _log_stats(
        ws,
        "short_path_retry",
        tid,
        path=path,
        n=n,
        max=_SHORT_PATH_FAIL_MAX,
        why=str(why)[:200],
    )
    col_now = store.find_task(tid)[0]
    if n >= _SHORT_PATH_FAIL_MAX:
        engine_log(
            f"[{label}] {tid} {path} fail budget {n}/{_SHORT_PATH_FAIL_MAX} "
            f"→ abnormal ({why})"
        )
        from_col = col_now
        if col_now == "in_progress":
            store.move_task(tid, "in_progress", "abnormal")
        elif col_now == "planned":
            store.move_task(tid, "planned", "abnormal")
        try:
            store.patch_task(
                tid,
                {
                    "note": (
                        ((store.find_task(tid)[1] or {}).get("note") or "")
                        + f"\n[{label}] short_path_fail_budget path={path} n={n}: {why}"
                    )[-2000:]
                },
            )
        except Exception:
            pass
        # 与 quarantine 对齐：必入 failures.jsonl，清板后仍可复盘
        try:
            from _failure_ledger import record_failure

            record_failure(
                ws,
                task_id=tid,
                role="dev",
                reason=f"short_path_fail_budget path={path} n={n}: {why}",
                phase=1,
                from_col=from_col,
                to_col="abnormal",
                related_stats_event="short_path_fail",
                extra={"path": path, "n": n},
            )
        except Exception:
            engine_log(
                f"[failures] short_path record_failure failed for {tid}: "
                f"{_traceback.format_exc()[:300]}"
            )
        store.update_index()
        return True
    engine_log(
        f"[{label}] {tid} {path} FAILED ({n}/{_SHORT_PATH_FAIL_MAX}): {why}"
    )
    if col_now == "in_progress":
        store.move_task(tid, "in_progress", "planned")
    store.update_index()
    return True


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
    """发现 Engine 管辖的 workspace（v0.51：跳过 orch / engine:false）。

    优先级：
      1. CCC_WORKSPACES=name:path,name:path 或 path,path（仍尊重 orch 过滤）
      2. ~/.ccc/workspaces.json → 仅 engine-eligible 条目
      3. CCC_DISCOVER_ALL=1 全扫（过滤 orch 路径）
      4. 空 → idle（不再 fallback 只跑 CCC）
    """
    import os as _os

    seen: set[str] = set()
    workspaces: list[Path] = []

    def _is_orch(p: Path) -> bool:
        try:
            from _workspace_registry import is_orch_path

            return is_orch_path(p)
        except ImportError:
            home = getattr(cfg, "ccc_home", None)
            if home and Path(home).resolve() == p.resolve():
                return True
            return Path(__file__).resolve().parent.parent.resolve() == p.resolve()

    def _add(p: Path, *, allow_orch: bool = False) -> None:
        if not p.is_dir():
            return
        if not (p / ".ccc" / "board").is_dir():
            return
        try:
            resolved = p.resolve()
        except OSError:
            return
        if not allow_orch and _is_orch(resolved):
            return
        key = str(resolved)
        if key in seen:
            return
        workspaces.append(resolved)
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

    try:
        from _workspace_registry import list_engine_paths, migrate_registry_roles

        # Best-effort migrate roles once per process start path
        migrate_registry_roles(dry_run=False)
        for p in list_engine_paths():
            _add(p)
        if workspaces:
            return workspaces
        # Registry exists but only orch / empty eligible → idle
        registry = Path.home() / ".ccc" / "workspaces.json"
        if registry.is_file():
            engine_log(
                "[workspace] registry has no engine-eligible apps "
                "(orch-only or empty) → idle"
            )
            return []
    except ImportError:
        registry = Path.home() / ".ccc" / "workspaces.json"
        if registry.is_file():
            try:
                data = json.loads(registry.read_text(encoding="utf-8"))
                for item in data.get("workspaces") or []:
                    if isinstance(item, str):
                        _add(Path(item).expanduser())
                    elif isinstance(item, dict) and item.get("path"):
                        role = str(item.get("role") or "").lower()
                        eng = item.get("engine")
                        if role == "orch" or eng is False:
                            continue
                        _add(Path(item["path"]).expanduser())
            except (OSError, json.JSONDecodeError) as exc:
                engine_log(f"[workspace] registry parse failed: {exc}")
            if workspaces:
                return workspaces
            engine_log("[workspace] registry parse/empty eligible → idle")
            return []

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

    # v0.51: no CCC-only fallback — idle until apps are registered
    engine_log("[workspace] no registry / no eligible apps → idle")
    return []


def _queue_has_consumable_work(store: FileBoardStore) -> bool:
    """enabled 模式可消费列；abnormal 由窄版 auto-refeed 回灌，不在此列直接调度。"""
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


def _task_key(ws: Path, tid: str) -> str:
    return f"{ws.resolve()}|{tid}"


def _can_accept_dev(active_tasks: dict[str, dict]) -> bool:
    """dev 槽未满时可接受新 active_task。"""
    return len(active_tasks) < MAX_CONCURRENT


def _enqueue_pending_relaunch(
    ws: Path,
    tid: str,
    *,
    complexity: str = "medium",
    reason: str = "recover",
) -> None:
    key = _task_key(ws, tid)
    _pending_relaunch[key] = {
        "workspace": ws,
        "task_id": tid,
        "complexity": complexity,
        "reason": reason,
        "enqueued_at": time.time(),
    }
    engine_log(f"[slot] pending_relaunch +{tid} ({reason})")


def _git_head_for_task(ws: Path, tid: str) -> str:
    """最近一条含 task_id 的 commit hash；无则空串。"""
    try:
        r = subprocess.run(
            ["git", "log", "-1", "--format=%H", f"--grep={tid}", "-E"],
            cwd=str(ws),
            capture_output=True,
            text=True,
            timeout=5,
        )
        return (r.stdout or "").strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def _relaunch_backoff_key(ws: Path, tid: str, phase: int | None) -> str:
    return f"{_task_key(ws, tid)}:p{phase if phase is not None else 0}"


def _relaunch_allowed(ws: Path, tid: str, phase: int | None = None) -> bool:
    """同 phase 无新 task_id commit 时指数退避（60*2^n，封顶 600s）。"""
    key = _relaunch_backoff_key(ws, tid, phase)
    meta = _relaunch_meta.get(key) or {}
    now = time.time()
    last_ts = float(meta.get("last_ts") or 0)
    count = int(meta.get("count") or 0)
    last_head = str(meta.get("last_head") or "")
    cur_head = _git_head_for_task(ws, tid)
    if cur_head and cur_head != last_head:
        return True
    if last_ts <= 0:
        return True
    wait = min(60 * (2 ** max(count - 1, 0)), 600)
    if now - last_ts < wait:
        engine_log(
            f"[slot] relaunch backoff {tid} p={phase}: "
            f"wait {wait:.0f}s (elapsed {now - last_ts:.0f}s, n={count})"
        )
        return False
    return True


def _note_relaunch(ws: Path, tid: str, phase: int | None = None) -> None:
    key = _relaunch_backoff_key(ws, tid, phase)
    prev = _relaunch_meta.get(key) or {}
    _relaunch_meta[key] = {
        "last_ts": time.time(),
        "count": int(prev.get("count") or 0) + 1,
        "last_head": _git_head_for_task(ws, tid),
    }


def _product_inflight_for_ws(ws: Path) -> int:
    ws_s = str(ws.resolve())
    n = 0
    for info in _product_inflight.values():
        w = info.get("workspace")
        if w is None:
            continue
        if str(Path(w).resolve()) == ws_s:
            n += 1
    return n


def _can_launch_product(ws: Path) -> bool:
    if len(_product_inflight) >= MAX_PRODUCT_INFLIGHT:
        return False
    if _product_inflight_for_ws(ws) >= MAX_PRODUCT_PER_WS:
        return False
    return True


def _rebuild_product_inflight(workspaces: list[Path]) -> None:
    """从各 WS *.product.pid 重建 inflight，避免重启后重复 launch。"""
    global _product_inflight
    rebuilt: dict[str, dict] = {}
    for ws in workspaces:
        pids_dir = ws / ".ccc" / "pids"
        if not pids_dir.is_dir():
            continue
        for pid_file in pids_dir.glob("*.product.pid"):
            tid = pid_file.name[: -len(".product.pid")]
            try:
                pid = int(pid_file.read_text().strip())
            except (OSError, ValueError):
                continue
            alive = False
            try:
                os.kill(pid, 0)
                alive = True
            except (OSError, ProcessLookupError):
                alive = False
            if not alive:
                continue
            key = _task_key(ws, tid)
            rebuilt[key] = {
                "tid": tid,
                "started_at": now_iso(),
                "workspace": ws,
                "pid": pid,
            }
    _product_inflight = rebuilt
    if rebuilt:
        engine_log(
            f"[product] 重建 inflight={len(rebuilt)} "
            f"(max_global={MAX_PRODUCT_INFLIGHT}, max_per_ws={MAX_PRODUCT_PER_WS})"
        )


def _product_async_markers(ws: Path, tid: str) -> tuple[bool, bool, bool]:
    """返回 (pid_alive, has_done_marker, has_usable_out)。

    has_usable_out：``.product.out`` 非空。进程已死但无 ``.done`` 时仍须走
    ``check_product_async``，否则 GC 会把合法 CHILDREN 丢掉（epic 永久 pending）。
    """
    pids_dir = Path(ws) / ".ccc" / "pids"
    pid_file = pids_dir / f"{tid}.product.pid"
    done_file = pids_dir / f"{tid}.product.done"
    out_file = pids_dir / f"{tid}.product.out"
    alive = False
    if pid_file.is_file():
        try:
            pid = int(pid_file.read_text().strip())
            os.kill(pid, 0)
            alive = True
        except (OSError, ValueError, ProcessLookupError):
            alive = False
    has_out = False
    if out_file.is_file():
        try:
            has_out = bool(out_file.read_text(encoding="utf-8", errors="replace").strip())
        except OSError:
            has_out = False
    return alive, done_file.is_file(), has_out


def _drop_product_inflight(key: str, reason: str) -> None:
    if key not in _product_inflight:
        return
    info = _product_inflight.pop(key, None) or {}
    tid = info.get("tid") or "?"
    engine_log(f"[product] inflight GC drop {tid}: {reason}")


def _finalize_or_gc_product_key(ws: Path, tid: str, key: str) -> str:
    """对单个 inflight key：有 .done / 活 pid / 非空 .out 则 check 收尾。

    Returns: kept | dropped | finalized
    """
    if key not in _product_inflight:
        return "dropped"
    alive, has_done, has_out = _product_async_markers(ws, tid)
    if has_done or alive or has_out:
        via = (
            "done"
            if has_done
            else ("alive" if alive else "out")
        )
        try:
            _activate_workspace(ws)
            engine_log(f"[product] finalize via {via}: {tid}")
            result = ccc_board.check_product_async(tid)
        except Exception as exc:
            engine_log(f"[product] GC check {tid} 异常: {exc}")
            result = {"status": "running"}
        status = result.get("status")
        if status in ("success", "failed"):
            _drop_product_inflight(key, f"check→{status}")
            return "finalized"
        if alive:
            return "kept"
        # done/out 已处理完或 pid 死但 check 仍 running → 防卡死，drop
        _drop_product_inflight(key, "stale markers without live pid")
        return "dropped"

    # 无 pid、无 done、无 out：按看板状态决定
    try:
        store = _get_store(ws)
        col, task = store.find_task(tid)
    except Exception:
        col, task = None, None
    if col is None:
        _drop_product_inflight(key, "task missing from board")
        return "dropped"
    if col != "backlog":
        _drop_product_inflight(key, f"not in backlog (col={col})")
        return "dropped"
    kind = (task or {}).get("card_kind") or "epic"
    split = (task or {}).get("split_status") or "pending"
    if kind == "epic" and split != "pending":
        _drop_product_inflight(key, f"epic split_status={split}")
        return "dropped"
    # backlog pending 但无进程、无输出 → 孤儿占槽，释放以便 relaunch
    _drop_product_inflight(key, "no live product pid")
    return "dropped"


def _gc_product_inflight(workspaces: list[Path]) -> int:
    """每 tick 回收孤儿 product inflight，避免 cap 假占满。"""
    if not _product_inflight:
        return 0
    ws_set = {str(Path(w).resolve()) for w in workspaces}
    dropped = 0
    for key in list(_product_inflight.keys()):
        info = _product_inflight.get(key) or {}
        ws = info.get("workspace")
        tid = str(info.get("tid") or "").strip()
        if ws is None or not tid:
            _drop_product_inflight(key, "invalid entry")
            dropped += 1
            continue
        ws_p = Path(ws)
        try:
            ws_s = str(ws_p.resolve())
        except OSError:
            _drop_product_inflight(key, "workspace unreadable")
            dropped += 1
            continue
        if ws_set and ws_s not in ws_set:
            # 仍尝试 GC（可能是临时路径）；不因不在列表而跳过
            pass
        before = key in _product_inflight
        outcome = _finalize_or_gc_product_key(ws_p, tid, key)
        if before and outcome != "kept":
            dropped += 1
    return dropped


def _handle_task_result(
    ws: Path,
    tid: str,
    result: dict,
    *,
    complexity: str = "medium",
    started_at: str | None = None,
) -> bool:
    """处理 dev_role_check_complete 结果。返回 True 表示从 active_tasks 移除。"""
    _activate_workspace(ws)
    store = _get_store(ws)
    label = _ws_label(ws)
    status = result.get("status", "unknown")
    err = str(result.get("error") or "")

    # 终态埋点（running / phase_done 再启另计 start）
    if status in ("success", "failed", "quarantined", "not_found"):
        try:
            _log_opencode_done(
                ws,
                tid,
                status=status,
                complexity=complexity,
                started_at=started_at,
                result=result,
            )
        except Exception as exc:
            engine_log(f"[{label}] opencode_done stats: {exc}")

    def _quarantine_keep_phases(reason: str) -> bool:
        """失败隔离：保留 phases/plan，禁止删图回 backlog 触发 product。"""
        col = _find_task_column(store, tid) or "in_progress"
        if col != "abnormal":
            try:
                store.move_task(tid, col, "abnormal")
            except Exception as exc:
                engine_log(f"[{label}] {tid} move→abnormal 失败: {exc}")
        try:
            _, task = store.find_task(tid)
            note = ((task or {}).get("note") or "") + f"\n[{label}] {reason}"
            store.patch_task(tid, {"note": note[-2000:]})
        except Exception:
            pass
        store.update_index()
        engine_log(f"[{label}] {tid} → abnormal（{reason}）")
        return True

    # commit-gate：有产出但无 task_id commit — 不得走 phase-regen/product
    if status in ("failed", "quarantined") and err.startswith("commit-gate"):
        return _quarantine_keep_phases(err)

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
            _note_relaunch(ws, tid, next_phase)
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
        # v0.31 (P0.1): phase 图无法解析 → 仅对「无 parent 的遗留单卡」允许删 phases 回 backlog
        # epic 子卡（work+parent_id）禁止：否则会被 _process_backlog 误跑 product
        if failure_summary.get("unresolvable"):
            _, _task = store.find_task(tid)
            from _board_store import normalize_task_view as _ntv

            _task = _ntv(_task or {"id": tid}, column="in_progress")
            if _task.get("card_kind") == "work" and _task.get("parent_id"):
                detail = (
                    f"phase graph unresolvable（epic 子卡，禁止 product regen）; "
                    f"summary={failure_summary!r}; err={err[:300]}"
                )
                return _quarantine_keep_phases(detail[:500])
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
        if not _relaunch_allowed(ws, tid, cur):
            return False
        _note_relaunch(ws, tid, cur)
        try:
            relaunch = dev_role_relaunch(tid)
        except Exception as exc:
            engine_log(f"[{label}] {tid} relaunch 异常: {exc}")
            return False
        if not (
            relaunch.get("ok")
            or relaunch.get("status") in ("launched", "ok", "running")
        ):
            engine_log(f"[{label}] {tid} relaunch 未成功: {relaunch}")
        return False

    if status == "quarantined":
        failure_summary = _check_phase_failures(tid)
        # v0.31 (P0.1): phase 图无法解析 — epic 子卡禁止 product regen
        if failure_summary.get("unresolvable"):
            _, _task = store.find_task(tid)
            from _board_store import normalize_task_view as _ntv

            _task = _ntv(_task or {"id": tid}, column="in_progress")
            if _task.get("card_kind") == "work" and _task.get("parent_id"):
                detail = (
                    f"phase graph unresolvable（epic 子卡，禁止 product regen）; "
                    f"summary={failure_summary!r}; err={err[:300]}"
                )
                return _quarantine_keep_phases(detail[:500])
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
    """记录一次 phase_graph_regen 到 warnings.json（原子写 + 文件锁）。"""
    try:
        import fcntl
        import tempfile

        _wf = ws / ".ccc" / "warnings.json"
        _wf.parent.mkdir(parents=True, exist_ok=True)
        # 锁文件与目标同目录，跨进程互斥
        lock_path = _wf.with_suffix(".json.lock")
        with open(lock_path, "a+", encoding="utf-8") as lock_f:
            fcntl.flock(lock_f.fileno(), fcntl.LOCK_EX)
            try:
                _existing: list = []
                if _wf.exists():
                    try:
                        raw = json.loads(_wf.read_text(encoding="utf-8"))
                        if isinstance(raw, list):
                            _existing = raw
                    except Exception:
                        _existing = []
                _regen_count = (
                    sum(
                        1
                        for w in _existing
                        if isinstance(w, dict)
                        and w.get("type") == "phase_graph_regen"
                        and w.get("task_id") == tid
                    )
                    + 1
                )
                _existing.append(
                    {
                        "type": "phase_graph_regen",
                        "task_id": tid,
                        "regen_count": _regen_count,
                        "detected_at": datetime.now(timezone.utc).isoformat(),
                    }
                )
                payload = json.dumps(_existing, ensure_ascii=False, indent=2)
                fd, tmp_name = tempfile.mkstemp(
                    dir=str(_wf.parent), prefix=".warnings-", suffix=".tmp"
                )
                try:
                    with os.fdopen(fd, "w", encoding="utf-8") as tf:
                        tf.write(payload)
                        tf.flush()
                        os.fsync(tf.fileno())
                    os.replace(tmp_name, str(_wf))
                except Exception:
                    try:
                        os.unlink(tmp_name)
                    except OSError:
                        pass
                    raise
            finally:
                fcntl.flock(lock_f.fileno(), fcntl.LOCK_UN)
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════
# v0.35: degraded mode — 引擎自我保护
# ═══════════════════════════════════════════════════════════════

def _recent_events(ws: Path, event_type: str, window_sec: int) -> list[dict]:
    """从 events.jsonl 读最近指定类型事件（滑动窗口）。

    大文件只扫尾部（默认 512KiB），避免每 6 tick 全量解析。
    """
    ev_file = ws / ".ccc" / "stats" / "events.jsonl"
    if not ev_file.exists():
        return []
    now = time.time()
    events = []
    max_bytes = int(os.environ.get("CCC_RECENT_EVENTS_BYTES", "524288"))
    try:
        size = ev_file.stat().st_size
        with ev_file.open("r", encoding="utf-8", errors="replace") as f:
            if size > max_bytes:
                f.seek(max(0, size - max_bytes))
                f.readline()  # 丢弃可能截断的首行
            for line in f:
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


def _recover_tasks(ws: Path, active_tasks: dict[str, dict]) -> None:
    """Engine 启动后扫描 board，恢复 in_progress/testing 列的 task 上下文。

    验收点：
      - in_progress 列 task: 调 dev_role_check_complete 恢复 phase 执行状态
      - running → 登记 active_tasks（满槽则只告警 + pending，不超 MAX_CONCURRENT）
      - failed/not running → 不立即 relaunch，写入 pending_relaunch
      - testing 列 task: 调 `_run_reviewer_tester_gate`（small 不跳过审测）
      - 每恢复一个 task 间隔 5s，避免并发重启风暴
      - board 为空时静默跳过，无日志噪声
    """
    _activate_workspace(ws)
    try:
        ccc_board.clear_stale_review_locks()
    except Exception as exc:
        engine_log(f"[recover] [{_ws_label(ws)}] clear_stale_review_locks: {exc}")
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
            f"（间隔 5s 避免并发；dev_slots={len(active_tasks)}/{MAX_CONCURRENT}）"
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
            if status == "running":
                if _register_active(
                    active_tasks, ws, tid, complexity=complexity
                ):
                    engine_log(f"[recover] [{label}] {tid} PID 仍存活，继续监控")
                else:
                    engine_log(
                        f"[recover] [{label}] {tid} PID 存活但槽已满，"
                        f"排入 pending_relaunch"
                    )
                    _enqueue_pending_relaunch(
                        ws,
                        tid,
                        complexity=complexity,
                        reason="recover_running_wait_slot",
                    )
            elif status == "success":
                _handle_task_result(
                    ws, tid, result, complexity=complexity
                )
                _release_dev_slot(None, ws, tid)
            elif status in ("failed", "quarantined", "not_found"):
                # P1: 有 .done 优先收口，禁止无脑 pending_relaunch 占槽
                done_marker = ws / ".ccc" / "pids" / f"{tid}.done"
                if done_marker.is_file() or status in ("quarantined", "not_found"):
                    _handle_task_result(
                        ws, tid, result, complexity=complexity
                    )
                    _release_dev_slot(None, ws, tid)
                elif status == "failed":
                    failure_summary = _check_phase_failures(tid)
                    if failure_summary.get("unresolvable") or failure_summary.get(
                        "all_failed_or_skipped"
                    ):
                        _handle_task_result(
                            ws, tid, result, complexity=complexity
                        )
                        _release_dev_slot(None, ws, tid)
                    else:
                        _enqueue_pending_relaunch(
                            ws, tid, complexity=complexity, reason="recover"
                        )
            elif status == "phase_done":
                _enqueue_pending_relaunch(
                    ws, tid, complexity=complexity, reason="phase_done"
                )
            else:
                # unknown — 走原结果处理（无强制 relaunch）
                _handle_task_result(
                    ws, tid, result, complexity=complexity
                )
                _release_dev_slot(None, ws, tid)
        except Exception as exc:
            engine_log(f"[recover] [{label}] {tid} in_progress 恢复异常: {exc}")

        if idx < len(in_prog) - 1:
            time.sleep(5)

    if testing:
        engine_log(
            f"[recover] [{label}] 恢复 {len(testing)} 个 testing task "
            f"（限预算门禁，不堵后续 launch）"
        )
        try:
            _run_testing_tasks_gate(ws)
        except Exception as exc:
            engine_log(f"[recover] [{label}] testing 恢复异常: {exc}")


def _try_fill_pending_relaunch(active_tasks: dict[str, dict]) -> bool:
    """消费 pending_relaunch 填空槽。返回是否启动/登记了至少一个。"""
    if not _pending_relaunch or not _can_accept_dev(active_tasks):
        return False
    did = False
    for key, item in list(_pending_relaunch.items()):
        if not _can_accept_dev(active_tasks):
            break
        if key in active_tasks:
            _pending_relaunch.pop(key, None)
            continue
        ws = item["workspace"]
        tid = item["task_id"]
        complexity = item.get("complexity", "medium")
        reason = item.get("reason", "recover")
        label = _ws_label(ws)
        try:
            _activate_workspace(ws)
            phase = _current_running_phase(tid)
            if reason == "recover_running_wait_slot":
                result = dev_role_check_complete(tid)
                if result.get("status") == "running":
                    if _register_active(
                        active_tasks, ws, tid, complexity=complexity
                    ):
                        _pending_relaunch.pop(key, None)
                        did = True
                        engine_log(
                            f"[slot] [{label}] {tid} 补槽登记（仍在跑）"
                        )
                    continue
                # 已不在跑 → 走 relaunch
            if not _relaunch_allowed(ws, tid, phase):
                continue
            _note_relaunch(ws, tid, phase)
            relaunch = dev_role_relaunch(tid)
            ok = relaunch.get("ok") or relaunch.get("status") in (
                "launched",
                "ok",
                "running",
            )
            if not ok:
                engine_log(
                    f"[slot] [{label}] pending_relaunch {tid} 失败: {relaunch}"
                )
                continue
            if _register_active(active_tasks, ws, tid, complexity=complexity):
                _pending_relaunch.pop(key, None)
                did = True
                engine_log(
                    f"[slot] [{label}] pending_relaunch {tid} 已启动 ({reason})"
                )
        except Exception as exc:
            engine_log(f"[slot] [{label}] pending_relaunch {tid} 异常: {exc}")
    return did


def _startup_scan_workspace(ws: Path, active_tasks: dict[str, dict]) -> None:
    """兼容旧调用：委托 _recover_tasks（含槽位上限）。"""
    _recover_tasks(ws, active_tasks)


def _refresh_epic_statuses(ws: Path) -> None:
    """扫 backlog epic：按子卡列推导五态（pending/planned/running/done/failed）。"""
    try:
        from _product_fanout import refresh_epic_lifecycle
    except ImportError:
        return
    store = _get_store(ws)
    for task in store.list_tasks("backlog"):
        if task.get("card_kind") != "epic":
            continue
        try:
            refresh_epic_lifecycle(store, task["id"])
        except Exception as exc:
            engine_log(f"[fanout] refresh {task.get('id')}: {exc}")


def _process_backlog(ws: Path) -> bool:
    """消费 backlog：只对 pending epic 调 Claude 扇出；epic 永不 move 出待办。

    work 误落 backlog：
    - plan+phases 齐全 → planned
    - 有 parent_id（epic 子卡）且缺 phases → abnormal（禁止 product 重拆）
    - 无 parent 的遗留单卡 → 可走 product 补 phases（兼容）
    """
    global _degraded_mode, _intake_bypass_degraded, _intake_bypass_ticks_left
    if _degraded_mode and not (
        _intake_bypass_degraded or _intake_bypass_ticks_left > 0
    ):
        return False

    _activate_workspace(ws)
    store = _get_store(ws)
    label = _ws_label(ws)
    from _board_store import normalize_task_view

    _refresh_epic_statuses(ws)

    backlog = store.list_tasks("backlog")
    if not backlog:
        return False

    did_something = False
    for task in backlog:
        tid = task["id"]
        key = _task_key(ws, tid)
        _task_data = normalize_task_view(task, column="backlog")
        kind = _task_data.get("card_kind") or "epic"
        split = _task_data.get("split_status") or "pending"

        # Epic：仅 pending 走 product；其余五态不自动重拆
        if kind == "epic":
            if split in ("planned", "running", "done", "failed"):
                if key in _product_inflight:
                    _finalize_or_gc_product_key(ws, tid, key)
                continue
            # pending（含存量 active 已被 refresh 精算）→ 下方走 product fanout
        else:
            # work 兼容：plan+phases 齐全 → planned
            phases_file = ws / ".ccc" / "phases" / f"{tid}.phases.json"
            plan_file = ws / ".ccc" / "plans" / f"{tid}.plan.md"
            parent_id = _task_data.get("parent_id")
            if phases_file.exists() and plan_file.exists():
                if key in _product_inflight:
                    _finalize_or_gc_product_key(ws, tid, key)
                if store.move_task(tid, "backlog", "planned"):
                    engine_log(
                        f"[product] [{label}] work {tid} → planned（兼容单卡）"
                    )
                    _log_stats(ws, "move", tid, from_col="backlog", to_col="planned")
                    did_something = True
                continue
            # epic 子卡禁止走 Claude product 扇出（扇出只服务 pending epic）
            if parent_id:
                if key in _product_inflight:
                    _finalize_or_gc_product_key(ws, tid, key)
                engine_log(
                    f"[product] [{label}] work {tid} parent={parent_id} "
                    f"缺 phases → abnormal（禁止 product 重拆）"
                )
                store.quarantine(
                    tid,
                    "epic child missing phases; refuse product regen",
                )
                store.update_index()
                did_something = True
                continue
            # 无 parent 的遗留 work：下方可走 product 补 phases

        # v0.35: auto/quick 仅对非 epic（或显式）—— epic 不做 auto
        if kind != "epic":
            try:
                _pipeline_class = ccc_board._classify_task_intake(_task_data)
            except Exception:
                _pipeline_class = "full"
            if _pipeline_class in ("auto", "quick"):
                if key in _product_inflight:
                    _finalize_or_gc_product_key(ws, tid, key)
                if _pipeline_class == "auto":
                    result = ccc_board._run_auto_fix(_task_data)
                    if result.get("ok"):
                        store.move_task(tid, "backlog", "released")
                    else:
                        store.move_task(tid, "backlog", "abnormal")
                else:
                    result = ccc_board._run_quick_fix(_task_data)
                    if result.get("ok"):
                        store.move_task(tid, "backlog", "testing")
                    else:
                        store.move_task(tid, "backlog", "abnormal")
                store.update_index()
                did_something = True
                continue

        # 2. 上游健康检测（避免 upstream 宕机 + fail_counter 永久锁死）
        if not _is_upstream_healthy():
            engine_log(
                f"[product] [{label}] {tid} 跳过 — upstream 不可用，下次 tick 重试（不计数）"
            )
            continue

        # 3. 失败计数器（step decay；禁止 15min 清零 — 否则 smoke 死循环）
        _COUNTER_DECAY_SEC = 900  # 15 分钟最多减 1，不归零
        fail_counter_dir = ws / ".ccc" / ".product-fail-counter"
        fail_counter_path = fail_counter_dir / f"{tid}.json"
        from _product_fail_counter import (
            clear_product_fail_count,
            load_product_fail_count,
            write_product_fail_count,
        )

        fail_count, _decay_msg = load_product_fail_count(
            fail_counter_path,
            decay_sec=_COUNTER_DECAY_SEC,
            max_retries=_MAX_PRODUCT_RETRIES,
        )
        if _decay_msg:
            engine_log(f"[product] [{label}] {tid} {_decay_msg}")

        def _mark_product_exhausted(reason: str) -> None:
            """epic 留 backlog 标 failed；work 才可 quarantine。"""
            if kind == "epic":
                store.patch_task(
                    tid,
                    {
                        "split_status": "failed",
                        "note": (_task_data.get("note") or "")
                        + f"\n[product] {reason}",
                    },
                )
                # 冻结算失败次数，防止衰减后重新 launch
                write_product_fail_count(
                    fail_counter_path, max(fail_count, _MAX_PRODUCT_RETRIES)
                )
                engine_log(
                    f"[product] [{label}] epic {tid} → failed（{reason}），仍留待办"
                )
            else:
                _quarantine_with_notify(
                    ws, tid, reason, store, phase=0, role="product", from_col="backlog"
                )
                clear_product_fail_count(fail_counter_path)
            _ccc_notify("CCC", f"product 拆分 {tid}: {reason[:120]}")

        if fail_count >= _MAX_PRODUCT_RETRIES:
            engine_log(
                f"[product] [{label}] {tid} 已失败 {fail_count} 次 >= {_MAX_PRODUCT_RETRIES}"
            )
            _mark_product_exhausted(f"product_role 连续失败 {fail_count} 次")
            did_something = True
            continue

        # 3. 检查 inflight 异步 product
        if key in _product_inflight:
            engine_log(f"[product] [{label}] {tid} 异步 product 检查...")
            result = ccc_board.check_product_async(tid)
            if result["status"] == "success":
                _product_inflight.pop(key, None)
                clear_product_fail_count(fail_counter_path)
                _log_stats(ws, "product_done", tid, fail_count=fail_count)
                kids = result.get("child_ids") or []
                if kids:
                    engine_log(
                        f"[product] [{label}] {tid} ✓ fanout {len(kids)} work → planned"
                    )
                else:
                    engine_log(f"[product] [{label}] {tid} ✓ 异步 product 完成")
                did_something = True
                continue
            elif result["status"] == "failed":
                _product_inflight.pop(key, None)
                err = result.get("error", "")[:200]
                if result.get("fatal") or str(err).startswith("auth:"):
                    fail_count = _MAX_PRODUCT_RETRIES
                else:
                    fail_count += 1
                write_product_fail_count(fail_counter_path, fail_count)
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
                    _q_reason = (
                        f"product_role 致命失败: {err}"
                        if result.get("fatal") or str(err).startswith("auth:")
                        else f"product_role 连续失败 {fail_count} 次"
                    )
                    _mark_product_exhausted(_q_reason)
                did_something = True
                continue
            engine_log(f"[product] [{label}] {tid} 异步 product 执行中...")
            continue

        # 4. Hub 定稿已挂 plan+phases → 跳过 Claude，本地扇出 work
        if kind == "epic":
            plan_file = ws / ".ccc" / "plans" / f"{tid}.plan.md"
            phases_file = ws / ".ccc" / "phases" / f"{tid}.phases.json"
            if plan_file.is_file() and phases_file.is_file() and not (
                _task_data.get("child_ids") or []
            ):
                try:
                    from _product_fanout import fanout_from_seeded_epic

                    seed_r = fanout_from_seeded_epic(
                        store, _task_data, max_phases=cfg.max_phases
                    )
                except Exception as exc:
                    seed_r = {"ok": False, "error": str(exc)}
                if seed_r.get("ok"):
                    engine_log(
                        f"[product] [{label}] epic {tid} seeded fanout → "
                        f"{seed_r.get('child_ids')}（跳过 Claude）"
                    )
                    clear_product_fail_count(fail_counter_path)
                    _log_stats(ws, "product_done", tid, fail_count=0, seeded=True)
                    did_something = True
                    continue
                engine_log(
                    f"[product] [{label}] epic {tid} seeded fanout 失败: "
                    f"{seed_r.get('error', '?')} — 回退 Claude product"
                )

        # 5. 启动异步 product（epic 扇出 / work 单卡）
        if not _can_launch_product(ws):
            engine_log(
                f"[product] [{label}] cap 已满 "
                f"(global={len(_product_inflight)}/{MAX_PRODUCT_INFLIGHT}, "
                f"ws={_product_inflight_for_ws(ws)}/{MAX_PRODUCT_PER_WS})，"
                f"跳过 launch {tid}"
            )
            continue

        engine_log(
            f"[product] [{label}] backlog 异步拆分: {tid} "
            f"kind={kind} (此前失败 {fail_count} 次)"
        )
        _log_stats(ws, "product_start", tid, fail_count=fail_count)
        launch_r = ccc_board.launch_product_async(tid)
        if launch_r.get("ok"):
            _product_inflight[key] = {
                "tid": tid,
                "started_at": now_iso(),
                "workspace": ws,
            }
            did_something = True
            continue

        # 6. 启动失败
        fail_count += 1
        write_product_fail_count(fail_counter_path, fail_count)
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
            _mark_product_exhausted(f"product_role 连续失败 {fail_count} 次")
        did_something = True

    return did_something


def _auto_replenish_backlog(ws: Path, store, program_dir: Path) -> bool:
    """backlog + planned 都为空时，立即触发 audit_role 补充新任务。

    v0.42.4: **永久禁用**（自动识别投入会吃爆内存）。恒返回 False。
    """
    return False


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


def _build_phase_prompt(
    task_id: str, phase_num: int, plan_content: str, *, workspace: Path
) -> str:
    """构造单 phase 的 prompt（委托 board.prompt，显式传 workspace）。"""
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
        pf = workspace / ".ccc" / "pids" / f"{task_id}.pytest_fail.md"
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
        workspace=workspace,
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
        _build_phase_prompt(task_id, phase_num, plan_content, workspace=ws),
        encoding="utf-8",
    )
    try:
        os.chmod(prompt_file, 0o600)
    except OSError:
        pass
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
            try:
                from _workspace_isolation import capture_isolation_baseline

                capture_isolation_baseline(ws, task_id)
            except Exception as _iso_exc:
                engine_log(f"[isolation] baseline {task_id}: {_iso_exc}")
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
        # 只调度 work 小卡（epic 永不进入 planned）
        from _board_store import normalize_task_view as _norm

        tview = _norm(task, column="planned")
        if tview.get("card_kind") == "epic":
            engine_log(f"[{label}] 跳过误入 planned 的 epic {tid}")
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
        if not _can_accept_dev(active_tasks):
            return False
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
                    if not _register_active(
                        active_tasks,
                        ws,
                        tid,
                        complexity=complexity,
                        mode="parallel",
                    ):
                        engine_log(
                            f"[{label}] {tid} 并行已启动但槽满，无法登记（异常）"
                        )
                        continue
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
        # 短路径硬门（P5）：board_ops / script_seed / feature_seed 不占 OpenCode 槽，
        # 必须在同仓互斥检查之前 —— 否则纸面/卫生卡被活 opencode 拖成 queue_wait 地板。
        short_path: str | None = None
        try:
            from board.roles.board_ops import run_board_ops, should_use_board_ops
            from board.roles.script_seed import (
                run_feature_seed,
                run_script_seed,
                should_use_feature_seed,
                should_use_script_seed,
            )

            task_meta = next(
                (t for t in store.list_tasks("planned") if t.get("id") == tid),
                None,
            )
            if task_meta and should_use_script_seed(ws, task_meta):
                short_path = "script_seed"
                engine_log(
                    f"[{label}] {tid} script_seed short path "
                    f"(intent probe, no opencode; bypass same-ws mutex)"
                )
                if store.find_task(tid)[0] == "planned":
                    store.move_task(tid, "planned", "in_progress")
                seed_r = run_script_seed(ws, tid)
                if not seed_r.get("ok"):
                    return _handle_short_path_failure(
                        ws,
                        tid,
                        store,
                        label=label,
                        path="script_seed",
                        why=str(
                            seed_r.get("error")
                            or seed_r.get("why")
                            or seed_r
                        )[:300],
                    )
                _clear_short_path_fail(ws, tid)
                _log_stats(
                    ws,
                    "dev_path",
                    tid,
                    path="script_seed",
                    ok=True,
                )
                # P0 KPI: short-path OK must advance — never leave done+in_progress ghost
                col_now = store.find_task(tid)[0]
                if col_now == "in_progress":
                    store.move_task(tid, "in_progress", "testing")
                    engine_log(f"[{label}] {tid} script_seed OK → testing")
                store.update_index()
                return True
            if task_meta and should_use_feature_seed(ws, task_meta):
                short_path = "feature_seed"
                engine_log(
                    f"[{label}] {tid} feature_seed short path "
                    f"(feature probe, no opencode; bypass same-ws mutex)"
                )
                if store.find_task(tid)[0] == "planned":
                    store.move_task(tid, "planned", "in_progress")
                feat_r = run_feature_seed(ws, tid)
                if not feat_r.get("ok"):
                    return _handle_short_path_failure(
                        ws,
                        tid,
                        store,
                        label=label,
                        path="feature_seed",
                        why=str(
                            feat_r.get("error")
                            or feat_r.get("why")
                            or feat_r
                        )[:300],
                    )
                _clear_short_path_fail(ws, tid)
                _log_stats(
                    ws,
                    "dev_path",
                    tid,
                    path="feature_seed",
                    ok=True,
                )
                col_now = store.find_task(tid)[0]
                if col_now == "in_progress":
                    store.move_task(tid, "in_progress", "testing")
                    engine_log(f"[{label}] {tid} feature_seed OK → testing")
                store.update_index()
                return True
            if task_meta and should_use_board_ops(ws, task_meta):
                short_path = "board_ops"
                engine_log(
                    f"[{label}] {tid} board_ops short path "
                    f"(no opencode; bypass same-ws mutex)"
                )
                if store.find_task(tid)[0] == "planned":
                    store.move_task(tid, "planned", "in_progress")
                ops_r = run_board_ops(ws, tid)
                if not ops_r.get("ok"):
                    return _handle_short_path_failure(
                        ws,
                        tid,
                        store,
                        label=label,
                        path="board_ops",
                        why=str(ops_r.get("why") or ops_r)[:300],
                    )
                _clear_short_path_fail(ws, tid)
                _log_stats(
                    ws,
                    "dev_path",
                    tid,
                    path="board_ops",
                    ok=True,
                )
                col_now = store.find_task(tid)[0]
                if col_now == "in_progress":
                    store.move_task(tid, "in_progress", "testing")
                    engine_log(f"[{label}] {tid} board_ops OK → testing")
                store.update_index()
                return True
        except Exception as _bo_exc:
            if short_path:
                return _handle_short_path_failure(
                    ws,
                    tid,
                    store,
                    label=label,
                    path=short_path,
                    why=str(_bo_exc)[:300],
                )
            engine_log(
                f"[{label}] {tid} board_ops/script_seed probe error: {_bo_exc}"
            )

        # 同仓互斥：仅挡 OpenCode 路径（P1：死 pid+.done 不挡）
        if _workspace_blocks_new_opencode(ws, active_tasks):
            engine_log(
                f"[engine] [{label}] 同仓已有 active opencode，延后启动 {tid}"
            )
            continue

        if not _try_acquire_opencode_slot(tkey):
            engine_log(
                f"[engine] opencode 槽忙（全局 "
                f"{_GLOBAL_OPENCODE_COUNT}/{_GLOBAL_OPENCODE_MAX} 或同仓互斥），等待"
            )
            continue
        launch_r = dev_role_launch(tid)
        if "error" in launch_r:
            _release_opencode_slot(tkey, 1)
            engine_log(f"[{label}] 启动 {tid} 失败: {launch_r['error']}")
            continue
        if not _register_active(
            active_tasks, ws, tid, complexity=complexity
        ):
            _release_opencode_slot(tkey, 1)
            engine_log(f"[{label}] {tid} launch 成功但槽满，拒绝登记")
            continue
        _log_stats(
            ws,
            "opencode_start",
            tid,
            complexity=complexity,
            pid=launch_r.get("pid"),
            mode="serial",
            path="opencode",
        )
        _log_stats(ws, "dev_path", tid, path="opencode", ok=True)
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
    """原子写 phases.json：写 temp + fsync + os.replace。容错 fallback 直写。"""
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as tf:
            tf.write(payload)
            tf.flush()
            os.fsync(tf.fileno())
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
    """引擎主循环：多 workspace 轮询，全局 MAX_CONCURRENT 共享。"""
    global MAX_RETRY
    global _engine_shutdown
    global _intake_bypass_ticks_left, _intake_bypass_degraded

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

    # 启动即消费 wake（须在 recover 之前：ccc-demo testing recover 可堵数分钟，否则人下达饿死）
    try:
        if _apply_dispatch_wake(workspaces):
            workspaces[:] = _prioritize_wake_workspace(workspaces)
            engine_log("[wake] applied before recover — priority intake armed")
    except Exception as exc:
        engine_log(f"[wake] pre-recover apply failed: {exc}")

    program_dir = Path.home() / "program"
    labels = [_ws_label(w, program_dir) for w in workspaces]
    engine_log(f"CCC Engine 启动 ({len(workspaces)} workspace)")
    engine_log(f"  workspaces={labels}")
    engine_log(
        f"  poll_interval={cfg.engine_poll_interval}s, idle_sleep={cfg.engine_idle_sleep}s"
    )
    engine_log(f"  max_retry={MAX_RETRY}, max_concurrent={MAX_CONCURRENT}")
    engine_log(
        f"  max_product_inflight={MAX_PRODUCT_INFLIGHT}, "
        f"max_product_per_ws={MAX_PRODUCT_PER_WS}"
    )

    _write_engine_restart("started")

    active_tasks: dict[str, dict] = {}
    iteration = 0

    # R4: 从持久化文件恢复 active_tasks，避免重启丢上下文
    active_tasks = _load_active_tasks()
    # 持久化可能超过并发上限（旧 bug）；裁到 MAX_CONCURRENT
    if len(active_tasks) > MAX_CONCURRENT:
        overflow = list(active_tasks.keys())[MAX_CONCURRENT:]
        for k in overflow:
            info = active_tasks.pop(k)
            _enqueue_pending_relaunch(
                info.get("workspace") or Path(k.split("|")[0]),
                info.get("task_id") or k.split("|")[-1],
                complexity=info.get("complexity", "medium"),
                reason="trim_overflow",
            )
        _save_active_tasks(active_tasks)
        engine_log(
            f"[slot] 启动裁剪 active_tasks → {MAX_CONCURRENT}，"
            f"溢出 {len(overflow)} 入 pending_relaunch"
        )
    _load_hang_retry_counter()

    # v0.36: 启动时先采样内存（在 recover 之前，避免 recover 间隔拖慢 heartbeat）
    try:
        _cleanup_global_opencode_pids()
    except Exception as exc:
        engine_log(f"[pids] global opencode-pids cleanup failed: {exc}")
    for ws in workspaces:
        try:
            _check_process_memory(ws)
            _cleanup_zombie_pid_refs(ws)
        except Exception as exc:
            engine_log(f"[mem] startup sample failed for {_ws_label(ws)}: {exc}")

    _rebuild_product_inflight(workspaces)

    for ws in workspaces:
        _recover_tasks(ws, active_tasks)

    _start_tick_watchdog()

    while not _engine_shutdown:
        # 运行中也能响应 disable/ui：否则 control 切换后仍继续拉任务吃内存
        if not may_start_engine():
            engine_log(
                f"CCC control={get_mode()} — mid-loop idle hold "
                f"(resume: python3 scripts/_ccc_control.py enable)"
            )
            while not _engine_shutdown and not may_start_engine():
                time.sleep(15)
            if _engine_shutdown:
                break
            engine_log(f"CCC control={get_mode()} — resume engine loop")
            continue

        iteration += 1
        _mark_engine_tick()
        _maybe_sample_host_resources(active_tasks)
        tick_start = time.time()
        # 非深睡时也消费 wake：人下达立刻优先 intake，不等人空闲
        try:
            if _apply_dispatch_wake(workspaces):
                workspaces[:] = _prioritize_wake_workspace(workspaces)
        except Exception as exc:
            engine_log(f"[wake] apply dispatch wake failed: {exc}")
        if _intake_bypass_ticks_left > 0:
            _intake_bypass_ticks_left -= 1
            if _intake_bypass_ticks_left <= 0:
                _intake_bypass_degraded = False
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

                    if _handle_task_result(
                        ws,
                        tid,
                        result,
                        complexity=complexity,
                        started_at=info.get("started_at"),
                    ):
                        # P1: 任意终态统一释槽（serial；parallel 在 group 完成时已递减）
                        if mode != "parallel":
                            _release_dev_slot(None, ws, tid, reap=True)
                            # active_tasks pop 仍由下方 completed_tasks 负责，避免双重 save 竞态
                            # 槽位已在 release_dev_slot(None) 释放；此处只 pop dict
                        completed_tasks.append(key)

                for key in completed_tasks:
                    active_tasks.pop(key, None)
                if completed_tasks:
                    _save_active_tasks(active_tasks)
                # tick 边界重置 fallback 标志
                _reset_parallel_disabled_after_tick()

            # product 不占 dev 槽：先 GC 孤儿 inflight，再 backlog intake（自有 cap）
            try:
                _gc_product_inflight(workspaces)
            except Exception as exc:
                engine_log(f"[product] inflight GC error: {exc}")
            for ws in workspaces:
                _activate_workspace(ws)
                if _process_backlog(ws):
                    any_active = True

            # P4: 先 launch planned，再跑 testing 门禁（禁止「先测完全列才 launch」）
            while len(active_tasks) < MAX_CONCURRENT and not _engine_shutdown:
                did_something = False
                if _try_fill_pending_relaunch(active_tasks):
                    did_something = True
                    any_active = True
                for ws in workspaces:
                    if len(active_tasks) >= MAX_CONCURRENT:
                        break
                    if _try_launch_planned(ws, active_tasks):
                        did_something = True
                        any_active = True
                if not did_something:
                    break

            # 每 tick 抽干 testing（短路径优先、限张）；避免每 60s 才审 → gate_wall 空等
            for ws in workspaces:
                try:
                    _activate_workspace(ws)
                    _store = _get_store(ws)
                    if _store.list_tasks("testing"):
                        _run_testing_tasks_gate(ws)
                except Exception as exc:
                    engine_log(f"[testing-gate] {_ws_label(ws)}: {exc}")

            # 每 6 轮（~60s）跑一次 degraded 检测 + stale check + 统计聚合
            if iteration % 6 == 0:
                for ws in workspaces:
                    _activate_workspace(ws)
                    _check_degraded(ws)
                    _store = _get_store(ws)
                    _check_stale(ws, active_tasks)
                    # enabled 下：瞬态 abnormal work 有限自动 reopen（非 invent）
                    try:
                        _retry_abnormal_failures(ws)
                    except Exception as exc:
                        engine_log(
                            f"[abnormal-refeed] {_ws_label(ws)}: {exc}"
                        )
                    # v0.36: 每 36 tick (~6min) 内存监控 + 残影 PID 清理
                    if iteration % 36 == 0:
                        try:
                            _cleanup_global_opencode_pids()
                        except Exception as exc:
                            engine_log(f"[pids] global opencode-pids cleanup 异常: {exc}")
                        try:
                            _check_process_memory(ws)
                        except Exception as exc:
                            engine_log(f"[mem] {_ws_label(ws)} 异常: {exc}")
                        try:
                            _cleanup_zombie_pid_refs(ws)
                        except Exception as exc:
                            engine_log(f"[pids] {_ws_label(ws)} cleanup 异常: {exc}")
                    # testing 已在每 tick 处理；此处不再重复
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
                try:
                    testing_n = len(_get_store(ws).list_tasks("testing"))
                except Exception:
                    testing_n = 0
                _write_heartbeat(
                    ws,
                    running_task_id,
                    ws_count,
                    ws_pids,
                    testing_count=testing_n,
                    global_active_count=len(active_tasks),
                )

            if not active_tasks:
                for ws in workspaces:
                    _activate_workspace(ws)
                    _check_stale(ws, active_tasks)
                    # 空闲时立即处理 testing 任务（仍限预算）
                    _store2 = _get_store(ws)
                    test_tasks = _store2.list_tasks("testing")
                    if test_tasks:
                        label = _ws_label(ws)
                        engine_log(
                            f"[{label}] idle: testing 列有 {len(test_tasks)} 个任务，跑 reviewer+tester 门禁（限预算）"
                        )
                        _run_testing_tasks_gate(ws)
                    if _store2.list_tasks("verified"):
                        _run_verified_kb_gate(ws)
                    _write_heartbeat(
                        ws,
                        None,
                        0,
                        [],
                        testing_count=len(test_tasks),
                        global_active_count=0,
                    )

                    # v0.40: enabled=只消费；invent 才允许 audit/evolve/replenish/abnormal
                    # v0.51.0 P2-1: _may_invent() 恒 False（INVENT_HARD_DISABLED），化简为仅检查 consumable
                    _has_consumable = _queue_has_consumable_work(_store2)
                    if not _has_consumable:
                        continue

                    # v0.51.0 P2-1: 删除 _may_invent() 守护的 audit_role 自动触发（永不触发）
                    # v0.51.0 P2-1: 删除 _may_invent() 守护的 evolve-on-idle 块（永不触发）
                    # v0.51.0 P2-1: 删除 _may_invent() 守护的 _auto_replenish_backlog / _retry_abnormal_failures 块（永不触发）

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
                wake_payload = _sleep_until_wake(60)
                if wake_payload is not None:
                    engine_log("[wake] 收到 engine.wake，立即进入下一 tick")
                    # 唤醒后必须重扫 registry：新 register 的 app 否则永远 invisible
                    # （曾导致 clawmed-ccc epic 在 backlog，Engine 只盯 ccc-demo 报 queue empty）
                    workspaces[:] = _rediscover_workspaces(workspaces)
                    try:
                        _apply_dispatch_wake(
                            workspaces, already_consumed=wake_payload
                        )
                        workspaces[:] = _prioritize_wake_workspace(workspaces)
                    except Exception as exc:
                        engine_log(f"[wake] post-deep-sleep apply failed: {exc}")
                elif iteration % 12 == 0:
                    # 深睡满轮也轻量重扫，覆盖「只 register 未 wake」
                    workspaces[:] = _rediscover_workspaces(workspaces)
                continue

            if not any_active:
                time.sleep(cfg.engine_tick_interval)
                continue

        except KeyboardInterrupt:
            engine_log("收到 SIGINT, 优雅关闭")
            break
        except Exception as e:
            engine_log(f"异常: {e}")
            tb_text = _traceback.format_exc()
            engine_log(f"{tb_text[:2000]}")
            # 末行上下文（勿用未定义的 _tb）
            last = next(
                (ln for ln in reversed(tb_text.splitlines()) if ln.strip()),
                "",
            )
            if last:
                engine_log(f"  {last[:300]}")
            time.sleep(cfg.engine_idle_sleep)
            continue

        _wait_tick(tick_start)

    engine_log("收到关闭信号，停止接收新任务")


def _rediscover_workspaces(current: list[Path]) -> list[Path]:
    """Re-read ~/.ccc/workspaces.json；名单变化时打日志。返回最新列表（失败则保留旧）。"""
    try:
        discovered = _discover_workspaces()
    except Exception as exc:
        engine_log(f"[workspace] rediscover failed: {exc}")
        return current
    if not discovered:
        return current
    old = {str(p.resolve()) for p in current}
    new = {str(p.resolve()) for p in discovered}
    if old != new:
        program_dir = Path.home() / "program"
        labels = [_ws_label(w, program_dir) for w in discovered]
        engine_log(
            f"[workspace] rediscover {len(current)} → {len(discovered)}: {labels}"
        )
        return discovered
    return current


def _apply_wake_payload(payload: dict | None, workspaces: list[Path]) -> bool:
    """Apply task_dispatch wake: bypass degraded intake + remember priority workspace.

    Returns True if a dispatch-style wake was applied.
    """
    global _degraded_mode, _degraded_since, _intake_bypass_degraded
    global _intake_bypass_ticks_left, _wake_priority_workspace
    if not payload or not isinstance(payload, dict):
        return False
    reason = str(payload.get("reason") or "")
    # Human transfer / Hub ensure uses task_dispatch; also accept bare wake
    is_dispatch = (
        reason.startswith("task_dispatch")
        or reason in ("wake", "task_dispatch", "hub_manual_start")
        or "task_dispatch" in reason
        or bool(payload.get("workspace") or payload.get("task_id"))
    )
    if not is_dispatch:
        return False
    engine_log(
        f"[wake] apply reason={reason!r} task={payload.get('task_id')} "
        f"ws={payload.get('workspace')}"
    )
    _intake_bypass_degraded = True
    _intake_bypass_ticks_left = _INTAKE_BYPASS_TICKS
    if _degraded_mode:
        _degraded_mode = False
        _degraded_since = None
        engine_log("[wake] cleared degraded — human dispatch must intake pending epic")
    ws_raw = payload.get("workspace")
    if ws_raw:
        try:
            wp = Path(str(ws_raw)).resolve()
            if wp.is_dir():
                _wake_priority_workspace = wp
        except OSError:
            pass
    return True


def _apply_dispatch_wake(
    workspaces: list[Path], *, already_consumed: dict | None = None
) -> bool:
    """Consume ~/.ccc/engine.wake (unless already_consumed) and apply dispatch priority."""
    if already_consumed is not None:
        return _apply_wake_payload(already_consumed, workspaces)
    try:
        from _engine_wake import consume_wake

        payload = consume_wake()
    except Exception:
        return False
    return _apply_wake_payload(payload, workspaces)


def _prioritize_wake_workspace(workspaces: list[Path]) -> list[Path]:
    """Move wake target workspace to front so product intake isn't starved by other apps."""
    global _wake_priority_workspace
    pri = _wake_priority_workspace
    if pri is None or not workspaces:
        return workspaces
    try:
        pri_res = pri.resolve()
    except OSError:
        return workspaces
    head: list[Path] = []
    rest: list[Path] = []
    for ws in workspaces:
        try:
            if ws.resolve() == pri_res:
                head.append(ws)
            else:
                rest.append(ws)
        except OSError:
            rest.append(ws)
    if not head:
        # Wake workspace not yet in list — prepend if registered path exists
        if pri_res.is_dir():
            return [pri_res] + list(workspaces)
        return workspaces
    return head + rest


def _sleep_until_wake(seconds: float) -> dict | None:
    """深睡可被 ~/.ccc/engine.wake 打断。返回 wake payload 或 None。"""
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
                return payload if isinstance(payload, dict) else {"reason": "wake"}
            time.sleep(min(2.0, max(0.1, end - time.time())))
        # 超时前再看一眼
        payload = consume_wake()
        if payload is not None:
            return payload if isinstance(payload, dict) else {"reason": "wake"}
        return None
    except Exception:
        time.sleep(seconds)
        return None


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
    """enabled 下有限回灌：仅业务仓 work 卡、瞬态、每卡 ≤2，走 reopen_task。

    禁止 orch/invent；permanent / fail_loop_exhausted 不重开。
    """
    from datetime import datetime as _dt
    import json as _json

    global _breaker_open, _breaker_since

    recovery = getattr(cfg, "breaker_recovery_seconds", _BREAKER_RECOVERY_SECONDS)
    if _breaker_open and time.time() - _breaker_since < recovery:
        engine_log(f"[{_ws_label(ws)}] 熔断中，跳过 abnormal 重试")
        return

    try:
        from _workspace_registry import is_orch_path

        if is_orch_path(ws):
            return
    except Exception:
        # registry 不可用时仍允许业务路径启发式
        if "CCC" in str(ws) and (ws / "scripts" / "ccc-engine.py").is_file():
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
    MAX_AUTO_RETRY = 2
    _EXHAUSTED = (
        "reviewer_fail_loop_exhausted",
        "tester_fail_loop_exhausted",
        "fail_loop_exhausted",
        "重试耗尽",
        "次全部失败",
        "missing plan",
        "缺 plan",
        "缺 phases",
    )

    moved_tasks: list[str] = []

    for task in store.list_tasks("abnormal"):
        tid = task["id"]
        kind_card = str(task.get("card_kind") or "")
        if kind_card == "epic":
            continue
        # work 或有 parent 的子卡；裸 backlog 杂卡跳过
        if kind_card and kind_card not in ("work", "task"):
            if not task.get("parent_id"):
                continue

        reason = str(task.get("note") or task.get("abnormal_reason") or "")
        low = reason.lower()
        if any(m.lower() in low for m in _EXHAUSTED):
            engine_log(f"[{label}] skip auto-retry {tid}: exhausted/permanent marker")
            continue

        kind = _classify_failure(reason, tid, task.get("note") or "")
        if kind == "permanent":
            engine_log(
                f"[{label}] skip auto-retry {tid}: 不可恢复错误（permanent）"
            )
            continue

        # 须有 review_fail 包，或 reason 命中瞬态关键字（兼容旧 quarantine）
        try:
            from _failure_learning import (
                review_fail_path,
                write_review_fail_pack,
            )

            pack_p = review_fail_path(ws, tid)
            has_pack = pack_p.is_file()
        except Exception:
            has_pack = False
            write_review_fail_pack = None  # type: ignore
        transient_hit = any(kw.lower() in low for kw in _TRANSIENT_KEYWORDS)
        keyword_hit = any(kw in reason for kw in _ABNORMAL_RETRY_KEYWORDS)
        if not has_pack and not (transient_hit or keyword_hit):
            continue
        if not has_pack and write_review_fail_pack is not None:
            try:
                write_review_fail_pack(
                    ws, tid, status="abnormal", extra=reason[:1500]
                )
            except Exception as exc:
                engine_log(f"[{label}] {tid} seed review_fail: {exc}")

        updated_str = task.get("updated_at", task.get("created_at", ""))
        if not updated_str:
            continue
        try:
            updated = _dt.fromisoformat(updated_str.replace("Z", "+00:00"))
            minutes_since = (now - updated).total_seconds() / 60
        except (ValueError, TypeError):
            continue

        auto_retried = int(retry_counts.get(tid, 0) or 0)
        if auto_retried >= MAX_AUTO_RETRY:
            continue
        needed_minutes = _retry_cooldown_seconds(auto_retried) / 60
        if minutes_since < needed_minutes:
            continue

        try:
            from _task_reopen import reopen_task

            note = (
                f"auto-refeed #{auto_retried + 1}/{MAX_AUTO_RETRY}: "
                f"{reason[:80]}"
            )
            abn = ws / ".ccc/board/abnormal" / f"{tid}.jsonl"
            if abn.is_file():
                try:
                    task_json = _json.loads(abn.read_text(encoding="utf-8"))
                    if isinstance(task_json, dict):
                        task_json["note"] = note
                        task_json["updated_at"] = now_iso()
                        from _board_store import _atomic_write

                        _atomic_write(
                            abn,
                            _json.dumps(task_json, ensure_ascii=False) + "\n",
                        )
                except Exception:
                    pass
            rr = reopen_task(ws, tid, to_col="planned", wake=True)
            if not rr.get("ok"):
                raise RuntimeError(rr.get("error") or "reopen failed")
            retry_counts[tid] = auto_retried + 1
            engine_log(
                f"[{label}] auto-refeed #{auto_retried + 1}/{MAX_AUTO_RETRY}: "
                f"{tid} (冷却 {minutes_since:.0f}/{needed_minutes:.0f}min, "
                f"{kind}) → planned"
            )
            moved_tasks.append(tid)
        except Exception as e:
            _log.warning("auto-refeed failed for %s: %s", tid, e)

    try:
        from _board_store import _atomic_write

        _atomic_write(
            retry_counter_file,
            _json.dumps(retry_counts, ensure_ascii=False) + "\n",
        )
    except OSError:
        pass

    if moved_tasks:
        engine_log(f"[{label}] abnormal refeed moved={moved_tasks}")


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


def _cleanup_global_opencode_pids() -> int:
    """清理 ~/.ccc/opencode-pids 中已死进程的 .pid（防残影堆积误判占槽）。"""
    pids_dir = Path.home() / ".ccc" / "opencode-pids"
    if not pids_dir.is_dir():
        return 0
    cleaned = 0
    for f in sorted(pids_dir.glob("*.pid")):
        try:
            raw = f.read_text(encoding="utf-8", errors="replace").strip()
            pid = int(raw.split()[0]) if raw else 0
        except (ValueError, OSError):
            pid = 0
        alive = False
        if pid > 0:
            try:
                os.kill(pid, 0)
                alive = True
            except (ProcessLookupError, PermissionError, OSError):
                alive = False
        if alive:
            continue
        try:
            f.unlink()
            cleaned += 1
        except OSError:
            pass
    if cleaned:
        engine_log(f"[global] 清理 {cleaned} 个死掉的 opencode-pids")
    return cleaned


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
    *,
    testing_count: int | None = None,
    global_active_count: int | None = None,
) -> None:
    ws = ws.resolve()
    # 保留上次 memory_mb，避免常规 heartbeat 覆盖掉内存采样
    if memory_mb is None:
        prev = _read_heartbeat(ws)
        if prev and isinstance(prev.get("memory_mb"), dict):
            memory_mb = prev["memory_mb"]
    used = (
        global_active_count
        if global_active_count is not None
        else active_task_count
    )
    if testing_count is None:
        try:
            testing_count = len(_get_store(ws).list_tasks("testing"))
        except Exception:
            testing_count = 0
    hb = {
        "workspace": str(ws),
        "running": running_task_id or None,
        "active_task_count": active_task_count,
        "running_pids": running_pids or [],
        "timestamp": now_iso(),
        "dev_slots": {"used": used, "max": MAX_CONCURRENT},
        "product_inflight": len(_product_inflight),
        "testing": testing_count,
        "pending_relaunch": len(_pending_relaunch),
    }
    if memory_mb is not None:
        hb["memory_mb"] = memory_mb
    hb_file = ws / ".ccc" / "engine-heartbeat.json"
    try:
        from _board_store import _atomic_write

        _atomic_write(hb_file, json.dumps(hb, ensure_ascii=False) + "\n")
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

    if _check_last_exit_was_kill():
        engine_log("⚠️ 上次退出为强制杀死（无正常日志），可能是 OOM 或信号中断")

    def _handle_signal(signum, frame):
        global _engine_shutdown
        if _engine_shutdown:
            return
        _engine_shutdown = True
        signal_names = {
            signal.SIGTERM: "SIGTERM",
            signal.SIGINT: "SIGINT",
            signal.SIGHUP: "SIGHUP",
            signal.SIGQUIT: "SIGQUIT",
        }
        name = signal_names.get(signum, f"SIG{signum}")
        engine_log(f"收到 {name}, 优雅关闭中...")
        _write_engine_restart("shutdown", name)

    def _final_restart_log():
        _write_engine_restart("stopped", "normal_exit")

    atexit.register(_final_restart_log)

    for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP, signal.SIGQUIT):
        try:
            signal.signal(sig, _handle_signal)
        except (OSError, ValueError):
            pass

    _run_stats_server(args.port)

    try:
        engine_loop(workspaces)
    except KeyboardInterrupt:
        engine_log("Engine 关闭")
        _write_engine_restart("shutdown", "KeyboardInterrupt")
    except SystemExit as e:
        code = e.code if e.code else 0
        if code != 0:
            _write_engine_restart("stopped", f"SystemExit({code})")
        _log.debug(f"engine exiting via SystemExit({code})")
    except Exception as e:
        engine_log(f"Engine 异常退出: {e}")
        _write_engine_restart("stopped", f"exception: {type(e).__name__}: {e}")
        tb_text = _traceback.format_exc()
        engine_log(f"{tb_text[:3000]}")
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
