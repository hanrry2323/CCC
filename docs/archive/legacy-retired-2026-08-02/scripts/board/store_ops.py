"""board.store_ops — 看板 CRUD / 列操作（显式 workspace + FileBoardStore）。"""
from __future__ import annotations

from pathlib import Path

from _board_store import FileBoardStore

from board.context import get_workspace

_store_cache: dict[str, FileBoardStore] = {}


def get_store(workspace: Path | str | None = None) -> FileBoardStore:
    ws = get_workspace(workspace)
    key = str(ws)
    store = _store_cache.get(key)
    if store is None:
        store = FileBoardStore(ws)
        _store_cache[key] = store
    return store


def reset_store_cache() -> None:
    _store_cache.clear()


def create_task(
    data: dict, column: str = "backlog", workspace: Path | str | None = None
) -> bool:
    return get_store(workspace).create_task(data, column=column)


def list_tasks(column: str, workspace: Path | str | None = None) -> list[dict]:
    return get_store(workspace).list_tasks(column)


def move_task(
    task_id: str,
    from_col: str,
    to_col: str,
    workspace: Path | str | None = None,
) -> bool:
    return get_store(workspace).move_task(task_id, from_col, to_col)


def update_index(workspace: Path | str | None = None) -> dict:
    return get_store(workspace).update_index()


def quarantine(
    task_id: str, reason: str, workspace: Path | str | None = None
) -> None:
    get_store(workspace).quarantine(task_id, reason)
