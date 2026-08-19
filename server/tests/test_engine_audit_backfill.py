"""ccc006: engine 机审通过后自动落盘 ## 机审区。"""

from __future__ import annotations

from pathlib import Path

from server.engine.main import (
    _append_machine_audit_pass,
    _audit_output_indicates_pass,
    _card_machine_audit_passed,
)


def test_audit_output_pass_and_fail() -> None:
    assert _audit_output_indicates_pass("独立取证完成。\n机审通过\n停手。")
    assert _audit_output_indicates_pass("## 机审区\n\n机审：通过\n")
    assert not _audit_output_indicates_pass("机审：不通过\n缺 diff\n")
    assert not _audit_output_indicates_pass("")


def test_audit_output_ignores_prompt_fail_wording() -> None:
    """prompt 含「不通过写机审：不通过」不得盖过 child 后的「机审通过」。"""
    text = (
        "[ccc.engine] start work=xy001 phase=audit "
        "cmd=claude -p …不通过写「机审：不通过」并以非0退出…\n"
        "[ccc.engine] child_pid=9091\n"
        "各项一致，**机审通过**。现在把机审区写进绝对路径卡文件。\n"
    )
    assert _audit_output_indicates_pass(text)


def test_append_machine_audit_pass(tmp_path: Path) -> None:
    card = tmp_path / "ccc999-demo.md"
    card.write_text("# 卡\n\n> 状态：已回写\n\n## 回写区\n\nok\n", encoding="utf-8")
    assert not _card_machine_audit_passed(str(card))
    assert _append_machine_audit_pass(str(card), source="test", evidence="log says 机审通过")
    text = card.read_text(encoding="utf-8")
    assert "## 机审区" in text
    assert "结论：通过" in text
    assert _card_machine_audit_passed(str(card))


def test_append_replaces_existing_reject_section(tmp_path: Path) -> None:
    """已有「不通过」机审区 → 重审通过时替换旧区为「通过」（2026-08-20 事故修复）。

    事故：mx055 首审「不通过」（误判），重审通过时旧区阻塞落盘 → 重审链路断。
    新契约：不通过区必须可被通过区覆盖；通过区保持不重复写。
    """
    card = tmp_path / "ccc998-demo.md"
    card.write_text(
        "# 卡\n\n## 机审区\n\n**机审：不通过（维护区声明不实）**\n\n原因：x\n\n## 回写区\n\nok\n",
        encoding="utf-8",
    )
    assert not _card_machine_audit_passed(str(card))
    assert _append_machine_audit_pass(str(card), source="test", evidence="pass")
    text = card.read_text(encoding="utf-8")
    assert "机审：不通过" not in text
    assert "结论：通过" in text
    assert "## 回写区" in text
    assert _card_machine_audit_passed(str(card))


def test_append_keeps_existing_pass_section(tmp_path: Path) -> None:
    """已有「通过」机审区 → 不重复写，内容保持不变。"""
    card = tmp_path / "ccc997-demo.md"
    original = "# 卡\n\n## 机审区\n\n结论：通过\n证据：x\n\n## 回写区\n\nok\n"
    card.write_text(original, encoding="utf-8")
    assert _card_machine_audit_passed(str(card))
    assert _append_machine_audit_pass(str(card), source="test", evidence="pass")
    assert card.read_text(encoding="utf-8") == original


def test_audit_pass_with_result_format(tmp_path: Path) -> None:
    """clw011 事故回归：机审区用 `**机审**：<评审人>· 结果：**通过**` 格式也须识别为通过。"""
    card = tmp_path / "clw011-demo.md"
    card.write_text(
        "# 卡\n\n## 机审区\n\n"
        "**机审**：2017 机审席（claude）· 日期：2026-08-10 · 结果：**通过**\n\n"
        "### 审查摘要\n业务意图全部兑现，无原则性红线。\n",
        encoding="utf-8",
    )
    from server.engine.main import _card_machine_audit_passed

    assert _card_machine_audit_passed(str(card))


def test_audit_reject_with_result_format(tmp_path: Path) -> None:
    """「结果：不通过」格式同样被识别为不通过（不误判为通过）。"""
    card = tmp_path / "clw011-reject-demo.md"
    card.write_text(
        "# 卡\n\n## 机审区\n\n"
        "**机审**：2017 机审席（claude）· 日期：2026-08-10 · 结果：**不通过**\n\n"
        "### 审查摘要\n核心业务意图未实现。\n",
        encoding="utf-8",
    )
    from server.engine.main import _card_machine_audit_passed

    assert not _card_machine_audit_passed(str(card))


def test_append_rejects_invalid_audit_section(tmp_path, monkeypatch):
    """F1 挂钩：validate_audit_section 判非法时拒绝落盘，卡内容保持不变。

    engine 输出的机审区格式恒合法，故 monkeypatch 校验器触发拦截路径，
    钉死「挂钩存在且生效」不变量（防 F1 被误删 / section 模板被改坏）。
    """
    card = tmp_path / "ccc035-hook.md"
    card.write_text("# 卡\n\n> 状态：已回写\n\n## 回写区\n\nok\n", encoding="utf-8")
    original = card.read_text(encoding="utf-8")
    monkeypatch.setattr(
        "server.board.card_header.validate_audit_section",
        lambda _t: (False, "测试注入：非法格式"),
    )
    assert _append_machine_audit_pass(str(card), source="test", evidence="x") is False
    assert card.read_text(encoding="utf-8") == original  # 未落盘
