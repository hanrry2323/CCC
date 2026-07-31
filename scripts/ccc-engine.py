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
from typing import Any
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

from _stats_aggregator import aggregate_stats, load_summary
from _cost_telemetry import check_abnormal_traffic as _check_abnormal_traffic
from _capability_evolver import record_failure_pattern as _record_failure_pattern

_log = get_logger("engine")

_engine_shutdown = False


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
    workspace_scope,
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
from engine.restart_log import (  # noqa: E402
    ENGINE_VERSION as _ENGINE_VERSION,
    ENGINE_START_TS as _engine_start_ts,
    RESTART_LOG_PATH as _RESTART_LOG_PATH,
    write_restart as _write_engine_restart,
    check_last_exit_was_kill as _check_last_exit_was_kill,
)
from engine.tick import (  # noqa: E402
    mark_tick as _mark_engine_tick,
    start_watchdog as _start_tick_watchdog,
)
from engine.process import (  # noqa: E402
    kill_process_tree as _kill_process_tree,
    kill_pid as _kill_pid,
    graceful_kill_active_tasks as _graceful_kill_active_tasks,
    collect_grandchildren as _collect_grandchildren,
    get_proc_rss_mb as _get_proc_rss_mb,
    cleanup_zombie_pid_refs as _cleanup_zombie_pid_refs,
    cleanup_global_opencode_pids as _cleanup_global_opencode_pids,
    check_process_memory as _check_process_memory,
)
from engine.upstream import (  # noqa: E402
    get_relay_url as _get_relay_url,
    is_upstream_healthy as _is_upstream_healthy,
)
from engine.notify import (  # noqa: E402
    ccc_notify as _ccc_notify,
    NOTIFY_SCRIPT as _NOTIFY_SCRIPT,
)
from engine.discover import (  # noqa: E402
    discover_workspaces as _discover_workspaces,
    queue_has_consumable_work as _queue_has_consumable_work,
    may_invent as _may_invent,
    rediscover_workspaces as _rediscover_workspaces,
    apply_wake_payload as _apply_wake_payload,
    apply_dispatch_wake as _apply_dispatch_wake,
    prioritize_wake_workspace as _prioritize_wake_workspace,
    sleep_until_wake as _sleep_until_wake,
    wait_tick as _wait_tick,
)
from engine.task_registry import (  # noqa: E402
    task_key as _task_key,
    can_accept_dev as _can_accept_dev,
    enqueue_pending_relaunch as _enqueue_pending_relaunch,
    git_head_for_task as _git_head_for_task,
    relaunch_backoff_key as _relaunch_backoff_key,
    relaunch_allowed as _relaunch_allowed,
    note_relaunch as _note_relaunch,
    product_inflight_for_ws as _product_inflight_for_ws,
    can_launch_product as _can_launch_product,
    rebuild_product_inflight as _rebuild_product_inflight,
    product_async_markers as _product_async_markers,
    drop_product_inflight as _drop_product_inflight,
    finalize_or_gc_product_key as _finalize_or_gc_product_key,
    gc_product_inflight as _gc_product_inflight,
    _pending_relaunch as _pending_relaunch,
    _relaunch_meta as _relaunch_meta,
    _product_inflight as _product_inflight,
    MAX_CONCURRENT as MAX_CONCURRENT,
    MAX_PRODUCT_INFLIGHT as MAX_PRODUCT_INFLIGHT,
    MAX_PRODUCT_PER_WS as MAX_PRODUCT_PER_WS,
)

# 最小可跑通重构：大段实现迁入 engine/*_impl.py（attach 见 main 前）
from engine import results as _engine_results  # noqa: E402
from engine import backlog as _engine_backlog  # noqa: E402
from engine import launch as _engine_launch  # noqa: E402
from engine import loop as _engine_loop  # noqa: E402
from engine import recover as _engine_recover  # noqa: E402
from engine import stats_server as _engine_stats  # noqa: E402


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


# v0.35: degraded mode — 引擎自我保护
_degraded_mode = False
_degraded_since: float | None = None
_DEGRADED_QUARANTINE_THRESHOLD = 10  # 30min 内 quarantine > 此值 → degraded
_DEGRADED_FAIL_THRESHOLD = 10  # 30min 内 product_fail > 此值 → degraded
# v0.53+: 人下达 task_dispatch 可绕过 degraded intake（防 pending epic 饿死）
_intake_bypass_degraded = False
_intake_bypass_ticks_left = 0
_wake_priority_workspace: Path | None = None
_INTAKE_BYPASS_TICKS = 12  # ~2min @10s tick — enough for product launch
_DEGRADED_RECOVERY_SECONDS = 600  # 10min 无异常 → 自动恢复

