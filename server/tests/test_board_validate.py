"""卡头校验器测试（2026-08-04 新增；T54 增补新命名规则）。"""

from __future__ import annotations

from pathlib import Path

from server.board.validate import validate_cards


def _errors(issues: list) -> list:
    """只取阻断性问题（warn 提示不参与断言，旧卡提示是新常态）。"""
    return [i for i in issues if i.severity == "error"]


def _write_card(
    tmp: Path,
    name: str,
    state: str,
    with_body: bool = True,
    hdr_id: str | None = None,
) -> Path:
    p = tmp / name
    body = "\n## 目标\nx\n\n## 验收标准\nx\n\n## 回写区\n**执行体**：X · 日期：\n" if with_body else "\n## 目标\nx\n"
    p.write_text(
        f"# 任务卡 {hdr_id or name.split('.')[0]} · 测试\n"
        f"> 关联：TEST · 执行体：X · 验收：Codex · 状态：{state} · 日期：2026-08-04\n"
        f"{body}",
        encoding="utf-8",
    )
    return p


def test_valid_cards_pass(tmp_path: Path) -> None:
    _write_card(tmp_path, "T1-ok.md", "待分派")
    _write_card(tmp_path, "T2-ok.md", "已关闭")
    assert _errors(validate_cards(tmp_path)) == []


def test_invalid_state_reported(tmp_path: Path) -> None:
    _write_card(tmp_path, "T3-bad.md", "已完成X")
    issues = _errors(validate_cards(tmp_path))
    assert len(issues) == 1
    assert "状态值非法" in issues[0].reason


def test_missing_body_sections_reported(tmp_path: Path) -> None:
    _write_card(tmp_path, "T4-nobody.md", "已关闭", with_body=False)
    issues = _errors(validate_cards(tmp_path))
    reasons = " | ".join(i.reason for i in issues)
    assert "## 回写区" in reasons
    assert "## 验收标准" in reasons


def test_missing_header_key_reported(tmp_path: Path) -> None:
    p = tmp_path / "T5-nohdr.md"
    p.write_text("# 任务卡 T5 · 测试\n> 关联：TEST · 状态：待分派 · 日期：2026-08-04\n", encoding="utf-8")
    issues = _errors(validate_cards(tmp_path))
    assert any("执行体" in i.reason for i in issues)


class TestT54Naming:
    """T54 命名规则：新卡强制 <前缀><NNN>-<slug>.md 于 <前缀>/ 子目录；旧卡仅提示。"""

    def _new_card(self, tmp: Path, subdir: str, name: str, hdr_id: str | None = None) -> Path:
        (tmp / subdir).mkdir(parents=True, exist_ok=True)
        return _write_card(tmp / subdir, name, "待分派", hdr_id=hdr_id)

    def test_valid_new_style_card_pass(self, tmp_path: Path) -> None:
        self._new_card(tmp_path, "ccc", "ccc001-test.md", "ccc001")
        assert _errors(validate_cards(tmp_path)) == []

    def test_new_card_number_unique_across_prefixes(self, tmp_path: Path) -> None:
        """编号跨项目唯一：不同前缀同序号（ccc001 / qb001）不冲突。"""
        self._new_card(tmp_path, "ccc", "ccc001-test.md", "ccc001")
        self._new_card(tmp_path, "qb", "qb001-test.md", "qb001")
        assert _errors(validate_cards(tmp_path)) == []

    def test_new_card_duplicate_number_rejected(self, tmp_path: Path) -> None:
        self._new_card(tmp_path, "ccc", "ccc001-a.md", "ccc001")
        self._new_card(tmp_path, "ccc", "ccc001-b.md", "ccc001")
        issues = _errors(validate_cards(tmp_path))
        assert len(issues) == 1
        assert "ccc001 重复" in issues[0].reason

    def test_new_card_at_root_rejected(self, tmp_path: Path) -> None:
        _write_card(tmp_path, "ccc002-root.md", "待分派", hdr_id="ccc002")
        issues = _errors(validate_cards(tmp_path))
        assert len(issues) == 1
        assert "必须位于子目录" in issues[0].reason

    def test_new_card_wrong_subdir_rejected(self, tmp_path: Path) -> None:
        self._new_card(tmp_path, "qb", "ccc003-wrong.md", "ccc003")
        issues = _errors(validate_cards(tmp_path))
        assert len(issues) == 1
        assert "与前缀 'ccc' 不符" in issues[0].reason

    def test_unknown_prefix_rejected(self, tmp_path: Path) -> None:
        self._new_card(tmp_path, "xyz", "xyz001-foo.md", "xyz001")
        issues = _errors(validate_cards(tmp_path))
        assert len(issues) == 1
        assert "未知前缀" in issues[0].reason

    def test_header_number_mismatch_rejected(self, tmp_path: Path) -> None:
        self._new_card(tmp_path, "ccc", "ccc004-mismatch.md", "ccc005")
        issues = _errors(validate_cards(tmp_path))
        assert len(issues) == 1
        assert "与文件名" in issues[0].reason

    def test_old_card_only_warns(self, tmp_path: Path) -> None:
        """旧卡（根目录 T*.md）仅提示迁移，不阻断门禁。"""
        _write_card(tmp_path, "T90-test.md", "待分派")
        issues = validate_cards(tmp_path)
        assert _errors(issues) == []
        assert len(issues) == 1
        assert issues[0].severity == "warn"
        assert "旧卡" in issues[0].reason

    def test_non_card_doc_skipped(self, tmp_path: Path) -> None:
        """T-mapping.md 等说明文档（无卡头标题）不参与校验。"""
        _write_card(tmp_path, "T91.md", "待分派")
        (tmp_path / "T-mapping.md").write_text(
            "# T 卡 → 前缀映射\n说明文档，无 `# 任务卡` 卡头\n",
            encoding="utf-8",
        )
        issues = validate_cards(tmp_path)
        assert not any("T-mapping" in i.path for i in issues)

    def test_old_style_card_in_subdir_warns(self, tmp_path: Path) -> None:
        """旧卡样式文件位于子目录 → 提示（不阻断），要求子目录只放新规则卡。"""
        self._new_card(tmp_path, "ccc", "T92-old.md", "T92")
        issues = validate_cards(tmp_path)
        assert _errors(issues) == []
        assert any("位于子目录" in i.reason for i in issues)
