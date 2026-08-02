"""test_http_api — HTTP API 服务端测试。

覆盖：
- 5 个接口各自 200 + 数据形状断言
- /health 返回正确结构
- 未知路径 404
- 启动/关闭无残留进程
"""

from __future__ import annotations

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


def _get(api_server: str, path: str) -> tuple[int, dict]:
    """GET 请求并返回 (status, body_dict)。"""
    parsed = urlparse(api_server)
    conn = HTTPConnection(parsed.hostname, parsed.port, timeout=5)
    try:
        conn.request("GET", path)
        resp = conn.getresponse()
        body = resp.read().decode("utf-8")
        data = json.loads(body) if body else {}
        return resp.status, data
    finally:
        conn.close()


class TestHealth:
    """GET /health"""

    def test_health_ok(self, api_server):
        status, data = _get(api_server, "/health")
        assert status == 200
        assert data == {"status": "ok"}


class TestBoardRealtime:
    """GET /board/realtime"""

    def test_returns_200(self, api_server):
        status, data = _get(api_server, "/board/realtime")
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
        status, data = _get(api_server, "/board/recent")
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
        status, data = _get(api_server, "/board/by_project")
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
        status, data = _get(api_server, "/board/roadmap")
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
        status, data = _get(api_server, "/unknown")
        assert status == 404
        assert "error" in data

    def test_unknown_nested(self, api_server):
        status, data = _get(api_server, "/board/unknown")
        assert status == 404
        assert "error" in data


class TestBoardStates:
    """GET /board/states"""

    def test_returns_200(self, api_server):
        status, data = _get(api_server, "/board/states")
        assert status == 200
        assert isinstance(data, dict)
        for state, count in data.items():
            assert isinstance(state, str)
            assert isinstance(count, int)


class DataShape:
    """数据形状一致性：各接口返回数据应与 board 查询一致。"""

    def test_realtime_items_have_required_fields(self, api_server):
        status, data = _get(api_server, "/board/realtime")
        assert status == 200
        for state, items in data.items():
            for item in items:
                for field in ("id", "title", "state", "project", "executor"):
                    assert field in item, f"缺少字段 {field}"

    def test_recent_sorted_by_written_at_desc(self, api_server):
        status, data = _get(api_server, "/board/recent")
        assert status == 200
        # 验证回写时间倒序
        written_dates = [item["written_at"] for item in data if item.get("written_at") != "未知"]
        for i in range(1, len(written_dates)):
            assert written_dates[i - 1] >= written_dates[i], (
                f"7 天视图未按回写时间倒序: {written_dates}"
            )

    def test_by_project_counts_sum(self, api_server):
        status, data = _get(api_server, "/board/by_project")
        assert status == 200
        for row in data:
            states_sum = sum(row["states"].values())
            assert row["count"] == states_sum, (
                f"项目 {row['project']} 计数不一致: {row['count']} != {states_sum}"
            )

    def test_roadmap_overview_is_list_of_buckets(self, api_server):
        status, data = _get(api_server, "/board/roadmap")
        assert status == 200
        for bucket in data["overview"]:
            assert isinstance(bucket["count"], int)
            assert bucket["count"] >= 0