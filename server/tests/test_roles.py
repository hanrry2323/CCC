"""交叉验收 / 席位归一。"""

from __future__ import annotations

from server.board.roles import (
    DEFAULT_ACCEPTANCE,
    DEFAULT_EXECUTOR,
    acceptance_issue,
    cross_acceptance_ok,
    default_acceptance_for,
    expected_acceptance,
    normalize_tool,
)


def test_normalize_aliases() -> None:
    assert normalize_tool("Claude") == "Claude Code"
    assert normalize_tool("claude code") == "Claude Code"
    assert normalize_tool("OpenCode") == "OpenCode"
    assert normalize_tool("Codex") == "Codex"


def test_cross_pair() -> None:
    assert expected_acceptance("OpenCode") == "Claude Code"
    assert expected_acceptance("Claude Code") == "OpenCode"
    assert cross_acceptance_ok("OpenCode", "Claude Code")
    assert cross_acceptance_ok("Claude", "OpenCode")
    assert not cross_acceptance_ok("OpenCode", "OpenCode")
    assert not cross_acceptance_ok("OpenCode", "Codex")


def test_forbidden_acceptors() -> None:
    assert acceptance_issue("OpenCode", "Codex")
    assert acceptance_issue("OpenCode", "Cursor")
    assert "Codex" in (acceptance_issue("OpenCode", "Codex") or "")
    assert acceptance_issue("OpenCode", "Claude Code") is None
    assert acceptance_issue("Claude Code", "OpenCode") is None


def test_defaults() -> None:
    assert DEFAULT_EXECUTOR == "OpenCode"
    assert DEFAULT_ACCEPTANCE == "Claude Code"
    assert default_acceptance_for("OpenCode") == "Claude Code"
    assert default_acceptance_for("Claude Code") == "OpenCode"
