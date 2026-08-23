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


@pytest.fixture(autouse=True)
def _clear_conversation_state(monkeypatch):
    """每个测试前清空对话历史与大脑 env，避免跨用例污染。"""
    from server.web import server as srv_mod

    srv_mod._conversations.clear()
    srv_mod._thread_conversations.clear()
    _clear_brain_env()
    # 强制将 M1 对话桥设为空，确保对话代理测试完全隔离，不受本地 config.env 生产配置污染
    monkeypatch.setattr("server.web.server._chat_bridge_url", lambda: "")
    yield
    srv_mod._conversations.clear()
    srv_mod._thread_conversations.clear()
    _clear_brain_env()


class TestConversation:
    """/conversation 大脑代理测试：缺配置 503、忙 503、成功 200 reply、
    超时 504、失败 502、历史落盘、prompt 含上下文、鉴权不回归。"""

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
    def _clear_conversation_state(self, monkeypatch):
        """每个测试前清空对话历史与大脑 env，避免跨用例污染。"""
        from server.web import server as srv_mod

        srv_mod._conversations.clear()
        srv_mod._thread_conversations.clear()
        _clear_brain_env()
        # 强制将 M1 对话桥设为空，确保对话代理测试完全隔离，不受本地 config.env 生产配置污染
        monkeypatch.setattr("server.web.server._chat_bridge_url", lambda: "")
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
    def _clear_conversation_state(self, monkeypatch):
        """每个测试前清空对话历史（含会话桶）与大脑 env，避免跨用例污染。"""
        from server.web import server as srv_mod
        from server.web import brain as brain_mod

        srv_mod._conversations.clear()
        srv_mod._thread_conversations.clear()
        brain_mod._session_locks.clear()
        _clear_brain_env()
        # 强制将 M1 对话桥设为空，确保对话代理测试完全隔离，不受本地 config.env 生产配置污染
        monkeypatch.setattr("server.web.server._chat_bridge_url", lambda: "")
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
        """GET / 返回 DSH 监控墙页（ccc-plan-045：对话页职能由墙承接）。

        旧断言为 legacy-chat（<title>CCC</title>）；2026-08-24 根路径改服务墙页，
        legacy-chat 退居 /app 回滚位（见 test_app_returns_legacy_chat_html）。"""
        status, body_text = _get_raw(api_server, "/")
        assert status == 200
        assert "<html" in body_text.lower()
        assert "DSH 监控墙" in body_text
        assert "/wall/api/stream" in body_text

    def test_wall_page_served(self, api_server):
        """GET /wall 与 / 同源等价（墙页书签入口）。"""
        status_root, root_text = _get_raw(api_server, "/")
        status_wall, wall_text = _get_raw(api_server, "/wall")
        assert (status_root, status_wall) == (200, 200)
        assert wall_text == root_text

    def test_app_returns_legacy_chat_html(self, api_server):
        """GET /app 返回 legacy-chat/index.html（回滚位完好）。"""
        status, body_text = _get_raw(api_server, "/app")
        assert status == 200
        assert "<title>CCC</title>" in body_text
        assert "信息墙" in body_text  # hub-nav 对话标签已替换为墙入口

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
        """看板静态资源免鉴权；board.js 未 export 时 404（勿 401）。"""
        status, _ = _get_raw(api_server, "/css/base.css")
        assert status == 200
        status, _ = _get_raw(api_server, "/data/board.js")
        assert status in (200, 404)

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
        # Phase2：/board/roadmap 改读 roadmap.py 的项目线路图（roadmaps），不再从 epic 卡派生 overview/by_project
        assert "roadmaps" in data
        assert "total" in data
        assert isinstance(data["roadmaps"], list)

    def test_roadmap_projects_200(self, api_server):
        """GET /roadmap/projects（Phase2 新增）返回项目线路图列表。"""
        token = _get_token(api_server)
        status, data = _get(api_server, "/roadmap/projects", token=token)
        assert status == 200
        assert "roadmaps" in data
        assert "total" in data
        assert isinstance(data["roadmaps"], list)
        # 真实仓库应有 docs/projects/<p>/roadmap.md；至少应返回结构合法
        for rm in data["roadmaps"]:
            assert "project" in rm
            assert "drafts" in rm
            assert "milestones" in rm


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
        assert "columns" in data
        assert isinstance(data["columns"], dict)
        assert "机审" in data["columns"]
        assert data.get("note")
        for state, count in data.items():
            if state in ("columns", "note"):
                continue
            assert isinstance(state, str)
            assert isinstance(count, int)
        for col, count in data["columns"].items():
            assert isinstance(col, str)
            assert isinstance(count, int)

    def test_columns_match_snapshot_counts(self, api_server):
        """columns 与 snapshot.counts 同看板列语义；已关闭 snapshot 有 cap 10。"""
        token = _get_token(api_server)
        status_s, states = _get(api_server, "/board/states", token=token)
        status_p, snap = _get(api_server, "/board/snapshot", token=token)
        assert status_s == 200 and status_p == 200
        for col in ("待分派", "执行中", "机审", "已回写", "打回"):
            assert states["columns"].get(col, 0) == snap["counts"].get(col, 0)
        # snapshot 已关闭最多展示 10；states.columns 为全量列计数
        assert states["columns"].get("已关闭", 0) >= snap["counts"].get("已关闭", 0)


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
        # counts 与 columns 同步；已关闭 cap 10 → counts 之和 ≤ 项目总数
        for state, count in data["counts"].items():
            assert count == len(data["columns"].get(state, []))
        total = sum(data["counts"].values())
        assert total <= proj_rows[0]["count"]
        assert data.get("closed_capped") is True
        assert data.get("closed_limit") == 10
        if data["counts"].get("已关闭", 0) < 10:
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

    @pytest.fixture(autouse=True)
    def _clear_running_cache(self):
        """tasks/running 整表缓存按测试隔离（marker/mock 变化需即时重算）。"""
        from server.web.server import _RUNNING_TASKS_CACHE

        _RUNNING_TASKS_CACHE.update(ts=0.0, key="__reset__", data=None)
        yield
        _RUNNING_TASKS_CACHE.update(ts=0.0, key="__reset__", data=None)

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
        (log_dir / "T999.running").write_text("pid=1\n", encoding="utf-8")
        monkeypatch.setenv("EXECUTOR_LOG_DIR", str(log_dir))
        monkeypatch.setattr(
            srv,
            "_load_board_items",
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
            srv,
            "_load_board_items",
            lambda: [BoardItem(id="T777", title="脏", state="执行中", executor="Claude Code")],
        )
        status, data = _get(api_server, "/tasks/running")
        assert status == 200
        t = data["tasks"][0]
        assert t["dirty_files"] == 1
        wd.clear_dirty_cache()

    def test_only_running_included(self, api_server, monkeypatch):
        """/tasks/running：执行中 + 机审（已回写且未过机审）；其它列不进。"""
        from server.web import server as srv
        from server.board.models import BoardItem

        monkeypatch.setattr(
            srv,
            "_load_board_items",
            lambda: [
                BoardItem(id="T1", title="待分派", state="待分派"),
                BoardItem(
                    id="T2",
                    title="已回写过审",
                    state="已回写",
                    machine_audit_passed=True,
                ),
                BoardItem(
                    id="T3",
                    title="机审中",
                    state="已回写",
                    machine_audit_passed=False,
                ),
                BoardItem(id="T4", title="跑着", state="执行中"),
                BoardItem(id="T5", title="已关闭", state="已关闭"),
            ],
        )
        status, data = _get(api_server, "/tasks/running")
        assert status == 200
        ids = {t["work_id"] for t in data["tasks"]}
        assert ids == {"T3", "T4"}
        by_id = {t["work_id"]: t for t in data["tasks"]}
        assert by_id["T3"]["board_column"] == "机审"
        assert by_id["T4"]["board_column"] == "执行中"

    def test_no_log_dir_still_returns_cards(self, api_server, monkeypatch):
        """EXECUTOR_LOG_DIR 未配置 → 仍返回执行中卡（日志字段空）。"""
        from server.web import server as srv
        from server.board.models import BoardItem

        monkeypatch.delenv("EXECUTOR_LOG_DIR", raising=False)
        monkeypatch.delenv("CCC_CONFIG_ENV", raising=False)
        monkeypatch.setattr(
            srv,
            "_load_board_items",
            lambda: [BoardItem(id="T5", title="跑着", state="执行中", executor="X")],
        )
        status, data = _get(api_server, "/tasks/running")
        assert status == 200
        t = data["tasks"][0]
        assert t["work_id"] == "T5"
        assert t["log_tail"] == []
        assert t["elapsed_s"] is None

    def test_log_dir_from_ccc_config_env(self, api_server, tmp_path, monkeypatch):
        """web-server 仅有 CCC_CONFIG_ENV 时也能读到 EXECUTOR_LOG_DIR（生产 launchd 形态）。"""
        from server.web import server as srv
        from server.board.models import BoardItem

        log_dir = tmp_path / "exec-from-cfg"
        log_dir.mkdir()
        (log_dir / "T77.log").write_text("a\nb\nc\n→ Read x\n", encoding="utf-8")
        (log_dir / "T77.running").write_text("pid=9\n", encoding="utf-8")
        cfg = tmp_path / "config.env"
        cfg.write_text(f"EXECUTOR_LOG_DIR={log_dir}\n", encoding="utf-8")
        monkeypatch.delenv("EXECUTOR_LOG_DIR", raising=False)
        monkeypatch.setenv("CCC_CONFIG_ENV", str(cfg))
        monkeypatch.setattr(
            srv,
            "_load_board_items",
            lambda: [BoardItem(id="T77", title="cfg日志", state="执行中", executor="OpenCode")],
        )
        status, data = _get(api_server, "/tasks/running")
        assert status == 200
        t = data["tasks"][0]
        assert t["work_id"] == "T77"
        assert t["elapsed_s"] is not None
        assert t["tool_calls"] == 1
        assert "→ Read x" in t["log_tail"] or t["log_tail"][-1].endswith("Read x")
        assert t.get("log_bytes", 0) > 0

    def test_stale_dead_pid_marker_not_treated_as_running(self, api_server, tmp_path, monkeypatch):
        """死 PID 残留标记不点亮进行中：已关闭卡不进 /tasks/running、live 徽章为 False。

        引擎崩溃/部署后遗留的死标记不应让看板把死卡当「进行中」并每轮富化。
        """
        import os

        from server.web import server as srv
        from server.board.models import BoardItem

        log_dir = tmp_path / "exec-logs"
        log_dir.mkdir()
        # 死 PID 标记（已关闭卡残留）
        (log_dir / "Tdead.running").write_text(
            "engine_pid=99999999\npid=99999998\nchild_pid=99999997\n",
            encoding="utf-8",
        )
        # 活 PID 标记
        (log_dir / "Talive.running").write_text(
            f"pid={os.getpid()}\n",
            encoding="utf-8",
        )
        monkeypatch.setenv("EXECUTOR_LOG_DIR", str(log_dir))
        monkeypatch.setattr(
            srv,
            "_load_board_items",
            lambda: [
                BoardItem(id="Tdead", title="残留死标记", state="已关闭", executor="OpenCode"),
                BoardItem(id="Talive", title="活标记", state="已回写", executor="OpenCode"),
            ],
        )
        status, data = _get(api_server, "/tasks/running")
        assert status == 200
        ids = {t["work_id"] for t in data["tasks"]}
        assert ids == {"Talive"}
        by_id = {t["work_id"]: t for t in data["tasks"]}
        assert by_id["Talive"]["metrics_live"] is True


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


