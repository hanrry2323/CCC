"""engine.slots — 跨进程 opencode 槽位（对接 board.slots）。"""
from __future__ import annotations

import os
import time
from pathlib import Path

_GLOBAL_OPENCODE_MAX = 6

# v0.51.0 P1-8: OpenCodeCountProxy TTL 缓存窗口（秒）。
# 每次 dunder 调用原本都触发 board.slots.snapshot() 读文件，Engine 主循环
# 热路径（_GLOBAL_OPENCODE_COUNT 字符串化）频繁命中会拖累 I/O。缓存窗口
# 默认 3 秒；显式 acquire/release 后会调用 invalidate() 立即失效。
try:
    _SLOT_CACHE_TTL = max(0.0, float(os.environ.get("CCC_SLOT_CACHE_TTL", "3") or 3))
except (TypeError, ValueError):
    _SLOT_CACHE_TTL = 3.0


def opencode_slots_path() -> Path:
    from board.slots import default_state_path
    return default_state_path()


def global_opencode_count() -> int:
    from board.slots import snapshot
    return int(snapshot(opencode_slots_path()).get("count") or 0)


class OpenCodeCountProxy:
    """跨进程 opencode 计数代理。

    v0.51.0 P1-8: 引入 TTL 缓存避免每次 dunder 调用都读文件。
    acquire/release 函数会调用 invalidate() 立即失效本进程缓存。
    """

    _cache_value: int = 0
    _cache_ts: float = 0.0

    @classmethod
    def invalidate(cls) -> None:
        """显式失效缓存（acquire/release 后调用）。"""
        cls._cache_ts = 0.0

    @classmethod
    def _get_cached_count(cls) -> int:
        now = time.monotonic()
        if _SLOT_CACHE_TTL <= 0 or now - cls._cache_ts >= _SLOT_CACHE_TTL:
            cls._cache_value = global_opencode_count()
            cls._cache_ts = now
        return cls._cache_value

    def __int__(self) -> int:
        return self._get_cached_count()

    def __index__(self) -> int:
        return self._get_cached_count()

    def __format__(self, spec: str) -> str:
        return format(self._get_cached_count(), spec)

    def __repr__(self) -> str:
        return str(self._get_cached_count())

    def __str__(self) -> str:
        return str(self._get_cached_count())

    def __eq__(self, other: object) -> bool:
        return self._get_cached_count() == other

    def __lt__(self, other: object) -> bool:
        return self._get_cached_count() < other  # type: ignore[operator]

    def __hash__(self) -> int:
        return hash(self._get_cached_count())


GLOBAL_OPENCODE_COUNT = OpenCodeCountProxy()


def try_acquire_opencode_slot(task_key: str) -> bool:
    """占全局槽；同 workspace 最多 1 路 opencode（防同仓 database is locked）。

    这与 MAX_CONCURRENT（跨仓总并发）正交：三任务并发可以是三仓各一路，
    或同仓排队。卡死根因是同仓这一路不退出/残留，不是「倒 20 张堵全局槽」。

    task_key 约定：``{workspace_resolved}|{task_id}``（见 ccc-engine._task_key）。

    P1：同仓 holder 若已有 ``.done`` 或 pid 已死 → 先释幽灵槽，不挡新卡。
    """
    from board.slots import snapshot, try_acquire

    OpenCodeCountProxy.invalidate()  # 占槽后立即失效缓存
    # 同仓互斥：key 前缀为 workspace path
    if "|" in task_key:
        ws_s, _tid = task_key.rsplit("|", 1)
        ws_prefix = ws_s + "|"
        ws_path = Path(ws_s)
        snap = snapshot(opencode_slots_path())
        for held in list(snap.get("tasks") or {}):
            if not held.startswith(ws_prefix) or held == task_key:
                continue
            other_tid = held.rsplit("|", 1)[-1]
            done = ws_path / ".ccc" / "pids" / f"{other_tid}.done"
            pid_alive = False
            pid_path = ws_path / ".ccc" / "pids" / f"{other_tid}.pid"
            if pid_path.is_file() and not done.is_file():
                try:
                    pid = int(pid_path.read_text().strip())
                    os.kill(pid, 0)
                    pid_alive = True
                except (OSError, ValueError, ProcessLookupError):
                    pid_alive = False
            if done.is_file() or not pid_alive:
                # 幽灵槽：释后再判
                release_opencode_slot(held, None)
                continue
            return False
    return try_acquire(
        task_key,
        max_slots=_GLOBAL_OPENCODE_MAX,
        state_path=opencode_slots_path(),
    )


def release_opencode_slot(task_key: str, n: int | None = None) -> int:
    from board.slots import release
    OpenCodeCountProxy.invalidate()  # 释放后立即失效缓存
    return release(task_key, n, state_path=opencode_slots_path())


# legacy aliases
_opencode_slots_path = opencode_slots_path
_global_opencode_count = global_opencode_count
_OpenCodeCountProxy = OpenCodeCountProxy
_GLOBAL_OPENCODE_COUNT = GLOBAL_OPENCODE_COUNT
_try_acquire_opencode_slot = try_acquire_opencode_slot
_release_opencode_slot = release_opencode_slot
_GLOBAL_OPENCODE_MAX = _GLOBAL_OPENCODE_MAX
