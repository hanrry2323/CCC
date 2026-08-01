"""auth rate-limit 桶 + 会话 token / 写操作提权门。"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))


@pytest.fixture(autouse=True)
def _reset_buckets():
    from chat_server import auth

    auth._auth_failures.clear()
    auth._auth_call_count = 0
    auth._sessions.clear()
    yield
    auth._auth_failures.clear()
    auth._sessions.clear()


def _client(monkeypatch, *, viewer_pass: str = ""):
    from fastapi.testclient import TestClient

    monkeypatch.setenv("CCC_CHAT_USER", "ccc")
    monkeypatch.setenv("CCC_CHAT_PASS", "ccc")
    if viewer_pass:
        monkeypatch.setenv("CCC_HUB_VIEWER_PASS", viewer_pass)
    monkeypatch.delenv("CCC_HUB_VIEWER_PASS", raising=False) if not viewer_pass else None
    monkeypatch.delenv("CCC_AGENT_PROXY", raising=False)
    from chat_server.app import create_app

    return TestClient(create_app())


# ── rate-limit 桶（round 1） ──


def test_sweep_removes_stale_ip_keeps_active():
    from chat_server import auth

    now = time.monotonic()
    auth._auth_failures["stale-ip"] = [now - auth._AUTH_WINDOW_S - 10]
    auth._auth_failures["active-ip"] = [now - 1]
    auth._sweep_stale_auth_buckets(now)

    assert "stale-ip" not in auth._auth_failures
    assert "active-ip" in auth._auth_failures


def test_sweep_removes_empty_buckets():
    from chat_server import auth

    now = time.monotonic()
    auth._auth_failures["empty-ip"] = []
    auth._sweep_stale_auth_buckets(now)
    assert "empty-ip" not in auth._auth_failures


def test_rate_limit_blocks_after_max_fails():
    from fastapi import HTTPException

    from chat_server import auth

    for _ in range(auth._AUTH_MAX_FAILS):
        auth._auth_failures["ip-x"].append(time.monotonic())
    with pytest.raises(HTTPException) as ei:
        auth._rate_limit_auth("ip-x")
    assert ei.value.status_code == 429


# ── 会话 token / 提权门（round 2） ──


def test_no_credential_401(monkeypatch):
    c = _client(monkeypatch)
    r = c.get("/api/auth/session")
    assert r.status_code == 401


def test_basic_read_ok_compat(monkeypatch):
    c = _client(monkeypatch)
    r = c.get("/api/auth/session", auth=("ccc", "ccc"))
    assert r.status_code == 200
    assert r.json()["role"] == "operator"


def test_token_issue_and_bearer_read(monkeypatch):
    c = _client(monkeypatch)
    r = c.post("/api/auth/token", auth=("ccc", "ccc"))
    assert r.status_code == 200
    data = r.json()
    assert data["role"] == "operator"
    assert data["scheme"] == "bearer"
    assert data["token"]
    r2 = c.get("/api/auth/session", headers={"Authorization": f"Bearer {data['token']}"})
    assert r2.status_code == 200
    assert r2.json()["role"] == "operator"


def test_bad_token_401(monkeypatch):
    c = _client(monkeypatch)
    r = c.get("/api/auth/session", headers={"Authorization": "Bearer not-a-token"})
    assert r.status_code == 401


def test_token_issue_bad_creds_401(monkeypatch):
    c = _client(monkeypatch)
    r = c.post("/api/auth/token", auth=("ccc", "wrong"))
    assert r.status_code == 401


def test_viewer_token_write_403_operator_ok(monkeypatch):
    """写操作提权门：viewer token → 403；operator token → 放行（进 body 校验）。"""
    c = _client(monkeypatch, viewer_pass="viewer-secret")
    v = c.post("/api/auth/token", auth=("viewer", "viewer-secret"))
    assert v.status_code == 200, v.text
    assert v.json()["role"] == "viewer"
    viewer_tok = v.json()["token"]

    # viewer 写 /api/desktop/transfer → 403（require_write 拦截）
    r = c.post(
        "/api/desktop/transfer",
        headers={"Authorization": f"Bearer {viewer_tok}"},
        json={},
    )
    assert r.status_code == 403

    # operator token 写 → 通过提权门（body 无效 → 400/422，而非 403）
    o = c.post("/api/auth/token", auth=("ccc", "ccc"))
    op_tok = o.json()["token"]
    r2 = c.post(
        "/api/desktop/transfer",
        headers={"Authorization": f"Bearer {op_tok}"},
        json={},
    )
    assert r2.status_code != 403


def test_basic_write_compat(monkeypatch):
    """legacy Basic（ccc:ccc）写 → 全权放行（过渡期兼容）。"""
    c = _client(monkeypatch)
    r = c.post("/api/desktop/transfer", auth=("ccc", "ccc"), json={})
    assert r.status_code != 403


def test_write_no_credential_401(monkeypatch):
    c = _client(monkeypatch)
    r = c.post("/api/desktop/transfer", json={})
    assert r.status_code == 401


def test_logout_revokes_token(monkeypatch):
    c = _client(monkeypatch)
    tok = c.post("/api/auth/token", auth=("ccc", "ccc")).json()["token"]
    assert c.get("/api/auth/session", headers={"Authorization": f"Bearer {tok}"}).status_code == 200
    r = c.post("/api/auth/logout", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    assert c.get("/api/auth/session", headers={"Authorization": f"Bearer {tok}"}).status_code == 401


def test_expired_token_401(monkeypatch):
    c = _client(monkeypatch)
    tok = c.post("/api/auth/token", auth=("ccc", "ccc")).json()["token"]
    from chat_server import auth

    auth._sessions[tok]["expires"] = time.monotonic() - 1
    assert c.get("/api/auth/session", headers={"Authorization": f"Bearer {tok}"}).status_code == 401
