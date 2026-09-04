"""ccc062: Q1 校验收紧为 AND——方案同步[是]必须同时满足「方案已推进」且「关联卡含本卡」。

场景：
1. 方案已推进 + 关联卡含本卡 → 通过
2. 方案未推进（草案）但关联卡含本卡 → 打回（缺状态）
3. 方案已推进但关联卡不含本卡 → 打回（缺关联卡）
4. 勾选[否] + 卡头有方案编号 + 说明未解释 → 提示
"""

from pathlib import Path
from unittest.mock import patch

from server.board.docgate import verify_maintenance


def _make_env(tmp_path: Path, plan_status: str, plan_cards: str, card_id: str = "ccc101") -> Path:
    """造一个最小合规卡环境：卡 + 方案文件 + 维护区四问 + 引用工件。"""
    card_file = tmp_path / "docs" / "dispatch" / "ccc" / "ccc101-x.md"
    card_file.parent.mkdir(parents=True, exist_ok=True)
    card_file.write_text(
        f"# 任务卡 {card_id}\n"
        "> 关联：ccc-plan-011 · 执行体：OpenCode · 状态：已回写\n"
        "## 维护区\n"
        "1. **方案同步**：[是]\n"
        "   - 说明：方案已推进并关联本卡\n"
        "2. **教训沉淀**：[无]\n"
        "   - 说明：无新教训\n"
        "3. **档案/README**：[否]\n"
        "   - 说明：无结构变化\n"
        "4. **线路图**：[否]\n"
        "   - 说明：无线路变化\n",
        encoding="utf-8",
    )

    plan_file = tmp_path / "docs" / "projects" / "ccc" / "plans" / "011-x.md"
    plan_file.parent.mkdir(parents=True, exist_ok=True)
    plan_file.write_text(
        "# 方案\n"
        f"> 状态：{plan_status}\n"
        f"> 关联卡：{plan_cards}\n",
        encoding="utf-8",
    )

    (tmp_path / "docs" / "notes").mkdir(parents=True, exist_ok=True)
    return card_file


def test_q1_and_both_satisfied(tmp_path: Path):
    """方案已推进 + 关联卡含本卡 → 通过。"""
    card_file = _make_env(tmp_path, plan_status="部分执行", plan_cards="ccc101")
    with patch("server.board.docgate.get_modified_files", return_value=[]):
        ok, problems = verify_maintenance(card_file, tmp_path)
    assert ok is True, problems


def test_q1_and_missing_status(tmp_path: Path):
    """关联卡含本卡但方案未推进（草案）→ 打回（AND：状态也须满足）。"""
    card_file = _make_env(tmp_path, plan_status="草案", plan_cards="ccc101")
    with patch("server.board.docgate.get_modified_files", return_value=[]):
        ok, problems = verify_maintenance(card_file, tmp_path)
    assert ok is False
    assert any("状态为「草案」" in p for p in problems)


def test_q1_and_missing_card(tmp_path: Path):
    """方案已推进但关联卡不含本卡 → 打回（AND：关联卡也须满足）。"""
    card_file = _make_env(tmp_path, plan_status="部分执行", plan_cards="ccc200")
    with patch("server.board.docgate.get_modified_files", return_value=[]):
        ok, problems = verify_maintenance(card_file, tmp_path)
    assert ok is False
    assert any("不包含本卡 ID「ccc101」" in p for p in problems)


def test_blank_checkbox_choice_is_rejected(tmp_path: Path):
    """空格 checkbox 不得被当作合法勾选。"""
    card_file = _make_env(tmp_path, plan_status="部分执行", plan_cards="ccc101")
    text = card_file.read_text(encoding="utf-8").replace("1. **方案同步**：[是]", "1. **方案同步**：[ ]")
    card_file.write_text(text, encoding="utf-8")
    with patch("server.board.docgate.get_modified_files", return_value=[]):
        ok, problems = verify_maintenance(card_file, tmp_path)
    assert ok is False
    assert any("未正确勾选" in problem for problem in problems)


def test_q1_no_choice_with_plan_explained(tmp_path: Path):
    """勾选[否] + 卡头有方案编号 + 说明里解释 → 通过（不硬拒绝）。"""
    card_file = _make_env(tmp_path, plan_status="草案", plan_cards="")
    text = card_file.read_text(encoding="utf-8")
    text = text.replace(
        "1. **方案同步**：[是]\n   - 说明：方案已推进并关联本卡",
        "1. **方案同步**：[否]\n   - 说明：无直接关联方案，不涉及推进",
    )
    card_file.write_text(text, encoding="utf-8")
    with patch("server.board.docgate.get_modified_files", return_value=[]):
        ok, problems = verify_maintenance(card_file, tmp_path)
    assert ok is True, problems
