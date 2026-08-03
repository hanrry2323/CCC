"""test_engine_cluster — 集群采集解析 + 状态检查。

验证：
1. parse_cluster_targets：正常 / 空 / 无效格式
2. parse_cluster_services：正常 / 空 / 坏格式（T33 新增）
3. check_tcp_reachable：可达 / 不可达
4. check_service_status：进程存在 / 不存在（T33：签名加 name 参数）
5. collect_cluster_status：写入文件 + 摘要格式（T33：服务清单来自配置）
6. 既有用例不回归
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
    parse_cluster_services,
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


class TestParseClusterServices:
    """CLUSTER_SERVICES 配置解析（T33 新增）。"""

    def test_parses_valid_services(self) -> None:
        """正常格式：逗号分隔 name:keyword。"""
        services = parse_cluster_services({
            "CLUSTER_SERVICES": "web-server:server.web.server,engine:server.engine.main"
        })
        assert services == [
            ("web-server", "server.web.server"),
            ("engine", "server.engine.main"),
        ]

    def test_parses_single_service(self) -> None:
        services = parse_cluster_services({"CLUSTER_SERVICES": "web-server:server.web.server"})
        assert services == [("web-server", "server.web.server")]

    def test_returns_empty_for_empty_string(self) -> None:
        """空字符串 → 空列表。"""
        assert parse_cluster_services({"CLUSTER_SERVICES": ""}) == []

    def test_returns_empty_for_missing_key(self) -> None:
        """缺键 → 空列表。"""
        assert parse_cluster_services({}) == []

    def test_skips_invalid_format_no_colon(self, caplog: pytest.LogCaptureFixture) -> None:
        """无冒号 → 跳过并 warning。"""
        services = parse_cluster_services({"CLUSTER_SERVICES": "badformat,web-server:server.web.server"})
        assert services == [("web-server", "server.web.server")]

    def test_skips_empty_name_or_keyword(self, caplog: pytest.LogCaptureFixture) -> None:
        """name 或 keyword 为空 → 跳过。"""
        services = parse_cluster_services({"CLUSTER_SERVICES": ":keyword,web-server:server.web.server,name:"})
        assert services == [("web-server", "server.web.server")]

    def test_keyword_can_contain_colon(self) -> None:
        """keyword 含冒号时按首个冒号拆分（keyword 保留剩余部分）。"""
        services = parse_cluster_services({"CLUSTER_SERVICES": "svc:python3.11:server.web"})
        assert services == [("svc", "python3.11:server.web")]

    def test_new_stack_three_services(self) -> None:
        """新栈三服务示例值解析正确。"""
        services = parse_cluster_services({
            "CLUSTER_SERVICES": "web-server:server.web.server,engine:server.engine.main,board-scheduler:server.board.scheduler"
        })
        assert services == [
            ("web-server", "server.web.server"),
            ("engine", "server.engine.main"),
            ("board-scheduler", "server.board.scheduler"),
        ]


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
    """服务进程状态检查（T33：签名加 name 参数）。"""

    def test_service_not_found(self) -> None:
        """不存在的进程名 → 未运行；name 字段为配置名。"""
        result = check_service_status("web-server", "__nonexistent_process_xyz__")
        assert not result.running
        assert result.name == "web-server"

    def test_returns_service_status(self) -> None:
        result = check_service_status("engine", "__nonexistent_process_xyz__")
        assert isinstance(result, ServiceStatus)
        assert result.name == "engine"


class TestCollectClusterStatus:
    """集采完整流程（T33：服务清单来自 CLUSTER_SERVICES 配置）。"""

    def test_collect_with_empty_targets_and_services(self, tmp_path: Path) -> None:
        """空目标 + 空服务清单 → 成功采集，摘要含零节点零服务。"""
        cfg = {
            "CLUSTER_TARGETS": "",
            "CLUSTER_SERVICES": "",
            "DATA_DIR": str(tmp_path),
            "SCHEDULER_INTERVAL": "60",
            "SCHEDULER_DISPATCH_DIR": "",
            "BOARD_PORT": "8102",
            "WEB_PORT": "8103",
        }
        ok, summary = collect_cluster_status(cfg)
        assert ok
        assert summary["nodes_checked"] == 0
        assert summary["services_checked"] == 0  # T33：空配置 → 零服务

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
            "CLUSTER_SERVICES": "",
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
        assert summary["services_checked"] == 0  # T33：空配置 → 零服务

    def test_collect_with_services_config(self, tmp_path: Path) -> None:
        """有服务清单 → 服务被采集（不存在的关键词 → running=False）。"""
        cfg = {
            "CLUSTER_TARGETS": "",
            "CLUSTER_SERVICES": "web-server:__nonexistent_xyz__,engine:__nonexistent_abc__",
            "DATA_DIR": str(tmp_path),
            "SCHEDULER_INTERVAL": "60",
            "SCHEDULER_DISPATCH_DIR": "",
            "BOARD_PORT": "",
            "WEB_PORT": "",
        }
        ok, summary = collect_cluster_status(cfg)
        assert ok
        assert summary["services_checked"] == 2
        assert summary["services_running"] == 0
        # 验证服务名是配置的 name（非 keyword）
        output = tmp_path / "cluster.js"
        data = json.loads(output.read_text(encoding="utf-8").split("=", 1)[1].strip().rstrip(";"))
        service_names = [s["name"] for s in data["services"]]
        assert service_names == ["web-server", "engine"]
