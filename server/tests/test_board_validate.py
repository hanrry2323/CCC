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
        f"> 关联：TEST · 执行体：OpenCode · 验收：OpenCode · 状态：{state} · 日期：2026-08-07\n"
        f"{body}",
        encoding="utf-8",
    )
    return p


def test_valid_cards_pass(tmp_path: Path) -> None:
    _write_card(tmp_path, "T1-ok.md", "待分派")
    p = _write_card(tmp_path, "T2-ok.md", "已关闭")
    p.write_text(p.read_text(encoding="utf-8") + "\n## 验收区\n\n**合入批准** · 日期：2026-08-08\n- 判定：通过\n", encoding="utf-8")
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

    def test_index_reconciliation_detects_mismatch(self, tmp_path: Path) -> None:
        """测试索引对账：手动篡改索引后对账报错。"""
        p = self._new_card(tmp_path, "ccc", "ccc100-reconcile.md", "ccc100")
        issues = validate_cards(tmp_path)
        assert _errors(issues) == []

        from server.board.loader import get_index_path, load_index_file, save_index_file
        index_entries = load_index_file(tmp_path)
        assert "ccc100" in index_entries

        index_entries["ccc100"]["title"] = "Mismatched Title"
        save_index_file(index_entries, tmp_path)

        issues = validate_cards(tmp_path)
        errs = _errors(issues)
        assert len(errs) == 1
        assert "索引对账失败" in errs[0].reason
        assert "标题不一致" in errs[0].reason


def test_epic_task_validation(tmp_path: Path) -> None:
    # 1. Epic card with parent card -> Error (Epic cannot have parent)
    p_epic = tmp_path / "T10-epic.md"
    p_epic.write_text(
        "# 任务卡 T10 · Epic 测试\n"
        "> 关联：TEST · 执行体：X · 状态：待分派 · 日期：2026-08-04 · 类型：epic · 父卡：T11\n"
        "## 目标\nx\n\n## 验收标准\nx\n",
        encoding="utf-8"
    )
    issues = validate_cards(tmp_path)
    errs = _errors(issues)
    assert any("Epic 卡片不能指定父卡" in i.reason for i in errs)

    # 2. Task card with non-existent parent card -> Error
    p_task = tmp_path / "T11-task.md"
    p_task.write_text(
        "# 任务卡 T11 · Task 测试\n"
        "> 关联：TEST · 执行体：X · 状态：待分派 · 日期：2026-08-04 · 类型：task · 父卡：T999\n"
        "## 目标\nx\n\n## 验收标准\nx\n",
        encoding="utf-8"
    )
    p_epic.unlink()
    issues = validate_cards(tmp_path)
    errs = _errors(issues)
    assert any("父卡 T999 不存在" in i.reason for i in errs)

    # 3. Task card with parent card of different project -> Error
    p_parent = tmp_path / "T12-parent.md"
    p_parent.write_text(
        "# 任务卡 T12 · Parent\n"
        "> 关联：TEST · 执行体：X · 状态：待分派 · 日期：2026-08-04 · 类型：epic · 项目：ccc\n"
        "## 目标\nx\n\n## 验收标准\nx\n",
        encoding="utf-8"
    )
    p_child = tmp_path / "T13-child.md"
    p_child.write_text(
        "# 任务卡 T13 · Child\n"
        "> 关联：TEST · 执行体：X · 状态：待分派 · 日期：2026-08-04 · 类型：task · 父卡：T12 · 项目：qb\n"
        "## 目标\nx\n\n## 验收标准\nx\n",
        encoding="utf-8"
    )
    p_task.unlink()
    issues = validate_cards(tmp_path)
    errs = _errors(issues)
    assert any("项目 (ccc) 与当前卡片项目 (qb) 不一致" in i.reason for i in errs)


def test_acceptance_consistency(tmp_path: Path) -> None:
    # 1. 验收区 + 已关闭 -> 通过
    p1 = tmp_path / "T201-accepted-closed.md"
    p1.write_text(
        "# 任务卡 T201 · 验收关闭\n"
        "> 关联：TEST · 执行体：X · 状态：已关闭 · 日期：2026-08-04\n"
        "## 目标\nx\n\n## 验收标准\nx\n\n## 回写区\n**执行体**：X · 日期：2026-08-04\n\n"
        "## 验收区\n✅ 判定：通过\n",
        encoding="utf-8"
    )
    issues = validate_cards(tmp_path)
    assert _errors(issues) == []

    # 删除 index 以便下一次检测能重新生成
    idx_path = tmp_path / "cards.index.jsonl"
    if idx_path.is_file():
        idx_path.unlink()

    # 2. 验收区 + 待分派 -> 报错 (error)
    p2 = tmp_path / "T202-accepted-dispatched.md"
    p2.write_text(
        "# 任务卡 T202 · 验收待分派\n"
        "> 关联：TEST · 执行体：X · 状态：待分派 · 日期：2026-08-04\n"
        "## 目标\nx\n\n## 验收标准\nx\n\n"
        "## 验收区\n判定：通过\n",
        encoding="utf-8"
    )
    issues = validate_cards(tmp_path)
    errs = _errors(issues)
    assert len(errs) == 1
    assert "期望：'已关闭'" in errs[0].reason

    if idx_path.is_file():
        idx_path.unlink()

    # 3. 验收区超过 20 行含有 ✅ -> 不触发 (视为未验收)
    p2.write_text(
        "# 任务卡 T202 · 验收待分派\n"
        "> 关联：TEST · 执行体：X · 状态：待分派 · 日期：2026-08-04\n"
        "## 目标\nx\n\n## 验收标准\nx\n\n"
        "## 验收区\n" + "\n" * 21 + "✅\n",
        encoding="utf-8"
    )
    issues = validate_cards(tmp_path)
    assert _errors(issues) == []


