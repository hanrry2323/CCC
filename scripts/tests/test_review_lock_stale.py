"""Review 僵尸锁 TTL：超龄 .lock 应被清除。"""

from __future__ import annotations

import importlib.util
import os
import sys
import time
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))


def _load_board():
    spec = importlib.util.spec_from_file_location(
        "ccc_board_lock", SCRIPTS / "ccc-board.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_clear_stale_review_locks_removes_old(tmp_path, monkeypatch):
    board = _load_board()
    lock_dir = tmp_path / ".ccc" / "review-locks"
    lock_dir.mkdir(parents=True)
    stale = lock_dir / "old-task.lock"
    fresh = lock_dir / "new-task.lock"
    stale.write_text("1")
    fresh.write_text("1")
    # 伪造超龄 mtime
    old_mtime = time.time() - 700
    os.utime(stale, (old_mtime, old_mtime))
    os.utime(fresh, None)

    cleared = board.clear_stale_review_locks(lock_dir, stale_sec=600)
    assert "old-task.lock" in cleared
    assert not stale.exists()
    assert fresh.exists()


def test_reviewer_role_clears_stale_before_scan(tmp_path, monkeypatch):
    board = _load_board()
    monkeypatch.setattr(board, "get_workspace", lambda: tmp_path)
    lock_dir = tmp_path / ".ccc" / "review-locks"
    lock_dir.mkdir(parents=True)
    (tmp_path / ".ccc" / "board" / "testing").mkdir(parents=True)
    for col in (
        "backlog",
        "planned",
        "in_progress",
        "verified",
        "released",
        "abnormal",
    ):
        (tmp_path / ".ccc" / "board" / col).mkdir(parents=True, exist_ok=True)

    stale = lock_dir / "stuck.lock"
    stale.write_text("x")
    os.utime(stale, (time.time() - 999, time.time() - 999))

    # testing 空 → reviewer 早退，但仍应清锁
    monkeypatch.setattr(
        board,
        "list_tasks",
        lambda col: [],
    )
    board.reviewer_role()
    assert not stale.exists()
