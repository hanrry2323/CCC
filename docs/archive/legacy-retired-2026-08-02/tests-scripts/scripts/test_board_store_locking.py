"""test_board_store_locking.py — H4: 写操作 lock 失败时正确中止

覆盖：
  - create_task / move_task / update_index / quarantine 在 lock=None 时不修改文件系统
  - abort 返回语义（False / False / {} / None）
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS = ROOT / "scripts"

os.chdir(str(SCRIPTS))
sys.path.insert(0, str(SCRIPTS))
_spec = importlib.util.spec_from_file_location("cb", str(SCRIPTS / "_board_store.py"))
bs = importlib.util.module_from_spec(_spec)
sys.modules["cb"] = bs
_spec.loader.exec_module(bs)

FileBoardStore = bs.FileBoardStore
COLUMNS = bs.COLUMNS


def _make_store(tmp_path: Path) -> FileBoardStore:
    """构造 FileBoardStore，目录布局合法"""
    board = tmp_path / ".ccc" / "board"
    board.mkdir(parents=True, exist_ok=True)
    for col in COLUMNS:
        (board / col).mkdir(parents=True, exist_ok=True)
    (board / "events").mkdir(parents=True, exist_ok=True)
    return FileBoardStore(tmp_path)


def _valid_task(task_id: str = "lock-test-1") -> dict:
    return {
        "id": task_id,
        "title": "Lock 测试",
        "description": "验证 lock 失败时中止",
        "status": "backlog",
        "created_at": "2026-07-11T14:00:00Z",
        "updated_at": "2026-07-11T14:00:00Z",
        "assignee": "alice",
        "tags": ["test"],
        "note": None,
        "schema_version": "1.0",
        "color_group": "A",
        "color_depth": 0,
    }


class TestLockGuard:
    """H4: lock 失败时所有写操作必须中止"""

    def test_create_task_aborts_on_lock_none(self, tmp_path):
        store = _make_store(tmp_path)
        store._lock = lambda: None

        ok = store.create_task(_valid_task(), column="backlog")
        assert ok is False

        # 不应创建任何文件
        backlog = tmp_path / ".ccc" / "board" / "backlog"
        assert not (backlog / "lock-test-1.jsonl").exists()

    def test_create_task_unaffected_when_lock_works(self, tmp_path):
        store = _make_store(tmp_path)
        ok = store.create_task(_valid_task(), column="backlog")
        assert ok is True
        assert (tmp_path / ".ccc" / "board" / "backlog" / "lock-test-1.jsonl").exists()

    def test_move_task_aborts_on_lock_none(self, tmp_path):
        store = _make_store(tmp_path)
        # 先创建一个 task（lock 正常工作）
        assert store.create_task(_valid_task("move-me"), column="backlog")

        # 模拟 lock 失败
        store._lock = lambda: None

        ok = store.move_task("move-me", "backlog", "planned")
        assert ok is False

        # task 仍在 backlog 列
        assert (tmp_path / ".ccc" / "board" / "backlog" / "move-me.jsonl").exists()
        assert not (tmp_path / ".ccc" / "board" / "planned" / "move-me.jsonl").exists()

    def test_update_index_aborts_on_lock_none(self, tmp_path):
        store = _make_store(tmp_path)
        index_file = tmp_path / ".ccc" / "board" / "index.json"

        # lock 失败前，index.json 不存在
        assert not index_file.exists()

        store._lock = lambda: None
        result = store.update_index()

        assert result == {}
        assert not index_file.exists()

    def test_quarantine_aborts_on_lock_none(self, tmp_path):
        store = _make_store(tmp_path)
        assert store.create_task(_valid_task("quar-test"), column="backlog")

        # 模拟 lock 失败
        store._lock = lambda: None
        store.quarantine("quar-test", "test reason")

        # task 仍在 backlog 列
        assert (tmp_path / ".ccc" / "board" / "backlog" / "quar-test.jsonl").exists()
        assert not (tmp_path / ".ccc" / "board" / "abnormal" / "quar-test.jsonl").exists()

    def test_lock_release_safely_handles_none(self, tmp_path):
        """M3: _unlock(None) 不抛异常"""
        store = _make_store(tmp_path)
        # 直接调用不应抛异常
        store._unlock(None)
