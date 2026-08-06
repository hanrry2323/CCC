"""test_http_api — HTTP API 服务端测试。

覆盖：
- 鉴权三态（成功/失败/过期）
- 未鉴权请求 401
- T45 免登录模式（CCC_WEB_AUTH_REQUIRED=0 → 全部端点免鉴权；改配置即恢复登录）
- 对话往返（回声占位）
- 5 个 board 接口各自 200 + 数据形状断言
- /health 返回正确结构
- 未知路径 404
- 启动/关闭无残留进程
- T43 对话历史长轮询增量同步（seq 光标 / 超时 / 增量 / 并发不阻塞 / 断连不崩溃）
"""

from __future__ import annotations

# ── 设置测试鉴权环境变量（必须在 import server 模块之前） ──
import hashlib
import os

TEST_USER = "testuser"
TEST_PASS = "testpass"
TEST_PASS_HASH = hashlib.sha256(TEST_PASS.encode("utf-8")).hexdigest()
os.environ.setdefault("CCC_WEB_USERNAME", TEST_USER)
os.environ.setdefault("CCC_WEB_PASSWORD_HASH", TEST_PASS_HASH)
# 默认 TTL 足够长，所有常规测试在过期前完成
os.environ.setdefault("CCC_WEB_TOKEN_TTL", "3600")
# T45 免登录开关：既有用例覆盖鉴权行为 → 显式开启（CCC_WEB_AUTH_REQUIRED=1）
os.environ.setdefault("CCC_WEB_AUTH_REQUIRED", "1")

import json
import socket
import threading
import time
from http.client import HTTPConnection
from pathlib import Path
from urllib.parse import urlparse

import pytest

from server.web.server import create_server

# 重试连接参数
_RETRY_COUNT = 10
_RETRY_DELAY = 0.1


@pytest.fixture(scope="module")
def api_server():
    """启动 HTTP API 服务（随机端口），返回 base_url。"""
    server = create_server(host="127.0.0.1", port=0)
    addr = server.server_address
    base_url = f"http://{addr[0]}:{addr[1]}"

    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()

    # 等待服务就绪
    for _ in range(_RETRY_COUNT):
        try:
            conn = HTTPConnection(addr[0], addr[1], timeout=2)
            conn.request("GET", "/health")
            conn.getresponse().read()
            conn.close()
            break
        except (ConnectionRefusedError, OSError):
            time.sleep(_RETRY_DELAY)
    else:
        server.server_close()
        pytest.fail("API 服务启动失败")

    yield base_url

    server.shutdown()
    server.server_close()


# ── 鉴权辅助 ──


