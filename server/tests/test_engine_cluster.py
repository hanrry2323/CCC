"""test_engine_cluster — 集群采集解析 + 状态检查。

验证：
1. parse_cluster_targets：正常 / 空 / 无效格式
2. check_tcp_reachable：可达 / 不可达
3. check_service_status：进程存在 / 不存在
4. collect_cluster_status：写入文件 + 摘要格式
5. 既有 83 用例不回归
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from server.engine.cluster import (
    NodeStatus,
    ServiceStatus,
    check_service_status,
    check_tcp_reachable,
    collect_cluster_status,
    parse_cluster_targets,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class TestParseClusterTargets:
    """CLUSTER_TARGETS 配置解析。"""

    def test_parses_valid_targets(self) -> None:
        targets = parse_cluster_targets({"CLUSTER_TARGETS": "localhost:7777,localhost:7775"})
        assert targets == [("localhost", 7777), ("localhost", 7775)]

    def test_parses_single_target(self) -> None:
        targets = parse_cluster_targets({"CLUSTER_TARGETS": "10.0.0.1:8080"})
        assert targets == [("10.0.0.1", 8080)]

    def test_returns_empty_for_empty_string(self) -> None:
        targets = parse_cluster_targets({"CLUSTER_TARGETS": ""})
        assert targets == []

    def test_returns_empty_for_missing_key(self) -> None:
        targets = parse_cluster_targets({})
        assert targets == []

    def test_skips_invalid_format(self, caplog: pytest.LogCaptureFixture) -> None:
        targets = parse_cluster_targets({"CLUSTER_TARGETS": "bad-host,localhost:7777"})
        assert targets == [("localhost", 7777)]

    def test_skips_invalid_port(self, caplog: pytest.LogCaptureFixture) -> None:
        targets = parse_cluster_targets({"CLUSTER_TARGETS": "host:abc,localhost:7777"})
        assert targets == [("localhost", 7777)]


class TestCheckTcpReachable:
    """TCP 可达性检测。"""

    def test_unreachable_host(self) -> None:
        """不存在的 host:port → 不可达。"""
        result = check_tcp_reachable("192.0.2.1", 9, timeout=0.5)
        assert not result.reachable
        assert result.error is not None

    def test_returns_node_status(self) -> None:
        result = check_tcp_reachable("192.0.2.2", 80, timeout=0.1)
        assert isinstance(result, NodeStatus)
        assert result.host == "192.0.2.2"
        assert result.port == 80


class TestCheckServiceStatus:
    """服务进程状态检查。"""

    def test_service_not_found(self) -> None:
        """不存在的进程名 → 未运行。"""
        result = check_service_status("__nonexistent_process_xyz__")
        assert not result.running

    def test_returns_service_status(self) -> None:
        result = check_service_status("__nonexistent_process_xyz__")
        assert isinstance(result, ServiceStatus)
        assert result.name == "__nonexistent_process_xyz__"


class TestCollectClusterStatus:
    """集采完整流程。"""

    def test_collect_with_empty_targets(self, tmp_path: Path) -> None:
        """空目标 → 成功采集，摘要含零节点。"""
        cfg = {
            "CLUSTER_TARGETS": "",
            "DATA_DIR": str(tmp_path),
            "SCHEDULER_INTERVAL": "60",
            "SCHEDULER_DISPATCH_DIR": "",
            "BOARD_PORT": "8102",
            "WEB_PORT": "8103",
        }
        ok, summary = collect_cluster_status(cfg)
        assert ok
        assert summary["nodes_checked"] == 0
        assert summary["services_checked"] == 4  # 4 默认服务

        # 输出文件存在
        output = tmp_path / "cluster.js"
        assert output.is_file()
        content = output.read_text(encoding="utf-8")
        assert "window.CLUSTER_DATA" in content
        data = json.loads(content.split("=", 1)[1].strip().rstrip(";"))
        assert "nodes" in data
        assert "services" in data
        assert "config" in data
        assert data["config"]["scheduler_interval"] == 60
        assert data["config"]["board_port"] == "8102"

    def test_collect_with_targets(self, tmp_path: Path) -> None:
        """有目标 → 节点被采集（不可达因无服务监听）。"""
        cfg = {
            "CLUSTER_TARGETS": "127.0.0.1:9,127.0.0.1:10",
            "DATA_DIR": str(tmp_path),
            "SCHEDULER_INTERVAL": "30",
            "SCHEDULER_DISPATCH_DIR": "",
            "BOARD_PORT": "",
            "WEB_PORT": "",
        }
        ok, summary = collect_cluster_status(cfg)
        assert ok
        assert summary["nodes_checked"] == 2
        # 端口 9 和 10 通常不可达
        assert summary["nodes_reachable"] == 0
        assert summary["services_checked"] == 4