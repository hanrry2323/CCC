"""test_http_api — HTTP API 服务端测试。

覆盖：
- 鉴权三态（成功/失败/过期）
- 未鉴权请求 401
- 对话往返（回声占位）
- 5 个 board 接口各自 200 + 数据形状断言
- /health 返回正确结构
- 未知路径 404
- 启动/关闭无残留进程
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

import json
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


# ── 对话测试 ──


class TestConversation:
    """对话接口（回声占位）。"""

    def test_conversation_round_trip(self, api_server):
        """POST /conversation 往返：发消息应返回回声。"""
        token = _get_token(api_server)
        status, data = _post(api_server, "/conversation", {"message": "hello"}, token=token)
        assert status == 200
        assert data["reply"] == "echo: hello"

    def test_conversation_history(self, api_server):
        """GET /conversation 应返回对话历史。"""
        token = _get_token(api_server)
        # 先发一条消息
        _post(api_server, "/conversation", {"message": "first"}, token=token)
        # 获取历史
        status, data = _get(api_server, "/conversation", token=token)
        assert status == 200
        assert "messages" in data
        # 应包含 user 和 assistant 两条消息
        assert len(data["messages"]) >= 2
        assert data["messages"][-2]["role"] == "user"
        assert data["messages"][-1]["role"] == "assistant"

    def test_conversation_no_auth(self, api_server):
        """未鉴权的对话请求返回 401。"""
        status, data = _post(api_server, "/conversation", {"message": "hello"})
        assert status == 401

    def test_conversation_empty_message(self, api_server):
        """空消息返回 400。"""
        token = _get_token(api_server)
        status, data = _post(api_server, "/conversation", {"message": ""}, token=token)
        assert status == 400


# ── 健康检查 ──


class TestHealth:
    """GET /health（无鉴权）"""

    def test_health_ok(self, api_server):
        status, data = _get(api_server, "/health")
        assert status == 200
        assert data == {"status": "ok"}


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
            assert written_dates[i - 1] >= written_dates[i], (
                f"7 天视图未按回写时间倒序: {written_dates}"
            )

    def test_by_project_counts_sum(self, api_server):
        token = _get_token(api_server)
        status, data = _get(api_server, "/board/by_project", token=token)
        assert status == 200
        for row in data:
            states_sum = sum(row["states"].values())
            assert row["count"] == states_sum, (
                f"项目 {row['project']} 计数不一致: {row['count']} != {states_sum}"
            )

    def test_roadmap_overview_is_list_of_buckets(self, api_server):
        token = _get_token(api_server)
        status, data = _get(api_server, "/board/roadmap", token=token)
        assert status == 200
        for bucket in data["overview"]:
            assert isinstance(bucket["count"], int)
            assert bucket["count"] >= 0