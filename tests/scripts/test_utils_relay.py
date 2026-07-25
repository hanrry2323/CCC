"""get_relay_url / upstream health URL resolution"""
from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import _utils as u  # noqa: E402

# 三档契约:不用特定上游 URL 作 fixture；用通用的 relay URL 替代


def test_get_relay_url_prefers_anthropic(monkeypatch):
    monkeypatch.delenv("AGENT_PLANNER_BASE_URL", raising=False)
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "http://127.0.0.1:4000/anthropic")
    assert u.get_relay_url() == "http://127.0.0.1:4000/anthropic"


def test_get_relay_url_agent_planner_wins(monkeypatch):
    monkeypatch.setenv("AGENT_PLANNER_BASE_URL", "https://example.test/anthropic")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "http://127.0.0.1:4000/anthropic")
    assert u.get_relay_url() == "https://example.test/anthropic"


def test_get_relay_url_default(monkeypatch):
    monkeypatch.delenv("AGENT_PLANNER_BASE_URL", raising=False)
    monkeypatch.delenv("ANTHROPIC_BASE_URL", raising=False)
    url = u.get_relay_url()
    assert url, "should return a non-empty URL"
