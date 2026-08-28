"""test_web_p0_auth — P0 暴露面止血 + 凭证文件回退回归测试（2026-08-29）。

对应 ccc-frontend-audit-20260829 P0 分期，覆盖：
- 免登录模式（CCC_WEB_AUTH_REQUIRED=0）下的读闸：/wall/api/*、/ops/ports、
  /ops/portals、/ops/services、/projects/*/threads 无 token 一律 401，带 token 200；
- SSE 端点 ?token= 携带方式（EventSource 无法带 Authorization 头）；
- ~/.ccc/web-auth.txt 凭证回退（单行口令 / user:pass），/session 可正常签发；
- 零消费遗留路由下线：/dsh/workspaces、/dsh/sessions/<id> 返回 404；
- /config 公开面收敛：不再广播 chat_bridge_url。

环境：与 test_http_api 不同，本模块在免登录模式下跑（读闸与全量鉴权是两层）。
"""

from __future__ import annotations

import hashlib
import json
import os
from http.client import HTTPConnection
from urllib.parse import urlparse

import pytest

from server.web.server import create_server

_FILE_USER = "fileuser"
_FILE_PASS = "filepass-安全P0"


@pytest.fixture(scope="module")
def free_server():
    """免登录模式 HTTP 服务（随机端口）。_auth_required 请求时读 env，
    各用例以 monkeypatch 控制模式，不需重启服务。"""
    import threading
    import time

    server = create_server(host="127.0.0.1", port=0)
    addr = server.server_address
    base_url = f"http://{addr[0]}:{addr[1]}"
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    for _ in range(10):
        try:
            conn = HTTPConnection(addr[0], addr[1], timeout=2)
            conn.request("GET", "/health")
            conn.getresponse().read()
            conn.close()
            break
        except (ConnectionRefusedError, OSError):
            time.sleep(0.1)
    else:
        server.server_close()
        pytest.fail("free-mode API 服务启动失败")
    yield base_url
    server.shutdown()
    server.server_close()


def _request(base_url: str, method: str, path: str, body: dict | None = None, headers: dict | None = None):
    parsed = urlparse(base_url)
    conn = HTTPConnection(parsed.hostname, parsed.port, timeout=10)
    try:
        payload = json.dumps(body).encode() if body is not None else None
        conn.request(
            method,
            path,
            body=payload,
            headers={"Content-Type": "application/json", **(headers or {})},
        )
        resp = conn.getresponse()
        data = resp.read()
        return resp.status, resp.headers, data
    finally:
        conn.close()


def _json(data: bytes) -> dict:
    return json.loads(data.decode("utf-8"))


def _login(base_url: str, username: str, password: str):
    return _request(base_url, "POST", "/session", {"username": username, "password": password})


