"""测试共享任务卡头 CardHeader 契约与解析（A1 · ccc059）。"""

from __future__ import annotations

import pytest
from server.board.card_header import CardHeader, parse_metadata, card_id, is_task_card_text, bump_reject_count
from server.board.models import UNKNOWN

SAMPLE_CARD = """# 任务卡 T99 · 示例任务（OpenCode 执行）

> 关联：PRJ-X（示例）· 状态：执行中 · 日期：2026-07-28
> 执行体：OpenCode · 验收：Claude Code · 派发：manual · 类型：epic

## 目标
测试

## 验收标准
测试通过
"""

def test_parse_metadata() -> None:
    # 正常块解析
    meta = parse_metadata(SAMPLE_CARD)
    assert meta["关联"] == "PRJ-X（示例）"
    assert meta["状态"] == "执行中"
    assert meta["日期"] == "2026-07-28"
    assert meta["执行体"] == "OpenCode"
    assert meta["验收"] == "Claude Code"
    assert meta["派发"] == "manual"
    assert meta["类型"] == "epic"

    # 空文本/无元数据
    assert parse_metadata("") == {}
    assert parse_metadata("# Header\nNo meta\n") == {}

def test_card_id() -> None:
    assert card_id(SAMPLE_CARD) == "T99"
    # 带连字符/其他特殊
    assert card_id("# 任务卡 ccc059-schema · Title\n") == "ccc059-schema"
    # 无匹配
    assert card_id("# No card id here") == ""

def test_is_task_card_text() -> None:
    assert is_task_card_text(SAMPLE_CARD) is True
    assert is_task_card_text("# T-mapping.md\nThis is not a task card") is False

# Removed reject_count_in test

def test_card_header_from_text() -> None:
    header = CardHeader.from_text(SAMPLE_CARD)
    assert header.id == "T99"
    assert header.title == "示例任务（OpenCode 执行）"
    assert header.related == "PRJ-X（示例）"
    assert header.executor == "OpenCode"
    assert header.acceptance == "Claude Code"
    assert header.state == "执行中"
    assert header.dispatched_at == "2026-07-28"
    assert header.dispatch == "manual"
    assert header.card_type == "epic"
    assert header.reject_count == 0

    # Fallback ID when title row doesn't match standard
    header_fallback = CardHeader.from_text("> 状态：待分派\n", fallback_id="stem-id")
    assert header_fallback.id == "stem-id"
    assert header_fallback.title == UNKNOWN


def test_bump_reject_count_existing() -> None:
    """已有 打回次数：N → 递增。"""
    text = "# 任务卡 T99 · 示例\n\n> 状态：打回（原因） · 打回次数：3\n"
    out = bump_reject_count(text)
    assert "打回次数：4" in out
    assert "打回次数：3" not in out


def test_bump_reject_count_missing() -> None:
    """无字段 → 在标题行后新增 `> 打回次数：1`。"""
    text = "# 任务卡 T99 · 示例\n\n> 状态：待分派\n"
    out = bump_reject_count(text)
    assert "> 打回次数：1" in out
    assert CardHeader.from_text(out).reject_count == 1

