"""Dual-port shell — hub-config + agent_proxy opt-in."""

import os

from fastapi.testclient import TestClient


def test_hub_config_dual_port(monkeypatch):
    monkeypatch.setenv("CCC_CHAT_USER", "ccc")
    monkeypatch.setenv("CCC_CHAT_PASS", "ccc")
    monkeypatch.setenv("CCC_DESKTOP_AGENT_URL", "http://192.168.3.140:7788")
    monkeypatch.delenv("CCC_AGENT_PROXY", raising=False)
    monkeypatch.setenv(
        "CCC_DESKTOP_WORKSPACE_MAP",
        '{"ccc":"/Users/apple/program/CCC"}',
    )
    from chat_server.app import create_app

    c = TestClient(create_app())
    r = c.get("/api/hub-config", auth=("ccc", "ccc"))
    assert r.status_code == 200
    d = r.json()
    assert d.get("dual_port") is True
    assert d.get("agent_proxy") in (None, "", False)
    assert "7788" in (d.get("dialogue_url") or "")
    assert d["workspace_map"].get("ccc")
    assert "ccc-demo" not in (d.get("workspace_map") or {})
    # 默认不挂载 /api/agent
    assert c.get("/api/agent/health", auth=("ccc", "ccc")).status_code == 404


def test_agent_proxy_opt_in(monkeypatch):
    monkeypatch.setenv("CCC_CHAT_USER", "ccc")
    monkeypatch.setenv("CCC_CHAT_PASS", "ccc")
    monkeypatch.setenv("CCC_AGENT_PROXY", "1")
    monkeypatch.setenv("CCC_DESKTOP_AGENT_URL", "http://127.0.0.1:9")
    from chat_server.app import create_app

    c = TestClient(create_app())
    # 路由存在（上游不可达可能 502，但非 404）
    r = c.get("/api/agent/health", auth=("ccc", "ccc"))
    assert r.status_code != 404


def test_remote_chat_gone(monkeypatch):
    monkeypatch.setenv("CCC_CHAT_USER", "ccc")
    monkeypatch.setenv("CCC_CHAT_PASS", "ccc")
    from chat_server.app import create_app

    c = TestClient(create_app())
    r = c.post("/api/remote-chat/stream", json={}, auth=("ccc", "ccc"))
    assert r.status_code in (404, 405)


def test_agent_proxy_still_importable():
    from chat_server.routers import agent_proxy

    assert "7788" in agent_proxy._agent_base()