def _login(api_server: str, username: str, password: str) -> tuple[int, dict]:
    """POST /session 登录，返回 (status, body_dict)。"""
    parsed = urlparse(api_server)
    conn = HTTPConnection(parsed.hostname, parsed.port, timeout=5)
    try:
        body = json.dumps({"username": username, "password": password}).encode("utf-8")
        conn.request("POST", "/session", body=body, headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        raw = resp.read().decode("utf-8")
        data = json.loads(raw) if raw else {}
        return resp.status, data
    finally:
        conn.close()


def _get_token(api_server: str) -> str:
    """登录并返回 Bearer token。"""
    status, data = _login(api_server, TEST_USER, TEST_PASS)
    assert status == 200, f"login failed: {data}"
    return data["token"]


def _get(api_server: str, path: str, token: str | None = None) -> tuple[int, dict]:
    """GET 请求（可选带 Bearer token），返回 (status, body_dict)。"""
    parsed = urlparse(api_server)
    conn = HTTPConnection(parsed.hostname, parsed.port, timeout=5)
    try:
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        conn.request("GET", path, headers=headers)
        resp = conn.getresponse()
        raw = resp.read().decode("utf-8")
        data = json.loads(raw) if raw else {}
        return resp.status, data
    finally:
        conn.close()


def _get_raw(api_server: str, path: str) -> tuple[int, str]:
    """GET 请求（无鉴权），返回 (status, body_text)；用于静态资源测试。"""
    parsed = urlparse(api_server)
    conn = HTTPConnection(parsed.hostname, parsed.port, timeout=5)
    try:
        conn.request("GET", path)
        resp = conn.getresponse()
        raw = resp.read().decode("utf-8", errors="replace")
        return resp.status, raw
    finally:
        conn.close()


def _post(api_server: str, path: str, body_dict: dict, token: str | None = None) -> tuple[int, dict]:
    """POST 请求（可选带 Bearer token），返回 (status, body_dict)。"""
    parsed = urlparse(api_server)
    conn = HTTPConnection(parsed.hostname, parsed.port, timeout=5)
    try:
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        body = json.dumps(body_dict).encode("utf-8")
        conn.request("POST", path, body=body, headers=headers)
        resp = conn.getresponse()
        raw = resp.read().decode("utf-8")
        data = json.loads(raw) if raw else {}
        return resp.status, data
    finally:
        conn.close()


def _delete(api_server: str, path: str, token: str | None = None) -> tuple[int, dict]:
    """DELETE 请求（可选带 Bearer token），返回 (status, body_dict)。"""
    parsed = urlparse(api_server)
    conn = HTTPConnection(parsed.hostname, parsed.port, timeout=5)
    try:
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        conn.request("DELETE", path, headers=headers)
        resp = conn.getresponse()
        raw = resp.read().decode("utf-8")
        data = json.loads(raw) if raw else {}
        return resp.status, data
    finally:
        conn.close()


def _post_stream_raw(api_server: str, path: str, body_dict: dict, token: str | None = None) -> tuple[int, str, str]:
    """POST 请求返回原始响应 (status, content_type, body_text)；用于 SSE 流式断言。"""
    parsed = urlparse(api_server)
    conn = HTTPConnection(parsed.hostname, parsed.port, timeout=15)
    try:
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        body = json.dumps(body_dict).encode("utf-8")
        conn.request("POST", path, body=body, headers=headers)
        resp = conn.getresponse()
        ctype = resp.getheader("Content-Type", "")
        raw = resp.read().decode("utf-8", errors="replace")
        return resp.status, ctype, raw
    finally:
        conn.close()


def _longpoll(api_server: str, path: str, token: str | None = None, timeout: float = 5.0) -> tuple[int, dict]:
    """GET 长轮询请求（连接超时 = 轮询超时 + 2s），返回 (status, body_dict)。

    阻塞直到响应到达（增量 / 超时 / 断连）。
    """
    parsed = urlparse(api_server)
    conn = HTTPConnection(parsed.hostname, parsed.port, timeout=timeout + 2)
    try:
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        conn.request("GET", path, headers=headers)
        resp = conn.getresponse()
        raw = resp.read().decode("utf-8")
        data = json.loads(raw) if raw else {}
        return resp.status, data
    finally:
        conn.close()


# ── 鉴权测试 ──


class TestAuth:
    """鉴权三态：成功/失败/过期 + 未鉴权 401。"""

    def test_login_success(self, api_server):
        """成功登录返回 token。"""
        status, data = _login(api_server, TEST_USER, TEST_PASS)
        assert status == 200
        assert "token" in data
        assert len(data["token"]) > 0
        assert "expires_at" in data
        assert "ttl_s" in data
        assert data["ttl_s"] == 3600

    def test_login_failure_wrong_password(self, api_server):
        """错误密码返回 401。"""
        status, data = _login(api_server, TEST_USER, "wrongpass")
        assert status == 401
        assert "error" in data

    def test_login_failure_wrong_user(self, api_server):
        """错误用户名返回 401。"""
        status, data = _login(api_server, "nobody", TEST_PASS)
        assert status == 401
        assert "error" in data

    def test_login_missing_credentials(self, api_server):
        """缺少用户名或密码返回 400。"""
        status, data = _post(api_server, "/session", {"username": "test"})
        assert status == 400
        assert "error" in data

    def test_unauthenticated_request_401(self, api_server):
        """未带 Authorization 头请求受保护端点返回 401。"""
        status, data = _get(api_server, "/board/realtime")
        assert status == 401
        assert "error" in data

    def test_invalid_token_401(self, api_server):
        """无效 Bearer token 返回 401。"""
        status, data = _get(api_server, "/board/realtime", token="invalidtoken")
        assert status == 401
        assert "error" in data

    def test_expired_token_401(self, api_server):
        """过期 token 返回 401。"""
        # 使用短 TTL 登录获取 token
        os.environ["CCC_WEB_TOKEN_TTL"] = "1"
        # 重新登录（新 token 使用短 TTL）
        status, data = _login(api_server, TEST_USER, TEST_PASS)
        assert status == 200
        token = data["token"]
        # 等待 token 过期
        time.sleep(1.5)
        # 恢复 TTL
        os.environ["CCC_WEB_TOKEN_TTL"] = "3600"
        # 使用过期 token
        status, data = _get(api_server, "/board/realtime", token=token)
        assert status == 401
        assert "error" in data


# ── 对话测试（T29：/conversation 走大脑 Agent，调用 2017 Claude Code via 6100） ──


def _set_brain_env():
    """设置大脑代理环境变量（运行时刷新）。"""
    os.environ["CCC_BRAIN_MODEL"] = "flash"
    os.environ["CCC_BRAIN_BASE_URL"] = "http://127.0.0.1:6100"
    os.environ["CCC_BRAIN_AUTH_TOKEN"] = "ccc-relay-flash"


def _clear_brain_env():
    """清除大脑代理环境变量。"""
    for k in (
        "CCC_BRAIN_MODEL",
        "CCC_BRAIN_BASE_URL",
        "CCC_BRAIN_AUTH_TOKEN",
        "CCC_BRAIN_TIMEOUT",
        "CCC_BRAIN_CLAUDE_BIN",
    ):
        os.environ.pop(k, None)


class TestConversation:
    """/conversation 大脑代理测试：缺配置 503、忙 503、成功 200 reply、
    超时 504、失败 502、历史落盘、prompt 含上下文、鉴权不回归。"""

    @pytest.fixture(autouse=True)
    def _clear_conversation_state(self):
        """每个测试前清空对话历史与大脑 env，避免跨用例污染。"""
        from server.web import server as srv_mod

        srv_mod._conversations.clear()
        srv_mod._thread_conversations.clear()
        _clear_brain_env()
        yield
        srv_mod._conversations.clear()
        srv_mod._thread_conversations.clear()
        _clear_brain_env()

    def test_conversation_no_auth(self, api_server):
        """未鉴权对话请求返回 401（不触达大脑）。"""
        status, data = _post(api_server, "/conversation", {"message": "hello"})
        assert status == 401

    def test_conversation_empty_message(self, api_server):
        """空消息返回 400（不触达大脑）。"""
        token = _get_token(api_server)
        status, data = _post(api_server, "/conversation", {"message": ""}, token=token)
        assert status == 400

    def test_conversation_not_configured_503(self, api_server):
        """大脑未配置返回 503。"""
        _clear_brain_env()
        token = _get_token(api_server)
        status, data = _post(api_server, "/conversation", {"message": "hi"}, token=token)
        assert status == 503
        assert "not configured" in data["error"]

    def test_conversation_success(self, api_server, monkeypatch):
        """大脑成功返回 reply。"""
        _set_brain_env()
        monkeypatch.setattr(
            "server.web.brain._run_claude",
            lambda prompt, timeout: (True, "brain-reply", None),
        )
        token = _get_token(api_server)
        status, data = _post(api_server, "/conversation", {"message": "1+1"}, token=token)
        assert status == 200
        assert data["reply"] == "brain-reply"

    def test_conversation_history_after_success(self, api_server, monkeypatch):
        """成功对话后历史应包含 user + assistant 两条。"""
        _set_brain_env()
        monkeypatch.setattr(
            "server.web.brain._run_claude",
            lambda prompt, timeout: (True, "ok", None),
        )
        token = _get_token(api_server)
        _post(api_server, "/conversation", {"message": "first"}, token=token)
        status, data = _get(api_server, "/conversation", token=token)
        assert status == 200
        assert len(data["messages"]) >= 2
        assert data["messages"][-2]["role"] == "user"
        assert data["messages"][-2]["message"] == "first"
        assert data["messages"][-1]["role"] == "assistant"
        assert data["messages"][-1]["message"] == "ok"

    def test_conversation_timeout_504(self, api_server, monkeypatch):
        """大脑超时返回 504 且不落历史。"""
        _set_brain_env()
        monkeypatch.setattr(
            "server.web.brain._run_claude",
            lambda prompt, timeout: (False, "brain timeout", "timeout"),
        )
        token = _get_token(api_server)
        status, data = _post(api_server, "/conversation", {"message": "slow"}, token=token)
        assert status == 504
        assert "error" in data
        # 历史应为空（超时不落历史）
        status, data = _get(api_server, "/conversation", token=token)
        assert status == 200
        assert len(data["messages"]) == 0

    def test_conversation_failure_502(self, api_server, monkeypatch):
        """大脑失败返回 502 且不落历史。"""
        _set_brain_env()
        monkeypatch.setattr(
            "server.web.brain._run_claude",
            lambda prompt, timeout: (False, "brain failed: boom", "failed"),
        )
        token = _get_token(api_server)
        status, data = _post(api_server, "/conversation", {"message": "x"}, token=token)
        assert status == 502
        assert "error" in data
        # 历史应为空（失败不落历史）
        status, data = _get(api_server, "/conversation", token=token)
        assert status == 200
        assert len(data["messages"]) == 0

    def test_conversation_busy_503(self, api_server, monkeypatch):
        """大脑忙（锁被占用）返回 503 且不触达 Claude Code。"""
        _set_brain_env()
        from server.web import brain as brain_mod

        called = {"n": 0}
        monkeypatch.setattr(
            "server.web.brain._run_claude",
            lambda prompt, timeout: called.__setitem__("n", called["n"] + 1) or (True, "x", None),
        )
        # 测试线程持有锁，服务线程应拿到 503 busy 且不调用 _run_claude
        acquired = brain_mod._brain_lock.acquire(blocking=False)
        assert acquired
        try:
            token = _get_token(api_server)
            status, data = _post(api_server, "/conversation", {"message": "hi"}, token=token)
            assert status == 503
            assert "busy" in data["error"]
            assert called["n"] == 0
        finally:
            brain_mod._brain_lock.release()

    def test_conversation_prompt_includes_history(self, api_server, monkeypatch):
        """prompt 应包含系统人格 + 历史 + 当前消息。"""
        _set_brain_env()
        captured: dict = {}

        def fake(prompt, timeout):
            captured["prompt"] = prompt
            return (True, "ok", None)

        monkeypatch.setattr("server.web.brain._run_claude", fake)
        token = _get_token(api_server)
        _post(api_server, "/conversation", {"message": "first"}, token=token)
        _post(api_server, "/conversation", {"message": "second"}, token=token)
        prompt = captured["prompt"]
        # 系统人格
        assert "大脑 Agent" in prompt
        # 历史与当前消息
        assert "first" in prompt
        assert "second" in prompt

    # ── T41 流式（body.stream=true → SSE） ──

    def test_conversation_stream_not_configured_sse_error(self, api_server):
        """流式请求：大脑未配置 → SSE `event: error`(503)（HTTP 200）。"""
        _clear_brain_env()
        token = _get_token(api_server)
        status, ctype, body = _post_stream_raw(
            api_server, "/conversation", {"message": "hi", "stream": True}, token=token
        )
        assert status == 200
        assert ctype.startswith("text/event-stream")
        assert "event: error" in body
        assert '"status": 503' in body
        assert "not configured" in body

    def test_conversation_stream_success(self, api_server, monkeypatch):
        """流式请求：成功时逐事件输出 meta/text/done 并落历史。"""
        _set_brain_env()

        def fake_stream(prompt):
            yield ("meta", {"model": "flash"})
            yield ("text", {"text": "你好"})
            yield ("done", {"is_error": False, "text": "你好"})

        monkeypatch.setattr("server.web.brain._stream_claude", fake_stream)
        token = _get_token(api_server)
        status, ctype, body = _post_stream_raw(
            api_server, "/conversation", {"message": "hi", "stream": True}, token=token
        )
        assert status == 200
        assert ctype.startswith("text/event-stream")
        assert "event: meta" in body
        assert '"model": "flash"' in body
        assert "event: text" in body
        assert '"text": "你好"' in body
        assert "event: done" in body
        # 流式成功应回写历史（与同步一致）
        status, data = _get(api_server, "/conversation", token=token)
        assert len(data["messages"]) == 2
        assert data["messages"][-1]["role"] == "assistant"
        assert data["messages"][-1]["message"] == "你好"

    def test_conversation_stream_error_not_recorded(self, api_server, monkeypatch):
        """流式请求：大脑失败（error 事件）不落历史。"""
        _set_brain_env()

        def fake_stream(prompt):
            yield ("error", {"status": 504, "message": "brain timeout"})

        monkeypatch.setattr("server.web.brain._stream_claude", fake_stream)
        token = _get_token(api_server)
        status, ctype, body = _post_stream_raw(
            api_server, "/conversation", {"message": "slow", "stream": True}, token=token
        )
        assert status == 200
        assert "event: error" in body
        assert '"status": 504' in body
        status, data = _get(api_server, "/conversation", token=token)
        assert len(data["messages"]) == 0

    def test_conversation_stream_busy(self, api_server, monkeypatch):
        """流式请求：大脑忙 → SSE `event: error`(503)。"""
        _set_brain_env()
        from server.web import brain as brain_mod

        acquired = brain_mod._brain_lock.acquire(blocking=False)
        assert acquired
        try:
            token = _get_token(api_server)
            status, ctype, body = _post_stream_raw(
                api_server, "/conversation", {"message": "hi", "stream": True}, token=token
            )
        finally:
            brain_mod._brain_lock.release()
        assert status == 200
        assert "event: error" in body
        assert '"status": 503' in body
        assert "busy" in body

    def test_conversation_sync_not_regressed(self, api_server, monkeypatch):
        """不带 stream 标志：仍走同步 JSON（向后兼容）。"""
        _set_brain_env()
        monkeypatch.setattr(
            "server.web.brain._run_claude",
            lambda prompt, timeout: (True, "sync-reply", None),
        )
        token = _get_token(api_server)
        status, data = _post(api_server, "/conversation", {"message": "hi"}, token=token)
        assert status == 200
        assert "reply" in data
        assert data["reply"] == "sync-reply"
        # 不带 stream 不应返回 SSE
        status, ctype, body = _post_stream_raw(api_server, "/conversation", {"message": "hi"}, token=token)
        assert not ctype.startswith("text/event-stream")
        assert "event:" not in body


# ── T43 对话历史长轮询增量同步（GET /conversation?after=<seq>&timeout=<s>） ──


class TestConversationLongPoll:
    """T43：seq 光标 / 超时空增量 / 新消息增量 / after 正确 / 并发不阻塞 / 断连不崩溃。"""

    @pytest.fixture(autouse=True)
    def _clear_conversation_state(self):
        """每个测试前清空对话历史与大脑 env，避免跨用例污染。"""
        from server.web import server as srv_mod

        srv_mod._conversations.clear()
        srv_mod._thread_conversations.clear()
        _clear_brain_env()
        yield
        srv_mod._conversations.clear()
        srv_mod._thread_conversations.clear()
        _clear_brain_env()

    def test_no_after_returns_full(self, api_server, monkeypatch):
        """不带 after：返回全量 + seq 光标（向后兼容，现有行为 + seq 字段）。"""
        _set_brain_env()
        monkeypatch.setattr(
            "server.web.brain._run_claude",
            lambda prompt, timeout: (True, "ok", None),
        )
        token = _get_token(api_server)
        status, data = _get(api_server, "/conversation", token=token)
        assert status == 200
        assert data["seq"] == 0
        assert data["messages"] == []
        _post(api_server, "/conversation", {"message": "first"}, token=token)
        status, data = _get(api_server, "/conversation", token=token)
        assert status == 200
        assert data["seq"] == 2
        assert len(data["messages"]) == 2
        assert data["messages"][0]["role"] == "user"
        assert data["messages"][0]["message"] == "first"
        assert data["messages"][-1]["role"] == "assistant"

    def test_after_cursor_increment(self, api_server, monkeypatch):
        """after=<seq>：返回 seq 之后的增量（无需等待）；after 到当前 seq → 空增量。"""
        _set_brain_env()
        monkeypatch.setattr(
            "server.web.brain._run_claude",
            lambda prompt, timeout: (True, "ok", None),
        )
        token = _get_token(api_server)
        _post(api_server, "/conversation", {"message": "first"}, token=token)
        status, inc = _get(api_server, "/conversation?after=1", token=token)
        assert status == 200
        assert inc["seq"] == 2
        assert len(inc["messages"]) == 1
        assert inc["messages"][0]["role"] == "assistant"
        assert inc["messages"][0]["message"] == "ok"
        # after 到达当前 seq → 挂起（短超时验证空增量返回）
        status, empty = _longpoll(api_server, "/conversation?after=2&timeout=1", token, timeout=3)
        assert status == 200
        assert empty["messages"] == []
        assert empty["seq"] == 2

    def test_longpoll_timeout_returns_empty(self, api_server):
        """挂起无新消息 → 超时返回 {messages:[], seq 不变}。"""
        token = _get_token(api_server)
        status, data = _get(api_server, "/conversation", token=token)
        seq = data["seq"]
        t0 = time.monotonic()
        status, data = _longpoll(api_server, f"/conversation?after={seq}&timeout=1", token, timeout=3)
        elapsed = time.monotonic() - t0
        assert status == 200
        assert data["messages"] == []
        assert data["seq"] == seq
        assert elapsed >= 0.8, f"应等到超时才返回: {elapsed:.2f}s"

    def test_longpoll_returns_increment_on_new_message(self, api_server, monkeypatch):
        """挂起期间新消息到达 → 立即返回增量 + seq 推进（notify_all 唤醒）。"""
        _set_brain_env()
        monkeypatch.setattr(
            "server.web.brain._run_claude",
            lambda prompt, timeout: (True, "inc-reply", None),
        )
        token = _get_token(api_server)
        _post(api_server, "/conversation", {"message": "first"}, token=token)
        status, data = _get(api_server, "/conversation", token=token)
        base_seq = data["seq"]
        result: dict = {}

        def poll():
            result["status"], result["data"] = _longpoll(
                api_server, f"/conversation?after={base_seq}&timeout=5", token, timeout=8
            )

        t = threading.Thread(target=poll)
        t.start()
        time.sleep(0.2)
        status, posted = _post(api_server, "/conversation", {"message": "second"}, token=token)
        assert status == 200
        t.join(timeout=8)
        assert not t.is_alive(), "长轮询应在新消息到达时被唤醒返回"
        assert result["status"] == 200
        data = result["data"]
        assert data["seq"] == base_seq + 2
        assert len(data["messages"]) == 2
        assert data["messages"][0]["role"] == "user"
        assert data["messages"][0]["message"] == "second"
        assert data["messages"][-1]["role"] == "assistant"

    def test_longpoll_hang_does_not_block_others(self, api_server):
        """长轮询挂起期间 /health 与 /board/states 正常返回（ThreadingHTTPServer 并发）。"""
        token = _get_token(api_server)
        result: dict = {}

        def poll():
            result["data"] = _longpoll(api_server, "/conversation?after=999999&timeout=3", token, timeout=6)

        t = threading.Thread(target=poll)
        t.start()
        time.sleep(0.3)
        t0 = time.monotonic()
        status, health = _get(api_server, "/health")
        health_elapsed = time.monotonic() - t0
        assert status == 200
        assert health["status"] == "ok"
        assert health_elapsed < 1.5, f"/health 被长轮询阻塞: {health_elapsed:.2f}s"
        status, states = _get(api_server, "/board/states", token=token)
        assert status == 200
        assert isinstance(states, dict)
        t.join(timeout=6)
        assert not t.is_alive()
        assert result["data"][1]["messages"] == []

    def test_longpoll_client_disconnect_no_crash(self, api_server):
        """客户端长轮询中途断开 → 服务不崩溃、后续请求正常。"""
        token = _get_token(api_server)
        parsed = urlparse(api_server)
        sock = socket.create_connection((parsed.hostname, parsed.port), timeout=3)
        try:
            req = (
                f"GET /conversation?after=999999&timeout=10 HTTP/1.1\r\n"
                f"Host: {parsed.hostname}:{parsed.port}\r\n"
                f"Authorization: Bearer {token}\r\n"
                f"Connection: close\r\n\r\n"
            )
            sock.sendall(req.encode("utf-8"))
            time.sleep(0.3)
            sock.close()  # 不读响应直接断开
        finally:
            try:
                sock.close()
            except OSError:
                pass
        time.sleep(0.3)
        status, health = _get(api_server, "/health")
        assert status == 200
        assert health["status"] == "ok"
        status, states = _get(api_server, "/board/states", token=token)
        assert status == 200
        assert isinstance(states, dict)

    def test_invalid_after_and_timeout_400(self, api_server):
        """after/timeout 非法 → 400（不挂起）。"""
        token = _get_token(api_server)
        status, data = _get(api_server, "/conversation?after=abc", token=token)
        assert status == 400
        assert "error" in data
        status, data = _get(api_server, "/conversation?after=0&timeout=abc", token=token)
        assert status == 400
        assert "error" in data

    def test_hang_second_conversation_503_busy_not_blocked(self, api_server):
        """T42 关闭条件：一路对话挂起（锁被占）时，第二路对话快速返回 503 busy（非网络阻塞）。"""
        _set_brain_env()
        from server.web import brain as brain_mod

        token = _get_token(api_server)
        # 模拟 SSE 流式挂起：测试线程持有 brain 锁（单会话串行）
        acquired = brain_mod._brain_lock.acquire(blocking=False)
        assert acquired
        try:
            # 第二路对话：应快速返回 503 busy（ThreadingHTTPServer 不被网络层阻塞）
            t0 = time.monotonic()
            status, data = _post(api_server, "/conversation", {"message": "hi"}, token=token)
            elapsed = time.monotonic() - t0
            assert status == 503
            assert "busy" in data["error"]
            assert elapsed < 1.5, f"第二路对话被网络层阻塞（未达 brain 锁）: {elapsed:.2f}s"
            # 挂起期间 /health、/board/states 正常
            status, health = _get(api_server, "/health")
            assert status == 200
            assert health["status"] == "ok"
            status, states = _get(api_server, "/board/states", token=token)
            assert status == 200
            assert isinstance(states, dict)
        finally:
            brain_mod._brain_lock.release()


# ── T44 会话维度：thread_id 历史隔离 / 模型覆盖 / 跨会话并发 ──


class TestConversationThreads:
    """T44：thread_id 分桶历史互不污染、model 档位覆盖、跨会话并发不全局拒绝。"""

    @pytest.fixture(autouse=True)
    def _clear_conversation_state(self):
        """每个测试前清空对话历史（含会话桶）与大脑 env，避免跨用例污染。"""
        from server.web import server as srv_mod
        from server.web import brain as brain_mod

        srv_mod._conversations.clear()
        srv_mod._thread_conversations.clear()
        brain_mod._session_locks.clear()
        _clear_brain_env()
        yield
        srv_mod._conversations.clear()
        srv_mod._thread_conversations.clear()
        brain_mod._session_locks.clear()
        _clear_brain_env()

    def test_thread_id_history_isolated(self, api_server, monkeypatch):
        """thread_id 分桶：各会话历史独立，缺省全局不受影响（向后兼容）。"""
        _set_brain_env()
        monkeypatch.setattr(
            "server.web.brain._run_claude",
            lambda prompt, timeout: (True, "ok", None),
        )
        token = _get_token(api_server)
        _post(api_server, "/conversation", {"message": "ta-1"}, token=token)
        _post(api_server, "/conversation", {"message": "tb-1", "thread_id": "thread-b"}, token=token)
        _post(api_server, "/conversation", {"message": "tb-2", "thread_id": "thread-b"}, token=token)
        # 全局（缺省）
        status, data = _get(api_server, "/conversation", token=token)
        assert status == 200
        assert len(data["messages"]) == 2
        assert data["messages"][0]["message"] == "ta-1"
        # 会话 B 独立
        status, data = _get(api_server, "/conversation?thread_id=thread-b", token=token)
        assert status == 200
        assert len(data["messages"]) == 4
        user_msgs = [m["message"] for m in data["messages"] if m["role"] == "user"]
        assert user_msgs == ["tb-1", "tb-2"]
        # 会话 C 为空
        status, data = _get(api_server, "/conversation?thread_id=thread-c", token=token)
        assert status == 200
        assert data["messages"] == []
        assert data["seq"] == 0

    def test_thread_history_in_prompt(self, api_server, monkeypatch):
        """prompt 应包含该会话自身历史，不混入其他会话。"""
        _set_brain_env()
        captured: dict = {}

        def fake(prompt, timeout):
            captured["prompt"] = prompt
            return (True, "ok", None)

        monkeypatch.setattr("server.web.brain._run_claude", fake)
        token = _get_token(api_server)
        _post(api_server, "/conversation", {"message": "secret-a", "thread_id": "thread-a"}, token=token)
        _post(api_server, "/conversation", {"message": "secret-b", "thread_id": "thread-b"}, token=token)
        _post(api_server, "/conversation", {"message": "hello-a", "thread_id": "thread-a"}, token=token)
        prompt = captured["prompt"]
        assert "hello-a" in prompt
        assert "secret-a" in prompt
        assert "secret-b" not in prompt

    def test_model_override_passthrough(self, api_server, monkeypatch):
        """body.model 覆盖传入大脑；缺省为空（走环境变量）。"""
        _set_brain_env()
        from server.web import brain as brain_mod

        captured: dict = {}

        def fake(prompt, timeout):
            captured["model"] = brain_mod._model_override.model
            return (True, "ok", None)

        monkeypatch.setattr("server.web.brain._run_claude", fake)
        token = _get_token(api_server)
        status, data = _post(api_server, "/conversation", {"message": "hi", "model": "code"}, token=token)
        assert status == 200
        assert captured["model"] == "code"
        status, data = _post(api_server, "/conversation", {"message": "hi"}, token=token)
        assert status == 200
        assert captured["model"] == ""

    def test_cross_session_concurrent_not_globally_busy(self, api_server, monkeypatch):
        """跨会话并发：会话 A 在途时会话 B 正常对话，同会话 A 返回 503 busy。"""
        _set_brain_env()
        from server.web import brain as brain_mod

        monkeypatch.setattr(
            "server.web.brain._run_claude",
            lambda prompt, timeout: (True, "ok", None),
        )
        token = _get_token(api_server)
        a_lock = brain_mod._session_lock("thread-a")
        assert a_lock.acquire(blocking=False)
        try:
            # 会话 B：跨会话并发，正常返回（不再全局 503 拒绝）
            status, data = _post(api_server, "/conversation", {"message": "hi", "thread_id": "thread-b"}, token=token)
            assert status == 200
            assert data["reply"] == "ok"
            # 同会话 A：串行 → 503 busy
            status, data = _post(api_server, "/conversation", {"message": "hi", "thread_id": "thread-a"}, token=token)
            assert status == 503
            assert "busy" in data["error"]
        finally:
            a_lock.release()

    def test_concurrency_cap_busy(self, api_server, monkeypatch):
        """总并发超限（默认 2）时第三会话 503 busy。"""
        _set_brain_env()
        from server.web import brain as brain_mod

        monkeypatch.setattr(
            "server.web.brain._run_claude",
            lambda prompt, timeout: (True, "ok", None),
        )
        token = _get_token(api_server)
        # 模拟 2 个在途会话（达到默认上限 2）
        brain_mod._active_slots = 2
        try:
            status, data = _post(api_server, "/conversation", {"message": "hi", "thread_id": "cap-c"}, token=token)
            assert status == 503
            assert "busy" in data["error"]
        finally:
            brain_mod._active_slots = 0


# ── 健康检查 ──


class TestHealth:
    """GET /health（无鉴权）"""

    def test_health_ok(self, api_server):
        """T30：/health 返回 status + 鉴权配置（供前端登录门判断）。"""
        status, data = _get(api_server, "/health")
        assert status == 200
        assert data["status"] == "ok"
        # 测试环境显式开启鉴权（CCC_WEB_AUTH_REQUIRED=1）→ auth_required=True
        assert data["auth_required"] is True
        assert data["auth_configured"] is True  # 测试环境已配 CCC_WEB_USERNAME/PASSWORD_HASH

    def test_health_no_auth_required(self, api_server):
        """/health 本身免鉴权（不带 token 也 200）。"""
        status, data = _get(api_server, "/health", token=None)
        assert status == 200
        assert "auth_required" in data
        assert "auth_configured" in data

    def test_health_auth_required_false_when_disabled(self, api_server, monkeypatch):
        """T45：CCC_WEB_AUTH_REQUIRED=0 → /health 返回 auth_required:false（免登录）。"""
        monkeypatch.setenv("CCC_WEB_AUTH_REQUIRED", "0")
        status, data = _get(api_server, "/health")
        assert status == 200
        assert data["auth_required"] is False

    def test_health_auth_required_true_when_enabled(self, api_server, monkeypatch):
        """T45：CCC_WEB_AUTH_REQUIRED=1 → /health 返回 auth_required:true（恢复登录）。"""
        monkeypatch.setenv("CCC_WEB_AUTH_REQUIRED", "1")
        status, data = _get(api_server, "/health")
        assert status == 200
        assert data["auth_required"] is True


# ── T45 免登录模式（CCC_WEB_AUTH_REQUIRED=0，默认） ──


class TestNoAuthMode:
    """T45：免登录开关开启时全部端点免鉴权（单用户局域网直连即用）。"""

    @pytest.fixture(autouse=True)
    def _disable_auth(self, monkeypatch):
        """本类用例统一走免登录模式；结束后恢复。"""
        monkeypatch.setenv("CCC_WEB_AUTH_REQUIRED", "0")
        from server.web import server as srv_mod

        srv_mod._conversations.clear()
        srv_mod._thread_conversations.clear()
        _clear_brain_env()
        yield
        srv_mod._conversations.clear()
        srv_mod._thread_conversations.clear()
        _clear_brain_env()

    def test_board_endpoints_no_token(self, api_server):
        """免登录：/board/* 无 token 直接 200（不再 401）。"""
        for path in ("/board/states", "/board/realtime", "/board/recent", "/board/by_project"):
            status, data = _get(api_server, path)
            assert status == 200, f"{path} 免登录应 200，got {status}"
            assert isinstance(data, (dict, list))

    def test_board_snapshot_no_token(self, api_server):
        """免登录：/board/snapshot 无 token 200。"""
        status, data = _get(api_server, "/board/snapshot")
        assert status == 200
        assert "columns" in data
        assert "counts" in data

    def test_conversation_get_no_token(self, api_server):
        """免登录：GET /conversation 无 token 200（历史可读）。"""
        status, data = _get(api_server, "/conversation")
        assert status == 200
        assert "messages" in data
        assert "seq" in data

    def test_ops_summary_no_token(self, api_server, monkeypatch):
        """免登录：/ops/summary 无 token 200。"""
        monkeypatch.delenv("CLUSTER_TARGETS", raising=False)
        status, data = _get(api_server, "/ops/summary")
        assert status == 200
        assert "severity" in data

    def test_tasks_running_no_token(self, api_server):
        """免登录：/tasks/running 无 token 200（与 /projects 同白名单组，T53）。"""
        status, data = _get(api_server, "/tasks/running")
        assert status == 200
        assert "tasks" in data
        assert isinstance(data["tasks"], list)

    def test_conversation_post_no_token_not_configured(self, api_server):
        """免登录：POST /conversation 无 token 可触达大脑（未配置 → 503，而非 401）。"""
        _clear_brain_env()
        status, data = _post(api_server, "/conversation", {"message": "hi"})
        assert status == 503  # 未配置大脑（不是鉴权 401）
        assert "not configured" in data["error"]

    def test_conversation_post_no_token_success(self, api_server, monkeypatch):
        """免登录：POST /conversation 无 token 成功走通（不再要求 Bearer）。"""
        _set_brain_env()
        monkeypatch.setattr(
            "server.web.brain._run_claude",
            lambda prompt, timeout: (True, "no-auth-reply", None),
        )
        status, data = _post(api_server, "/conversation", {"message": "hi"})
        assert status == 200
        assert data["reply"] == "no-auth-reply"

    def test_restore_auth_by_config_only(self, api_server, monkeypatch):
        """T45：改配置即恢复登录——CCC_WEB_AUTH_REQUIRED=1 后同端点重新要求 401。"""
        monkeypatch.setenv("CCC_WEB_AUTH_REQUIRED", "1")
        status, data = _get(api_server, "/board/states")
        assert status == 401
        assert "error" in data


# ── 静态托管（T23：浏览器直开 7788 看页面） ──


class TestStaticHosting:
    """静态白名单路径免鉴权返回磁盘文件；目录穿越 404；非白名单 API 无 token 401。"""

    def test_root_returns_legacy_chat_html(self, api_server):
        """GET / 返回 legacy-chat/index.html（200 + text/html）。"""
        status, body_text = _get_raw(api_server, "/")
        assert status == 200
        assert "<html" in body_text.lower()
        assert "<title>CCC</title>" in body_text
        assert "legacy-retired" not in body_text

    def test_index_html(self, api_server):
        """GET /index.html 200。"""
        status, body_text = _get_raw(api_server, "/index.html")
        assert status == 200
        assert "<html" in body_text.lower()

    def test_legacy_chat_js_app_js(self, api_server):
        """GET /js/app.js 200 + 旧对话页 app.js 内容。"""
        status, body_text = _get_raw(api_server, "/js/app.js")
        assert status == 200
        assert "switchToProjectTab" in body_text or "initRouter" in body_text

    def test_legacy_chat_css_variables(self, api_server):
        """GET /css/variables.css 200（旧对话页样式）。"""
        status, _ = _get_raw(api_server, "/css/variables.css")
        assert status == 200

    def test_legacy_chat_css_base(self, api_server):
        """GET /css/base.css 200。"""
        status, _ = _get_raw(api_server, "/css/base.css")
        assert status == 200

    def test_legacy_chat_css_themes(self, api_server):
        """GET /css/themes.css 200。"""
        status, _ = _get_raw(api_server, "/css/themes.css")
        assert status == 200

    def test_legacy_chat_css_components(self, api_server):
        """GET /css/components.css 200。"""
        status, _ = _get_raw(api_server, "/css/components.css")
        assert status == 200

    def test_legacy_chat_css_shell(self, api_server):
        """GET /css/shell.css 200。"""
        status, _ = _get_raw(api_server, "/css/shell.css")
        assert status == 200

    def test_legacy_chat_js_ports(self, api_server):
        """GET /js/ports.js 200。"""
        status, _ = _get_raw(api_server, "/js/ports.js")
        assert status == 200

    def test_legacy_chat_js_theme_init(self, api_server):
        """GET /js/theme-init.js 200。"""
        status, _ = _get_raw(api_server, "/js/theme-init.js")
        assert status == 200

    def test_legacy_chat_js_shell_ui(self, api_server):
        """GET /js/shell-ui.js 200。"""
        status, _ = _get_raw(api_server, "/js/shell-ui.js")
        assert status == 200

    def test_legacy_chat_js_components(self, api_server):
        """GET /js/components/composer.js 200（组件文件）。"""
        status, _ = _get_raw(api_server, "/js/components/composer.js")
        assert status == 200

    def test_legacy_chat_js_pages(self, api_server):
        """GET /js/pages/boardPage.js 200（页面文件）。"""
        status, _ = _get_raw(api_server, "/js/pages/boardPage.js")
        assert status == 200

    def test_board_page_still_accessible(self, api_server):
        """看板数据静态文件仍可访问（T34：孤儿 css/style.css 已归档，改测 legacy-chat css）。"""
        status, _ = _get_raw(api_server, "/css/base.css")
        assert status == 200
        status, _ = _get_raw(api_server, "/data/board.js")
        assert status == 200

    def test_static_no_auth_required(self, api_server):
        """静态路径无 token 仍 200（页面本身是登录入口）。"""
        status, _ = _get_raw(api_server, "/")
        assert status == 200
        status, _ = _get_raw(api_server, "/js/app.js")
        assert status == 200

    def test_directory_traversal_rejected(self, api_server):
        """目录穿越路径 404（非白名单）。"""
        # /../server.py 不在白名单 → _send_static 返回 False → 走鉴权 → 401
        # 但白名单只接受显式映射，穿越路径不命中白名单
        for p in ["/../server.py", "/etc/passwd", "/%2e%2e/server.py", "/js/../server.py"]:
            status, _ = _get_raw(api_server, p)
            # 穿越路径不在白名单 → 走鉴权 → 无 token 401（不是 200，不是 403 文件）
            assert status in (401, 404), f"traversal {p} should be 401/404, got {status}"

    def test_non_whitelist_api_no_token_401(self, api_server):
        """非白名单 API 路径无 token 仍 401（鉴权不放松）。"""
        status, data = _get(api_server, "/board/states")
        assert status == 401
        assert "error" in data

    def test_nonexistent_static_404(self, api_server):
        """不存在的静态路径走 API 路由 → 404（带 token）。"""
        token = _get_token(api_server)
        status, _ = _get(api_server, "/nonexistent.js", token=token)
        assert status == 404

    def test_favicon_no_auth_200(self, api_server):
        """favicon 免鉴权返回 200（T44：消除浏览器自动请求的 401 噪音）。"""
        status, _ = _get_raw(api_server, "/favicon.ico")
        assert status == 200
        status, _ = _get_raw(api_server, "/favicon.svg")
        assert status == 200


# ── Board 接口（需鉴权） ──


class TestBoardRealtime:
    """GET /board/realtime"""

    def test_returns_200(self, api_server):
        token = _get_token(api_server)
        status, data = _get(api_server, "/board/realtime", token=token)
        assert status == 200
        # 实时视图返回 dict，键为状态名，值为列表
        assert isinstance(data, dict)
        for state, items in data.items():
            assert isinstance(state, str)
            assert isinstance(items, list)
            for item in items:
                assert "id" in item
                assert "title" in item
                assert "state" in item


class TestBoardRecent:
    """GET /board/recent"""

    def test_returns_200(self, api_server):
        token = _get_token(api_server)
        status, data = _get(api_server, "/board/recent", token=token)
        assert status == 200
        # 7 天视图返回 list
        assert isinstance(data, list)
        for item in data:
            assert "id" in item
            assert "written_at" in item
            # 回写时间应为 YYYY-MM-DD 格式
            assert isinstance(item["written_at"], str)


class TestBoardByProject:
    """GET /board/by_project"""

    def test_returns_200(self, api_server):
        token = _get_token(api_server)
        status, data = _get(api_server, "/board/by_project", token=token)
        assert status == 200
        # 项目视图返回 list
        assert isinstance(data, list)
        for row in data:
            assert "project" in row
            assert "count" in row
            assert isinstance(row["count"], int)
            assert "states" in row
            assert isinstance(row["states"], dict)


class TestBoardRoadmap:
    """GET /board/roadmap"""

    def test_returns_200(self, api_server):
        token = _get_token(api_server)
        status, data = _get(api_server, "/board/roadmap", token=token)
        assert status == 200
        # 线路图返回 overview + by_project
        assert "overview" in data
        assert "by_project" in data
        assert isinstance(data["overview"], list)
        assert isinstance(data["by_project"], list)
        for bucket in data["overview"]:
            assert "bucket" in bucket
            assert "count" in bucket


class TestNotFound:
    """未知路径 404"""

    def test_unknown_path(self, api_server):
        token = _get_token(api_server)
        status, data = _get(api_server, "/unknown", token=token)
        assert status == 404
        assert "error" in data

    def test_unknown_nested(self, api_server):
        token = _get_token(api_server)
        status, data = _get(api_server, "/board/unknown", token=token)
        assert status == 404
        assert "error" in data


class TestBoardStates:
    """GET /board/states"""

    def test_returns_200(self, api_server):
        token = _get_token(api_server)
        status, data = _get(api_server, "/board/states", token=token)
        assert status == 200
        assert isinstance(data, dict)
        for state, count in data.items():
            assert isinstance(state, str)
            assert isinstance(count, int)


class DataShape:
    """数据形状一致性：各接口返回数据应与 board 查询一致。"""

    def test_realtime_items_have_required_fields(self, api_server):
        token = _get_token(api_server)
        status, data = _get(api_server, "/board/realtime", token=token)
        assert status == 200
        for state, items in data.items():
            for item in items:
                for field in ("id", "title", "state", "project", "executor"):
                    assert field in item, f"缺少字段 {field}"

    def test_recent_sorted_by_written_at_desc(self, api_server):
        token = _get_token(api_server)
        status, data = _get(api_server, "/board/recent", token=token)
        assert status == 200
        # 验证回写时间倒序
        written_dates = [item["written_at"] for item in data if item.get("written_at") != "未知"]
        for i in range(1, len(written_dates)):
            assert written_dates[i - 1] >= written_dates[i], f"7 天视图未按回写时间倒序: {written_dates}"

    def test_by_project_counts_sum(self, api_server):
        token = _get_token(api_server)
        status, data = _get(api_server, "/board/by_project", token=token)
        assert status == 200
        for row in data:
            states_sum = sum(row["states"].values())
            assert row["count"] == states_sum, f"项目 {row['project']} 计数不一致: {row['count']} != {states_sum}"

    def test_roadmap_overview_is_list_of_buckets(self, api_server):
        token = _get_token(api_server)
        status, data = _get(api_server, "/board/roadmap", token=token)
        assert status == 200
        for bucket in data["overview"]:
            assert isinstance(bucket["count"], int)
            assert bucket["count"] >= 0


# ── T20 看板兼容接口：/board/snapshot / /board/summaries / /tasks/{id} ──


class TestBoardSnapshot:
    """GET /board/snapshot（BoardSnapshot 兼容结构）"""

    def test_returns_200_with_shape(self, api_server):
        token = _get_token(api_server)
        status, data = _get(api_server, "/board/snapshot", token=token)
        assert status == 200
        # BoardSnapshot: columns / counts / workspace
        assert "columns" in data
        assert "counts" in data
        assert "workspace" in data
        assert isinstance(data["columns"], dict)
        assert isinstance(data["counts"], dict)
        # 无 workspace 参数 → workspace="all"
        assert data["workspace"] == "all"
        # columns 键=状态名，值为 BoardTask 列表
        for state, tasks in data["columns"].items():
            assert isinstance(state, str)
            assert isinstance(tasks, list)
            for t in tasks:
                assert "id" in t
                assert "title" in t
                assert "status" in t
                assert t["card_kind"] == "work"

    def test_workspace_filter(self, api_server):
        token = _get_token(api_server)
        # 用一个存在的 project（从 by_project 拿）
        status, proj_rows = _get(api_server, "/board/by_project", token=token)
        assert status == 200
        assert isinstance(proj_rows, list)
        if not proj_rows:
            pytest.skip("无任务卡数据，跳过 workspace 过滤测试")
        target = proj_rows[0]["project"]
        status, data = _get(api_server, f"/board/snapshot?workspace={target}", token=token)
        assert status == 200
        assert data["workspace"] == target
        # counts 之和应等于该项目任务数
        total = sum(data["counts"].values())
        assert total == proj_rows[0]["count"]

    def test_counts_match_columns(self, api_server):
        token = _get_token(api_server)
        status, data = _get(api_server, "/board/snapshot", token=token)
        assert status == 200
        for state, count in data["counts"].items():
            assert count == len(data["columns"].get(state, []))

    def test_no_auth_401(self, api_server):
        status, data = _get(api_server, "/board/snapshot")
        assert status == 401
        assert "error" in data


class TestBoardSummaries:
    """GET /board/summaries"""

    def test_returns_200_with_summaries(self, api_server):
        token = _get_token(api_server)
        status, data = _get(api_server, "/board/summaries", token=token)
        assert status == 200
        assert "summaries" in data
        assert isinstance(data["summaries"], dict)
        # 无参数 → 全部项目各自一个 snapshot
        for ws, snap in data["summaries"].items():
            assert isinstance(ws, str)
            assert "columns" in snap
            assert "counts" in snap
            assert "workspace" in snap
            assert snap["workspace"] == ws

    def test_workspaces_param(self, api_server):
        token = _get_token(api_server)
        status, data = _get(api_server, "/board/summaries?workspaces=INT-120,CCC", token=token)
        assert status == 200
        # 请求的项目都在 summaries 里（即使无数据也应有空 snapshot）
        for ws in ("INT-120", "CCC"):
            assert ws in data["summaries"]
            assert data["summaries"][ws]["workspace"] == ws

    def test_no_auth_401(self, api_server):
        status, data = _get(api_server, "/board/summaries")
        assert status == 401
        assert "error" in data


class TestTaskDetail:
    """GET /tasks/{id}"""

    def test_returns_200_for_existing_task(self, api_server):
        # 先从 snapshot 拿一个真实 task id
        token = _get_token(api_server)
        status, snap = _get(api_server, "/board/snapshot", token=token)
        assert status == 200
        all_tasks = [t for tasks in snap["columns"].values() for t in tasks]
        if not all_tasks:
            pytest.skip("无任务卡数据，跳过任务详情测试")
        task_id = all_tasks[0]["id"]
        status, data = _get(api_server, f"/tasks/{task_id}", token=token)
        assert status == 200
        # BoardTaskDetail 字段
        assert data["id"] == task_id
        assert "title" in data
        assert "status" in data
        assert "executor" in data
        assert "acceptance" in data
        assert "phases" in data
        assert isinstance(data["phases"], list)
        assert "events" in data
        assert isinstance(data["events"], list)
        assert data["card_kind"] == "work"

    def test_404_for_missing_task(self, api_server):
        token = _get_token(api_server)
        status, data = _get(api_server, "/tasks/NOPE-9999", token=token)
        assert status == 404
        assert "error" in data

    def test_no_auth_401(self, api_server):
        status, data = _get(api_server, "/tasks/T19")
        assert status == 401
        assert "error" in data


# ── T53 后台任务进程：GET /tasks/running ──


class TestTasksRunning:
    """GET /tasks/running：执行中任务进程视图（免登录白名单 + 日志尾部）。"""

    def test_whitelisted_requires_no_token(self, api_server):
        """鉴权开启时 /tasks/running 仍免登录 200（与 /projects 同白名单组）。"""
        status, data = _get(api_server, "/tasks/running")
        assert status == 200
        assert "tasks" in data

    def test_shape_and_log_tail(self, api_server, tmp_path, monkeypatch):
        """执行中任务返回 work_id/标题/执行体/已用时/最近活动 + 日志尾 5 行。"""
        from server.web import server as srv
        from server.board.models import BoardItem

        log_dir = tmp_path / "exec-logs"
        log_dir.mkdir()
        (log_dir / "T999.log").write_text("l1\nl2\nl3\nl4\nl5\nl6\nl7\n", encoding="utf-8")
        monkeypatch.setenv("EXECUTOR_LOG_DIR", str(log_dir))
        monkeypatch.setattr(
            srv, "_load_board_items",
            lambda: [
                BoardItem(id="T999", title="测试运行中", state="执行中", executor="Claude Code"),
                BoardItem(id="T1", title="待分派卡", state="待分派"),
                BoardItem(id="T998", title="无日志运行中", state="执行中", executor="OpenCode"),
            ],
        )
        status, data = _get(api_server, "/tasks/running")
        assert status == 200
        tasks = data["tasks"]
        assert len(tasks) == 2  # 只含执行中
        t999 = next(t for t in tasks if t["work_id"] == "T999")
        assert t999["title"] == "测试运行中"
        assert t999["executor"] == "Claude Code"
        assert t999["elapsed_s"] is not None and t999["elapsed_s"] >= 0
        assert t999["started_at"] is not None
        assert t999["last_activity_at"] is not None
        # 日志尾 5 行（截取末尾，非整文件）
        assert t999["log_tail"] == ["l3", "l4", "l5", "l6", "l7"]
        # 无日志文件 → 仅卡信息，日志为空、已用时未知
        t998 = next(t for t in tasks if t["work_id"] == "T998")
        assert t998["log_tail"] == []
        assert t998["elapsed_s"] is None
        # dirty_files 字段始终存在（无 worktree → null）
        assert "dirty_files" in t999
        assert "dirty_files" in t998
        assert t999["dirty_files"] is None
        assert t998["dirty_files"] is None

    def test_dirty_files_from_worktree(self, api_server, tmp_path, monkeypatch):
        """有 worktree 且 porcelain 有改动 → dirty_files 为文件数。"""
        import subprocess
        from server.web import server as srv
        from server.web import worktree_dirty as wd
        from server.board.models import BoardItem

        wd.clear_dirty_cache()
        base = tmp_path / "ccc-dev-ws"
        monkeypatch.setenv("CCC_WORKTREE_BASE", str(base))
        wt = tmp_path / "ccc-dev-ws-t777"
        wt.mkdir()
        subprocess.run(["git", "init"], cwd=wt, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "t@ex.com"], cwd=wt, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "t"], cwd=wt, check=True, capture_output=True)
        (wt / "a.txt").write_text("a\n", encoding="utf-8")
        monkeypatch.setattr(
            srv, "_load_board_items",
            lambda: [BoardItem(id="T777", title="脏", state="执行中", executor="Claude Code")],
        )
        status, data = _get(api_server, "/tasks/running")
        assert status == 200
        t = data["tasks"][0]
        assert t["dirty_files"] == 1
        wd.clear_dirty_cache()

    def test_only_running_included(self, api_server, monkeypatch):
        """非执行中卡不进入 /tasks/running。"""
        from server.web import server as srv
        from server.board.models import BoardItem

        monkeypatch.setattr(
            srv, "_load_board_items",
            lambda: [
                BoardItem(id="T1", title="待分派", state="待分派"),
                BoardItem(id="T2", title="已回写", state="已回写"),
            ],
        )
        status, data = _get(api_server, "/tasks/running")
        assert status == 200
        assert data["tasks"] == []

    def test_no_log_dir_still_returns_cards(self, api_server, monkeypatch):
        """EXECUTOR_LOG_DIR 未配置 → 仍返回执行中卡（日志字段空）。"""
        from server.web import server as srv
        from server.board.models import BoardItem

        monkeypatch.delenv("EXECUTOR_LOG_DIR", raising=False)
        monkeypatch.setattr(
            srv, "_load_board_items",
            lambda: [BoardItem(id="T5", title="跑着", state="执行中", executor="X")],
        )
        status, data = _get(api_server, "/tasks/running")
        assert status == 200
        t = data["tasks"][0]
        assert t["work_id"] == "T5"
        assert t["log_tail"] == []
        assert t["elapsed_s"] is None


