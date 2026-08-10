

class TestV6AuditCommitPin:
    """V6：机审信封钉被审 commit（approve 侧据此拦机审后漂移）。"""

    def test_pin_audit_commit(self, tmp_path: Path) -> None:
        from server.engine.main import _pin_audit_commit

        card = tmp_path / "w.md"
        card.write_text(
            "## 回写区\nx\n\n## 机审区\n\n机审：通过\n来源：engine-audit\n证据：ok\n",
            encoding="utf-8",
        )
        assert _pin_audit_commit(str(card), "abcdef1234567890abcdef") is True
        text = card.read_text(encoding="utf-8")
        assert "机审：通过（被审 abcdef123456）" in text

    def test_pin_idempotent(self, tmp_path: Path) -> None:
        from server.engine.main import _pin_audit_commit

        card = tmp_path / "w.md"
        card.write_text(
            "## 机审区\n\n机审：通过（被审 abcdef123456）\n", encoding="utf-8"
        )
        assert _pin_audit_commit(str(card), "deadbeef00") is True
        text = card.read_text(encoding="utf-8")
        assert text.count("被审 ") == 1
        assert "deadbeef00" not in text

    def test_pin_no_sha_noop(self, tmp_path: Path) -> None:
        from server.engine.main import _pin_audit_commit

        card = tmp_path / "w.md"
        card.write_text("## 机审区\n\n机审：通过\n", encoding="utf-8")
        assert _pin_audit_commit(str(card), "") is True
        assert card.read_text(encoding="utf-8").count("被审 ") == 0

    def test_pin_no_verdict_noop(self, tmp_path: Path) -> None:
        from server.engine.main import _pin_audit_commit

        card = tmp_path / "w.md"
        card.write_text("## 机审区\n\n机审：不通过\n", encoding="utf-8")
        assert _pin_audit_commit(str(card), "abcdef123456") is True
        assert card.read_text(encoding="utf-8").count("被审 ") == 0
