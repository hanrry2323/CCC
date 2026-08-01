"""Web 鉴权 API 契约测试 — /api/auth/*（窗口 A3，依赖 B2 后端）。

TestClient + monkeypatch。覆盖前端登录页对接契约：
- POST /api/auth/token：operator（ccc:ccc）/ viewer（CCC_HUB_VIEWER_PASS）换 Bearer
- GET  /api/auth/session：Bearer 有效 / 无效 token 401
- POST /api/auth/logout：吊销后 401（幂等）
- viewer token → 写端点 403（require_write 硬门）
- 无凭证 → 401（前端据此引导登录，不白屏不弹裸错误）
"""

from __future__ import annotations

import base64
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from chat_server.app import create_app  # noqa: E402

OPERATOR = ("ccc", "ccc")


@pytest.fixture()
def client(tmp_path, monkeypatch):
    chat_dir = tmp_path / "chat"
    chat_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("CCC_CHAT_DIR", str(chat_dir))
    monkeypatch.setenv("CCC_FLOW_EVENTS_LOG", str(tmp_path / "flow.jsonl"))
    from chat_server import config as hub_cfg
    from chat_server.services import flow_events as fe

    monkeypatch.setattr(hub_cfg, "CHAT_DIR", chat_dir)
    monkeypatch.setattr(fe, "events_log_path", lambda: tmp_path / "flow.jsonl")
    app = create_app()
    return TestClient(app)


def _basic_header(user: str, passwd: str) -> dict:
    token = base64.b64encode(f"{user}:{passwd}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def _bearer_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ── 登录换 token ──────────────────────────────────────────────────


def test_token_operator(client):
    r = client.post("/api/auth/token", headers=_basic_header(*OPERATOR))
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["role"] == "operator"
    assert d["scheme"] == "bearer"
    assert d["token"]
    assert d["ttl_s"] == 3600
    assert d["expires_at"]


def test_token_viewer_requires_pass(client, monkeypatch):
    monkeypatch.setenv("CCC_HUB_VIEWER_PASS", "vpass")
    r = client.post("/api/auth/token", headers=_basic_header("viewer", "vpass"))
    assert r.status_code == 200, r.text
    assert r.json()["role"] == "viewer"


def test_token_bad_creds_401(client):
    r = client.post("/api/auth/token", headers=_basic_header("ccc", "wrong"))
    assert r.status_code == 401
    assert r.headers.get("www-authenticate", "").lower().startswith("basic")


def test_token_no_creds_401(client):
    r = client.post("/api/auth/token", headers={})
    assert r.status_code == 401


# ── 会话探活 ─────────────────────────────────────────────────────


def test_session_bearer_valid(client):
    d = client.post("/api/auth/token", headers=_basic_header(*OPERATOR)).json()
    r = client.get("/api/auth/session", headers=_bearer_header(d["token"]))
    assert r.status_code == 200, r.text
    s = r.json()
    assert s["valid"] is True
    assert s["role"] == "operator"
    assert s["scheme"] == "bearer"


def test_session_invalid_token_401(client):
    r = client.get("/api/auth/session", headers=_bearer_header("bogus-token"))
    assert r.status_code == 401


# ── 登出吊销 ─────────────────────────────────────────────────────


def test_logout_revokes_token(client):
    d = client.post("/api/auth/token", headers=_basic_header(*OPERATOR)).json()
    h = _bearer_header(d["token"])
    assert client.post("/api/auth/logout", headers=h).status_code == 200
    # 吊销后 token 失效 → 401（重登即恢复）
    assert client.get("/api/auth/session", headers=h).status_code == 401


# ── 权限语义：viewer 写操作 403 ──────────────────────────────────


def test_viewer_write_forbidden_403(client, monkeypatch):
    monkeypatch.setenv("CCC_HUB_VIEWER_PASS", "vpass")
    d = client.post(
        "/api/auth/token", headers=_basic_header("viewer", "vpass")
    ).json()
    assert d["role"] == "viewer"
    # /api/ops/daily-review/run 是 require_write（ops.py:114，首行提权），viewer → 403
    r = client.post(
        "/api/ops/daily-review/run", headers=_bearer_header(d["token"]), json={}
    )
    assert r.status_code == 403, r.text
    assert "operator" in r.text.lower() or "privilege" in r.text.lower()


def test_operator_write_allowed_403_not_raised(client, monkeypatch):
    """operator token 不被 require_write 拒（403 只在 viewer；此处验证 operator 通过提权门）。"""
    monkeypatch.setenv("CCC_HUB_VIEWER_PASS", "vpass")
    d = client.post("/api/auth/token", headers=_basic_header(*OPERATOR)).json()
    assert d["role"] == "operator"
    r = client.post(
        "/api/ops/daily-review/run", headers=_bearer_header(d["token"]), json={}
    )
    assert r.status_code != 403, r.text