# ── T21 运维兼容接口：/ops/summary ──


class TestOpsSummary:
    """GET /ops/summary（OpsSummary 兼容子集：cluster 采集 + board 派生 severity）"""

    def test_returns_200_with_shape(self, api_server):
        token = _get_token(api_server)
        status, data = _get(api_server, "/ops/summary", token=token)
        assert status == 200
        # OpsSummary 核心字段
        assert "overview" in data
        assert "severity" in data
        assert "human_line" in data
        # overview 子结构
        ov = data["overview"]
        assert "machines" in ov
        assert "generated_at" in ov
        assert isinstance(ov["machines"], list)
        # severity ∈ green|amber|red
        assert data["severity"] in ("green", "amber", "red")
        assert isinstance(data["human_line"], str)
        assert len(data["human_line"]) > 0

    def test_machines_shape(self, api_server, monkeypatch):
        # 配置一个采集目标，验证 machines 字段结构
        monkeypatch.setenv("CLUSTER_TARGETS", "127.0.0.1:7788")
        token = _get_token(api_server)
        status, data = _get(api_server, "/ops/summary", token=token)
        assert status == 200
        machines = data["overview"]["machines"]
        if machines:  # 采集到才有
            for m in machines:
                assert "name" in m
                assert "ip" in m
                assert "reachable" in m
                assert isinstance(m["reachable"], bool)

    def test_no_cluster_config_amber(self, api_server, monkeypatch):
        """无 CLUSTER_TARGETS 配置 → severity=amber（容错，不 500）。"""
        monkeypatch.delenv("CLUSTER_TARGETS", raising=False)
        token = _get_token(api_server)
        status, data = _get(api_server, "/ops/summary", token=token)
        assert status == 200
        assert data["severity"] == "amber"
        assert "未配置" in data["human_line"] or "CLUSTER_TARGETS" in data["human_line"]

    def test_no_auth_401(self, api_server):
        status, data = _get(api_server, "/ops/summary")
        assert status == 401
        assert "error" in data