class TestOpsServices:
    """GET /ops/services + POST /ops/service/{action}（一键开关，模块 A）"""

    def test_get_services_shape(self, api_server):
        """GET /ops/services → 服务清单含 label/name/running。"""
        token = _get_token(api_server)
        status, data = _get(api_server, "/ops/services", token=token)
        assert status == 200
        assert "services" in data
        assert isinstance(data["services"], list)
        assert len(data["services"]) > 0
        for s in data["services"]:
            assert "label" in s
            assert "name" in s
            assert "running" in s
            assert isinstance(s["running"], bool)

    def test_post_service_requires_confirm(self, api_server):
        """POST /ops/service/restart 缺 confirm → 400（前端二次确认弹窗）。"""
        token = _get_token(api_server)
        status, data = _post(
            api_server, "/ops/service/restart",
            {"service": "com.ccc.web-server"}, token=token,
        )
        assert status == 400
        assert "confirm" in str(data)

    def test_post_service_unknown_rejected(self, api_server):
        """POST /ops/service/restart 未知服务 → 400（白名单拦截防命令注入）。"""
        token = _get_token(api_server)
        status, data = _post(
            api_server, "/ops/service/restart",
            {"service": "com.evil.service", "confirm": True}, token=token,
        )
        assert status == 400
        assert "未知服务" in str(data)


