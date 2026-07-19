"""test_executor.py — _executor.py OpenCode 执行器与路径解析"""
from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import _executor as ex
from _config import Config, get_logger
from _executor import OpenCodeExecutor, resolve_opencode, _sanitized_env


class TestResolveOpencode:
    def test_opencode_bin_env_absolute_path(self, tmp_path, monkeypatch):
        fake = tmp_path / "opencode"
        fake.write_text("#!/bin/sh\n", encoding="utf-8")
        fake.chmod(0o755)
        monkeypatch.setenv("OPENCODE_BIN", str(fake))
        assert resolve_opencode() == str(fake)

    def test_which_fallback(self, monkeypatch):
        monkeypatch.delenv("OPENCODE_BIN", raising=False)
        with patch("shutil.which", return_value="/usr/local/bin/opencode"):
            assert resolve_opencode() == "/usr/local/bin/opencode"

    def test_not_found_returns_none(self, monkeypatch):
        monkeypatch.delenv("OPENCODE_BIN", raising=False)
        with patch("shutil.which", return_value=None):
            with patch.object(Path, "exists", return_value=False):
                assert resolve_opencode() is None


class TestSanitizedEnv:
    def test_strips_credential_keys(self, monkeypatch):
        monkeypatch.setenv("MY_API_KEY", "secret")
        monkeypatch.setenv("SAFE_VAR", "ok")
        env = _sanitized_env()
        assert "MY_API_KEY" not in env
        assert env.get("SAFE_VAR") == "ok"

    def test_keeps_anthropic_relay_auth(self, monkeypatch):
        """launchd 继承的 ANTHROPIC_AUTH_TOKEN 不得被 TOKEN 规则误剥。"""
        monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "sk-trae-test")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-cp-test")
        monkeypatch.setenv("ANTHROPIC_BASE_URL", "http://127.0.0.1:4000")
        monkeypatch.setenv("RANDOM_TOKEN", "should-strip")
        env = _sanitized_env()
        assert env.get("ANTHROPIC_AUTH_TOKEN") == "sk-trae-test"
        assert env.get("ANTHROPIC_API_KEY") == "sk-cp-test"
        assert env.get("ANTHROPIC_BASE_URL") == "http://127.0.0.1:4000"
        assert "RANDOM_TOKEN" not in env

    def test_claude_env_sets_relay(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_BASE_URL", raising=False)
        env = ex._claude_env(relay_url="http://127.0.0.1:4000")
        assert env["ANTHROPIC_BASE_URL"] == "http://127.0.0.1:4000"


class TestOpenCodeExecutor:
    def test_not_found_returns_exit_10(self, monkeypatch):
        monkeypatch.setattr(ex, "resolve_opencode", lambda: None)
        result = OpenCodeExecutor(Config()).execute("p1", "hi", timeout=5)
        assert result["exit_code"] == 10
        assert "not found" in result["stderr"]

    def test_success_short_prompt(self, monkeypatch, tmp_path):
        monkeypatch.setattr(ex, "resolve_opencode", lambda: "/bin/echo")
        pid_dir = tmp_path / ".ccc" / "opencode-pids"
        pid_dir.mkdir(parents=True)
        with patch.object(Path, "home", return_value=tmp_path):
            with patch("subprocess.Popen") as popen:
                proc = MagicMock()
                proc.pid = 4242
                proc.returncode = 0
                proc.communicate.return_value = (b"ok", b"")
                popen.return_value = proc
                result = OpenCodeExecutor(Config()).execute(
                    "phase-1", "hello", timeout=30, cwd=str(tmp_path)
                )
        assert result["exit_code"] == 0
        assert result["killed"] is False
        assert not (pid_dir / "phase-1.pid").exists()

    def test_timeout_kills_process(self, monkeypatch, tmp_path):
        monkeypatch.setattr(ex, "resolve_opencode", lambda: "/bin/sleep")
        real_logger = get_logger("executor-test")
        monkeypatch.setattr(ex, "_log", real_logger)
        pid_dir = tmp_path / ".ccc" / "opencode-pids"
        pid_dir.mkdir(parents=True)
        with patch.object(Path, "home", return_value=tmp_path):
            with patch("subprocess.Popen") as popen:
                proc = MagicMock()
                proc.pid = 9999
                proc.poll.return_value = None
                proc.communicate.side_effect = subprocess.TimeoutExpired("cmd", 1)
                popen.return_value = proc
                with patch("os.killpg"):
                    with patch("os.wait", side_effect=ProcessLookupError):
                        result = OpenCodeExecutor(Config()).execute(
                            "phase-t", "x", timeout=1, cwd=str(tmp_path)
                        )
        assert result["killed"] is True
        assert result["exit_code"] == -1

    def test_long_prompt_uses_temp_file(self, monkeypatch, tmp_path):
        monkeypatch.setattr(ex, "resolve_opencode", lambda: "/bin/echo")
        pids_dir = tmp_path / ".ccc" / "pids"
        opids = tmp_path / ".ccc" / "opencode-pids"
        pids_dir.mkdir(parents=True)
        opids.mkdir(parents=True)
        long_prompt = "x" * 250
        with patch.object(Path, "home", return_value=tmp_path):
            with patch("subprocess.Popen") as popen:
                proc = MagicMock()
                proc.pid = 1
                proc.returncode = 0
                proc.communicate.return_value = (b"", b"")
                popen.return_value = proc
                OpenCodeExecutor(Config()).execute(
                    "long-p", long_prompt, timeout=5, cwd=str(tmp_path)
                )
                cmd = popen.call_args[0][0]
                assert "--file" in cmd

    def test_executor_protocol_not_implemented(self):
        from _executor import Executor
        with pytest.raises(NotImplementedError):
            Executor().execute("p", "x", 1)

    def test_npm_global_fallback(self, monkeypatch, tmp_path):
        monkeypatch.delenv("OPENCODE_BIN", raising=False)
        npm_path = str(tmp_path / "opencode")
        with patch("shutil.which", return_value=None):
            with patch("os.path.expanduser", return_value=npm_path):
                with patch.object(Path, "exists", return_value=True):
                    assert resolve_opencode() == npm_path

    def test_timeout_hard_kill_path(self, monkeypatch, tmp_path):
        monkeypatch.setattr(ex, "resolve_opencode", lambda: "/bin/sleep")
        monkeypatch.setattr(ex, "_log", get_logger("ex-kill-test"))
        opids = tmp_path / ".ccc" / "opencode-pids"
        opids.mkdir(parents=True)
        with patch.object(Path, "home", return_value=tmp_path):
            with patch("subprocess.Popen") as popen:
                proc = MagicMock()
                proc.pid = 8888
                proc.poll.return_value = None
                proc.communicate.side_effect = subprocess.TimeoutExpired("cmd", 1)
                proc.wait.side_effect = [
                    subprocess.TimeoutExpired("cmd", 5),
                    subprocess.TimeoutExpired("cmd", 10),
                    None,
                ]
                popen.return_value = proc
                with patch("os.killpg"):
                    result = OpenCodeExecutor(Config()).execute(
                        "hard-kill", "x", timeout=2, cwd=str(tmp_path)
                    )
        assert result["killed"] is True
