"""engine.workspace — workspace 切换与 per-workspace FileBoardStore 缓存。"""
from __future__ import annotations

import sys
import threading
from pathlib import Path

from _board_store import FileBoardStore
from board.context import set_workspace

_workspace_switch_lock = threading.RLock()
_stores: dict[str, FileBoardStore] = {}

_BOARD_COLUMNS = (
    "backlog",
    "planned",
    "in_progress",
    "testing",
    "verified",
    "released",
    "abnormal",
)


def _reset_board_lazy() -> None:
    cb = sys.modules.get("ccc_board")
    if cb is not None:
        cb._reset_lazy()


def _activate_workspace(ws: Path) -> Path:
    """切换当前 workspace：env + ContextVar + lazy 缓存重置。"""
    ws = ws.resolve()
    with _workspace_switch_lock:
        set_workspace(ws)
        _reset_board_lazy()
    return ws


def _get_store(workspace: Path) -> FileBoardStore:
    key = str(workspace.resolve())
    if key not in _stores:
        _stores[key] = FileBoardStore(workspace)
    return _stores[key]


def _ws_label(ws: Path, program_dir: Path | None = None) -> str:
    program_dir = program_dir or (Path.home() / "program")
    try:
        return ws.relative_to(program_dir).as_posix()
    except ValueError:
        return ws.name


def _find_task_column(store: FileBoardStore, tid: str) -> str | None:
    for col in _BOARD_COLUMNS:
        if any(t["id"] == tid for t in store.list_tasks(col)):
            return col
    return None


def _ensure_task_in_testing(store: FileBoardStore, tid: str) -> None:
    """reviewer 可能提前挪 verified；拉回 testing 以便 tester/pytest 门禁。"""
    if _find_task_column(store, tid) == "verified":
        store.move_task(tid, "verified", "testing")
