"""engine/restart_log.py — Engine 重启日志 + 上次退出检测。

fix-planning-2026-07-24 ccc-engine.py 拆分布局：自包含模块，零内部依赖。
原 ccc-engine.py:382-434 迁移到此处。
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any

_log = logging.getLogger("ccc.engine.restart_log")

ENGINE_START_TS = time.time()
RESTART_LOG_PATH = Path.home() / ".ccc" / "logs" / "engine-restarts.jsonl"
ENGINE_VERSION = "unknown"
try:
    ENGINE_VERSION = (Path(__file__).resolve().parent.parent.parent / "VERSION").read_text(encoding="utf-8").strip()
except OSError:
    pass


def _now_iso() -> str:
    from _utils import now_iso_utc

    return now_iso_utc()


def write_restart(
    status: str,
    reason: str | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    """写入结构化重启日志到 ~/.ccc/logs/engine-restarts.jsonl."""
    uptime = max(0.001, time.time() - ENGINE_START_TS)
    entry: dict[str, Any] = {
        "ts": _now_iso(),
        "pid": os.getpid(),
        "uptime_sec": round(uptime, 3),
        "status": status,
        "reason": reason,
        "source": "engine",
        "version": ENGINE_VERSION,
    }
    if extra:
        entry.update(extra)
    try:
        from _jsonl_rotate import append_jsonl

        append_jsonl(RESTART_LOG_PATH, entry)
    except ImportError:
        try:
            RESTART_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            with RESTART_LOG_PATH.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError:
            pass


def check_last_exit_was_kill() -> bool:
    """检查上次退出是否为强制杀死（无正常日志）。返回 True=上次被强杀。"""
    if not RESTART_LOG_PATH.exists():
        return False
    try:
        lines = RESTART_LOG_PATH.read_text(encoding="utf-8").splitlines()
    except OSError:
        return False
    for ln in reversed(lines):
        ln = ln.strip()
        if not ln:
            continue
        try:
            obj = json.loads(ln)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        return obj.get("status", "") == "started"
    return False
