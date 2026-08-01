"""7788 对话口账号密码鉴权契约测试（窗口 K，依赖 sidecar 鉴权模块）。

TestClient 挂 AGENT_AUTH_ROUTER 到 mini app（不 import sidecar 脚本，避免启动副作用）。
覆盖验收：
- 未配置凭证 → login 503「未配置登录凭证」（绝不回退默认口令）
- 错密码 401；对密码换 token → /api/auth/agent-session 200（对话接口经 authorize 授权）
- 无 token / 错 token / 过期 token → 401
- logout 吊销后 401
- 登录限速（20 次失败 → 429）
- authorize_agent_request：session / legacy（Desktop 兼容窗口）/ None
- 凭证优先级：env > 文件；缺失 → None
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

fastapi = pytest.importorskip("fastapi")
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from _agent_auth import (  # noqa: E402
    AGENT_AUTH_ROUTER,
    _LOGIN_MAX_FAILS,
    _sessions,
    agent_credentials,
    authorize_agent_request,
    credentials_configured,
    issue_agent_session,
    reset_agent_auth_state,
    session_ttl,
)

USER = "boss"
PASS = "s3cret-account"


@pytest.fixture(autouse=True)
def _reset():
    reset_agent_auth_state()
    yield
    reset_agent_auth_state()


@pytest.fixture()
def client(tmp_path, monkeypatch):
    # 指向不存在文件 → 未配置（不读真实 ~/.ccc/agent-auth.json）；已配置用例另设 env
    monkeypatch.setenv("CCC_AGENT_AUTH_FILE", str(tmp_path / "no-agent-auth.json"))
    monkeypatch.delenv("CCC_AGENT_AUTH_USER", raising=False)
    monkeypatch.delenv("CCC_AGENT_AUTH_PASS", raising=False)
    app = FastAPI()
    app.include_router(AGENT_AUTH_ROUTER)
    return TestClient(app)


def _configured(monkeypatch):
    monkeypatch.setenv("CCC_AGENT_AUTH_USER", USER)
    monkeypatch.setenv("CCC_AGENT_AUTH_PASS", PASS)


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ── 未配置凭证 → 拒绝登录并明确提示 ────────────────────────


def test_login_unconfigured_503(client):
    r = client.post("/api/auth/agent-login", json={"user": USER, "password": PASS})
    assert r.status_code == 503, r.text
    assert "未配置登录凭证" in r.json()["detail"]


def test_credentials_unconfigured_is_none(client):
    assert credentials_configured() is False
    assert agent_credentials() is None


# ── 登录换 token ──────────────────────────────────────────


def test_login_wrong_password_401(client, monkeypatch):
    _configured(monkeypatch)
    r = client.post("/api/auth/agent-login", json={"user": USER, "password": "wrong"})
    assert r.status_code == 401
    assert r.json()["detail"] == "账号或密码错误"


def test_login_ok_and_session_probe(client, monkeypatch):
    _configured(monkeypatch)
    r = client.post("/api/auth/agent-login", json={"user": USER, "password": PASS})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["role"] == "operator"
    assert d["token"]
    assert d["expires_in"] == session_ttl()
    s = client.get("/api/auth/agent-session", headers=_bearer(d["token"]))
    assert s.status_code == 200, s.text
    assert s.json()["valid"] is True


def test_chat_endpoint_authorization_flow(client, monkeypatch):
    """正确密码换 token → 对话接口授权（session 方案）；无 token → 未授权（sidecar 回 401）。"""
    _configured(monkeypatch)
    tok = client.post("/api/auth/agent-login", json={"user": USER, "password": PASS}).json()["token"]
    assert authorize_agent_request(f"Bearer {tok}", "", legacy_token="") == "session"
    assert authorize_agent_request("", "", legacy_token="") is None


# ── 无 / 错 / 过期 token → 401 ────────────────────────────


def test_session_no_token_401(client):
    assert client.get("/api/auth/agent-session").status_code == 401


def test_session_bad_token_401(client):
    r = client.get("/api/auth/agent-session", headers=_bearer("bogus-token"))
    assert r.status_code == 401


def test_session_expired_401(client, monkeypatch):
    _configured(monkeypatch)
    tok = client.post("/api/auth/agent-login", json={"user": USER, "password": PASS}).json()["token"]
    _sessions[tok]["expires"] = time.monotonic() - 1
    r = client.get("/api/auth/agent-session", headers=_bearer(tok))
    assert r.status_code == 401


# ── 登出吊销 ──────────────────────────────────────────────


def test_logout_revokes_token(client, monkeypatch):
    _configured(monkeypatch)
    tok = client.post("/api/auth/agent-login", json={"user": USER, "password": PASS}).json()["token"]
    h = _bearer(tok)
    assert client.post("/api/auth/agent-logout", headers=h).status_code == 200
    assert client.get("/api/auth/agent-session", headers=h).status_code == 401


# ── 登录限速 ──────────────────────────────────────────────


def test_login_rate_limit_429(client, monkeypatch):
    _configured(monkeypatch)
    for _ in range(_LOGIN_MAX_FAILS):
        r = client.post("/api/auth/agent-login", json={"user": USER, "password": "wrong"})
        assert r.status_code == 401
    r = client.post("/api/auth/agent-login", json={"user": USER, "password": "wrong"})
    assert r.status_code == 429


# ── authorize_agent_request 纯函数 ────────────────────────


def test_authorize_no_headers_none():
    assert authorize_agent_request("", "", "") is None


def test_authorize_session_scheme():
    tok = issue_agent_session()
    assert authorize_agent_request(f"Bearer {tok}", "", "") == "session"


def test_authorize_legacy_compat_scheme():
    # Desktop 兼容窗口：旧共享密钥经 Authorization 或 X-CCC-Agent-Token 均可
    assert authorize_agent_request("Bearer old-secret", "", "old-secret") == "legacy"
    assert authorize_agent_request("", "old-secret", "old-secret") == "legacy"


def test_authorize_legacy_mismatch_none():
    assert authorize_agent_request("Bearer nope", "", "old-secret") is None


def test_authorize_expired_session_none():
    tok = issue_agent_session()
    _sessions[tok]["expires"] = time.monotonic() - 1
    assert authorize_agent_request(f"Bearer {tok}", "", "") is None


# ── 凭证优先级：env > 文件；缺失 → None ───────────────────


def test_credentials_env_precedence(tmp_path, monkeypatch):
    monkeypatch.setenv("CCC_AGENT_AUTH_FILE", str(tmp_path / "agent-auth.json"))
    (tmp_path / "agent-auth.json").write_text(
        json.dumps({"user": "fileuser", "password": "filepass"}), encoding="utf-8"
    )
    monkeypatch.setenv("CCC_AGENT_AUTH_USER", "envuser")
    monkeypatch.setenv("CCC_AGENT_AUTH_PASS", "envpass")
    assert agent_credentials() == ("envuser", "envpass")


def test_credentials_from_file(tmp_path, monkeypatch):
    monkeypatch.setenv("CCC_AGENT_AUTH_FILE", str(tmp_path / "agent-auth.json"))
    monkeypatch.delenv("CCC_AGENT_AUTH_USER", raising=False)
    monkeypatch.delenv("CCC_AGENT_AUTH_PASS", raising=False)
    (tmp_path / "agent-auth.json").write_text(
        json.dumps({"user": "fileuser", "password": "filepass"}), encoding="utf-8"
    )
    assert agent_credentials() == ("fileuser", "filepass")


def test_credentials_file_missing_none(tmp_path, monkeypatch):
    monkeypatch.setenv("CCC_AGENT_AUTH_FILE", str(tmp_path / "nope.json"))
    monkeypatch.delenv("CCC_AGENT_AUTH_USER", raising=False)
    monkeypatch.delenv("CCC_AGENT_AUTH_PASS", raising=False)
    assert agent_credentials() is None
