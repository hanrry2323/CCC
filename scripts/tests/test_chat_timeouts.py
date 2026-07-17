"""Hub chat timeout helpers — idle + hard-max (no live Claude)."""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1]
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from chat_server.services.claude_client import resolve_chat_timeouts  # noqa: E402


def test_resolve_defaults():
    idle, hard = resolve_chat_timeouts(None, idle_default=600, max_default=1800)
    assert idle == 600
    assert hard == 1800


def test_legacy_client_180_promoted():
    """前端旧硬编码 180 不应拖死后端默认。"""
    idle, hard = resolve_chat_timeouts(180, idle_default=600, max_default=1800)
    assert idle == 600
    assert hard == 1800


def test_explicit_long_idle_kept():
    idle, hard = resolve_chat_timeouts(900, idle_default=600, max_default=1800)
    assert idle == 900
    assert hard == 1800


def test_idle_cannot_exceed_hard_cap_without_raising_hard():
    idle, hard = resolve_chat_timeouts(2000, idle_default=600, max_default=1800)
    # idle clamped to 3600 max in helper, but hard must be >= idle
    assert idle >= 1800
    assert hard >= idle
    assert hard <= 7200


def test_invalid_requested_falls_back():
    idle, hard = resolve_chat_timeouts("nope", idle_default=600, max_default=1800)  # type: ignore[arg-type]
    assert idle == 600
    assert hard == 1800
