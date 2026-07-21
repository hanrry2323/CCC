"""Security hardening regression (2026-07-19 adversarial review fixes)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS))


def test_redact_secrets_masks_tokens():
    from _secret_redact import redact_secrets

    raw = "API_KEY=sk-abcdefghijklmnopqrstuvwxyz123456 Bearer abc.def.ghi password=hunter2"
    out = redact_secrets(raw)
    assert "sk-abcdefghijklmnopqrstuvwxyz123456" not in out
    assert "Bearer ***" in out or "Bearer" in out
    assert "hunter2" not in out


def test_role_lock_blocks_dev_claude():
    from _role_lock import RoleLockViolation, assert_role_executor

    os.environ.pop("CCC_ROLE_LOCK_BYPASS", None)
    assert_role_executor("dev", "opencode")
    with pytest.raises(RoleLockViolation):
        assert_role_executor("dev", "claude-code")
    with pytest.raises(RoleLockViolation):
        assert_role_executor("product", "opencode")


def test_role_lock_bypass_warns_but_allows(caplog):
    import logging

    from _role_lock import assert_role_executor

    os.environ["CCC_ROLE_LOCK_BYPASS"] = "1"
    # _logger 配置后 ccc.propagate=False，需临时打开才能进 caplog（挂在 root）
    ccc_log = logging.getLogger("ccc")
    prev_propagate = ccc_log.propagate
    try:
        ccc_log.propagate = True
        with caplog.at_level(logging.WARNING, logger="ccc.role_lock"):
            assert_role_executor("dev", "claude-code")
        assert any("CCC_ROLE_LOCK_BYPASS" in r.message for r in caplog.records)
    finally:
        ccc_log.propagate = prev_propagate
        os.environ.pop("CCC_ROLE_LOCK_BYPASS", None)


def test_backlog_rejects_work_card(tmp_path):
    from _board_store import FileBoardStore

    os.environ.pop("CCC_ALLOW_BACKLOG_WORK", None)
    (tmp_path / ".ccc" / "board" / "backlog").mkdir(parents=True)
    store = FileBoardStore(tmp_path)
    ok = store.create_task(
        {
            "id": "inj-work-1",
            "title": "evil",
            "card_kind": "work",
            "schema_version": "1.2",
        },
        column="backlog",
    )
    assert ok is False
    # epic still ok
    ok2 = store.create_task(
        {
            "id": "epic-ok-1",
            "title": "good",
            "card_kind": "epic",
            "schema_version": "1.2",
        },
        column="backlog",
    )
    assert ok2 is True


def test_sanitized_env_strips_role_lock_bypass(monkeypatch):
    monkeypatch.setenv("CCC_ROLE_LOCK_BYPASS", "1")
    from _executor import _sanitized_env

    env = _sanitized_env()
    assert "CCC_ROLE_LOCK_BYPASS" not in env
