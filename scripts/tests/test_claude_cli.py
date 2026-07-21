"""tests for scripts/_claude_cli.py + sanitized PATH (v0.40.1)"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

from _claude_cli import (  # noqa: E402
    ClaudeCliMissing,
    claude_path_prefixes,
    ensure_engine_claude_config_dir,
    ensure_loop_code_config_dir,
    path_is_loop_code,
    resolve_claude_cli,
)
from _executor import _sanitized_env  # noqa: E402


def test_resolve_respects_ccc_claude_bin(tmp_path, monkeypatch):
    fake = tmp_path / "my-claude"
    fake.write_text("#!/bin/sh\necho ok\n")
    fake.chmod(0o755)
    monkeypatch.setenv("CCC_CLAUDE_BIN", str(fake))
    monkeypatch.delenv("CCC_EXECUTOR", raising=False)
    assert resolve_claude_cli(require=True, executor_strict=False) == str(fake.resolve())


def test_resolve_executor_loop_code(tmp_path, monkeypatch):
    import _claude_cli as mod

    fake_home = tmp_path / "ccc"
    vendor = fake_home / "vendor" / "loop-code"
    vendor.mkdir(parents=True)
    cli = vendor / "cli"
    cli.write_text("#!/bin/sh\necho loop\n")
    cli.chmod(0o755)
    monkeypatch.delenv("CCC_CLAUDE_BIN", raising=False)
    monkeypatch.setenv("CCC_EXECUTOR", "loop-code")
    monkeypatch.setattr(mod, "ccc_home", lambda: fake_home)
    assert resolve_claude_cli(require=True) == str(cli.resolve())


def test_strict_rejects_personal_ccc_claude_bin(tmp_path, monkeypatch):
    """CCC_EXECUTOR=loop-code 时 CCC_CLAUDE_BIN 指向个人 claude → 拒绝。"""
    personal = tmp_path / "claude"
    personal.write_text("#!/bin/sh\necho personal\n")
    personal.chmod(0o755)
    monkeypatch.setenv("CCC_CLAUDE_BIN", str(personal))
    monkeypatch.setenv("CCC_EXECUTOR", "loop-code")
    with pytest.raises(ClaudeCliMissing, match="not loop-code"):
        resolve_claude_cli(require=True)
    assert resolve_claude_cli(require=False) is None


def test_strict_accepts_loop_code_ccc_claude_bin(tmp_path, monkeypatch):
    vendor = tmp_path / "vendor" / "loop-code"
    vendor.mkdir(parents=True)
    cli = vendor / "cli"
    cli.write_text("#!/bin/sh\necho loop\n")
    cli.chmod(0o755)
    monkeypatch.setenv("CCC_CLAUDE_BIN", str(cli))
    monkeypatch.setenv("CCC_EXECUTOR", "loop-code")
    assert resolve_claude_cli(require=True) == str(cli.resolve())
    assert path_is_loop_code(cli)


def test_strict_no_path_fallback_when_vendor_missing(tmp_path, monkeypatch):
    """缺 vendor/loop-code/cli 时不得落到 PATH 个人 claude。"""
    import _claude_cli as mod

    personal = tmp_path / "bin" / "claude"
    personal.parent.mkdir(parents=True)
    personal.write_text("#!/bin/sh\necho personal\n")
    personal.chmod(0o755)
    monkeypatch.delenv("CCC_CLAUDE_BIN", raising=False)
    monkeypatch.setenv("CCC_EXECUTOR", "loop-code")
    monkeypatch.setenv("PATH", str(personal.parent))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(mod, "loop_code_cli_path", lambda: tmp_path / "missing" / "cli")
    monkeypatch.setattr(mod, "_candidates", lambda: [personal])
    with pytest.raises(ClaudeCliMissing, match="missing executable"):
        resolve_claude_cli(require=True)
    assert resolve_claude_cli(require=False) is None


def test_ensure_engine_claude_config_dir(tmp_path):
    root = ensure_engine_claude_config_dir(tmp_path / "engine-claude")
    assert (root / "CLAUDE.md").is_file()
    assert (root / "settings.json").is_file()
    assert "Engine" in (root / "CLAUDE.md").read_text(encoding="utf-8")


def test_ensure_loop_code_seeds_settings(tmp_path):
    root = ensure_loop_code_config_dir(tmp_path / "loop-code")
    assert (root / "settings.json").is_file()


def test_resolve_missing_raises(monkeypatch, tmp_path):
    monkeypatch.delenv("CCC_CLAUDE_BIN", raising=False)
    monkeypatch.delenv("CCC_EXECUTOR", raising=False)
    monkeypatch.setenv("PATH", str(tmp_path))  # empty of claude
    monkeypatch.setenv("HOME", str(tmp_path))
    import _claude_cli as mod

    # 屏蔽系统绝对路径候选（本机可能真有 /opt/homebrew/bin/claude）
    monkeypatch.setattr(mod, "_candidates", lambda: [tmp_path / "nope-claude"])
    monkeypatch.setattr(mod, "_extra_path_dirs", lambda: [str(tmp_path)])
    monkeypatch.setattr(mod, "loop_code_cli_path", lambda: tmp_path / "missing-cli")
    with pytest.raises(ClaudeCliMissing):
        resolve_claude_cli(require=True, executor_strict=False)
    assert resolve_claude_cli(require=False, executor_strict=False) is None


def test_sanitized_env_prepends_local_bin(monkeypatch, tmp_path):
    local = tmp_path / ".local" / "bin"
    local.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("PATH", "/usr/bin")
    monkeypatch.delenv("API_KEY_FOO", raising=False)
    monkeypatch.setenv("SECRET_X", "leak")
    env = _sanitized_env()
    assert "SECRET_X" not in env
    assert str(local) in env.get("PATH", "").split(":")
    assert claude_path_prefixes()  # local dir exists
