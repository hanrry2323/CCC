"""test_quarantine_archive.py — v0.28.0 quarantine 副本归档测试"""

import json
import tarfile
import tempfile
import time
from pathlib import Path

import pytest

from _board_store import (
    quarantine_store_content,
    quarantines_cleanup_task,
    quarantines_harvesting_index,
    quarantines_index_task,
)


class TestQuarantineStoreContent:
    """quarantine content 归档功能单元测试"""

    def test_quarantine_store_content_basic(self):
        """基本的 quarantine 内容存储（无 content 时返回 False）"""
        with tempfile.TemporaryDirectory() as tmpdir:
            quarantine_dir = Path(tmpdir) / ".ccc" / "quarantines"
            quarantine_dir.mkdir(parents=True)

            result = quarantine_store_content(
                task_id="test-task-001",
                content_path=Path(tmpdir) / "source.txt",
            )

            assert result is False, "无 content_path 时返回 False"

    def test_quarantine_store_content_with_file(self):
        """有 content_path 时正确归档 tar.gz"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建源文件
            source_dir = Path(tmpdir) / "source"
            source_dir.mkdir()
            (source_dir / "file.txt").write_text("test content\n")

            quarantine_dir = Path(tmpdir) / ".ccc" / "quarantines"

            # 归档
            result = quarantine_store_content(
                task_id="test-task-001",
                content_path=source_dir,
            )

            assert result is True

            # 验证副本存在
            copy_file = quarantine_dir / f"{quarantine_store_content.base_name}"
            assert copy_file.exists()
            assert copy_file.stat().st_size > 0

    def test_quarantine_cleanup_task_filters_old(self):
        """quarantines_cleanup_task 清理超过指定时间的副本"""
        with tempfile.TemporaryDirectory() as tmpdir:
            quarantine_dir = Path(tmpdir) / ".ccc" / "quarantines"
            quarantine_dir.mkdir(parents=True)

            base_tar = quarantine_store_content.base_name

            # 创建两个副本（一个 12 小时前，一个 2 小时前）
            import os

            old_copy = quarantine_dir / f"{base_tar}.1.tar.gz"
            old_copy.touch()
            old_copy.chmod(0o644)

            fresh_copy = quarantine_dir / f"{base_tar}.2.tar.gz"
            fresh_copy.touch()
            fresh_copy.chmod(0o644)

            time.sleep(1)  # 确保时间戳不同

            # 运行清理任务（参数：超过 5 小时的内容）
            removed_count = quarantines_cleanup_task(hours_threshold=5)

            # 应该删除旧的，保留新的
            assert removed_count == 1
            assert not old_copy.exists()
            assert fresh_copy.exists()

    def test_quarantine_index_task_populates_index(self):
        """quarantines_index_task 写入 quarantines index.json"""
        with tempfile.TemporaryDirectory() as tmpdir:
            quarantine_dir = Path(tmpdir) / ".ccc" / "quarantines"
            quarantine_dir.mkdir(parents=True)

            base_tar = quarantine_store_content.base_name

            # 手动添加一个副本
            copy_file = quarantine_dir / f"{base_tar}.1.tar.gz"
            copy_file.write_text("fake tar content")
            original_mtime = time.time()

            # 更新 mtime
            time.sleep(0.1)
            copy_file.touch()

            # 运行索引任务
            quarantines_index_task()

            # 检查 index.json 存在
            index_file = quarantine_dir / "index.json"
            assert index_file.exists()

            # 解析 index.json
            index = json.loads(index_file.read_text())

            assert base_tar in index["quarantines"]
            entry = index["quarantines"][base_tar]

            assert "file" in entry
            assert "first_seen" in entry
            assert "last_seen" in entry
            assert entry["file"] == f"{base_tar}.1.tar.gz"
            assert entry["count"] == 1

    def test_quarantine_harvesting_index_stats(self):
        """quarantines_harvesting_index 生成 清零后单个 index"""
        with tempfile.TemporaryDirectory() as tmpdir:
            quarantine_dir = Path(tmpdir) / ".ccc" / "quarantines"
            quarantine_dir.mkdir(parents=True)

            base_tar = quarantine_store_content.base_name

            # 添加多个副本
            for i in range(3):
                copy_file = quarantine_dir / f"{base_tar}.tar.gz"
                copy_file.write_text(f"content {i}")
                time.sleep(0.1)  # 差异化时间戳
                copy_file.rename(f"{base_tar}.{i}.tar.gz")

            # 运行采集索引任务
            counts = quarantines_harvesting_index()

            assert counts["total"] == 3
            assert counts["completed"] == 1
            assert counts["remaining"] == 2

            # 检查 index.json 袡糊 single-violation
            index_file = quarantine_dir / "index.json"
            assert index_file.exists()

            index = json.loads(index_file.read_text())

            # harvesting 只会保留一个副本
            assert len(index["quarantines"].keys()) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
