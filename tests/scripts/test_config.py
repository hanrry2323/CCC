"""test_config.py — _config.py 配置加载与环境变量覆盖"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from _config import (
    TIMEOUT_MAX,
    TIMEOUT_MIN,
    Config,
    parse_duration,
    _default_workspaces,
    _resolve_workspace,
)


class TestParseDuration:
    def test_int_passthrough_clamped(self):
        assert parse_duration(300, 1800) == 300
        assert parse_duration(30, 1800) == TIMEOUT_MIN
        assert parse_duration(999999, 1800) == TIMEOUT_MAX

    def test_duration_expressions(self):
        assert parse_duration("5m", 1800) == 300
        assert parse_duration("2h", 1800) == 7200
        assert parse_duration("1d", 1800) == 86400

    def test_empty_and_invalid_fallback(self):
        assert parse_duration("", 1800) == 1800
        assert parse_duration("not-a-duration", 600) == 600
        assert parse_duration("-5", 1800) == 1800
        assert parse_duration("0m", 1800) == TIMEOUT_MIN


class TestResolveWorkspace:
    def test_ccc_workspace_env(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CCC_WORKSPACE", str(tmp_path))
        assert _resolve_workspace() == tmp_path.resolve()

    def test_default_is_ccc_home(self, monkeypatch):
        monkeypatch.delenv("CCC_WORKSPACE", raising=False)
        ws = _resolve_workspace()
        assert ws.is_dir()
        assert (ws / "scripts" / "_config.py").exists()


class TestConfigEnvOverrides:
    def test_timeout_duration_override(self, monkeypatch):
        monkeypatch.setenv("CCC_TIMEOUT", "15m")
        monkeypatch.setenv("CCC_HOOK_TIMEOUT", "90")
        cfg = Config()
        assert cfg.default_timeout == 900
        assert cfg.hook_timeout == 90

    def test_int_and_str_overrides(self, monkeypatch):
        monkeypatch.setenv("CCC_MAX_RETRY", "7")
        monkeypatch.setenv("OPENCODE_MODEL", "loop/code")
        monkeypatch.setenv("BOARD_PORT", "8888")
        monkeypatch.setenv("BOARD_HOST", "0.0.0.0")
        cfg = Config()
        assert cfg.max_retry == 7
        assert cfg.model == "loop/code"
        assert cfg.board_port == 8888
        assert cfg.board_host == "0.0.0.0"

    def test_invalid_int_env_keeps_default(self, monkeypatch):
        monkeypatch.setenv("CCC_MAX_RETRY", "not-int")
        cfg = Config()
        assert cfg.max_retry == 5


class TestDefaultWorkspaces:
    def test_audit_workspaces_env(self, monkeypatch):
        monkeypatch.setenv("CCC_AUDIT_WORKSPACES", "/tmp/a,/tmp/b")
        assert _default_workspaces() == ["/tmp/a", "/tmp/b"]

    def test_scan_program_dir_when_no_env(self, monkeypatch, tmp_path):
        monkeypatch.delenv("CCC_AUDIT_WORKSPACES", raising=False)
        program = tmp_path / "program"
        proj = program / "demo"
        (proj / ".ccc" / "board").mkdir(parents=True)
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        found = _default_workspaces()
        assert str(proj) in found
