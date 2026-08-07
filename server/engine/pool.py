"""Engine 派发池：收割 + 补位（跨心跳全局在途槽）。

持续模式每轮只填空闲槽、不 join 全员；``--once`` 可 drain 后再退出。
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from server.engine.store import BoardStore
from server.engine.task import State

Outcome = dict[str, int]  # collected / timed_out / failed


class DispatchPool:
    """进程内在途线程池（work_id → Thread）。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._threads: dict[str, threading.Thread] = {}
        self._outcomes: dict[str, Outcome] = {}

    def reset(self) -> None:
        """测试用：丢弃登记（调用方须确保无线程在跑）。"""
        with self._lock:
            self._threads.clear()
            self._outcomes.clear()

    def alive_ids(self) -> set[str]:
        with self._lock:
            return {wid for wid, t in self._threads.items() if t.is_alive()}

    def occupancy(self, store: BoardStore, log_dir: Path) -> int:
        """池内存活 id ∪（执行中且有 ``{id}.running``）。manual 无标记不占槽。"""
        ids = self.alive_ids()
        for w in store.list_work(state=State.RUNNING):
            if (log_dir / f"{w.id}.running").is_file():
                ids.add(w.id)
        return len(ids)

    def free_slots(self, max_n: int, store: BoardStore, log_dir: Path) -> int:
        return max(0, int(max_n) - self.occupancy(store, log_dir))

    def submit(self, work_id: str, fn: Callable[[], Outcome]) -> None:
        """启动 worker 线程；调用方须已确认有空位且未重复派发。"""

        def _wrapper() -> None:
            outcome: Outcome = {"collected": 0, "timed_out": 0}
            try:
                result = fn()
                if isinstance(result, dict):
                    outcome = {
                        "collected": int(result.get("collected", 0)),
                        "timed_out": int(result.get("timed_out", 0)),
                    }
            finally:
                with self._lock:
                    self._outcomes[work_id] = outcome

        thread = threading.Thread(
            target=_wrapper,
            name=f"ccc-dispatch-{work_id}",
            daemon=True,
        )
        with self._lock:
            existing = self._threads.get(work_id)
            if existing is not None and existing.is_alive():
                raise RuntimeError(f"work already in flight: {work_id}")
            self._threads[work_id] = thread
        thread.start()

    def reap(self) -> Outcome:
        """回收已结束线程，返回本轮累计 collected / timed_out / failed。"""
        collected = 0
        timed_out = 0
        failed = 0
        with self._lock:
            finished = [wid for wid, t in self._threads.items() if not t.is_alive()]
            for wid in finished:
                del self._threads[wid]
                out = self._outcomes.pop(wid, None) or {}
                collected += int(out.get("collected", 0))
                timed_out += int(out.get("timed_out", 0))
                failed += int(out.get("failed", 0))
        return {"collected": collected, "timed_out": timed_out, "failed": failed}

    def drain(self, join_slice: float = 0.5) -> Outcome:
        """阻塞直到池空，返回期间 reap 累计。"""
        totals: Outcome = {"collected": 0, "timed_out": 0, "failed": 0}
        while True:
            with self._lock:
                alive = [(wid, t) for wid, t in self._threads.items() if t.is_alive()]
            if not alive:
                got = self.reap()
                totals["collected"] += got["collected"]
                totals["timed_out"] += got["timed_out"]
                totals["failed"] += got["failed"]
                return totals
            for _wid, t in alive:
                t.join(timeout=join_slice)
            got = self.reap()
            totals["collected"] += got["collected"]
            totals["timed_out"] += got["timed_out"]
            totals["failed"] += got["failed"]


_POOL = DispatchPool()
_AUDIT_POOL = DispatchPool()


def get_dispatch_pool() -> DispatchPool:
    return _POOL


def get_audit_pool() -> DispatchPool:
    return _AUDIT_POOL


def reset_dispatch_pool() -> None:
    """测试夹具：清空全局执行池与机审池。"""
    _POOL.reset()
    _AUDIT_POOL.reset()
