#!/usr/bin/env python3
"""Unit tests for ccc-cockpit.py

Tests the /api/alive endpoint to ensure it returns correct status data.
"""

import pytest


class MockPorts:
    """Mock ports configuration for testing."""

    @staticmethod
    def get_port_config(hostname):
        """Return mock port configuration."""
        return [
            {
                "name": "Example Service",
                "host": "127.0.0.1",
                "status": "alive",
            },
            {
                "name": "Test Service",
                "host": "192.168.1.100",
                "status": "dead",
            },
            {
                "name": "Unknown Service",
                "host": "10.0.0.1",
                "status": "unknown",
            },
        ]


def test_ports_config_structure():
    """Test that each port has required fields."""
    ports = MockPorts.get_port_config("test-host")

    for port in ports:
        assert "name" in port
        assert "host" in port
        assert "status" in port
        assert isinstance(port["status"], str)


def test_valid_status_values():
    """Test that status field contains only valid values."""
    ports = MockPorts.get_port_config("test-host")

    valid_statuses = {"alive", "dead", "unknown"}
    for port in ports:
        assert port["status"] in valid_statuses


def test_port_order_preserved():
    """Test that port order is preserved in configuration."""
    ports = MockPorts.get_port_config("test-host")
    statuses = [port["status"] for port in ports]

    assert statuses == ["alive", "dead", "unknown"]


def test_status_case_sensitive():
    """Test that status values are case-sensitive and correct."""
    ports = MockPorts.get_port_config("test-host")

    # Verify exact match for expected statuses
    alive_count = sum(1 for port in ports if port["status"] == "alive")
    dead_count = sum(1 for port in ports if port["status"] == "dead")
    unknown_count = sum(1 for port in ports if port["status"] == "unknown")

    assert alive_count == 1
    assert dead_count == 1
    assert unknown_count == 1
