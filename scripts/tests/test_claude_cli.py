"""tests for scripts/_claude_cli.py + sanitized PATH (v0.40.1)"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

from _claude_cli import ClaudeCliMissing, claude_path_prefixes, resolve_claude_cli  # noqa: E402
from _executor import _sanitized_env  # noqa: E402


def test_resolve_respects_ccc_claude_bin(tmp_path, monkeypatch):
    fake = tmp_path / "my-claude"
    fake.write_text("#!/bin/sh\necho ok\n")
    fake.chmod(0o755)
    monkeypatch.setenv("CCC_CLAUDE_BIN", str(fake))
    assert resolve_claude_cli(require=True) == str(fake.resolve())


def test_resolve_missing_raises(monkeypatch, tmp_path):
    monkeypatch.delenv("CCC_CLAUDE_BIN", raising=False)
    monkeypatch.setenv("PATH", str(tmp_path))  # empty of claude
    monkeypatch.setenv("HOME", str(tmp_path))
    import _claude_cli as mod

    # 屏蔽系统绝对路径候选（本机可能真有 /opt/homebrew/bin/claude）
    monkeypatch.setattr(mod, "_candidates", lambda: [tmp_path / "nope-claude"])
    monkeypatch.setattr(mod, "_extra_path_dirs", lambda: [str(tmp_path)])
    with pytest.raises(ClaudeCliMissing):
        resolve_claude_cli(require=True)
    assert resolve_claude_cli(require=False) is None


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