class TestReadGateFreeMode:
    """免登录模式下敏感读端点必须持 token（audit 报告 §5 暴露面封堵）。"""

    @pytest.fixture(autouse=True)
    def _free_mode(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("CCC_WEB_AUTH_REQUIRED", "0")
        # 确保走 env 凭证（conftest 已注入），读闸签发 token 用
        monkeypatch.setenv("CCC_WEB_USERNAME", "testuser")
        monkeypatch.setenv("CCC_WEB_PASSWORD_HASH", hashlib.sha256(b"testpass").hexdigest())

    def _token(self, free_server) -> str:
        status, _, data = _login(free_server, "testuser", "testpass")
        assert status == 200, data
        return _json(data)["token"]

    def test_ops_ports_401_without_token(self, free_server):
        status, _, _ = _request(free_server, "GET", "/ops/ports")
        assert status == 401

    def test_ops_portals_401_without_token(self, free_server):
        status, _, _ = _request(free_server, "GET", "/ops/portals")
        assert status == 401

    def test_ops_services_401_without_token(self, free_server):
        status, _, _ = _request(free_server, "GET", "/ops/services")
        assert status == 401

    def test_wall_active_401_without_token(self, free_server):
        status, _, _ = _request(free_server, "GET", "/wall/api/active")
        assert status == 401

    def test_wall_stream_401_without_token(self, free_server):
        status, _, _ = _request(free_server, "GET", "/wall/api/stream")
        assert status == 401

    def test_threads_401_without_token(self, free_server):
        status, _, _ = _request(free_server, "GET", "/projects/qb/threads")
        assert status == 401

    def test_wall_active_200_with_bearer(self, free_server):
        token = self._token(free_server)
        status, _, data = _request(
            free_server, "GET", "/wall/api/active", headers={"Authorization": f"Bearer {token}"}
        )
        assert status == 200
        assert "sessions" in _json(data)

    def test_ops_ports_200_with_bearer(self, free_server):
        token = self._token(free_server)
        status, _, data = _request(
            free_server, "GET", "/ops/ports", headers={"Authorization": f"Bearer {token}"}
        )
        assert status == 200
        assert "ports" in _json(data)

    def test_wall_stream_200_with_query_token(self, free_server):
        """SSE 走 ?token=（EventSource 限制）；读到首帧即断（服务端断连安全）。"""
        token = self._token(free_server)
        parsed = urlparse(free_server)
        conn = HTTPConnection(parsed.hostname, parsed.port, timeout=10)
        try:
            conn.request("GET", f"/wall/api/stream?token={token}")
            resp = conn.getresponse()
            assert resp.status == 200
            assert resp.headers.get("Content-Type", "").startswith("text/event-stream")
            first = resp.read(64)
            assert first.startswith(b"event: state")
        finally:
            conn.close()

    def test_bad_token_401(self, free_server):
        status, _, _ = _request(free_server, "GET", "/wall/api/active?token=deadbeef")
        assert status == 401

    def test_open_read_stays_free(self, free_server):
        """读闸只封清单内端点：/cards 等常规读在免登录模式仍直连可用。"""
        status, _, _ = _request(free_server, "GET", "/cards")
        assert status == 200


class TestFileCredentials:
    """~/.ccc/web-auth.txt 凭证回退：env 未配置时 /session 正常签发。"""

    @pytest.fixture(autouse=True)
    def _file_mode(self, monkeypatch: pytest.MonkeyPatch, tmp_path):
        monkeypatch.setenv("CCC_WEB_AUTH_REQUIRED", "0")
        monkeypatch.delenv("CCC_WEB_USERNAME", raising=False)
        monkeypatch.delenv("CCC_WEB_PASSWORD_HASH", raising=False)
        self.auth_file = tmp_path / "web-auth.txt"
        monkeypatch.setattr("server.web.server._WEB_AUTH_FILE", self.auth_file)

    def test_session_500_without_any_credentials(self, free_server):
        status, _, data = _login(free_server, "ccc", "whatever")
        assert status == 500
        assert "not configured" in _json(data)["error"]

    def test_session_issues_token_from_password_file(self, free_server):
        self.auth_file.write_text(_FILE_PASS + "\n", encoding="utf-8")
        status, _, data = _login(free_server, "ccc", _FILE_PASS)
        assert status == 200
        token = _json(data)["token"]
        assert token
        # 文件签发的 token 可过读闸
        hs, _, _ = _request(
            free_server, "GET", "/wall/api/active", headers={"Authorization": f"Bearer {token}"}
        )
        assert hs == 200

    def test_session_user_pass_format(self, free_server):
        self.auth_file.write_text(f"{_FILE_USER}:{_FILE_PASS}\n", encoding="utf-8")
        status, _, data = _login(free_server, _FILE_USER, _FILE_PASS)
        assert status == 200
        # 账号错 → 401
        bad, _, _ = _login(free_server, "ccc", _FILE_PASS)
        assert bad == 401

    def test_session_production_note_format(self, free_server):
        """现网格式（2026-08-24 轮换件）：标题行 + 「账号: ccc」+「口令: …」。"""
        self.auth_file.write_text(
            "CCC Web 新口令（2026-08-24 P0-2 轮换,此文件 600）\n"
            "账号: ccc\n"
            f"口令: {_FILE_PASS}\n",
            encoding="utf-8",
        )
        status, _, data = _login(free_server, "ccc", _FILE_PASS)
        assert status == 200
        bad, _, _ = _login(free_server, "ccc", "wrong")
        assert bad == 401

    def test_wrong_password_401(self, free_server):
        self.auth_file.write_text(_FILE_PASS, encoding="utf-8")
        status, _, _ = _login(free_server, "ccc", "wrong")
        assert status == 401

    def test_env_overrides_file(self, free_server, monkeypatch):
        self.auth_file.write_text(_FILE_PASS, encoding="utf-8")
        monkeypatch.setenv("CCC_WEB_USERNAME", "testuser")
        monkeypatch.setenv("CCC_WEB_PASSWORD_HASH", hashlib.sha256(b"testpass").hexdigest())
        status, _, _ = _login(free_server, "testuser", "testpass")
        assert status == 200
        status, _, _ = _login(free_server, "ccc", _FILE_PASS)
        assert status == 401


class TestRetiredRoutesAndConfig:
    """遗留路由下线 + /config 收敛。"""

    @pytest.fixture(autouse=True)
    def _free_mode(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("CCC_WEB_AUTH_REQUIRED", "0")

    def test_dsh_workspaces_retired_404(self, free_server):
        status, _, _ = _request(free_server, "GET", "/dsh/workspaces")
        assert status == 404

    def test_dsh_sessions_retired_404(self, free_server):
        status, _, _ = _request(free_server, "GET", "/dsh/sessions/session-abc")
        assert status == 404

    def test_config_no_chat_bridge_url(self, free_server):
        status, _, data = _request(free_server, "GET", "/config")
        assert status == 200
        body = _json(data)
        assert "chat_bridge_url" not in body
        # 公开面保留字段仍在
        assert "ports" in body and "models" in body and "version" in body
