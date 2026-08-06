"""执行体日志指标：运行时长 + 多阶段工具/调用计数。

macOS 上普通文件的 st_ctime 会随内容写入刷新，不能当「开始时间」。
开始时间优先用 ``{work_id}.running`` 的 birthtime（否则 mtime）。

调用数跨「开发 → 机审 → 回写」跟卡走：汇总 ``{id}.log`` / ``{id}.runN.log`` /
``{id}.audit.log``，并用 ``{id}.metrics.json`` 高水位防日志被覆盖后归零。
"""

from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
# OpenCode：→ Read / → Write；允许 ANSI 剥掉后匹配
_TOOL_RE = re.compile(r"^→\s+\S+")
_SHELL_RE = re.compile(r"^\$\s+\S")
_TURN_RE = re.compile(r"^>\s+\S")
# Claude Code 文本痕迹（机审席常见）：弱信号，计入 tool_calls
_CLAUDE_TOOL_RE = re.compile(
    r"^(?:I'll |I'|\*\*Reading|\*\*Writing|Reading `|Writing `|Using tool|tool_use)",
    re.IGNORECASE,
)

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
    """统计单份执行日志中的工具/壳/会话头次数。

    - tool_calls: OpenCode ``→ …``，兼计 Claude 弱工具痕迹
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
                if line.startswith("[ccc.engine]"):
                    continue
                if _TOOL_RE.match(line):
                    tool += 1
                elif _SHELL_RE.match(line):
                    shell += 1
                elif _TURN_RE.match(line):
                    headers += 1
                elif _CLAUDE_TOOL_RE.match(line):
                    tool += 1
    except OSError:
        return empty

    stats = {"tool_calls": tool, "shell_calls": shell, "model_headers": headers}
    _log_stats_cache[key] = (st.st_mtime, st.st_size, stats)
    return stats


def list_work_log_paths(log_dir: Path, work_id: str) -> list[Path]:
    """某卡全部阶段日志：``.log`` / ``.runN.log`` / ``.audit.log`` / ``.dev.log``。"""
    wid = (work_id or "").strip()
    if not wid or not log_dir.is_dir():
        return []
    out: list[Path] = []
    try:
        for p in log_dir.iterdir():
            if not p.is_file() or not p.name.endswith(".log"):
                continue
            name = p.name
            if not name.startswith(wid):
                continue
            rest = name[len(wid) :]
            # ccc005.log / ccc005.run1.log / ccc005.audit.log — 排除 ccc0050.log
            if rest == ".log" or rest.startswith(".run") or rest.startswith(".audit") or rest.startswith(".dev"):
                out.append(p)
    except OSError:
        return []
    return sorted(out, key=lambda x: x.name)


def _metrics_sidecar_path(log_dir: Path, work_id: str) -> Path:
    return log_dir / f"{work_id}.metrics.json"


def load_metrics_snapshot(log_dir: Path, work_id: str) -> dict[str, int]:
    path = _metrics_sidecar_path(log_dir, work_id)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return {"tool_calls": 0, "shell_calls": 0, "model_headers": 0}
    return {
        "tool_calls": int(data.get("tool_calls") or 0),
        "shell_calls": int(data.get("shell_calls") or 0),
        "model_headers": int(data.get("model_headers") or 0),
    }


def save_metrics_snapshot(log_dir: Path, work_id: str, stats: dict[str, int]) -> None:
    path = _metrics_sidecar_path(log_dir, work_id)
    payload = {
        "work_id": work_id,
        "tool_calls": int(stats.get("tool_calls") or 0),
        "shell_calls": int(stats.get("shell_calls") or 0),
        "model_headers": int(stats.get("model_headers") or 0),
        "updated_at": _iso(time.time()),
    }
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=0) + "\n", encoding="utf-8")
        tmp.replace(path)
    except OSError:
        pass


def parse_work_call_counts(log_dir: Path, work_id: str, *, force: bool = False) -> dict[str, int]:
    """汇总该卡全部阶段日志调用数，并与 sidecar 取高水位（只增不减）。"""
    totals = {"tool_calls": 0, "shell_calls": 0, "model_headers": 0}
    paths = list_work_log_paths(log_dir, work_id)
    for p in paths:
        part = parse_log_call_counts(p, force=force)
        for k in totals:
            totals[k] += int(part.get(k) or 0)

    snap = load_metrics_snapshot(log_dir, work_id)
    merged = {
        "tool_calls": max(totals["tool_calls"], snap["tool_calls"]),
        "shell_calls": max(totals["shell_calls"], snap["shell_calls"]),
        "model_headers": max(totals["model_headers"], snap["model_headers"]),
    }
    # 有日志进展或高于旧快照时落盘，保证进机审/回写后数字仍在且可继续涨
    if paths or merged["tool_calls"] > 0 or merged["shell_calls"] > 0:
        if merged["tool_calls"] >= snap["tool_calls"] and (
            merged["tool_calls"] > snap["tool_calls"]
            or merged["shell_calls"] > snap["shell_calls"]
            or not _metrics_sidecar_path(log_dir, work_id).is_file()
        ):
            save_metrics_snapshot(log_dir, work_id, merged)
    return merged


def running_timing(log_dir: Path, work_id: str, *, now: float | None = None) -> dict[str, Any]:
    """返回 started_at / elapsed_s / last_activity_at / log_bytes / live。

    - 有 ``{id}.running`` 或 ``{id}-audit.running``：直播时长（now − 最早 start）。
    - 仅有日志（已结束进机审/已回写等）：冻结为最晚 log.mtime − start。
    """
    now_ts = time.time() if now is None else now
    out: dict[str, Any] = {
        "started_at": None,
        "elapsed_s": None,
        "last_activity_at": None,
        "log_bytes": None,
        "live": False,
    }
    wid = (work_id or "").strip()
    if not wid:
        return out

    start_ts: float | None = None
    live = False
    for marker_name in (f"{wid}.running", f"{wid}-audit.running"):
        try:
            ts = _start_ts_from_stat((log_dir / marker_name).stat())
        except OSError:
            continue
        live = True
        if start_ts is None or ts < start_ts:
            start_ts = ts

    logs = list_work_log_paths(log_dir, wid)
    log_bytes = 0
    last_mtime: float | None = None
    earliest_log: float | None = None
    for p in logs:
        try:
            lst = p.stat()
        except OSError:
            continue
        log_bytes += int(lst.st_size)
        mt = float(lst.st_mtime)
        if last_mtime is None or mt > last_mtime:
            last_mtime = mt
        birth = _start_ts_from_stat(lst)
        if earliest_log is None or birth < earliest_log:
            earliest_log = birth

    if not logs and start_ts is None:
        # 仅有 sidecar：仍可展示调用，但无时长
        return out

    if start_ts is None:
        start_ts = earliest_log

    if start_ts is None:
        return out

    out["started_at"] = _iso(start_ts)
    out["live"] = live
    if log_bytes:
        out["log_bytes"] = log_bytes
    if last_mtime is not None:
        out["last_activity_at"] = _iso(last_mtime)

    if live:
        out["elapsed_s"] = max(0, int(now_ts - start_ts))
    elif last_mtime is not None:
        out["elapsed_s"] = max(0, int(last_mtime - start_ts))
    else:
        out["elapsed_s"] = max(0, int(now_ts - start_ts))
    return out


def card_wants_runtime(card: dict[str, Any]) -> bool:
    """执行过/在跑/待审的卡：指标应挂在卡上，随列移动。"""
    from server.board.models import base_state

    st = base_state(str(card.get("state") or ""))
    if st in ("执行中", "已回写", "打回", "已关闭"):
        return True
    col = str(card.get("board_column") or "")
    return col == "机审"


def enrich_card_runtime(
    row: dict[str, Any],
    log_dir: Path | None,
    *,
    force: bool = False,
) -> None:
    """把调用次数 / 时长 / dirty·行变更挂到卡片 dict（原地改）。"""
    from server.web.worktree_dirty import get_worktree_metrics

    wid = str(row.get("id") or "").strip()
    if not wid:
        return

    metrics = get_worktree_metrics(wid, force=force)
    for key in (
        "dirty_files",
        "lines_insert",
        "lines_delete",
        "branch_insert",
        "branch_delete",
    ):
        val = metrics.get(key)
        if val is not None:
            row[key] = val

    if log_dir is None:
        return

    timing = running_timing(log_dir, wid)
    if timing.get("elapsed_s") is not None:
        row["elapsed_s"] = timing["elapsed_s"]
    if timing.get("started_at"):
        row["started_at"] = timing["started_at"]
    if timing.get("last_activity_at"):
        row["last_activity_at"] = timing["last_activity_at"]
    if timing.get("log_bytes") is not None:
        row["log_bytes"] = timing["log_bytes"]
    row["metrics_live"] = bool(timing.get("live"))

    counts = parse_work_call_counts(log_dir, wid, force=force)
    # 有过执行痕迹就挂数字（含 0），跟卡走；纯无日志无 sidecar 不挂
    has_trace = (
        bool(list_work_log_paths(log_dir, wid))
        or _metrics_sidecar_path(log_dir, wid).is_file()
        or timing.get("live")
    )
    if has_trace:
        row["tool_calls"] = counts["tool_calls"]
        row["shell_calls"] = counts["shell_calls"]


def clear_exec_metrics_cache() -> None:
    _log_stats_cache.clear()