class TestOpsPortals:
    """GET /ops/portals（已开发成果汇总，模块 C）"""

    def test_get_portals_shape(self, api_server):
        """GET /ops/portals → 成果清单含 name/machine/port/url/alive。"""
        token = _get_token(api_server)
        status, data = _get(api_server, "/ops/portals", token=token)
        assert status == 200
        assert "portals" in data
        assert isinstance(data["portals"], list)
        assert len(data["portals"]) > 0
        for p in data["portals"]:
            assert "name" in p
            assert "machine" in p
            assert "port" in p
            assert "url" in p
            assert "alive" in p
            assert isinstance(p["alive"], bool)

    def test_portals_include_known_services(self, api_server):
        """成果清单应含 CCC/DSH/HP MCP 等已知服务。"""
        token = _get_token(api_server)
        status, data = _get(api_server, "/ops/portals", token=token)
        names = {p["name"] for p in data["portals"]}
        assert "CCC 控制台" in names
        assert "DSH Web" in names
        assert "HP MCP Server" in names


class TestOpsPgHealth:
    """GET /ops/pg-health（HP PostgreSQL 健康：探针状态文件 + TCP 兜底，ccc-plan-031）"""

    @staticmethod
    def _stub_tcp():
        from types import SimpleNamespace

        return lambda h, p, timeout=3.0: SimpleNamespace(host=h, port=p, reachable=True, latency_ms=1.0)

    def test_not_configured(self, api_server):
        """无 CLUSTER_PG_TARGET → configured=false + status=missing，不 500。"""
        token = _get_token(api_server)
        status, data = _get(api_server, "/ops/pg-health", token=token)
        assert status == 200
        assert data["configured"] is False
        assert data["status"] == "missing"

    def test_configured_probe_ok(self, api_server, monkeypatch):
        """配置目标 + 探针 ok → 透传 ok + tcp_reachable true。"""
        monkeypatch.setenv("CLUSTER_PG_TARGET", "192.168.3.131:5432")
        monkeypatch.setattr("server.web.server.check_tcp_reachable", self._stub_tcp())
        monkeypatch.setattr(
            "server.web.server._read_pg_probe_status",
            lambda host: {
                "status": "ok", "ts": "2026-08-15 19:00:52",
                "detail": "SELECT 1 ok", "elapsed_ms": "107",
                "consecutive_fail": "0",
            },
        )
        token = _get_token(api_server)
        status, data = _get(api_server, "/ops/pg-health", token=token)
        assert status == 200
        assert data["configured"] is True
        assert data["host"] == "192.168.3.131"
        assert data["port"] == 5432
        assert data["status"] == "ok"
        assert data["tcp_reachable"] is True
        assert data["probe_ts"] == "2026-08-15 19:00:52"

    def test_configured_probe_zombie(self, api_server, monkeypatch):
        """探针 zombie（本次事故形态：端口通但连接挂）→ status 透传 zombie。"""
        monkeypatch.setenv("CLUSTER_PG_TARGET", "192.168.3.131:5432")
        monkeypatch.setattr("server.web.server.check_tcp_reachable", self._stub_tcp())
        monkeypatch.setattr(
            "server.web.server._read_pg_probe_status",
            lambda host: {
                "status": "zombie", "ts": "2026-08-14 23:05:00",
                "detail": "could not open shared memory segment", "consecutive_fail": "7",
            },
        )
        token = _get_token(api_server)
        status, data = _get(api_server, "/ops/pg-health", token=token)
        assert status == 200
        assert data["status"] == "zombie"
        assert data["consecutive_fail"] == "7"

    def test_probe_missing_fallback(self, api_server, monkeypatch):
        """探针文件缺失/SSH 失败 → status=missing，不 500。"""
        monkeypatch.setenv("CLUSTER_PG_TARGET", "192.168.3.131:5432")
        monkeypatch.setattr("server.web.server.check_tcp_reachable", self._stub_tcp())
        monkeypatch.setattr("server.web.server._read_pg_probe_status", lambda host: {})
        token = _get_token(api_server)
        status, data = _get(api_server, "/ops/pg-health", token=token)
        assert status == 200
        assert data["status"] == "missing"

    def test_no_auth_401(self, api_server):
        status, data = _get(api_server, "/ops/pg-health")
        assert status == 401
        assert "error" in data


