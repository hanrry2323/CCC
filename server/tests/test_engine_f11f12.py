"""F11+F12 合并验收测试（xy079 死循环根因，2026-09-19 外脑指令单）。

F11（主线阻塞）: 引擎 A2 代写 ``_replace_card_section`` 对「维护区」的 end 锚定
写死到 ``## 机审区``。xy079 卡节序偏离规范（维护区在回写区之前）时，切片
``text[:content_start] + maintenance + text[end:]`` 会把回写区/批注落实/人工批注
一并删除 → 卡头已置「已回写」却无 ``## 回写区`` → card-validate 拒提交 →
代写失败 → 打回 → 重派（死循环）。

F12（放大缺陷）: ``read_card_state`` 对 ``state:null`` 记录执行 ``out.pop(cid, None)``，
把整条卡记录（含 awaiting_human 挂人工冻结标记）删除 → F9 派发闸/F8 回收闸/F6
挂人工闸全失效 → 引擎按无冻结重派。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from server.engine.result_contract import _replace_card_section
from server.engine.runtime_state import clear_card_state, read_card_state, write_card_state


def _card_with_section_order(sections: list[tuple[str, str]]) -> str:
    """构造指定节序的卡文本（每节 ``## <name>`` + 空行 + 正文）。"""
    parts: list[str] = []
    for name, body in sections:
        parts.append(f"## {name}\n\n{body}")
    return "\n\n".join(parts)


# ── F11 ──────────────────────────────────────────────────────────────


class TestF11SectionOrderIndependent:
    """F11：_replace_card_section 节序无关锚定，非规范序卡不吞节。"""

    def test_xy079_nonstandard_order_sections_survive(self) -> None:
        """xy079 节序（维护区→批注落实→人工批注→回写区→机审区）代写后全保留。

        维护区替换不得越过回写区/批注落实/人工批注去锚定机审区。
        """
        sections = [
            ("目标", "目标正文"),
            ("维护区", "1. **方案同步**：[是] 说明"),
            ("批注落实", "落实批注正文"),
            ("人工批注", "（无批注时保留本节即可）"),
            ("回写区", "## 0. 卡标题复述\n\n标题"),
            ("机审区", "审核区正文"),
        ]
        text = _card_with_section_order(sections)

        # 复刻 main.py 真实代写次序：先回写区、再维护区（xy079 还带批注落实）
        updated = _replace_card_section(text, "回写区", "## 0. 卡标题复述\n\n标题")
        updated = _replace_card_section(updated, "维护区", "1. **方案同步**：[是] 更新")
        updated = _replace_card_section(updated, "批注落实", "落实批注更新")

        for keep in (
            "## 目标",
            "## 维护区",
            "## 批注落实",
            "## 人工批注",
            "## 回写区",
            "## 机审区",
        ):
            assert keep in updated, f"{keep} 被代写吞掉"
        # 维护区正文被替换为更新版
        assert "方案同步**：[是] 更新" in updated
        assert "回写区" in updated

    def test_standard_order_behavior_unchanged(self) -> None:
        """规范序（回写区→维护区→机审区）行为不回归：替换后回写区保留。"""
        sections = [
            ("目标", "目标正文"),
            ("回写区", "## 0. 卡标题复述\n\n标题"),
            ("维护区", "1. **方案同步**：[是] 说明"),
            ("机审区", "审核区正文"),
        ]
        text = _card_with_section_order(sections)

        updated = _replace_card_section(text, "回写区", "## 0. 卡标题复述\n\n标题")
        updated = _replace_card_section(updated, "维护区", "1. **方案同步**：[是] 更新")

        assert "## 回写区" in updated
        assert "## 维护区" in updated
        assert "## 机审区" in updated
        assert "方案同步**：[是] 更新" in updated
        # 机审区正文未被破坏
        assert "审核区正文" in updated

    def test_writeback_body_headings_not_appended_to_old_layer(self) -> None:
        """回写区硬锚 ## 维护区 保留（2026-09-08 多层互斥语义不回归）：

        回写正文含 `## 0.` 三级标题，若按 `\n## ` 边界截断会把旧层追加在新正文前。
        """
        sections = [
            ("目标", "目标正文"),
            ("回写区", "旧回写正文 ## 0. 旧层"),
            ("维护区", "维护正文"),
            ("机审区", "审核区正文"),
        ]
        text = _card_with_section_order(sections)

        updated = _replace_card_section(text, "回写区", "## 0. 卡标题复述\n\n新标题\n\n## 1. 探针输出\n\n探针")

        # 旧回写层不得残留在新正文前
        assert updated.index("## 回写区") < updated.index("## 维护区")
        assert "旧回写正文" not in updated.split("## 维护区")[0]

    def test_missing_heading_appends_section(self) -> None:
        """节不存在 → 追加到文件尾（不回归）。"""
        text = "## 目标\n\n目标正文"
        updated = _replace_card_section(text, "维护区", "维护正文")
        assert updated.rstrip().endswith("## 维护区\n\n维护正文")

    def test_section_without_trailing_neighbor_falls_back_to_eof(self) -> None:
        """目标节之后无相邻节 → end 回退文件尾（不丢尾）。"""
        sections = [("目标", "目标正文"), ("维护区", "维护正文")]
        text = _card_with_section_order(sections)
        updated = _replace_card_section(text, "维护区", "维护正文更新")
        assert updated.rstrip().endswith("## 维护区\n\n维护正文更新")
        assert "## 目标" in updated


# ── F12 ──────────────────────────────────────────────────────────────


class TestF12FreezeSticky:
    """F12：state:null 清除只清流程态，挂人工冻结标记保持粘性。"""

    def test_awaiting_human_survives_state_null(self, tmp_path: Path) -> None:
        """写 awaiting_human=True → 追加 state:null → state 被清、冻结标记保留。"""
        write_card_state(tmp_path, "xy079", awaiting_human=True, reject_budget_exhausted=True)
        # 引擎打回出口 clear_card_state 追加 state=null
        clear_card_state(tmp_path, "xy079")

        rt = read_card_state(tmp_path)
        assert "xy079" in rt, "卡记录不得被整体 pop 删除"
        rec = rt["xy079"]
        assert rec.get("state") is None
        assert rec.get("awaiting_human") is True, "挂人工冻结标记被误清"
        assert rec.get("reject_budget_exhausted") is True

    def test_plain_card_state_cleared_no_residue(self, tmp_path: Path) -> None:
        """正常卡（无冻结）：同记录 → state 被清、无残留（正向不回归）。"""
        write_card_state(tmp_path, "xy020", state="已回写", retry_count=1)
        clear_card_state(tmp_path, "xy020")

        rt = read_card_state(tmp_path)
        rec = rt.get("xy020")
        assert rec is None or rec.get("state") is None
        if rec is not None:
            assert rec.get("awaiting_human") is None
            assert rec.get("reject_budget_exhausted") is None

    def test_awaiting_human_false_explicitly_cleared(self, tmp_path: Path) -> None:
        """人审解冻后 awaiting_human=False 覆盖历史标记（人审通道仍可解冻）。"""
        write_card_state(tmp_path, "xy079", awaiting_human=True, reject_budget_exhausted=True)
        clear_card_state(tmp_path, "xy079")
        # 人审解冻：显式写 awaiting_human=False
        write_card_state(tmp_path, "xy079", state="待分派", retry_count=0, awaiting_human=False)

        rec = read_card_state(tmp_path)["xy079"]
        assert rec["state"] == "待分派"
        assert rec["awaiting_human"] is False
