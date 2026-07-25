"""engine/tick.py — Engine 主循环 tick 心跳 + watchdog 闭环。

fix-planning-2026-07-24 ccc-engine.py 拆分布局：自包含模块。
原 ccc-engine.py:436-553 迁移到此处。
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from pathlib import Path

_log = logging.getLogger("ccc.engine.tick")

_TICK_WATCHDOG_STALE_S = float(os.environ.get("CCC_ENGINE_TICK_STALE_S", "180") or "180")
_TICK_WATCHDOG_POLL_S = 30.0
_WATCHDOG_GRACE_S = float(os.environ.get("CCC_ENGINE_TICK_HARD_EXIT_GRACE_S", "30") or "30")

_last_tick_mono: float = 0.0
_engine_shutdown_ref: threading.Event | None = None


def _loop_heartbeat_path() -> Path:
    return Path.home() / ".ccc" / "engine-loop-heartbeat.json"


def _utils_now_iso():
    from _utils import now_iso_utc

    return now_iso_utc()


def mark_tick() -> None:
    """记录主循环 tick 进度。"""
    global _last_tick_mono
    _last_tick_mono = time.monotonic()
    _LOOP_HB_WRITE_MIN_S = float(os.environ.get("CCC_ENGINE_LOOP_HB_WRITE_S", "30"))
    if not hasattr(mark_tick, "_last_hb_write_mono"):
        mark_tick._last_hb_write_mono = 0.0  # type: ignore[attr-defined]
    if (_last_tick_mono - mark_tick._last_hb_write_mono) < _LOOP_HB_WRITE_MIN_S:  # type: ignore[attr-defined]
        return
    mark_tick._last_hb_write_mono = _last_tick_mono  # type: ignore[attr-defined]
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
    except OSError as exc:
        # loop heartbeat 写失败不应阻塞 Engine 主循环
        _log.debug("tick loop heartbeat write: %s", exc)


def start_watchdog(shutdown_event: threading.Event | None = None) -> None:
    """若主循环超过 stale 阈值无 tick，grace → hard exit。"""
    global _last_tick_mono, _engine_shutdown_ref
    _last_tick_mono = time.monotonic()
    _engine_shutdown_ref = shutdown_event

    def _watch() -> None:
        from engine.restart_log import write_restart

        while True:
            if _engine_shutdown_ref is not None and _engine_shutdown_ref.is_set():
                return
            time.sleep(_TICK_WATCHDOG_POLL_S)
            if _engine_shutdown_ref is not None and _engine_shutdown_ref.is_set():
                return
            age = time.monotonic() - _last_tick_mono
            if age <= _TICK_WATCHDOG_STALE_S:
                continue
            grace_deadline = time.monotonic() + _WATCHDOG_GRACE_S
            _log.warning(
                "[watchdog] no tick for %.0fs (>%.0fs) — grace %.0fs before hard exit",
                age,
                _TICK_WATCHDOG_STALE_S,
                _WATCHDOG_GRACE_S,
            )
            while time.monotonic() < grace_deadline:
                if _engine_shutdown_ref is not None and _engine_shutdown_ref.is_set():
                    _log.warning("[watchdog] main loop signaled exit during grace — cancel hard exit")
                    return
                tick_age = time.monotonic() - _last_tick_mono
                if tick_age <= _TICK_WATCHDOG_STALE_S:
                    _log.warning(
                        "[watchdog] tick recovered during grace (age %.1fs) — cancel hard exit",
                        tick_age,
                    )
                    return
                time.sleep(0.5)
            try:
                write_restart(
                    "stopped",
                    reason="tick_watchdog_hard_exit",
                    extra={"stale_sec": round(age, 1), "grace_s": _WATCHDOG_GRACE_S},
                )
            except Exception as exc:
                _log.debug("tick watchdog restart_log write: %s", exc)
            try:
                from _jsonl_rotate import append_jsonl

                append_jsonl(
                    Path.home() / ".ccc" / "stats" / "engine-events.jsonl",
                    {
                        "ts": _utils_now_iso(),
                        "kind": "engine_hard_exit_watchdog",
                        "stale_sec": round(age, 1),
                        "grace_s": _WATCHDOG_GRACE_S,
                        "stale_threshold_s": _TICK_WATCHDOG_STALE_S,
                        "pid": os.getpid(),
                    },
                )
            except Exception as exc:
                # watchdog 写日志失败不应阻止 hard exit
                _log.debug("tick watchdog hard_exit log write: %s", exc)
            os._exit(0)

    t = threading.Thread(target=_watch, daemon=True)
    t.start()
