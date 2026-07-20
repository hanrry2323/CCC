"""get_relay_url / upstream health URL resolution"""
from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import _utils as u  # noqa: E402


def test_get_relay_url_prefers_anthropic(monkeypatch):
    monkeypatch.delenv("AGENT_PLANNER_BASE_URL", raising=False)
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://api.minimaxi.com/anthropic")
    assert u.get_relay_url() == "https://api.minimaxi.com/anthropic"


def test_get_relay_url_agent_planner_wins(monkeypatch):
    monkeypatch.setenv("AGENT_PLANNER_BASE_URL", "https://example.test/anthropic")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://api.minimaxi.com/anthropic")
    assert u.get_relay_url() == "https://example.test/anthropic"


def test_get_relay_url_default_minimax(monkeypatch):
    monkeypatch.delenv("AGENT_PLANNER_BASE_URL", raising=False)
    monkeypatch.delenv("ANTHROPIC_BASE_URL", raising=False)
    assert u.get_relay_url() == "https://api.minimaxi.com/anthropic"
