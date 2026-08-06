"""test_board_redispatch — 打回卡人工重新分派（打回 → 待分派）。"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from server.board.redispatch import redispatch_card

_PROJECT_ROOT = Path(__file__).resolve().parents[2]

_CARD_TEMPLATE = """\
# 任务卡 {cid} · 测试（OpenCode 执行）

> 关联：测试 · 执行体：OpenCode · 验收：Claude Code · 状态：{state} · 派发：engine · 项目：ccc · 日期：2026-08-07 · 打回次数：2

## 目标

（一句话，可验收。）

## 红线（先看）

1. （本卡禁止触碰的边界）

## 范围

（明确本卡改动范围）

## 步骤

1. （可执行步骤）

## 验收标准

1. （可执行的验收点）

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据。

## 人工批注

（老板打回意见。）

## 回写区

**执行体**：OpenCode · 日期：
"""


@pytest.fixture()
def card_file(tmp_path: Path) -> Path:
    p = tmp_path / "ccc" / "ccc042-redispatch.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        _CARD_TEMPLATE.format(cid="ccc042", state="打回（测试失败）"),
        encoding="utf-8",
    )
    return p


def test_redispatch_rejected_card(card_file: Path):
    ok, msg = redispatch_card(card_file)
    assert ok, msg
    assert "待分派" in msg

    text = card_file.read_text(encoding="utf-8")
    # 状态回纯「待分派」（无重试标记 → 引擎 retry_count 归零）
    state_part = text.split("状态：", 1)[1].split("·", 1)[0]
    assert state_part.strip() == "待分派"
    # 打回历史与人工批注保留
    assert "打回次数：2" in text
    assert "## 人工批注" in text

    from server.board.loader import parse_card

    item = parse_card(card_file)
    assert item.state == "待分派"
    assert item.reject_count == 2


def test_redispatch_refuses_non_rejected(card_file: Path):
    text = card_file.read_text(encoding="utf-8").replace("打回（测试失败）", "执行中")
    card_file.write_text(text, encoding="utf-8")
    ok, msg = redispatch_card(card_file)
    assert not ok
    assert "仅「打回」卡可重新分派" in msg
    # 状态未被改动
    assert "状态：执行中" in card_file.read_text(encoding="utf-8")


def test_redispatch_missing_card(tmp_path: Path):
    ok, msg = redispatch_card(tmp_path / "nope.md")
    assert not ok
    assert "卡文件不存在" in msg


def test_new_card_template_has_annotation_section(tmp_path: Path):
    """新卡模板自带 `## 人工批注` 节与「执行体先读批注」红线（dry-run 不写盘）。"""
    result = subprocess.run(
        [
            "bash",
            str(_PROJECT_ROOT / "scripts" / "new-card.sh"),
            "--title",
            "人工批注模板",
            "--project",
            "ccc",
            "--dispatch-dir",
            str(tmp_path),
            "--dry-run",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "## 人工批注" in result.stdout
    assert "先读批注" in result.stdout
    assert "批注优先于正文" in result.stdout
    assert not list(tmp_path.rglob("*.md"))
