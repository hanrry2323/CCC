"""engine.slots — 跨进程 opencode 槽位（对接 board.slots）。"""
from __future__ import annotations

from pathlib import Path

_GLOBAL_OPENCODE_MAX = 6


def opencode_slots_path() -> Path:
    from board.slots import default_state_path
    return default_state_path()


def global_opencode_count() -> int:
    from board.slots import snapshot
    return int(snapshot(opencode_slots_path()).get("count") or 0)


class OpenCodeCountProxy:
    def __int__(self) -> int:
        return global_opencode_count()

    def __index__(self) -> int:
        return global_opencode_count()

    def __format__(self, spec: str) -> str:
        return format(global_opencode_count(), spec)

    def __repr__(self) -> str:
        return str(global_opencode_count())

    def __str__(self) -> str:
        return str(global_opencode_count())

    def __eq__(self, other: object) -> bool:
        return global_opencode_count() == other

    def __lt__(self, other: object) -> bool:
        return global_opencode_count() < other  # type: ignore[operator]


GLOBAL_OPENCODE_COUNT = OpenCodeCountProxy()


def try_acquire_opencode_slot(task_key: str) -> bool:
    from board.slots import try_acquire
    return try_acquire(
        task_key,
        max_slots=_GLOBAL_OPENCODE_MAX,
        state_path=opencode_slots_path(),
    )


def release_opencode_slot(task_key: str, n: int | None = None) -> int:
    from board.slots import release
    return release(task_key, n, state_path=opencode_slots_path())


# legacy aliases
_opencode_slots_path = opencode_slots_path
_global_opencode_count = global_opencode_count
_OpenCodeCountProxy = OpenCodeCountProxy
_GLOBAL_OPENCODE_COUNT = GLOBAL_OPENCODE_COUNT
_try_acquire_opencode_slot = try_acquire_opencode_slot
_release_opencode_slot = release_opencode_slot
_GLOBAL_OPENCODE_MAX = _GLOBAL_OPENCODE_MAX
