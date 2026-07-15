"""board.context — workspace 上下文（废除模块级 ROOT 猴子补丁）。

调用方应 set_workspace(ws) 或向 API 显式传 workspace=。
读取路径一律经 get_workspace() / board_dir()。
"""
from __future__ import annotations

import os
from contextvars import ContextVar
from pathlib import Path

_ws_var: ContextVar[Path | None] = ContextVar("ccc_board_workspace", default=None)


def set_workspace(ws: Path | str) -> Path:
    """设置当前协程/线程的 workspace（及 CCC_WORKSPACE env）。"""
    path = Path(ws).resolve()
    os.environ["CCC_WORKSPACE"] = str(path)
    _ws_var.set(path)
    return path


def clear_workspace() -> None:
    _ws_var.set(None)


def get_workspace(explicit: Path | str | None = None) -> Path:
    """解析 workspace：显式参数 > ContextVar > CCC_WORKSPACE env > Config 默认。"""
    if explicit is not None:
        return Path(explicit).resolve()
    cur = _ws_var.get()
    if cur is not None:
        return cur
    env = os.environ.get("CCC_WORKSPACE", "").strip()
    if env:
        return Path(env).resolve()
    # 延迟导入，避免 board ↔ _config 循环
    from _config import Config

    return Config().workspace.resolve()


def board_dir(ws: Path | str | None = None) -> Path:
    return get_workspace(ws) / ".ccc" / "board"


def events_dir(ws: Path | str | None = None) -> Path:
    return board_dir(ws) / "events"


def ccc_home() -> Path:
    from _config import Config

    return Config().ccc_home
