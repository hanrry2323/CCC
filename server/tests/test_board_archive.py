"""test_board_archive — 测试任务卡自动归档与回顾索引机制。"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from server.board.archive import archive_old_cards
from server.board.loader import (
    get_archive_dir,
    get_index_path,
    load_dispatch_cards,
    load_index_file,
)


def _write_card(dir_path: Path, name: str, content: str) -> Path:
    p = dir_path / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


@pytest.fixture
def temp_dispatch_env(tmp_path: Path, monkeypatch) -> Path:
    """创建隔离的任务卡调度及数据目录环境。"""
    dispatch_dir = tmp_path / "docs" / "dispatch"
    dispatch_dir.mkdir(parents=True, exist_ok=True)

    # 隔离数据和索引文件
    monkeypatch.setenv("CCC_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "1")

    return dispatch_dir


def test_archive_old_cards_rules(temp_dispatch_env: Path) -> None:
    """测试归档机制的各项时间、状态过滤规则。"""
    dispatch_dir = temp_dispatch_env
    today = date(2026, 8, 5)

    # 1. 应该被归档的卡 (关闭且超过 6 个月，即 2026-02-05 之前)
    c1 = (
        "# 任务卡 xy101 · 应该归档\n"
        "> 关联：xy · 执行体：Claude · 验收：Codex · 状态：已关闭 · 项目：xy · 日期：2026-01-10\n"
        "## 回写区\n"
        "**日期**：2026-01-15\n"
    )
    _write_card(dispatch_dir / "xy", "xy101-old-closed.md", c1)

    # 2. 不应该被归档的卡 A (关闭但未满 6 个月，如 2026-03-01 关闭)
    c2 = (
        "# 任务卡 xy102 · 不该归档未满期\n"
        "> 关联：xy · 执行体：Claude · 验收：Codex · 状态：已关闭 · 项目：xy · 日期：2026-02-10\n"
        "## 回写区\n"
        "**日期**：2026-03-01\n"
    )
    _write_card(dispatch_dir / "xy", "xy102-recent-closed.md", c2)

    # 3. 不应该被归档的卡 B (未关闭但超过 6 个月，如 2026-01-10 派发的执行中卡)
    c3 = (
        "# 任务卡 qb101 · 不该归档未关闭\n"
        "> 关联：QB · 执行体：OpenCode · 验收：Codex · 状态：执行中 · 项目：qb · 日期：2026-01-10\n"
    )
    _write_card(dispatch_dir / "qb", "qb101-old-active.md", c3)

    # 执行归档逻辑
    archived_ids = archive_old_cards(dispatch_dir, today=today)

    assert archived_ids == ["xy101"]

    # 验证文件是否物理移动
    archive_dir = get_archive_dir(dispatch_dir)
    assert not (dispatch_dir / "xy" / "xy101-old-closed.md").exists()
    assert (archive_dir / "xy" / "xy101-old-closed.md").exists()

    # 验证未归档文件依然存在
    assert (dispatch_dir / "xy" / "xy102-recent-closed.md").exists()
    assert (dispatch_dir / "qb" / "qb101-old-active.md").exists()


def test_index_archived_and_query_filtering(temp_dispatch_env: Path) -> None:
    """测试索引标记 archived=true 及看板不含、回顾含归档卡的能力。"""
    dispatch_dir = temp_dispatch_env
    today = date(2026, 8, 5)

    # 创建归档卡
    c1 = (
        "# 任务卡 xy201 · 归档卡\n"
        "> 关联：xy · 执行体：Claude · 状态：已关闭 · 项目：xy · 日期：2026-01-01\n"
        "## 回写区\n"
        "**日期**：2026-01-05\n"
    )
    _write_card(dispatch_dir / "xy", "xy201-old.md", c1)

    # 创建常规卡
    c2 = "# 任务卡 xy202 · 常规卡\n> 关联：xy · 执行体：Claude · 状态：执行中 · 项目：xy · 日期：2026-08-01\n"
    _write_card(dispatch_dir / "xy", "xy202-new.md", c2)

    # 首次加载建立完整索引
    load_dispatch_cards(dispatch_dir, include_archived=True)

    # 运行归档
    archive_old_cards(dispatch_dir, today=today)

    # 1. 验证 load_index_file 中可以读到 archived 状态
    index_entries = load_index_file(dispatch_dir)
    assert index_entries["xy201"]["archived"] is True
    assert not index_entries["xy202"].get("archived", False)
    assert "archive/ccc-tasks/xy" in index_entries["xy201"]["path"]

    # 2. 验证看板默认加载不含归档卡 (include_archived=False)
    items_default = load_dispatch_cards(dispatch_dir, include_archived=False)
    assert len(items_default) == 1
    assert items_default[0].id == "xy202"

    # 3. 验证看板显式加载含归档卡 (include_archived=True)
    items_all = load_dispatch_cards(dispatch_dir, include_archived=True)
    assert len(items_all) == 2
    ids = {item.id for item in items_all}
    assert ids == {"xy201", "xy202"}