class TestOpsConcurrency:
    """GET /ops/concurrency（槽位上限 + 并发/进程埋点尾部，只读）。"""

    def test_returns_slots_and_tails(self, api_server):
        token = _get_token(api_server)
        status, data = _get(api_server, "/ops/concurrency", token=token)
        assert status == 200
        assert data["slots"]["exec_max"] >= 1
        assert data["slots"]["audit_max"] >= 1
        assert isinstance(data["engine_metrics_tail"], list)
        assert isinstance(data["worker_events_tail"], list)

    def test_no_auth_401(self, api_server):
        status, data = _get(api_server, "/ops/concurrency")
        assert status == 401
        assert "error" in data


class TestOpsRelayStats:
    """GET /ops/relay-stats：今日请求（总/Pro/flash/code）+ 近10s增量 + 健康。"""

    def test_returns_today_and_deltas(self, api_server, monkeypatch, tmp_path):
        import json
        import time
        from datetime import datetime
        from server.web import server as srv

        # Clear cache to avoid state leakage from other tests
        srv._RELAY_STATS_CACHE = None
        srv._RELAY_LAST_SNAPSHOT = None

        now_ms = int(time.time() * 1000)
        today_start_ms = int(datetime.combine(datetime.now().date(), datetime.min.time()).timestamp() * 1000)
        usage = [
            {"timestamp": now_ms - 5000, "model": "flash"},
            {"timestamp": now_ms - 5000, "model": "code"},
            {"timestamp": now_ms - 5000, "model": "claude-sonnet-5"},
            {"timestamp": now_ms - 60000, "model": "flash"},
            {"timestamp": today_start_ms + 1000, "model": "flash"},
        ]
        f = tmp_path / "usage.json"
        f.write_text(json.dumps(usage), encoding="utf-8")
        monkeypatch.setenv("CCC_RELAY_USAGE_API", "")  # 显式空 = 跳过实时接口，走文件兜底
        monkeypatch.setenv("CCC_RELAY_USAGE_FILE", str(f))

        token = _get_token(api_server)
        status, data = _get(api_server, "/ops/relay-stats", token=token)
        assert status == 200
        assert data["today"]["total"] == 5
        assert data["today"]["flash"] == 3
        assert data["today"]["code"] == 1
        assert data["today"]["pro"] == 1
        assert data["healthy"] is True

    def test_delta_after_snapshot_change(self, monkeypatch, tmp_path):
        """增量 = 服务端上次读数差值（文件新增记录 → 下次 delta 反映）。"""
        import json
        import time

        from server.web import server as srv

        now_ms = int(time.time() * 1000)
        f = tmp_path / "usage.json"
        f.write_text(
            json.dumps([{"timestamp": now_ms - 5000, "model": "flash"}]),
            encoding="utf-8",
        )
        monkeypatch.setenv("CCC_RELAY_USAGE_API", "")
        monkeypatch.setenv("CCC_RELAY_USAGE_FILE", str(f))
        monkeypatch.setattr(srv, "_RELAY_STATS_TTL_S", 0)
        srv._RELAY_STATS_CACHE = None
        srv._RELAY_LAST_SNAPSHOT = None

        first = srv._compute_relay_stats()
        assert first["delta_10s"]["total"] == 0

        f.write_text(
            json.dumps(
                [
                    {"timestamp": now_ms - 5000, "model": "flash"},
                    {"timestamp": now_ms - 3000, "model": "code"},
                    {"timestamp": now_ms - 2000, "model": "code"},
                ]
            ),
            encoding="utf-8",
        )
        second = srv._compute_relay_stats()
        assert second["delta_10s"]["total"] == 2
        assert second["delta_10s"]["code"] == 2

    def test_api_by_tier_bucketing(self):
        from server.web.server import _relay_counts_from_api

        d = {
            "total": 100,
            "by_tier": {
                "flash": {"n": 30},
                "code": {"n": 40},
                "unknown": {"n": 25},
                "pro": {"n": 5},
            },
        }
        assert _relay_counts_from_api(d) == {
            "total": 100,
            "pro": 30,
            "flash": 30,
            "code": 40,
        }

    def test_missing_file_unhealthy(self, api_server, monkeypatch, tmp_path):
        from server.web import server as srv

        srv._RELAY_STATS_CACHE = None
        monkeypatch.setenv("CCC_RELAY_USAGE_API", "")
        monkeypatch.setenv("CCC_RELAY_USAGE_FILE", str(tmp_path / "nope.json"))
        token = _get_token(api_server)
        status, data = _get(api_server, "/ops/relay-stats", token=token)
        assert status == 200
        assert data["healthy"] is False
        assert data["alert"]

    def test_no_auth_401(self, api_server):
        status, data = _get(api_server, "/ops/relay-stats")
        assert status == 401
        assert "error" in data


