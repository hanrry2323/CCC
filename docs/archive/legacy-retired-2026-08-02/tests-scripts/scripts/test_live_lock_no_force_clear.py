"""F-LOCK-01/02: flock 活锁不 force-clear；死进程锁自动释放。"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from _board_store import _acquire_lock, _release_lock  # noqa: E402
from board.lock import FlockHandle  # noqa: E402


def test_live_holder_not_force_cleared(tmp_path):
    lockfile = tmp_path / "board.lock"
    first = _acquire_lock(lockfile, timeout_s=0.4)
    assert first is not None
    assert isinstance(first, FlockHandle)
    second = _acquire_lock(lockfile, timeout_s=0.3)
    assert second is None
    # flock 活锁文件仍在，pid 可读取
    assert first.exists()
    content = first.read_text()
    assert str(os.getpid()) in content
    _release_lock(first)


def test_second_acquire_after_release(tmp_path):
    lockfile = tmp_path / "board.lock"
    first = _acquire_lock(lockfile, timeout_s=1.0)
    assert first is not None
    _release_lock(first)
    second = _acquire_lock(lockfile, timeout_s=1.0)
    assert second is not None
    _release_lock(second)
