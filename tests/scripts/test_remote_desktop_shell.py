"""Remote Desktop Shell — agent proxy + hub-config."""

import os

from fastapi.testclient import TestClient


def test_agent_base_default(monkeypatch):
    monkeypatch.delenv("CCC_DESKTOP_AGENT_URL", raising=False)
    monkeypatch.delenv("CCC_AGENT_URL", raising=False)
    from chat_server.routers import agent_proxy

    assert "7788" in agent_proxy._agent_base()


def test_hub_config_desktop_remote(monkeypatch):
    monkeypatch.setenv("CCC_CHAT_USER", "ccc")
    monkeypatch.setenv("CCC_CHAT_PASS", "ccc")
    monkeypatch.setenv("CCC_DESKTOP_AGENT_URL", "http://192.168.3.140:7788")
    monkeypatch.setenv(
        "CCC_DESKTOP_WORKSPACE_MAP",
        '{"ccc-demo":"/Users/apple/program/apps/ccc-demo"}',
    )
    from chat_server.app import create_app

    c = TestClient(create_app())
    r = c.get("/api/hub-config", auth=("ccc", "ccc"))
    assert r.status_code == 200
    d = r.json()
    assert d.get("desktop_remote") is True
    assert d.get("agent_proxy") == "/api/agent"
    assert d["workspace_map"].get("ccc-demo")


def test_remote_chat_gone(monkeypatch):
    monkeypatch.setenv("CCC_CHAT_USER", "ccc")
    monkeypatch.setenv("CCC_CHAT_PASS", "ccc")
    from chat_server.app import create_app

    c = TestClient(create_app())
    r = c.post("/api/remote-chat/stream", json={}, auth=("ccc", "ccc"))
    assert r.status_code in (404, 405)
