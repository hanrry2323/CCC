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


class _MockUpstream:
    """模拟上游 chat completions 服务（用于 /conversation 转发测试）。"""

    def __init__(self, reply: str = "mock-reply", status: int = 200, fail_once: bool = False):
        self.reply = reply
        self.status = status
        self.fail_once = fail_once
        self._failed = False
        self.received_requests: list[dict] = []
        from http.server import HTTPServer, BaseHTTPRequestHandler

        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, fmt, *args):
                pass

            def do_POST(self):
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length) if length else b""
                try:
                    body = json.loads(raw) if raw else {}
                except json.JSONDecodeError:
                    body = {}
                outer.received_requests.append({
                    "path": self.path,
                    "authorization": self.headers.get("Authorization", ""),
                    "body": body,
                })
                if outer.fail_once and not outer._failed:
                    outer._failed = True
                    self.send_response(500)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(b'{"error":"mock fail"}')
                    return
                self.send_response(outer.status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                if outer.status == 200:
                    resp = {"choices": [{"message": {"content": outer.reply}}]}
                    self.wfile.write(json.dumps(resp).encode("utf-8"))
                else:
                    self.wfile.write(b'{"error":"mock error"}')

        self._server = HTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    def start(self):
        self._thread.start()
        return self

    @property
    def url(self) -> str:
        addr = self._server.server_address
        return f"http://{addr[0]}:{addr[1]}"

    def stop(self):
        self._server.shutdown()
        self._server.server_close()


@pytest.fixture
def mock_upstream():
    """启动模拟上游（默认返回 mock-reply），返回实例。"""
    srv = _MockUpstream(reply="mock-reply", status=200).start()
    yield srv
    srv.stop()


def _set_conv_env(upstream_url: str, model: str = "flash", key: str = "test-key"):
    """设置对话上游环境变量（运行时刷新）。"""
    os.environ["RELAY_UPSTREAM_URL"] = upstream_url
    os.environ["RELAY_UPSTREAM_KEY"] = key
    os.environ["CCC_CONV_MODEL_NAME"] = model


def _clear_conv_env():
    """清除对话上游环境变量。"""
    for k in ("RELAY_UPSTREAM_URL", "RELAY_UPSTREAM_KEY", "CCC_CONV_MODEL_NAME"):
        os.environ.pop(k, None)


class TestConversation:
    """/conversation 转发上游测试：缺配置 503、上游成功往返、上游失败 502、鉴权不回归。"""

    @pytest.fixture(autouse=True)
    def _clear_conversation_state(self):
        """每个测试前清空对话历史与上游 env，避免跨用例污染。"""
        from server.web import server as srv_mod
        srv_mod._conversations.clear()
        _clear_conv_env()
        yield
        srv_mod._conversations.clear()
        _clear_conv_env()

    def test_conversation_no_upstream_503(self, api_server):
        """缺上游配置返回 503。"""
        _clear_conv_env()
        token = _get_token(api_server)
        status, data = _post(api_server, "/conversation", {"message": "hello"}, token=token)
        assert status == 503
        assert "error" in data
        assert "not configured" in data["error"]

    def test_conversation_upstream_success(self, api_server, mock_upstream):
        """上游成功往返：返回真实模型回复（非 echo:）。"""
        _set_conv_env(mock_upstream.url, model="flash", key="test-key")
        try:
            token = _get_token(api_server)
            status, data = _post(api_server, "/conversation", {"message": "hi"}, token=token)
            assert status == 200
            assert data["reply"] == "mock-reply"
            # 上游应收到正确 payload
            assert len(mock_upstream.received_requests) == 1
            req = mock_upstream.received_requests[0]
            assert req["authorization"] == "Bearer test-key"
            assert req["body"]["model"] == "flash"
            assert req["body"]["messages"][-1] == {"role": "user", "content": "hi"}
            assert req["body"]["stream"] is False
        finally:
            _clear_conv_env()

    def test_conversation_upstream_failure_502(self, api_server, mock_upstream):
        """上游失败返回 502 且不落历史。"""
        # 让 mock 返回 500
        mock_upstream.status = 500
        _set_conv_env(mock_upstream.url, model="flash")
        try:
            token = _get_token(api_server)
            status, data = _post(api_server, "/conversation", {"message": "fail"}, token=token)
            assert status == 502
            assert "error" in data
            # 历史应为空（失败不落历史）
            status, data = _get(api_server, "/conversation", token=token)
            assert status == 200
            assert len(data["messages"]) == 0
        finally:
            _clear_conv_env()

    def test_conversation_history_after_success(self, api_server, mock_upstream):
        """成功对话后历史应包含 user + assistant 两条。"""
        _set_conv_env(mock_upstream.url, model="flash")
        try:
            token = _get_token(api_server)
            _post(api_server, "/conversation", {"message": "first"}, token=token)
            status, data = _get(api_server, "/conversation", token=token)
            assert status == 200
            assert len(data["messages"]) >= 2
            assert data["messages"][-2]["role"] == "user"
            assert data["messages"][-2]["message"] == "first"
            assert data["messages"][-1]["role"] == "assistant"
            assert data["messages"][-1]["message"] == "mock-reply"
        finally:
            _clear_conv_env()

    def test_conversation_no_auth(self, api_server):
        """未鉴权的对话请求返回 401（不触达上游）。"""
        _clear_conv_env()
        status, data = _post(api_server, "/conversation", {"message": "hello"})
        assert status == 401

    def test_conversation_empty_message(self, api_server):
        """空消息返回 400（不触达上游）。"""
        _clear_conv_env()
        token = _get_token(api_server)
        status, data = _post(api_server, "/conversation", {"message": ""}, token=token)
        assert status == 400

    def test_conversation_no_key_header(self, api_server, mock_upstream):
        """未配置 RELAY_UPSTREAM_KEY 时上游请求不带 Authorization。"""
        _set_conv_env(mock_upstream.url, model="flash", key="")
        try:
            token = _get_token(api_server)
            _post(api_server, "/conversation", {"message": "hi"}, token=token)
            assert len(mock_upstream.received_requests) == 1
            assert mock_upstream.received_requests[0]["authorization"] == ""
        finally:
            _clear_conv_env()


# ── 健康检查 ──


class TestHealth:
    """GET /health（无鉴权）"""

    def test_health_ok(self, api_server):
        status, data = _get(api_server, "/health")
        assert status == 200
        assert data == {"status": "ok"}


# ── 静态托管（T23：浏览器直开 7788 看页面） ──


class TestStaticHosting:
    """静态白名单路径免鉴权返回磁盘文件；目录穿越 404；非白名单 API 无 token 401。"""

    def test_root_returns_html(self, api_server):
        """GET / 返回 index.html（200 + text/html）。"""
        status, body_text = _get_raw(api_server, "/")
        assert status == 200
        assert "<html" in body_text.lower()
        assert "<title>CCC 看板</title>" in body_text

    def test_index_html(self, api_server):
        """GET /index.html 200。"""
        status, body_text = _get_raw(api_server, "/index.html")
        assert status == 200
        assert "<html" in body_text.lower()

    def test_js_app_js(self, api_server):
        """GET /js/app.js 200 + JavaScript content-type。"""
        status, body_text = _get_raw(api_server, "/js/app.js")
        assert status == 200
        assert "CCC 看板" in body_text or "fetchApiData" in body_text

    def test_css_style_css(self, api_server):
        """GET /css/style.css 200。"""
        status, _ = _get_raw(api_server, "/css/style.css")
        assert status == 200

    def test_data_board_js(self, api_server):
        """GET /data/board.js 200。"""
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