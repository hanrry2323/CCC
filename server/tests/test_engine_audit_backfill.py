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


def test_append_machine_audit_pass(tmp_path: Path) -> None:
    card = tmp_path / "ccc999-demo.md"
    card.write_text("# 卡\n\n> 状态：已回写\n\n## 回写区\n\nok\n", encoding="utf-8")
    assert not _card_machine_audit_passed(str(card))
    assert _append_machine_audit_pass(
        str(card), source="test", evidence="log says 机审通过"
    )
    text = card.read_text(encoding="utf-8")
    assert "## 机审区" in text
    assert "机审：通过" in text
    assert _card_machine_audit_passed(str(card))


def test_append_skips_existing_section(tmp_path: Path) -> None:
    card = tmp_path / "ccc998-demo.md"
    card.write_text(
        "# 卡\n\n## 机审区\n\n机审：不通过\n原因：x\n",
        encoding="utf-8",
    )
    assert not _append_machine_audit_pass(str(card), source="test", evidence="pass")
    assert "机审：不通过" in card.read_text(encoding="utf-8")
    assert "engine 自动落盘" not in card.read_text(encoding="utf-8")