class TestAuditStatusTag:
    """机审列状态标签辅助函数。"""

    def test_audit_marker_alive_web(self, tmp_path):
        import os

        from server.web.server import _marker_alive_web

        marker = tmp_path / "x1-audit.running"
        marker.write_text(f"engine_pid={os.getpid()}\npid={os.getpid()}\n", encoding="utf-8")
        assert _marker_alive_web(tmp_path, "x1", audit=True) is True
        marker.write_text("pid=99999999\n", encoding="utf-8")
        assert _marker_alive_web(tmp_path, "x1", audit=True) is False
        assert _marker_alive_web(tmp_path, "nope", audit=True) is False

    def test_infra_cooldown_active_web(self):
        from server.web.server import _infra_cooldown_active_web

        assert _infra_cooldown_active_web({"infra_cooldown_until": "2099-01-01T00:00:00Z"}, 0) is True
        assert _infra_cooldown_active_web({"infra_cooldown_until": "2000-01-01T00:00:00Z"}, 1e12) is False
        assert _infra_cooldown_active_web({}, 0) is False


class TestTaskTransition:
    """POST /tasks/{id}/transition → 运行时重新分派（主树卡文件只读）。"""

    def test_closed_card_rejected(self, api_server, monkeypatch, tmp_path):
        monkeypatch.setenv("EXECUTOR_LOG_DIR", str(tmp_path))
        token = _get_token(api_server)
        status, snap = _get(api_server, "/board/snapshot", token=token)
        assert status == 200
        closed = snap["columns"].get("已关闭", [])
        if not closed:
            pytest.skip("无已关闭卡")
        status, data = _post(
            api_server,
            f"/tasks/{closed[0]['id']}/transition",
            {"status": "待分派"},
            token=token,
        )
        assert status == 400
        assert "不可重新分派" in data["error"]

    def test_redispatch_writes_runtime_sidecar(self, api_server, monkeypatch, tmp_path):
        monkeypatch.setenv("EXECUTOR_LOG_DIR", str(tmp_path))
        token = _get_token(api_server)
        status, snap = _get(api_server, "/board/snapshot", token=token)
        assert status == 200
        candidates = [t["id"] for col in ("打回", "待分派") for t in snap["columns"].get(col, [])]
        if not candidates:
            pytest.skip("无打回/待分派卡")
        task_id = candidates[0]
        status, data = _post(
            api_server,
            f"/tasks/{task_id}/transition",
            {"status": "待分派"},
            token=token,
        )
        assert status == 200, data
        assert data["runtime"] is True
        from server.engine.runtime_state import read_card_state

        rt = read_card_state(tmp_path)
        assert rt[task_id]["state"] == "待分派"
        assert rt[task_id]["retry_count"] == 0
        assert rt[task_id]["redispatch"]


class TestCardsComposite:
    """GET /cards 走合成视图（运行时状态 + 分支证据 + closed_at）。"""

    def test_cards_reflects_runtime_state(self, api_server, monkeypatch, tmp_path):
        monkeypatch.setenv("EXECUTOR_LOG_DIR", str(tmp_path))
        token = _get_token(api_server)
        status, snap = _get(api_server, "/board/snapshot", token=token)
        assert status == 200
        pending = [t["id"] for t in snap["columns"].get("待分派", [])]
        if not pending:
            pytest.skip("无待分派卡")

        from server.engine.runtime_state import write_card_state
        from urllib.parse import quote

        write_card_state(tmp_path, pending[0], state="执行中", retry_count=0)
        status, data = _get(
            api_server,
            "/cards?state=" + quote("执行中") + "&page_size=50",
            token=token,
        )
        assert status == 200
        ids = [c["id"] for c in data.get("cards", [])]
        assert pending[0] in ids, "运行时状态应被 /cards 合成视图覆盖"

    def test_closed_cards_have_closed_at(self, api_server, monkeypatch, tmp_path):
        monkeypatch.setenv("EXECUTOR_LOG_DIR", str(tmp_path))
        token = _get_token(api_server)
        from urllib.parse import quote

        status, data = _get(
            api_server,
            "/cards?state=" + quote("已关闭") + "&page_size=50",
            token=token,
        )
        assert status == 200
        closed = data.get("cards", [])
        if not closed:
            pytest.skip("无已关闭卡")
        assert all(c.get("closed_at") for c in closed[:5]), "已关闭卡应带 closed_at（git 合入时间）"


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
        # 核心业务项目必须在列（QuantHive 可列示，但不可 taskable）
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
        """可下达任务：qb/medio-0；CCC 平台自研禁出卡（2026-08-10 红线）；QuantHive 禁止经 CCC 派发。"""
        status, data = _get(api_server, "/projects")
        assert status == 200
        by_name = {p["name"]: p for p in data["projects"]}
        for required in ("qb", "medio-0"):
            assert by_name[required]["is_taskable"] is True, f"{required} 应可下达任务"
        assert by_name["CCC"]["is_taskable"] is False, "CCC 平台自研禁出卡（2026-08-10 红线）"
        assert by_name["QuantHive"]["is_taskable"] is False, "QuantHive 禁止 CCC taskable"


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
            api_server,
            "/conversation",
            {"message": "你好世界", "thread_id": "qb::abc", "project": "qb"},
            token=token,
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
        _post(
            api_server, "/conversation", {"message": "persist", "thread_id": "qb::keep", "project": "qb"}, token=token
        )
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
            api_server,
            "/projects/qb/threads/qb%3A%3Ar1/rename",
            {"title": "新标题"},
            token=token,
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
        """GET /cards 与 /cards/search 走合成视图：真实卡文件 + 过滤/分页/搜索。"""
        from server.web import server as srv_mod

        dispatch_dir = tmp_path / "dispatch"
        rows = [
            ("xy001", "xy", "待分派", "Claude", "任务一"),
            ("xy002", "xy", "执行中", "OpenCode", "任务二"),
            ("qb001", "qb", "已回写", "Claude", "任务三"),
        ]
        for cid, proj, state, execu, title in rows:
            d = dispatch_dir / proj
            d.mkdir(parents=True, exist_ok=True)
            (d / f"{cid}-task.md").write_text(
                f"# 任务卡 {cid} · {title}\n"
                f"> 关联：{proj} · 执行体：{execu} · 验收：Claude Code · 状态：{state} · 日期：2026-08-07\n"
                "\n## 目标\nx\n\n## 验收标准\nx\n",
                encoding="utf-8",
            )
        monkeypatch.setattr(srv_mod, "_DISPATCH_DIR", dispatch_dir)

        # 1. Test GET /cards (no auth)
        status, data = _get(api_server, "/cards")
        assert status == 200
        assert data["total"] == 3
        assert len(data["cards"]) == 3
        assert {c["id"] for c in data["cards"]} == {"xy001", "xy002", "qb001"}

        # 2. Test GET /cards with project filter
        status, data = _get(api_server, "/cards?project=xy")
        assert status == 200
        assert data["total"] == 2
        assert all(c["project"] == "xy" for c in data["cards"])

        # 3. Test GET /cards with state filter
        from urllib.parse import quote

        status, data = _get(api_server, f"/cards?state={quote('执行中')}")
        assert status == 200
        assert data["total"] == 1
        assert data["cards"][0]["id"] == "xy002"

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

        # 重置模块级看板缓存（api_server 为 module 级共享实例，跨测试泄漏缓存
        # 会导致「索引缺失时命中旧缓存、断言重建失败」的顺序依赖 flaky）。
        import server.web.server as _srv

        monkeypatch.setattr(_srv, "_BOARD_CACHE", None)
        monkeypatch.setattr(_srv, "_ENRICHED_CACHE", None)

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


