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
        env = ex._claude_env(relay_url="https://api.minimaxi.com/anthropic")
        assert env["ANTHROPIC_BASE_URL"] == "https://api.minimaxi.com/anthropic"

    def test_claude_env_default_minimax(self, monkeypatch):
        # v0.61.0 阶段 A 改造:默认 ANTHROPIC_BASE_URL 走本机 relay :4000
        # (旧测试期望 MiniMax 直连已过期 — 共识 ① 三档契约 + 上游解耦)
        monkeypatch.delenv("ANTHROPIC_BASE_URL", raising=False)
        monkeypatch.delenv("AGENT_PLANNER_BASE_URL", raising=False)
        env = ex._claude_env()
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


class TestRelayFailOpen:
    """CCC Relay 2026-07-25 共识:relay 不可达时 _claude_env 不 block,自动回退直连。

    三档契约:relay_url=None → 走 ANTHROPIC_BASE_URL(env 设的直连);
    relay_url=set → 强制走 relay;relay_url=None 且 env 也无 → 默认 MiniMax 直连。
    """

    def test_relay_url_set_overrides_env(self, monkeypatch):
        """显式传 relay_url 时,env 设的 ANTHROPIC_BASE_URL 应被覆盖"""
        monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://custom.example.com")
        env = ex._claude_env(relay_url="http://127.0.0.1:4000")
        assert env["ANTHROPIC_BASE_URL"] == "http://127.0.0.1:4000"

    def test_relay_url_none_keeps_existing_env(self, monkeypatch):
        """relay_url=None 且 env 已设 ANTHROPIC_BASE_URL → 保持原值(fail-open 兜底)"""
        monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://api.minimaxi.com/anthropic")
        env = ex._claude_env(relay_url=None)
        assert env["ANTHROPIC_BASE_URL"] == "https://api.minimaxi.com/anthropic"

    def test_relay_url_none_no_env_falls_back_to_minimax(self, monkeypatch):
        """relay_url=None 且 env 也无 ANTHROPIC_BASE_URL → 默认 MiniMax 直连

        v0.61.0 阶段 A 改造后:默认走 relay :4000,而非 MiniMax 直连。
        三档契约 + 上游解耦共识(authority)已废 MiniMax 作为默认。
        """
        monkeypatch.delenv("ANTHROPIC_BASE_URL", raising=False)
        monkeypatch.delenv("AGENT_PLANNER_BASE_URL", raising=False)
        env = ex._claude_env(relay_url=None)
        assert env["ANTHROPIC_BASE_URL"] == "http://127.0.0.1:4000"

    def test_fail_open_path_emits_under_relay_down(self, monkeypatch):
        """模拟 _is_upstream_healthy 返回 False 时,relay_url 应传 None(让 _claude_env 兜底)

        这是 ccc-engine.py 1022/1312 fail-open 改造的契约:探活失败 → relay_url=None → 走直连
        而不是 skip 任务。
        """
        # 模拟 engine 调用模式
        healthy = False  # relay down
        relay_url_for_engine = "http://127.0.0.1:4000" if healthy else None
        assert relay_url_for_engine is None
        monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://api.minimaxi.com/anthropic")
        env = ex._claude_env(relay_url=relay_url_for_engine)
        # 走直连,任务不 block
        assert env["ANTHROPIC_BASE_URL"] == "https://api.minimaxi.com/anthropic"
        assert "ANTHROPIC_AUTH_TOKEN" in env or env.get("ANTHROPIC_AUTH_TOKEN", "") == ""
