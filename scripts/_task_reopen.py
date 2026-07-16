"""_task_reopen.py — failures → 一键重开（v0.42）

从 abnormal/testing（可选 in_progress）挪回 planned/in_progress，
清理相关 pid 标记，并 ensure_engine_for_task。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from _board_store import COLUMNS, FileBoardStore

_log = logging.getLogger("ccc.task_reopen")

_REOPEN_FROM = frozenset({"abnormal", "testing", "in_progress"})
_REOPEN_TO = frozenset({"planned", "in_progress"})

_PID_SUFFIXES = (
    ".product.out",
    ".product.done",
    ".product.pid",
    ".product.exitcode",
    ".product.prompt.md",
    ".reviewer.out",
    ".reviewer.done",
    ".reviewer.pid",
    ".tester.out",
    ".tester.done",
    ".tester.pid",
    ".tester.exitcode",
    ".dev.pid",
    ".opencode.pid",
    ".done",
)


def clear_task_pid_markers(workspace: Path, task_id: str) -> list[str]:
    """清理 .ccc/pids 下与 task 相关的标记文件。"""
    pids = workspace / ".ccc" / "pids"
    cleared: list[str] = []
    if not pids.is_dir():
        return cleared
    for sfx in _PID_SUFFIXES:
        fp = pids / f"{task_id}{sfx}"
        try:
            if fp.exists():
                fp.unlink()
                cleared.append(fp.name)
        except OSError as exc:
            _log.warning("unlink %s failed: %s", fp, exc)
    # 通配残留
    for fp in pids.glob(f"{task_id}.*"):
        try:
            fp.unlink()
            if fp.name not in cleared:
                cleared.append(fp.name)
        except OSError:
            pass
    return cleared


def find_task_column(store: FileBoardStore, task_id: str) -> str | None:
    for col in COLUMNS:
        for t in store.list_tasks(col):
            if t.get("id") == task_id:
                return col
    return None


def reopen_task(
    workspace: Path,
    task_id: str,
    *,
    to_col: str = "planned",
    wake: bool = True,
) -> dict[str, Any]:
    """重开任务并可选唤醒 Engine。"""
    task_id = (task_id or "").strip()
    if not task_id:
        return {"ok": False, "error": "missing task id"}
    if to_col not in _REOPEN_TO:
        return {"ok": False, "error": f"to must be one of {sorted(_REOPEN_TO)}"}

    ws = Path(workspace)
    store = FileBoardStore(ws)
    from_col = find_task_column(store, task_id)
    if from_col is None:
        return {"ok": False, "error": f"task not found: {task_id}"}
    if from_col not in _REOPEN_FROM:
        return {
            "ok": False,
            "error": f"cannot reopen from {from_col} (allowed: {sorted(_REOPEN_FROM)})",
            "from": from_col,
        }

    cleared = clear_task_pid_markers(ws, task_id)

    if from_col != to_col:
        moved = store.move_task(task_id, from_col, to_col)
        if not moved:
            return {
                "ok": False,
                "error": f"move failed {from_col}→{to_col}",
                "from": from_col,
                "to": to_col,
            }
    else:
        moved = True

    engine_wake = None
    if wake:
        try:
            from _engine_wake import ensure_engine_for_task

            engine_wake = ensure_engine_for_task(
                reason="task_reopen", task_id=task_id, workspace=ws
            )
        except Exception as exc:
            engine_wake = {"ok": False, "error": str(exc)[:200]}

    result = {
        "ok": True,
        "id": task_id,
        "from": from_col,
        "to": to_col,
        "cleared_pids": cleared,
        "engine_wake": engine_wake,
    }
    _log.info("reopen_task %s", result)
    return result
