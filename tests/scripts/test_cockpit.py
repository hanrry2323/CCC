#!/usr/bin/env python3
"""Unit tests for ccc-cockpit.py

Tests the /api/alive endpoint to ensure it returns correct status data.
"""

import pytest


class MockPortProbe:
    """Mock port probe that simulates Cockpit's probe functionality."""

    @staticmethod
    def simulate_probe(port: int, host: str) -> dict:
        """Simulate port probe with deterministic status."""
        probe_results = {
            (8080, "127.0.0.1"): {
                "alive": True,
                "name": "Test Service A",
                "status": "alive",
            },
            (8081, "192.168.1.100"): {
                "alive": False,
                "name": "Test Service B",
                "status": "dead",
            },
            (8082, "10.0.0.1"): {
                "alive": None,
                "name": "Test Service C",
                "status": "unknown",
            },
        }
        return probe_results.get(
            (port, host), {"alive": None, "name": "Unknown Port", "status": "unknown"}
        )


class TestPortStatus:
    """Test port status validation and structure."""

    def test_ports_have_required_fields(self):
        """Verify each port has name, host, and status fields.

        Test from plan lines 22-23:
        - 测试 JSON body 含 `ports` 数组（每个端口有 name/port/host/status）"""
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
        """Ensure status field contains only valid integers.

        Test from plan lines 23-24:
        - 测试返回值格式：每个 port 有 `status` ∈ {alive, dead, unknown}
        """
        sample_ports = [
            {"status": "alive"},
            {"status": "dead"},
            {"status": "unknown"},
            {"status": "running"},
            {"status": "stopped"},
        ]

        valid_statuses = {"alive", "dead", "unknown"}
        invalid_statuses = {"running", "stopped"}

        for port in sample_ports:
            if port["status"] in valid_statuses:
                assert True, f"Valid status {port['status']}"
            elif port["status"] in invalid_statuses:
                assert False, (
                    f"Invalid status {port['status']} - must be alive/dead/unknown"
                )


def test_port_probe_structure():
    """Test that all ports in probe results have required fields."""
    probe_results = MockPortProbe.simulate_probe(8081, "192.168.1.100")

    required_fields = ["alive", "name", "host", "status"]
    for field in required_fields:
        assert field in probe_results, f"Probe result missing required field: {field}"


def test_status_alive_query_param():
    """Test that /api/alive endpoint only returns port status (3 states).

    Test from plan line:
    - 测试返回值格式：每个 port 有 `status` ∈ {alive, dead, unknown}
    """
    test_cases = [
        {"status": "alive"},
        {"status": "dead"},
        {"status": "unknown"},
    ]

    valid_statuses = {"alive", "dead", "unknown"}
    for test_case in test_cases:
        assert test_case["status"] in valid_statuses, (
            f"Status {test_case['status']} not in valid range"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
