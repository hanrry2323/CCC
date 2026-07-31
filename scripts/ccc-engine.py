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

# board roles + ccc_board → engine.compat_board.attach (see _attach_engine_impls)
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
from engine import observability as _engine_observability  # noqa: E402
from engine import health as _engine_health  # noqa: E402
from engine import heartbeat as _engine_heartbeat  # noqa: E402
from engine import cli as _engine_cli  # noqa: E402
from engine import compat_board as _engine_compat_board  # noqa: E402


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


# Stats HTTP 共享状态（须在 attach 前就绪，供 _stats_server_impl 使用）
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


def _attach_engine_impls() -> None:
    """Exec extracted impls into this module (shared cfg / engine_log / slots)."""
    g = globals()
    _engine_compat_board.attach(g)
    _engine_observability.attach(g)
    _engine_health.attach(g)
    _engine_heartbeat.attach(g)
    _engine_results.attach(g)
    _engine_backlog.attach(g)
    _engine_launch.attach(g)
    _engine_recover.attach(g)
    _engine_loop.attach(g)
    _engine_stats.attach(g)
    _engine_cli.attach(g)


_attach_engine_impls()


if __name__ == "__main__":
    main()
