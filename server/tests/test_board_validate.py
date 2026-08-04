"""卡头校验器测试（2026-08-04）。"""

from __future__ import annotations

from pathlib import Path

from server.board.validate import validate_cards


def _write_card(tmp: Path, name: str, state: str, with_body: bool = True) -> Path:
    p = tmp / name
    body = "\n## 目标\nx\n\n## 验收标准\nx\n\n## 回写区\n**执行体**：X · 日期：\n" if with_body else "\n## 目标\nx\n"
    p.write_text(
        f"# 任务卡 {name.split('.')[0]} · 测试\n"
        f"> 关联：TEST · 执行体：X · 验收：Codex · 状态：{state} · 日期：2026-08-04\n"
        f"{body}",
        encoding="utf-8",
    )
    return p


def test_valid_cards_pass(tmp_path: Path) -> None:
    _write_card(tmp_path, "T1-ok.md", "待分派")
    _write_card(tmp_path, "T2-ok.md", "已关闭")
    assert validate_cards(tmp_path) == []


def test_invalid_state_reported(tmp_path: Path) -> None:
    _write_card(tmp_path, "T3-bad.md", "已完成X")
    issues = validate_cards(tmp_path)
    assert len(issues) == 1
    assert "状态值非法" in issues[0].reason


def test_missing_body_sections_reported(tmp_path: Path) -> None:
    _write_card(tmp_path, "T4-nobody.md", "已关闭", with_body=False)
    issues = validate_cards(tmp_path)
    reasons = " | ".join(i.reason for i in issues)
    assert "## 回写区" in reasons
    assert "## 验收标准" in reasons


def test_missing_header_key_reported(tmp_path: Path) -> None:
    p = tmp_path / "T5-nohdr.md"
    p.write_text("# 任务卡 T5 · 测试\n> 关联：TEST · 状态：待分派 · 日期：2026-08-04\n", encoding="utf-8")
    issues = validate_cards(tmp_path)
    assert any("执行体" in i.reason for i in issues)