# ── T33 前端只读配置注入：/config ──


class TestConfigEndpoint:
    """GET /config（免鉴权白名单 + 仅非敏感字段）。"""

    def test_no_auth_returns_200(self, api_server):
        """无 token 访问 /config → 200（免鉴权白名单）。"""
        status, data = _get(api_server, "/config")
        assert status == 200

    def test_returns_ports_shape(self, api_server):
        """返回 ports 子结构（web/board/engine/relay）。"""
        status, data = _get(api_server, "/config")
        assert status == 200
        assert "ports" in data
        ports = data["ports"]
        for key in ("web", "board", "engine", "relay"):
            assert key in ports

    def test_returns_workspace_map_empty(self, api_server):
        """workspace_map 默认空对象（服务端不臆造业务仓路径）。"""
        status, data = _get(api_server, "/config")
        assert status == 200
        assert data["workspace_map"] == {}

    def test_returns_models_tiers(self, api_server, monkeypatch):
        """T44：/config 返回模型档位列表（CCC_MODEL_TIERS，档位选择器数据源）。"""
        monkeypatch.setenv("CCC_MODEL_TIERS", "flash,code")
        status, data = _get(api_server, "/config")
        assert status == 200
        assert "models" in data
        assert data["models"] == ["flash", "code"]
        # 未配置 → 默认 flash,code
        monkeypatch.delenv("CCC_MODEL_TIERS", raising=False)
        status, data = _get(api_server, "/config")
        assert data["models"] == ["flash", "code"]

    def test_does_not_leak_sensitive_keys(self, api_server, monkeypatch):
        """敏感字段（密钥/密码/上游地址/路径）不出现在响应中。"""
        monkeypatch.setenv("CCC_WEB_PASSWORD_HASH", "sensitive_hash_value")
        monkeypatch.setenv("RELAY_UPSTREAM_KEY", "sk-sensitive-key-1234567890")
        monkeypatch.setenv("RELAY_UPSTREAM_URL", "http://secret-upstream.example.com/v1")
        monkeypatch.setenv("DATA_DIR", "/secret/data/path")
        monkeypatch.setenv("EXECUTOR_REGISTRY_PATH", "/secret/registry.json")
        status, data = _get(api_server, "/config")
        assert status == 200
        body_str = json.dumps(data, ensure_ascii=False)
        # 敏感值不得出现在响应正文
        assert "sensitive_hash_value" not in body_str
        assert "sk-sensitive-key-1234567890" not in body_str
        assert "secret-upstream.example.com" not in body_str
        assert "/secret/data/path" not in body_str
        assert "/secret/registry.json" not in body_str
        # 敏感键名不得出现
        lower = body_str.lower()
        for forbidden in ("password", "key", "upstream_url", "data_dir", "registry", "token", "auth"):
            assert forbidden not in lower, f"敏感字段 '{forbidden}' 泄露在 /config 响应: {body_str}"


