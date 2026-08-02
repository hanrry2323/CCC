"""test_quarantine_archive.py — quarantine 副本归档测试

v0.28 清理后仅保留仍存在的 API：quarantine_store_content / quarantines_index_task。
quarantines_cleanup_task / quarantines_harvesting_index 已作为 dead code 删除。
"""

import json
from pathlib import Path

from _board_store import (
    get_quarantine_base_name,
    quarantine_store_content,
    quarantines_index_task,
)


class TestQuarantineStoreContent:
    """quarantine content 归档功能单元测试"""

    def test_quarantine_store_content_basic(self):
        """无 content 时返回 False"""
        result = quarantine_store_content(
            task_id="test-task-001",
            content_path=Path("/nonexistent") / "source.txt",
        )
        assert result is False

    def test_quarantine_store_content_with_file(self, tmp_path, monkeypatch):
        """有 content_path 时正确归档（目录副本，非 tar.gz）"""
        monkeypatch.setenv("CCC_WORKSPACE", str(tmp_path))
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        (source_dir / "file.txt").write_text("test content\n")

        result = quarantine_store_content(
            task_id="test-task-001",
            content_path=source_dir,
        )
        assert result is True
        assert get_quarantine_base_name() == "test-task-001"

        # 副本落在 <workspace>/.ccc/quarantines/<task_id>
        copy = tmp_path / ".ccc" / "quarantines" / "test-task-001"
        assert copy.exists()


class TestQuarantineIndexTask:
    def test_quarantine_index_task_populates_index(self, tmp_path, monkeypatch):
        """quarantines_index_task 写入 quarantines index.json"""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CCC_WORKSPACE", str(tmp_path))
        quarantine_dir = tmp_path / ".ccc" / "quarantines"
        quarantine_dir.mkdir(parents=True)
        (quarantine_dir / "sample-task").mkdir()
        (quarantine_dir / "sample-task" / "note.txt").write_text("x")

        quarantines_index_task()

        index_file = quarantine_dir / "index.json"
        assert index_file.exists()
        index = json.loads(index_file.read_text())
        assert "sample-task" in index["quarantines"]
        entry = index["quarantines"]["sample-task"]
        assert "file" in entry
        assert "first_seen" in entry
        assert "last_seen" in entry
        assert entry["count"] >= 1


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