# v0.36: 熔断 — upstream 不可用时暂停 abnormal 自动重试
_breaker_open: bool = False
_breaker_since: float = 0.0
_BREAKER_RECOVERY_SECONDS = 120

# v0.36: abnormal 重试（指数退避）
_RETRY_BASE_INTERVAL = 120  # 2min
_RETRY_MAX_INTERVAL = 3600  # 1h
_RETRY_BACKOFF_FACTOR = 2.0
_ABNORMAL_RETRY_KEYWORDS = [
    "重试",
    "all_failed",
    "失败",
    "failed",
    "超时",
    "timeout",
    "unhealthy",
    "不可用",
    "quarantine",
    "异常",
    "exception",
    "stale",
    "stalled",
    "exit code",
    "opencode",
    "product_role",
    "dev_role",
    "reviewer",
    "tester",
]
_TRANSIENT_KEYWORDS = [
    "timeout",
    "超时",
    "network",
    "网络",
    "upstream",
    "hang",
    "hung",
    "连接",
    "unavailable",
    "不可用",
    "econnreset",
    "temporary",
    "transient",
    "unhealthy",
    "opencode",
    "rate limit",
    "429",
    "502",
    "503",
    "504",
    "connection",
    "reset by peer",
]
_PERMANENT_KEYWORDS = [
    "syntaxerror",
    "importerror",
    "typeerror",
    "nameerror",
    "indentationerror",
    "modulenotfounderror",
    "attributeerror",
    "语法错误",
    "编码错误",
    "invalid syntax",
    "cannot import",
    "compile failed",
    "assertionerror",
]

# v0.36: 内存阈值（MB）— 与 Config 默认对齐；cfg 覆盖优先
_MEM_WARN_MB = 400
_MEM_DEGRADED_MB = 800
_MEM_KILL_MB = 1500


# v0.28.2: Phase 并行调度（plan: engine-phase-parallel-dispatch）
PHASE_PARALLEL_MAX_WORKERS = 2


def _set_parallel_disabled(val: bool) -> None:
    """Set the global PHASE_PARALLEL_DISABLED toggle (module-level)."""
    global PHASE_PARALLEL_DISABLED
    PHASE_PARALLEL_DISABLED = val


PHASE_PARALLEL_DISABLED = False  # 故障 fallback 时设为 True（仅当次 Engine tick）

# Per-task 并行 phase 状态：
#   task_key -> {
#     "groups": [[phase_num, ...], ...],   # 待执行的 group 列表（每组内并行）
#     "current_group": [phase_num, ...] | None,  # 当前正在跑的 group
#     "phase_meta": {phase_num: {subid, pid, started_at}}
#   }
_parallel_phases: dict[str, dict] = {}


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
    """写一条结构化事件到 .ccc/stats/events.jsonl。

    修复 stability-audit-2026-07-24 类别②：事件写失败不再完全静默，
    至少 log.warning 让 ops 看到（仍不阻塞业务）。
    """
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
        except OSError as exc:
            _log.warning(
                "[stats] events.jsonl plain-append failed for %s event=%s: %s",
                sf,
                event,
                exc,
            )
    except OSError as exc:
        _log.warning(
            "[stats] events.jsonl append_jsonl failed for %s event=%s: %s",
            sf, event, exc,
        )
    # 跨仓耗时 SSOT（小卡分钟数统计用）
    if event in ("opencode_start", "opencode_done"):
        try:
            gdir = Path.home() / ".ccc" / "stats"
            gdir.mkdir(parents=True, exist_ok=True)
            from _jsonl_rotate import append_jsonl as _aj

            _aj(gdir / "opencode-timings.jsonl", record)
        except Exception:
            try:
                with (Path.home() / ".ccc" / "stats" / "opencode-timings.jsonl").open("a", encoding="utf-8") as f:
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
            except OSError as exc:
                _log.warning("[stats] opencode-timings.jsonl write failed: %s", exc)


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
    except Exception as exc:
        _log.warning("[heartbeat] write failed: %s", exc)


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
        except (OSError, ValueError, TypeError) as exc:
            engine_log("[task_result] result.json parse failed for %s: %s", tid, str(exc))
    wall_s = _wall_seconds_from_started(started_at)
    # result dict 兜底（salvage / check_complete 可能未落盘 result.json）
    if duration_s is None and isinstance(result, dict):
        try:
            if result.get("duration_s") is not None:
                duration_s = float(result["duration_s"])
        except (TypeError, ValueError) as exc:
            engine_log("[task_result] duration_s fallback parse failed for %s: %s", tid, str(exc))
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


# KPI R4: short-path fail budget — ban 1Hz planned↔in_progress storm
_SHORT_PATH_FAIL_MAX = 3
_ACCEPTANCE_FAIL_MAX = 2