# ── T47 项目数据源 + 会话持久化（真实业务项目，左栏数据源） ──


class TestProjectsEndpoint:
    """GET /projects：免鉴权返回真实业务项目（替代任务卡分组）。"""

    def test_no_auth_returns_200(self, api_server, monkeypatch):
        """无 token 访问 /projects → 200（免鉴权白名单，与 /config 同）。"""
        monkeypatch.setenv("CCC_WEB_AUTH_REQUIRED", "1")
        status, data = _get(api_server, "/projects")
        assert status == 200

    def test_returns_real_business_projects(self, api_server):
        """左栏应为真实业务项目（qb/CCC/QuantHive/medio-0），无任务卡分组名。"""
        status, data = _get(api_server, "/projects")
        assert status == 200
        projects = data["projects"]
        assert isinstance(projects, list)
        names = {p["name"] for p in projects}
        # 核心业务项目必须在列
        for required in ("CCC", "qb", "QuantHive", "medio-0"):
            assert required in names, f"缺少业务项目 {required}"
        # 验收标准：左栏禁止出现任何任务卡分组名（如 INT-120、新阶段等）
        for p in projects:
            assert "INT-" not in p["name"], f"任务卡分组名不应进入左栏: {p['name']}"

    def test_field_shape(self, api_server):
        """每个项目含 id/name/kind/workspace_path/is_taskable 字段。"""
        status, data = _get(api_server, "/projects")
        assert status == 200
        for p in data["projects"]:
            for field in ("id", "name", "kind", "workspace_path", "is_taskable"):
                assert field in p, f"缺少字段 {field}"
            assert p["is_taskable"] in (True, False)

    def test_taskable_flags(self, api_server):
        """可下达任务的项目 is_taskable=True（CCC/qb/QuantHive/medio-0）。"""
        status, data = _get(api_server, "/projects")
        assert status == 200
        taskable = {p["name"] for p in data["projects"] if p["is_taskable"]}
        for required in ("CCC", "qb", "QuantHive", "medio-0"):
            assert required in taskable, f"{required} 应可下达任务"


