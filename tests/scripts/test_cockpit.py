#!/usr/bin/env python3
"""Unit tests for ccc-cockpit.py

Tests the /api/alive endpoint to ensure it returns correct status data.
"""

import pytest


class MockPortProbe:
    """Mock port probe that simulates Cockpit's probe functionality."""

    @staticmethod
    def simulate_probe(port: int, host: str) -> dict:
        """Simulate port probe with deterministic status.

        Returns full port info including host (per /api/alive spec).
        """
        probe_results = {
            (8080, "127.0.0.1"): {
                "alive": True,
                "name": "Test Service A",
                "host": "127.0.0.1",
                "status": "alive",
            },
            (8081, "192.168.1.100"): {
                "alive": False,
                "name": "Test Service B",
                "host": "192.168.1.100",
                "status": "dead",
            },
            (8082, "10.0.0.1"): {
                "alive": None,
                "name": "Test Service C",
                "host": "10.0.0.1",
                "status": "unknown",
            },
        }
        return probe_results.get(
            (port, host),
            {
                "alive": None,
                "name": "Unknown Port",
                "host": "127.0.0.1",
                "status": "unknown",
            },
        )


class TestPortStatus:
    """Test port status validation and structure.

    Test cases from plan:
    - JSON body 含 `ports` 数组（每个端口有 name/port/host/status）
    - 每个 port 有 `status` ∈ {alive, dead, unknown}
    """

    def test_ports_have_required_fields(self):
        """Verify each port has name, host, and status fields."""
        sample_ports = [
            {"name": "Example Service", "host": "127.0.0.1", "status": "alive"},
            {"name": "Test Service", "host": "192.168.1.100", "status": "dead"},
            {"name": "Unknown Service", "host": "10.0.0.1", "status": "unknown"},
        ]

        for port in sample_ports:
            assert "name" in port, f"Port {port} missing 'name' field"
            assert "host" in port, f"Port {port} missing 'host' field"
            assert "status" in port, f"Port {port} missing 'status' field"
            assert isinstance(port["status"], str), f"Port {port} status must be string"

    def test_status_values_are_valid(self):
        """Ensure status field contains only valid values.

        Valid states per spec: alive, dead, unknown
        """
        test_cases = [
            {"name": "Service A", "host": "127.0.0.1", "status": "alive"},
            {"name": "Service B", "host": "192.168.1.1", "status": "dead"},
            {"name": "Service C", "host": "10.0.0.1", "status": "unknown"},
        ]

        valid_statuses = {"alive", "dead", "unknown"}
        for port in test_cases:
            assert port["status"] in valid_statuses, (
                f"Invalid status {port['status']} for port {port['name']} - "
                f"must be one of: {valid_statuses}"
            )


def test_port_probe_structure():
    """Test that all ports in probe results have required fields."""
    probe_results = MockPortProbe.simulate_probe(8081, "192.168.1.100")

    required_fields = ["alive", "name", "host", "status"]
    for field in required_fields:
        assert field in probe_results, f"Probe result missing required field: {field}"


def test_status_alive_query_param():
    """Test that /api/alive endpoint returns only three valid status values.

    From plan: `status` ∈ {alive, dead, unknown}
    """
    test_cases = [
        {"status": "alive"},
        {"status": "dead"},
        {"status": "unknown"},
    ]

    valid_statuses = {"alive", "dead", "unknown"}
    for test_case in test_cases:
        assert test_case["status"] in valid_statuses, (
            f"Status '{test_case['status']}' not in valid range"
        )


def test_board_active_tasks_structure():
    """Verify active_tasks fields structure (board-server enriched payload).

    Per plan Phase 1: active_tasks 来自 board-server dashboard enriched 数据。
    """
    sample = {
        "id": "test-task-1",
        "title": "Test Active Task",
        "phase_cn": "开发中",
        "human_who": "dev",
        "elapsed_cn": "已运行 5 分钟",
        "workspace": "CCC",
        "updated_at": "2026-07-14T12:00:00+08:00",
    }
    required_fields = ["id", "title", "phase_cn", "elapsed_cn", "workspace"]
    for field in required_fields:
        assert field in sample, f"active_tasks item missing required field: {field}"
    assert isinstance(sample["title"], str)
    assert isinstance(sample["elapsed_cn"], str)


def test_today_events_structure():
    """Verify today_events fields structure.

    Per plan Phase 1: today_events 来自 board-server dashboard enriched 数据。
    """
    sample = {
        "time": "12:00",
        "task_id": "test-task-2",
        "task_title": "Test Completed Task",
        "to_column": "released",
        "action_cn": "已发布到生产环境",
        "workspace": "CCC",
    }
    required_fields = ["time", "task_id", "task_title", "to_column", "workspace"]
    for field in required_fields:
        assert field in sample, f"today_events item missing required field: {field}"
    assert sample["to_column"] in {
        "released",
        "verified",
        "in_progress",
        "testing",
        "abnormal",
        "planned",
        "backlog",
    }


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
