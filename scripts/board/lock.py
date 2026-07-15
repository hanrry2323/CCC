"""board.lock — 统一 advisory 锁协议（fcntl.flock）。

F-LOCK-02: board store 与 product_role 共用 flock，不再使用 O_EXCL 旁路。
进程崩溃后内核自动释放 flock，无需 force-clear 活锁。
"""
from __future__ import annotations

import errno
import fcntl
import os
import time
from pathlib import Path
from typing import Any

# product_role 命名锁 fd 表（与历史 _product_lock_fds 行为一致）
_named_lock_fds: dict[str, int] = {}


def acquire_flock(lockfile: Path, timeout_s: float = 30.0) -> int | None:
    """对 lockfile 加 LOCK_EX（非阻塞轮询）。成功返回 fd，超时返回 None。

    调用方必须在 finally 中 release_flock(fd)（或 close）。
    """
    lockfile = Path(lockfile)
    lockfile.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(lockfile), os.O_CREAT | os.O_RDWR | os.O_CLOEXEC, 0o600)
    deadline = time.monotonic() + timeout_s
    while True:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            # 写入 pid 便于排查（不参与互斥）
            try:
                os.ftruncate(fd, 0)
                os.lseek(fd, 0, os.SEEK_SET)
                os.write(fd, f"{os.getpid()}|{time.time():.3f}".encode())
            except OSError:
                pass
            return fd
        except OSError as e:
            if e.errno not in (errno.EAGAIN, errno.EWOULDBLOCK, errno.EACCES):
                os.close(fd)
                raise
            if time.monotonic() > deadline:
                os.close(fd)
                return None
            time.sleep(0.1)


def release_flock(fd: int | None) -> None:
    if fd is None:
        return
    try:
        fcntl.flock(fd, fcntl.LOCK_UN)
    except OSError:
        pass
    try:
        os.close(fd)
    except OSError:
        pass


def acquire_named_lock(lockfile: Path, timeout_s: float = 30.0) -> None:
    """product_role 风格：按路径登记 fd，超时抛 OSError。"""
    lock_key = str(Path(lockfile))
    deadline = time.monotonic() + timeout_s
    while True:
        fd = os.open(lock_key, os.O_CREAT | os.O_RDWR | os.O_CLOEXEC, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            _named_lock_fds[lock_key] = fd
            return
        except OSError as e:
            os.close(fd)
            if e.errno not in (errno.EAGAIN, errno.EWOULDBLOCK, errno.EACCES):
                raise
            if time.monotonic() >= deadline:
                raise OSError(f"named lock timeout ({timeout_s}s): {lockfile}")
            time.sleep(0.5)


def release_named_lock(lockfile: Path) -> None:
    lock_key = str(Path(lockfile))
    fd = _named_lock_fds.pop(lock_key, None)
    release_flock(fd)


# --- FileBoardStore 兼容层：_acquire_lock / _release_lock 语义 ---


class FlockHandle:
    """可被 Path-like 测活的句柄；实际互斥靠 fd flock。"""

    __slots__ = ("path", "fd")

    def __init__(self, path: Path, fd: int):
        self.path = Path(path)
        self.fd = fd

    def exists(self) -> bool:
        return self.path.exists()

    def read_text(self, encoding: str = "utf-8") -> str:
        try:
            os.lseek(self.fd, 0, os.SEEK_SET)
            return os.read(self.fd, 256).decode(encoding, errors="replace")
        except OSError:
            return self.path.read_text(encoding=encoding)

    def unlink(self, missing_ok: bool = True) -> None:
        # flock 释放后可不删锁文件；保留文件供下次 open
        return

    def __str__(self) -> str:
        return str(self.path)


def acquire_board_lock(lockfile: Path, timeout_s: float = 30.0) -> FlockHandle | None:
    """FileBoardStore 用：返回 FlockHandle 或 None（超时）。"""
    fd = acquire_flock(lockfile, timeout_s=timeout_s)
    if fd is None:
        return None
    return FlockHandle(lockfile, fd)


def release_board_lock(lock_obj: Any) -> None:
    if lock_obj is None:
        return
    if isinstance(lock_obj, FlockHandle):
        release_flock(lock_obj.fd)
        return
    # 兼容旧 O_EXCL Path
    if isinstance(lock_obj, (str, Path)):
        try:
            Path(lock_obj).unlink(missing_ok=True)
        except OSError:
            pass
