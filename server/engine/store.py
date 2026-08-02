"""看板对接接口 + 内存实现（T3 落地前占位）。

engine 只依赖 `BoardStore` 接口做状态更新；不直接触碰 board/ 内部实现。
T3 用真实看板数据结构替换 `InMemoryBoardStore`，接口保持不变。

用法：
    from server.engine.store import InMemoryBoardStore
    from server.engine.task import Work, State

    store = InMemoryBoardStore()
    store.seed(Work(id="w1", role="开发执行体"))
    pending = store.list_work(state=State.TODO)
"""

from __future__ import annotations

from typing import Protocol

from server.engine.task import State, Work


class BoardStore(Protocol):
    """看板存储接口（T3 前最小集）。"""

    def list_work(self, state: State | None = None) -> list[Work]:
        """按状态过滤列出 work；state=None 列出全部。"""
        ...

    def save_work(self, work: Work) -> None:
        """持久化 work 状态更新。"""
        ...


class InMemoryBoardStore:
    """内存实现（进程内字典），T3 前占位。"""

    def __init__(self) -> None:
        self._items: dict[str, Work] = {}

    def seed(self, *works: Work) -> None:
        """注入初始 work（测试/演示用）。"""
        for work in works:
            self._items[work.id] = work

    def list_work(self, state: State | None = None) -> list[Work]:
        """按状态过滤；state=None 返回全部。"""
        if state is None:
            return list(self._items.values())
        return [w for w in self._items.values() if w.state is state]

    def save_work(self, work: Work) -> None:
        """按 work.id 写入。"""
        self._items[work.id] = work
