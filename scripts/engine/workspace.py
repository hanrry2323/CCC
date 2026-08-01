"""engine.workspace — workspace 切换与 per-workspace FileBoardStore 缓存。

2026-07-24 方案 2.2：废除 ccc_board.ROOT 猴子补丁全局，改用线程安全
WorkspaceContext + workspace_scope 上下文管理器。

设计：
- _activate_workspace(ws) 保留作为兼容入口（调用 _workspace_scope_legacy）
- 新代码优先用 workspace_scope(ws) 上下文管理器
- WorkspaceContext 持有 ws + store，线程本地存储（threading.local）
- get_current_workspace() 返回当前线程 ctx 或 None
"""
from __future__ import annotations

import sys
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Generator

from _board_store import FileBoardStore
from board.context import set_workspace
from _config import get_logger

_log = get_logger("engine")

_workspace_switch_lock = threading.RLock()
_stores: dict[str, FileBoardStore] = {}

# 2026-07-24 方案 2.2 步骤 1：WorkspaceContext + 线程本地存储
_thread_local = threading.local()

_BOARD_COLUMNS = (
    "backlog",
    "planned",
    "in_progress",
    "testing",
    "verified",
    "released",
    "abnormal",
)


@dataclass(frozen=True)
class WorkspaceContext:
    """线程安全 workspace 上下文（替代 ccc_board.ROOT 全局）。

    字段：
        ws: 当前 workspace 绝对路径
        store: 该 ws 对应的 FileBoardStore 实例（共享 _stores 缓存）
    """

    ws: Path
    store: FileBoardStore


def get_current_workspace() -> WorkspaceContext | None:
    """获取当前线程的 workspace 上下文（替代 ccc_board.ROOT）。

    Returns: WorkspaceContext 或 None（未进入 workspace_scope）
    """
    return getattr(_thread_local, "ctx", None)


@contextmanager
def workspace_scope(ws: Path) -> Generator[WorkspaceContext, None, None]:
    """线程级 workspace 上下文管理器。

    用法：
        with workspace_scope(ws):
            # 此 block 内 get_current_workspace() 返回 ctx
            # 且 board.context / ccc_board lazy 已切换到该 ws

    必须先走 _activate_workspace（set_workspace + reset_lazy），再挂 thread-local；
    否则仅设 ctx 不会切换 ContextVar，跨仓会污染。
    """
    resolved = _activate_workspace(ws)
    store = _get_store(resolved)
    ctx = WorkspaceContext(ws=resolved, store=store)
    prev = getattr(_thread_local, "ctx", None)
    _thread_local.ctx = ctx
    try:
        yield ctx
    finally:
        _thread_local.ctx = prev


def _reset_board_lazy() -> None:
    cb = sys.modules.get("ccc_board")
    if cb is not None:
        cb._reset_lazy()


def _activate_workspace(ws: Path) -> Path:
    """切换当前 workspace：env + ContextVar + lazy 缓存重置。

    2026-07-24 方案 2.2：兼容入口仍保留，调用 set_workspace（board.context 内已
    用 ContextVar 隔离）。新代码优先用 workspace_scope(ws) 上下文管理器。
    """
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
    """Phase 1.2: 用 find_task 路径探测（O(cols) stat）替代 list_tasks 全扫。"""
    col, _task = store.find_task(tid)
    return col


def _ensure_task_in_testing(store: FileBoardStore, tid: str) -> None:
    """兜底：异常情况下 task 若已到 verified，拉回 testing 以便 tester/pytest 门禁。

    verify 一扇门后 reviewer/tester 不再直接挪 verified；本函数作为防御，
    防遗留路径（如手动 CLI reviewer）把 task 提前推到 verified。
    """
    if _find_task_column(store, tid) != "verified":
        return
    ok = store.move_task(tid, "verified", "testing")
    if not ok:
        _log.warning(
            "pullback verified→testing rejected for %s (column transitions missing?)",
            tid,
        )