def test_self_acceptance_new_card(tmp_path: Path) -> None:
    """新卡自验收：执行体=验收；Codex 验收 = error；交叉（OpenCode→Claude）= error。"""
    sub = tmp_path / "ccc"
    sub.mkdir()
    bad = sub / "ccc900-self-bad.md"
    bad.write_text(
        "# 任务卡 ccc900 · 自验收坏\n"
        "> 关联：TEST · 执行体：OpenCode · 验收：Codex · 状态：待分派 · 项目：ccc · 日期：2026-08-06\n"
        "## 目标\nx\n\n## 验收标准\nx\n",
        encoding="utf-8",
    )
    errs = _errors(validate_cards(tmp_path))
    assert any("Codex" in i.reason for i in errs)

    bad.unlink()
    cross = sub / "ccc901-cross-now-invalid.md"
    cross.write_text(
        "# 任务卡 ccc901 · 交叉不再合法\n"
        "> 关联：TEST · 执行体：OpenCode · 验收：Claude Code · 状态：待分派 · 项目：ccc · 日期：2026-08-07\n"
        "## 目标\nx\n\n## 验收标准\nx\n",
        encoding="utf-8",
    )
    issues = validate_cards(tmp_path)
    assert any(
        i.severity == "warn" and "验收不匹配" in i.reason for i in issues
    ), "交叉不匹配应提示自验收规则（不阻断）"

    cross.unlink()
    good = sub / "ccc902-self-ok.md"
    good.write_text(
        "# 任务卡 ccc902 · 自验收好\n"
        "> 关联：TEST · 执行体：OpenCode · 验收：OpenCode · 状态：待分派 · 项目：ccc · 日期：2026-08-07\n"
        "## 目标\nx\n\n## 验收标准\nx\n",
        encoding="utf-8",
    )
    idx = tmp_path / "cards.index.jsonl"
    if idx.is_file():
        idx.unlink()
    assert _errors(validate_cards(tmp_path)) == []


def test_qh_prefix_forbidden(tmp_path: Path) -> None:
    """QuantHive 前缀 qh 禁止新卡走 CCC。"""
    sub = tmp_path / "qh"
    sub.mkdir()
    card = sub / "qh001-banned.md"
    card.write_text(
        "# 任务卡 qh001 · 禁止\n"
        "> 关联：TEST · 执行体：OpenCode · 验收：Claude Code · 状态：待分派 · 项目：qh · 日期：2026-08-06\n"
        "## 目标\nx\n\n## 验收标准\nx\n",
        encoding="utf-8",
    )
    errs = _errors(validate_cards(tmp_path))
    assert any("禁止" in i.reason or "QuantHive" in i.reason for i in errs)


class TestAnnotationGate:
    """老板批注（最高开发指令）：已执行卡必须带「## 批注落实」。"""

    def _card(self, tmp: Path, state: str, annotation: str = "", fulfillment: bool = False) -> Path:
        body = "\n## 目标\nx\n\n## 验收标准\nx\n"
        if annotation:
            body += f"\n## 人工批注\n\n{annotation}\n"
        body += "\n## 回写区\n**执行体**：X · 日期：\n"
        if fulfillment:
            body += "\n## 批注落实\n已按批注修订：x\n"
        p = tmp / f"T-{state}-{len(annotation)}-{fulfillment}.md"
        p.write_text(
            f"# 任务卡 T · 测试\n"
            f"> 关联：TEST · 执行体：OpenCode · 验收：Claude Code · 状态：{state} · 日期：2026-08-07\n"
            f"{body}",
            encoding="utf-8",
        )
        return p

    def test_annotated_written_back_requires_fulfillment(self, tmp_path: Path) -> None:
        self._card(tmp_path, "已回写", annotation="把接口改成 POST")
        issues = _errors(validate_cards(tmp_path))
        assert any("批注落实" in i.reason for i in issues)

    def test_annotated_with_fulfillment_passes(self, tmp_path: Path) -> None:
        self._card(tmp_path, "已回写", annotation="把接口改成 POST", fulfillment=True)
        assert _errors(validate_cards(tmp_path)) == []

    def test_placeholder_annotation_not_required(self, tmp_path: Path) -> None:
        self._card(
            tmp_path,
            "已回写",
            annotation="（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）",
        )
        assert _errors(validate_cards(tmp_path)) == []

    def test_rejected_card_annotation_waits_execution(self, tmp_path: Path) -> None:
        """打回卡有批注但未重跑 → 不要求批注落实（待执行后机审把关）。"""
        self._card(tmp_path, "打回", annotation="把接口改成 POST")
        assert _errors(validate_cards(tmp_path)) == []