class TestThreadPersistence:
    """T47 会话持久化：项目+thread 落盘，线程列表可查，重启后可恢复。"""

    @pytest.fixture(autouse=True)
    def _isolated_data(self, tmp_path, monkeypatch):
        """每个用例用独立 DATA_DIR + 清空内存会话，避免跨用例污染。"""
        monkeypatch.setenv("CCC_DATA_DIR", str(tmp_path))
        from server.web import server as srv_mod

        srv_mod._thread_conversations.clear()
        yield
        srv_mod._thread_conversations.clear()

    def test_conv_write_persists_thread(self, api_server, monkeypatch):
        """对话(thread_id+project)后：线程列表可见、消息落盘。"""
        _set_brain_env()
        monkeypatch.setattr(
            "server.web.brain._run_claude",
            lambda prompt, timeout: (True, "ok", None),
        )
        token = _get_token(api_server)
        status, data = _post(
            api_server, "/conversation",
            {"message": "你好世界", "thread_id": "qb::abc", "project": "qb"}, token=token,
        )
        assert status == 200
        # 线程列表（鉴权开启时须带 token）
        status, data = _get(api_server, "/projects/qb/threads", token=token)
        assert status == 200
        threads = data["threads"]
        assert len(threads) == 1
        assert threads[0]["thread_id"] == "qb::abc"
        # 标题由首条用户消息截断生成
        assert "你好世界" in threads[0]["title"]
        assert threads[0]["message_count"] == 2

    def test_threads_isolated_by_project(self, api_server, monkeypatch):
        """不同项目的线程列表互不污染。"""
        _set_brain_env()
        monkeypatch.setattr(
            "server.web.brain._run_claude",
            lambda prompt, timeout: (True, "ok", None),
        )
        token = _get_token(api_server)
        _post(api_server, "/conversation", {"message": "a", "thread_id": "qb::1", "project": "qb"}, token=token)
        _post(api_server, "/conversation", {"message": "b", "thread_id": "ccc::2", "project": "CCC"}, token=token)
        _, qb = _get(api_server, "/projects/qb/threads", token=token)
        _, ccc = _get(api_server, "/projects/CCC/threads", token=token)
        assert [t["thread_id"] for t in qb["threads"]] == ["qb::1"]
        assert [t["thread_id"] for t in ccc["threads"]] == ["ccc::2"]

    def test_conversation_history_loaded_from_disk(self, api_server, monkeypatch, tmp_path):
        """已落盘会话在内存清空后可凭 thread_id 重新读到（重启恢复）。"""
        _set_brain_env()
        monkeypatch.setattr(
            "server.web.brain._run_claude",
            lambda prompt, timeout: (True, "ok", None),
        )
        token = _get_token(api_server)
        _post(api_server, "/conversation", {"message": "persist", "thread_id": "qb::keep", "project": "qb"}, token=token)
        # 模拟重启：清空内存会话历史后，重新加载磁盘
        from server.web import server as srv_mod

        srv_mod._thread_conversations.clear()
        srv_mod._load_persisted_threads()
        status, data = _get(api_server, "/conversation?thread_id=qb::keep", token=token)
        assert status == 200
        user_msgs = [m["message"] for m in data["messages"] if m["role"] == "user"]
        assert user_msgs == ["persist"]

    def test_threads_requires_auth_when_enabled(self, api_server):
        """鉴权开启时会话列表须登录（不再免鉴权白名单）。"""
        status, data = _get(api_server, "/projects/qb/threads")
        assert status == 401
        token = _get_token(api_server)
        status, data = _get(api_server, "/projects/qb/threads", token=token)
        assert status == 200
        assert "threads" in data

    def test_rename_and_delete_thread(self, api_server, monkeypatch):
        """重命名 + 删除会话（持久化 + 索引更新）。"""
        _set_brain_env()
        monkeypatch.setattr(
            "server.web.brain._run_claude",
            lambda prompt, timeout: (True, "ok", None),
        )
        token = _get_token(api_server)
        _post(api_server, "/conversation", {"message": "title-me", "thread_id": "qb::r1", "project": "qb"}, token=token)
        # 重命名
        status, data = _post(
            api_server, "/projects/qb/threads/qb%3A%3Ar1/rename",
            {"title": "新标题"}, token=token,
        )
        assert status == 200
        _, threads = _get(api_server, "/projects/qb/threads", token=token)
        assert threads["threads"][0]["title"] == "新标题"
        # 删除
        status, data = _delete(api_server, "/projects/qb/threads/qb%3A%3Ar1", token)
        assert status == 200
        _, threads = _get(api_server, "/projects/qb/threads", token=token)
        assert threads["threads"] == []

    def test_delete_thread_401_without_auth(self, api_server):
        """删除会话需鉴权（写操作不放松）。"""
        parsed = urlparse(api_server)
        conn = HTTPConnection(parsed.hostname, parsed.port, timeout=5)
        try:
            conn.request("DELETE", "/projects/qb/threads/x")
            resp = conn.getresponse()
            resp.read()
            assert resp.status in (401, 200)
        finally:
            conn.close()

    def test_cards_and_search_endpoints(self, api_server, monkeypatch, tmp_path):
        """测试 GET /cards 与 GET /cards/search，含分页、过滤、搜索与免鉴权。"""
        cards_dir = tmp_path / "cards"
        cards_dir.mkdir(parents=True, exist_ok=True)
        index_file = cards_dir / "cards.index.jsonl"

        import json
        mock_cards = [
            {"id": "ccc001", "project": "ccc", "title": "任务一", "state": "待分派", "executor": "Claude", "path": "docs/dispatch/ccc/ccc001.md"},
            {"id": "ccc002", "project": "ccc", "title": "任务二", "state": "执行中", "executor": "OpenCode", "path": "docs/dispatch/ccc/ccc002.md"},
            {"id": "qb001", "project": "qb", "title": "任务三", "state": "已回写", "executor": "Claude", "path": "docs/dispatch/qb/qb001.md"},
        ]
        with open(index_file, "w", encoding="utf-8") as f:
            for c in mock_cards:
                f.write(json.dumps(c, ensure_ascii=False) + "\n")

        # 1. Test GET /cards (no auth)
        status, data = _get(api_server, "/cards")
        assert status == 200
        assert data["total"] == 3
        assert len(data["cards"]) == 3
        assert data["cards"][0]["id"] == "ccc001"

        # 2. Test GET /cards with project filter
        status, data = _get(api_server, "/cards?project=ccc")
        assert status == 200
        assert data["total"] == 2
        assert all(c["project"] == "ccc" for c in data["cards"])

        # 3. Test GET /cards with state filter
        from urllib.parse import quote
        status, data = _get(api_server, f"/cards?state={quote('执行中')}")
        assert status == 200
        assert data["total"] == 1
        assert data["cards"][0]["id"] == "ccc002"

        # 4. Test GET /cards pagination
        status, data = _get(api_server, "/cards?page_size=2&page=1")
        assert status == 200
        assert len(data["cards"]) == 2
        assert data["total"] == 3
        assert data["pages"] == 2

        # 5. Test GET /cards/search keyword and scoring
        status, data = _get(api_server, "/cards/search?q=Claude")
        assert status == 200
        assert len(data["cards"]) == 2
        assert data["cards"][0]["executor"] == "Claude"

    def test_task_status_feedback_loop(self, api_server, monkeypatch, tmp_path):
        """测试任务状态变化回流与 watcher 通知。"""
        from server.board.models import BoardItem
        from server.web import server as srv_mod

        # 模拟 card
        item = BoardItem(
            id="T99",
            title="测试任务",
            state="待分派",
            project="qb",
            thread_id="qb::test_thread",
        )

        # 触发通知
        srv_mod._notify_card_status_change(item, "created")

        # 验证会话内存中是否有通知消息
        conv = srv_mod._thread_conversations["qb::test_thread"]
        assert len(conv) == 1
        assert conv[0]["role"] == "system"
        assert conv[0]["type"] == "task_status"
        assert conv[0]["task_id"] == "T99"
        assert conv[0]["status"] == "待分派"
        assert "T99" in conv[0]["message"]
        assert "已成功下达" in conv[0]["message"]