# --- extracted 539-1051; see engine.*.attach() ---

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
                        if isinstance(w, dict) and w.get("type") == "phase_graph_regen" and w.get("task_id") == tid
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
                fd, tmp_name = tempfile.mkstemp(dir=str(_wf.parent), prefix=".warnings-", suffix=".tmp")
                try:
                    with os.fdopen(fd, "w", encoding="utf-8") as tf:
                        tf.write(payload)
                        tf.flush()
                        os.fsync(tf.fileno())
                    os.replace(tmp_name, str(_wf))
                except Exception:
                    try:
                        os.unlink(tmp_name)
                    except OSError as exc:
                        _log.debug("[plan_write] tmp unlink %s: %s", tmp_name, exc)
                    raise
            finally:
                fcntl.flock(lock_f.fileno(), fcntl.LOCK_UN)
    except Exception as exc:
        _log.warning("[regen] _record_regen %s failed: %s", tid, str(exc))


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
    except OSError as exc:
        _log.debug("[recent_events] read %s: %s", ev_file, exc)
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
    # CCC Relay 2026-07-25:fail-open — relay 不可达不 block,只警告;任务走直连
    recovery = getattr(cfg, "breaker_recovery_seconds", _BREAKER_RECOVERY_SECONDS)
    if not _is_upstream_healthy():
        if not _breaker_open:
            _breaker_open = True
            _breaker_since = time.time()
            engine_log(
                "[breaker] upstream(relay) 不可用 → 开熔断并切 fail-open 直连,"
                " 任务继续跑不 block(2026-07-25 fail-open 共识)"
            )
            _ccc_notify("CCC", "engine upstream 不可用,已切 fail-open 直连")
    elif _breaker_open:
        elapsed = time.time() - _breaker_since
        if elapsed >= recovery:
            _breaker_open = False
            _breaker_since = 0.0
            engine_log(f"[breaker] relay 已恢复（熔断 {elapsed:.0f}s）→ 关熔断,回切")

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
            f"[degraded] 30min 异常过高 (q={q_count}, f={f_count}, ok={_any_success}), 进入 degraded 模式 — 暂停 intake"
        )
        _ccc_notify("CCC", "engine 进入 degraded 模式（异常率过高，暂停 intake）")

    if _degraded_mode and not should_degrade:
        elapsed = time.time() - (_degraded_since or time.time())
        if elapsed > _DEGRADED_RECOVERY_SECONDS:
            _degraded_mode = False
            _degraded_since = None
            engine_log(f"[degraded] 异常率已恢复 (q={q_count}, f={f_count}), 退出 degraded 模式")
            _ccc_notify("CCC", "engine 退出 degraded 模式（指标恢复正常）")


# --- extracted 1224-1363; see engine.*.attach() ---

# --- extracted 1365-1701; see engine.*.attach() ---

# --- extracted 1703-2336; see engine.*.attach() ---

# --- extracted 2338-2795; see engine.*.attach() ---
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


# --- extracted 2829-3221; see engine.*.attach() ---

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
        except (ValueError, OSError) as exc:
            _log.debug("[collect_pids] read %s: %s", f, exc)
    return result


def _read_heartbeat(ws: Path) -> dict | None:
    hb_file = ws / ".ccc" / "engine-heartbeat.json"
    if hb_file.exists():
        try:
            return json.loads(hb_file.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            _log.debug("[read_engine_heartbeat] %s: %s", hb_file, exc)
    return None


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
    used = global_active_count if global_active_count is not None else active_task_count
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


def _attach_engine_impls() -> None:
    """Exec extracted impls into this module (shared cfg / engine_log / slots)."""
    # Use globals() — importlib 加载时 sys.modules[__name__] 可能尚未登记
    g = globals()
    _engine_results.attach(g)
    _engine_backlog.attach(g)
    _engine_launch.attach(g)
    _engine_recover.attach(g)
    _engine_loop.attach(g)
    _engine_stats.attach(g)


_attach_engine_impls()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="CCC Engine — multi-workspace scheduler")
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
        except (OSError, ValueError) as exc:
            _log.warning("[signal_register] %s: %s", sig, exc)

    _run_stats_server(args.port)

    try:
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
    finally:
        # 修复 stability-audit-2026-07-24 类别③：graceful shutdown 杀子进程组
        _engine_shutdown = True
        n = _graceful_kill_active_tasks()
        if n:
            engine_log(f"[shutdown] killed {n} active task subprocess(es)")
    engine_log("Engine 终止")


# ── Stats HTTP Endpoint（plan: engine-stats-endpoint） ──

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


# --- extracted 3417-3506; see engine.*.attach() ---
