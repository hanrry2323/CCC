"""自验收 / 席位归一（2026-08-07 改：谁开发谁验收）。"""

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


def test_self_acceptance() -> None:
    assert expected_acceptance("OpenCode") == "OpenCode"
    assert expected_acceptance("Claude Code") == "Claude Code"
    assert cross_acceptance_ok("OpenCode", "OpenCode")
    assert cross_acceptance_ok("Claude", "Claude Code")
    assert not cross_acceptance_ok("OpenCode", "Claude Code")
    assert not cross_acceptance_ok("OpenCode", "Codex")


def test_forbidden_acceptors() -> None:
    assert acceptance_issue("OpenCode", "Codex")
    assert acceptance_issue("OpenCode", "Cursor")
    assert "Codex" in (acceptance_issue("OpenCode", "Codex") or "")
    assert acceptance_issue("OpenCode", "OpenCode") is None
    assert acceptance_issue("Claude Code", "Claude Code") is None
    assert acceptance_issue("OpenCode", "Claude Code")  # 自验收下交叉不合法


def test_defaults() -> None:
    # 2026-08-23 随 DSH 化重构：产线执行/机审默认 DSH（P1-a）
    assert DEFAULT_EXECUTOR == "DSH"
    assert DEFAULT_ACCEPTANCE == "DSH"
    assert default_acceptance_for("DSH") == "DSH"
    assert default_acceptance_for("OpenCode") == "OpenCode"  # 兼容旧卡
    assert default_acceptance_for("Claude Code") == "Claude Code"  # 兼容旧卡
