"""人工批注 sentinel 统一解析回归测试。"""

from __future__ import annotations

import pytest

from server.board.annotation import classify_annotation, requires_fulfillment


@pytest.mark.parametrize(
    "value",
    [
        "",
        "（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）",
        "无批注",
        "（无批注。）",
    ],
)
def test_annotation_sentinels_are_none(value: str) -> None:
    text = f"# 任务卡 tst-p1\n\n## 人工批注\n\n{value}\n\n## 回写区\n"
    assert classify_annotation(text) == "NONE"
    assert requires_fulfillment(text) is False


def test_real_annotation_requires_fulfillment() -> None:
    text = "# 任务卡 tst-p1\n\n## 人工批注\n\n改成 POST 接口。\n"
    assert classify_annotation(text) == "REAL"
    assert requires_fulfillment(text) is True


def test_real_annotation_with_fulfillment_does_not_require_it() -> None:
    text = (
        "# 任务卡 tst-p1\n\n## 人工批注\n\n改成 POST 接口。\n\n"
        "## 批注落实\n\n已按要求修改。\n"
    )
    assert classify_annotation(text) == "REAL"
    assert requires_fulfillment(text) is False
