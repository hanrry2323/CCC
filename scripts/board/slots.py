"""board.slots — 跨进程 opencode 全局槽位（同一文件 fcntl.flock + 共享计数）。

F-ARCH-03 / Phase 2: 多 Engine 实例共享同一上限，互不超卖。
锁与状态同一文件：避免「锁文件 / 状态文件」双路径不一致。
进程崩溃后：持有者 pid 不可达时，acquire/snapshot 回收其槽位。
"""
from __future__ import annotations

import errno
import fcntl
import json
import os
import threading
import time
from pathlib import Path
from typing import Any

_DEFAULT_MAX = 6
_thread_gate = threading.Lock()


def default_state_path() -> Path:
    env = os.environ.get("CCC_OPENCODE_SLOTS_FILE", "").strip()
    if env:
        return Path(env)
    home = Path(os.environ.get("CCC_HOME", Path.home() / ".ccc"))
    return home / "opencode_slots.json"


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _empty_state(max_slots: int) -> dict[str, Any]:
    return {"max": max_slots, "count": 0, "tasks": {}}


def _reap_and_sync(state: dict[str, Any]) -> None:
    """回收死进程槽位；count 始终 = Σ tasks.n。"""
    tasks = state.get("tasks") or {}
    live: dict[str, Any] = {}
    for key, info in list(tasks.items()):
        if not isinstance(info, dict):
            continue
        pid = int(info.get("pid") or 0)
        n = int(info.get("n") or 0)
        if n <= 0 or not _pid_alive(pid):
            continue
        live[key] = {"n": n, "pid": pid}
    state["tasks"] = live
    state["count"] = sum(int(i["n"]) for i in live.values())


def _decode_state(raw: bytes, max_slots: int) -> dict[str, Any]:
    if not raw.strip():
        return _empty_state(max_slots)
    try:
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict):
            return _empty_state(max_slots)
        data.setdefault("max", max_slots)
        data.setdefault("tasks", {})
        data.setdefault("count", 0)
        return data
    except (UnicodeDecodeError, json.JSONDecodeError):
        return _empty_state(max_slots)


def _locked_update(
    path: Path,
    mutator,
    *,
    max_slots: int | None = None,
    timeout_s: float = 5.0,
):
    """对 state 文件加 LOCK_EX，读 → mutator(state) → 写回。返回 mutator 返回值。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(path), os.O_CREAT | os.O_RDWR | os.O_CLOEXEC, 0o600)
    deadline = time.monotonic() + timeout_s
    try:
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError as e:
                if e.errno not in (errno.EAGAIN, errno.EWOULDBLOCK, errno.EACCES):
                    raise
                if time.monotonic() > deadline:
                    return None
                time.sleep(0.02)
        os.lseek(fd, 0, os.SEEK_SET)
        raw = os.read(fd, 1 << 20)
        state = _decode_state(raw, max_slots if max_slots is not None else _DEFAULT_MAX)
        if max_slots is not None:
            state["max"] = max_slots
        _reap_and_sync(state)
        result = mutator(state)
        payload = (
            json.dumps(state, ensure_ascii=False, separators=(",", ":")) + "\n"
        ).encode("utf-8")
        os.ftruncate(fd, 0)
        os.lseek(fd, 0, os.SEEK_SET)
        os.write(fd, payload)
        os.fsync(fd)
        return result
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        except OSError:
            pass
        try:
            os.close(fd)
        except OSError:
            pass


def try_acquire(
    task_key: str,
    *,
    max_slots: int | None = None,
    state_path: Path | str | None = None,
) -> bool:
    path = Path(state_path) if state_path else default_state_path()
    limit = max_slots if max_slots is not None else int(
        os.environ.get("CCC_OPENCODE_MAX", _DEFAULT_MAX)
    )

    def _mut(state: dict[str, Any]):
        if int(state["count"]) >= limit:
            return False
        tasks = state["tasks"]
        info = tasks.get(task_key)
        if isinstance(info, dict) and int(info.get("pid") or 0) == os.getpid():
            info["n"] = int(info.get("n") or 0) + 1
            tasks[task_key] = info
        else:
            tasks[task_key] = {"n": 1, "pid": os.getpid()}
        state["tasks"] = tasks
        state["count"] = sum(int(i["n"]) for i in tasks.values())
        return True

    with _thread_gate:
        out = _locked_update(path, _mut, max_slots=limit)
        return bool(out)


def release(
    task_key: str,
    n: int | None = None,
    *,
    state_path: Path | str | None = None,
) -> int:
    path = Path(state_path) if state_path else default_state_path()

    def _mut(state: dict[str, Any]):
        tasks = state.get("tasks") or {}
        info = tasks.get(task_key)
        if not isinstance(info, dict):
            return 0
        held = int(info.get("n") or 0)
        if held <= 0:
            tasks.pop(task_key, None)
            state["tasks"] = tasks
            state["count"] = sum(int(i["n"]) for i in tasks.values())
            return 0
        rel = held if n is None else min(max(0, n), held)
        left = held - rel
        if left:
            info["n"] = left
            tasks[task_key] = info
        else:
            tasks.pop(task_key, None)
        state["tasks"] = tasks
        state["count"] = sum(int(i["n"]) for i in tasks.values())
        return rel

    with _thread_gate:
        out = _locked_update(path, _mut)
        return int(out or 0)


def snapshot(state_path: Path | str | None = None) -> dict[str, Any]:
    path = Path(state_path) if state_path else default_state_path()

    def _mut(state: dict[str, Any]):
        return {
            "max": state.get("max"),
            "count": state.get("count"),
            "tasks": dict(state.get("tasks") or {}),
        }

    with _thread_gate:
        out = _locked_update(path, _mut)
        return out if isinstance(out, dict) else {}