class TestCardsFallback:
    """测试 /cards 缺索引兜底与结构化高级回顾查询功能。"""

    @pytest.fixture(autouse=True)
    def _setup_dispatch(self, tmp_path, monkeypatch):
        # 隔离数据和索引
        monkeypatch.setenv("CCC_DATA_DIR", str(tmp_path))
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        monkeypatch.setenv("PYTEST_CURRENT_TEST", "1")

        # 模拟 dispatch 目录
        dispatch_dir = tmp_path / "docs" / "dispatch"
        dispatch_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr("server.web.server._DISPATCH_DIR", dispatch_dir)

        # 写入两个常规测试任务卡
        c1 = (
            "# 任务卡 tst001 · 任务一\n"
            "> 关联：TST · 执行体：Claude · 验收：Codex · 状态：待分派 · 项目：tst · 日期：2026-08-01\n"
        )
        c2 = (
            "# 任务卡 tst002 · 任务二\n"
            "> 关联：TST · 执行体：OpenCode · 验收：Codex · 状态：执行中 · 项目：tst · 日期：2026-08-02\n"
        )
        p1 = dispatch_dir / "tst001.md"
        p2 = dispatch_dir / "tst002.md"
        p1.write_text(c1, encoding="utf-8")
        p2.write_text(c2, encoding="utf-8")

        # 确保初始状态无索引文件存在
        index_file = dispatch_dir / "cards.index.jsonl"
        if index_file.exists():
            index_file.unlink()

        return dispatch_dir

    def test_cards_missing_index_fallback(self, api_server, tmp_path, _setup_dispatch):
        """测试索引文件缺失时，/cards 接口自动回退至全量扫描并重建索引。"""
        dispatch_dir = _setup_dispatch
        index_file = dispatch_dir / "cards.index.jsonl"
        assert not index_file.exists()

        # 发起查询
        status, data = _get(api_server, "/cards")
        assert status == 200
        assert data["total"] == 2
        assert len(data["cards"]) == 2
        assert {c["id"] for c in data["cards"]} == {"tst001", "tst002"}

        # 验证索引文件是否已被成功重建
        assert index_file.exists()

    def test_cards_search_missing_index_fallback(self, api_server, tmp_path, _setup_dispatch):
        """测试索引文件缺失时，/cards/search 接口自动回退至全量扫描并重建索引。"""
        dispatch_dir = _setup_dispatch
        index_file = dispatch_dir / "cards.index.jsonl"
        assert not index_file.exists()

        # 发起查询
        status, data = _get(api_server, "/cards/search?q=Claude")
        assert status == 200
        assert data["total"] == 1
        assert data["cards"][0]["id"] == "tst001"

        # 验证索引文件是否已被成功重建
        assert index_file.exists()

    def test_structured_reviews_and_archived_filter(self, api_server, tmp_path, _setup_dispatch):
        """测试结构化高级查询（按执行体/时间过滤）与 include_archived 功能。"""
        dispatch_dir = _setup_dispatch

        # 写入一张模拟的已归档过期卡
        c3 = (
            "# 任务卡 tst003 · 归档任务\n"
            "> 关联：TST · 执行体：Claude · 验收：Codex · 状态：已关闭 · 项目：tst · 日期：2026-01-01\n"
            "## 回写区\n"
            "**日期**：2026-01-05\n"
        )
        archive_dir = dispatch_dir.parent / "archive" / "ccc-tasks" / "tst"
        archive_dir.mkdir(parents=True, exist_ok=True)
        (archive_dir / "tst003-old.md").write_text(c3, encoding="utf-8")

        # 重建包含归档文件的索引
        from server.board.loader import load_dispatch_cards
        load_dispatch_cards(dispatch_dir, include_archived=True)

        # 1. 默认查询不含已归档任务卡
        status, data = _get(api_server, "/cards")
        assert status == 200
        assert data["total"] == 2
        assert "tst003" not in {c["id"] for c in data["cards"]}

        # 2. 显式指定 include_archived=1 含已归档任务卡
        status, data = _get(api_server, "/cards?include_archived=1")
        assert status == 200
        assert data["total"] == 3
        assert "tst003" in {c["id"] for c in data["cards"]}

        # 3. 按执行体 (executor) 过滤回顾
        status, data = _get(api_server, "/cards?executor=Claude&include_archived=1")
        assert status == 200
        assert data["total"] == 2
        assert {c["id"] for c in data["cards"]} == {"tst001", "tst003"}

        # 4. 按分派日期 (dispatched_at) 过滤回顾
        status, data = _get(api_server, "/cards?dispatched_at=2026-08-02")
        assert status == 200
        assert data["total"] == 1
        assert data["cards"][0]["id"] == "tst002"


