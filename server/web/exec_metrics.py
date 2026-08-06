"""执行体日志指标：运行时长 + OpenCode 工具/调用计数。

macOS 上普通文件的 st_ctime 会随内容写入刷新，不能当「开始时间」。
开始时间优先用 ``{work_id}.running`` 的 birthtime（否则 mtime）。
"""

from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_TOOL_RE = re.compile(r"^→\s+\S+")
_SHELL_RE = re.compile(r"^\$\s+\S")
_TURN_RE = re.compile(r"^>\s+\S")

# path → (mtime, size, stats)
_log_stats_cache: dict[str, tuple[float, int, dict[str, int]]] = {}


def strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


def _start_ts_from_stat(st: Any) -> float:
    birth = getattr(st, "st_birthtime", None)
    if birth is not None and float(birth) > 0:
        return float(birth)
    return float(st.st_mtime)


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(timespec="seconds")


def parse_log_call_counts(path: Path, *, force: bool = False) -> dict[str, int]:
    """统计 OpenCode 日志中的工具/壳/会话头次数。

    - tool_calls: ``→ …``（工具调用；看板「调用」主数字）
    - shell_calls: ``$ …``
    - model_headers: ``> …``（弱信号）
    """
    empty = {"tool_calls": 0, "shell_calls": 0, "model_headers": 0}
    try:
        st = path.stat()
    except OSError:
        return empty
    key = str(path.resolve())
    if not force:
        hit = _log_stats_cache.get(key)
        if hit is not None and hit[0] == st.st_mtime and hit[1] == st.st_size:
            return hit[2]

    tool = shell = headers = 0
    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            for raw in f:
                line = strip_ansi(raw).strip()
                if not line:
                    continue
                if _TOOL_RE.match(line):
                    tool += 1
                elif _SHELL_RE.match(line):
                    shell += 1
                elif _TURN_RE.match(line):
                    headers += 1
    except OSError:
        return empty

    stats = {"tool_calls": tool, "shell_calls": shell, "model_headers": headers}
    _log_stats_cache[key] = (st.st_mtime, st.st_size, stats)
    return stats


def running_timing(log_dir: Path, work_id: str, *, now: float | None = None) -> dict[str, Any]:
    """返回 started_at / elapsed_s / last_activity_at / log_bytes。"""
    now_ts = time.time() if now is None else now
    out: dict[str, Any] = {
        "started_at": None,
        "elapsed_s": None,
        "last_activity_at": None,
        "log_bytes": None,
    }
    wid = (work_id or "").strip()
    if not wid:
        return out

    start_ts: float | None = None
    try:
        start_ts = _start_ts_from_stat((log_dir / f"{wid}.running").stat())
    except OSError:
        pass

    log_path = log_dir / f"{wid}.log"
    try:
        lst = log_path.stat()
    except OSError:
        if start_ts is not None:
            out["elapsed_s"] = max(0, int(now_ts - start_ts))
            out["started_at"] = _iso(start_ts)
        return out

    out["log_bytes"] = int(lst.st_size)
    out["last_activity_at"] = _iso(float(lst.st_mtime))
    if start_ts is None:
        start_ts = _start_ts_from_stat(lst)
    out["started_at"] = _iso(start_ts)
    out["elapsed_s"] = max(0, int(now_ts - start_ts))
    return out


def clear_exec_metrics_cache() -> None:
    _log_stats_cache.clear()