# ── P1#10 机审返工：/loop/findings type 推导 ──


class TestFindingType:
    """从标题推导 finding type（observer 报告表无 id 列，机审红旗返工）。"""

    def test_unit_mapping_all_types(self):
        from server.web.server import _finding_type_from_title

        cases = {
            "任务卡 clw004 状态漂移：roadmap 标注进行中": "drift",
            "项目 qh 缺席 roadmap.md 的业务线路段落": "missing_section",
            "方案 clw-plan-001 已完成但关联卡未全部关闭: clw001(执行中)": "broken_link",
            "已关闭任务卡 clw001 缺失或未完成维护区四问": "missing_four_questions",
            "里程碑 clw/会话加固 进度不一致：声明 进行中": "consistency",
            "已登记死文件复活: server/web/legacy-chat/arch/qb-arch.html": "tech",
            "卡 clw002 有真实人工批注但未见「## 批注落实」段": "tech",
            "其他未知标题": "scan",
        }
        for title, expect in cases.items():
            got = _finding_type_from_title(title)
            assert got == expect, f"{title!r} → {got}，期望 {expect}"

    def test_findings_api_returns_type(self, api_server, tmp_path, monkeypatch):
        """集成：造 observer 报告 → GET /loop/findings → findings[].type 非空且正确。"""
        from server.web import server as srv_mod

        observer_dir = tmp_path / "observer"
        observer_dir.mkdir(parents=True)
        (observer_dir / "2026-08-13-test-patrol.md").write_text(
            "# test\n\n"
            "| 权重 (Weight) | 交叉确认 | 影响 | 频次 | 描述 (Title) | 项目 | 作用对象 | 证据 |\n"
            "| --- | --- | --- | --- | --- | --- | --- | --- |\n"
            "| 10 | 是 | 高 | 3 | clw004 状态漂移：roadmap 标注进行中但实际已关闭 | clw | clw004 | docs/roadmap.md |\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(srv_mod, "_config_value", lambda k, d: str(tmp_path))
        token = _get_token(api_server)
        status, data = _get(api_server, "/loop/findings", token=token)
        assert status == 200
        reports = data.get("loop_reports", [])
        assert reports and reports[0]["findings"], "应有 1 条 finding"
        f = reports[0]["findings"][0]
        assert f["type"] == "drift", f"type 应为 drift，实际 {f.get('type')!r}"


class TestDshFindings:
    """DSH 审计报告（6 列契约）解析 + API + 人审留档 + 提交落盘。"""

    _DSH_MD = (
        "# DSH 审计报告 — 测试\n\n"
        "> 采集时间: 2026-08-15T00:00:00 · 运行节点: 麦克2017\n\n"
        "| 面 | 位置 file:行号 | 现象 | 证据 | 建议处置 | 置信度 |\n"
        "| --- | --- | --- | --- | --- | --- |\n"
        "| 开发机审分离 | server/config/executors.json:5 | 开发槽越权 | grep 实测 | 改 | 高 |\n"
        "| 中转站 | server/config/config.env:7 | 退役端口残留 | lsof 实测 | 删 | 中 |\n"
        "| 文档落点 | docs/T-mapping.md:16 | 前缀表滞后 | sed 实测 | 留 | 低 |\n"
    )

    def test_parse_dsh_md(self):
        """6 列解析单测：字段映射 + 置信度→severity + action 透传。"""
        from server.web.server import _parse_dsh_md

        findings = _parse_dsh_md(self._DSH_MD, "2026-08-15-dsh-audit-01", 1.0)
        assert len(findings) == 3, f"应有 3 条 finding，实际 {len(findings)}"
        f = findings[0]
        assert f["face"] == "开发机审分离"
        assert f["location"] == "server/config/executors.json:5"
        assert f["phenomenon"] == "开发槽越权"
        assert f["action"] == "改"
        assert f["confidence"] == "高"
        assert f["severity"] == "红旗"
        assert findings[1]["severity"] == "黄旗"
        assert findings[2]["severity"] == "蓝旗"

    def test_parse_dsh_md_project_column(self):
        """7 列新契约（加项目列）解析：project 字段映射 + 6 列旧格式兼容兜底空串。"""
        from server.web.server import _parse_dsh_md

        md7 = (
            "# DSH 报告\n\n"
            "| 面 | 位置 file:行号 | 现象 | 证据 | 建议处置 | 项目 | 置信度 |\n"
            "| --- | --- | --- | --- | --- | --- | --- |\n"
            "| L1 | program/CCC/server/x:1 | 越权 | grep 实测 | 改 | ccc | 高 |\n"
            "| L2 | qx-map/ide/x.md:2 | 滞后 | sed 实测 | 留 | qx-map | 中 |\n"
        )
        findings7 = _parse_dsh_md(md7, "2026-08-17-test-7col", 1.0)
        assert len(findings7) == 2
        assert findings7[0]["project"] == "ccc"
        assert findings7[0]["confidence"] == "高"
        assert findings7[0]["severity"] == "红旗"
        assert findings7[1]["project"] == "qx-map"
        assert findings7[1]["confidence"] == "中"

        # 6 列旧格式无项目列 → project 兜底空串，confidence 仍在末列
        md6 = (
            "# DSH 报告\n\n"
            "| 面 | 位置 file:行号 | 现象 | 证据 | 建议处置 | 置信度 |\n"
            "| --- | --- | --- | --- | --- | --- |\n"
            "| L1 | server/config/x:1 | 越权 | grep 实测 | 改 | 高 |\n"
        )
        findings6 = _parse_dsh_md(md6, "2026-08-17-test-6col", 1.0)
        assert len(findings6) == 1
        assert findings6[0]["project"] == ""
        assert findings6[0]["confidence"] == "高"
        assert findings6[0]["severity"] == "红旗"

    def test_parse_dsh_md_confidence_normalize(self):
        """置信度值域容错：HIGH/High/低 归一化。"""
        from server.web.server import _dsh_severity_from_confidence

        assert _dsh_severity_from_confidence("HIGH") == "红旗"
        assert _dsh_severity_from_confidence("High") == "红旗"
        assert _dsh_severity_from_confidence("medium") == "黄旗"
        assert _dsh_severity_from_confidence("low") == "蓝旗"
        assert _dsh_severity_from_confidence("未知") == "蓝旗"

    def test_observer_md_not_in_dsh(self, api_server, tmp_path, monkeypatch):
        """隔离：8 列 observer md 喂 DSH 解析器 → 空（表头不触发 | 面）。"""
        from server.web import server as srv_mod

        dsh_dir = tmp_path / "dsh"
        dsh_dir.mkdir(parents=True)
        (dsh_dir / "2026-08-13-test-patrol.md").write_text(
            "| 权重 (Weight) | 交叉确认 | 影响 | 频次 | 描述 (Title) | 项目 | 作用对象 | 证据 |\n"
            "| --- | --- | --- | --- | --- | --- | --- | --- |\n"
            "| 10 | 是 | 高 | 3 | 状态漂移 | clw | clw004 | docs/roadmap.md |\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(srv_mod, "_config_value", lambda k, d: str(tmp_path))
        token = _get_token(api_server)
        status, data = _get(api_server, "/ops/dsh-findings", token=token)
        assert status == 200
        reports = data.get("dsh_reports", [])
        assert reports and reports[0]["findings"] == [], "observer 8 列报告不应被 DSH 解析器识别"

    def test_dsh_findings_api(self, api_server, tmp_path, monkeypatch):
        """集成：造 DSH 6 列报告 → GET /ops/dsh-findings → findings 字段正确 + commands 合成。"""
        from server.web import server as srv_mod

        dsh_dir = tmp_path / "dsh"
        dsh_dir.mkdir(parents=True)
        (dsh_dir / "2026-08-15-dsh-audit-01.md").write_text(self._DSH_MD, encoding="utf-8")
        monkeypatch.setattr(srv_mod, "_config_value", lambda k, d: str(tmp_path))
        token = _get_token(api_server)
        status, data = _get(api_server, "/ops/dsh-findings", token=token)
        assert status == 200
        reports = data.get("dsh_reports", [])
        assert reports and reports[0]["findings"], "应有 DSH findings"
        f = reports[0]["findings"][0]
        assert f["face"] == "开发机审分离"
        assert f["severity"] == "红旗"
        # 改/删 → 合成转卡命令；留 → 不合成
        cmds = reports[0]["commands"]
        assert len(cmds) == 2, f"改+删 应合成 2 条命令，实际 {cmds}"

    def test_dsh_report_post(self, api_server, tmp_path, monkeypatch):
        """POST /loop/dsh-report：markdown 落盘 + findings 数组渲染成表格落盘。"""
        from server.web import server as srv_mod

        monkeypatch.setattr(srv_mod, "_config_value", lambda k, d: str(tmp_path))
        token = _get_token(api_server)
        status, data = _post(
            api_server, "/loop/dsh-report",
            {"markdown": "# 测试报告\n\n| 面 | 位置 file:行号 | 现象 | 证据 | 建议处置 | 置信度 |\n| --- | --- | --- | --- | --- | --- |\n| 面A | f.py:1 | 现象 | 证据 | 改 | 高 |\n"},
            token=token,
        )
        assert status == 200, f"提交失败: {data}"
        dsh_dir = tmp_path / "dsh"
        files = sorted(dsh_dir.glob("*.md"))
        assert len(files) == 1, f"应有 1 份落盘，实际 {files}"
        # findings 数组渲染成表格
        status, data = _post(
            api_server, "/loop/dsh-report",
            {"findings": [{"face": "面B", "location": "g.py:2", "phenomenon": "现象B",
                           "evidence": "证据B", "action": "删", "confidence": "中"}]},
            token=token,
        )
        assert status == 200, f"findings 提交失败: {data}"
        assert len(sorted(dsh_dir.glob("*.md"))) == 2, "两次提交应落 2 份（同名自动递增序号）"

    def test_dsh_report_auto_draft(self, api_server, tmp_path, monkeypatch):
        """螺旋上升 P1-1：POST /loop/dsh-report 带 project 的 7 列报告 → 自动建草案池。"""
        from server.web import server as srv_mod
        from server.board import roadmap as _rm

        monkeypatch.setattr(srv_mod, "_config_value", lambda k, d: str(tmp_path))
        token = _get_token(api_server)
        # mock create_draft 捕获调用（不真写 roadmap 文件）
        calls: list[tuple] = []
        original = _rm.create_draft

        def fake_create_draft(project, title, *, source="", created=""):
            calls.append((project, title, source))
            return {"ok": True, "draft": title}

        monkeypatch.setattr(_rm, "create_draft", fake_create_draft)
        md = (
            "# 测试报告\n\n"
            "| 面 | 位置 file:行号 | 现象 | 证据 | 建议处置 | 项目 | 置信度 |\n"
            "| --- | --- | --- | --- | --- | --- | --- |\n"
            "| L1 | server/x.py:1 | bug | 证据 | 改 | ccc | 高 |\n"
            "| L2 | qx-map/y.md:2 | 提升 | 证据 | 留 | qx-map | 中 |\n"
        )
        status, data = _post(api_server, "/loop/dsh-report", {"markdown": md}, token=token)
        assert status == 200, f"提交失败: {data}"
        # 应只建 1 条（改=ccc；留 跳过）
        assert len(calls) == 1, f"应建 1 条草案，实际 {calls}"
        assert calls[0][0] == "ccc", f"project 应为 ccc，实际 {calls[0][0]}"
        assert calls[0][1].startswith("[DSH][ccc]"), f"标题格式应为 [DSH][ccc]，实际 {calls[0][1]}"
        assert calls[0][2] == "DSH", f"source 应为 DSH，实际 {calls[0][2]}"

    def test_adopt_source_field(self, api_server, tmp_path, monkeypatch):
        """POST /loop/adopt 带 source=dsh → 记录含 source；缺省仍为 observer。"""
        from server.web import server as srv_mod

        monkeypatch.setattr(srv_mod, "_config_value", lambda k, d: str(tmp_path))
        token = _get_token(api_server)
        status, data = _post(
            api_server, "/loop/adopt",
            {"report": "2026-08-15-dsh-audit-01", "finding": "开发机审分离|executors.json:5",
             "decision": "adopt", "reason": "dsh 页已处理", "source": "dsh"},
            token=token,
        )
        assert status == 200, f"adopt 失败: {data}"
        assert data["record"]["source"] == "dsh"
        adopted = (tmp_path / "observer" / ".adopted.jsonl").read_text(encoding="utf-8").strip().splitlines()
        assert '"source": "dsh"' in adopted[-1]
        # 缺省 source → observer
        status, data = _post(
            api_server, "/loop/adopt",
            {"report": "r", "finding": "f", "decision": "pending", "reason": ""},
            token=token,
        )
        assert data["record"]["source"] == "observer"


def test_last_worker_problem_reads_worker_events(tmp_path: Path) -> None:
    """P2：看板详情接 worker-events.jsonl 的失败原因（此前只显次数不显原因）。"""
    from server.web.server import _last_worker_problem

    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    (log_dir / "worker-events.jsonl").write_text(
        '{"ts":"2026-08-22T01:00:00Z","kind":"worker","work_id":"xy057","phase":"run","ok":false,"returncode":1,"problem":"退出码非 0: 1"}\n'
        '{"ts":"2026-08-22T02:00:00Z","kind":"worker","work_id":"xy057","phase":"audit","ok":false,"problem":"**机审：不通过（severity：重）**"}\n'
        '{"ts":"2026-08-22T03:00:00Z","kind":"worker","work_id":"xy999","phase":"run","ok":true,"problem":null}\n',
        encoding="utf-8",
    )
    # 取该卡最后一条有 problem 的事件（audit 那条）
    assert "机审：不通过" in _last_worker_problem(log_dir, "xy057")
    # 无 problem 的卡 → 空串
    assert _last_worker_problem(log_dir, "xy999") == ""
    # 无匹配卡 → 空串
    assert _last_worker_problem(log_dir, "nonexistent") == ""
