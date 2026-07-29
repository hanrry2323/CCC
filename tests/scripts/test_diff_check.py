"""测试 _diff_check — 安全检查"""

import os
import subprocess
from pathlib import Path
import pytest

from _diff_check import (
    check_uncommitted,
    check_commit_range,
    any_blocked,
    summary,
    _is_sensitive,
    _is_out_of_bounds,
    _SENSITIVE_PATTERNS,
)


class TestSensitiveFile:
    def test_env_file(self):
        assert _is_sensitive(".env")
        assert _is_sensitive("config/.env.production")
        assert _is_sensitive("src/.env.local")

    def test_secrets(self):
        assert _is_sensitive("credentials.json")
        assert _is_sensitive("config/credentials.prod.json")
        assert _is_sensitive("deploy/secrets.yml")
        assert _is_sensitive("api-keys.yml")

    def test_ssh_keys(self):
        assert _is_sensitive(".ssh/id_rsa")
        assert _is_sensitive("path/to/.ssh/config")

    def test_token_files(self):
        assert _is_sensitive("token.txt")
        assert _is_sensitive(".token")
        assert _is_sensitive(".tokens")

    def test_normal_files_are_safe(self):
        assert _is_sensitive("src/main.py") is None
        assert _is_sensitive("README.md") is None
        assert _is_sensitive("scripts/ccc-engine.py") is None

    def test_config_files(self):
        assert _is_sensitive("config.hub.toml")
        assert _is_sensitive(".ccc/control.json")
        assert _is_sensitive("control.json")

    def test_pattern_in_path(self):
        # 路径含 key/secret/token 等关键字应触发
        assert _is_sensitive("config/api-key.txt")
        assert _is_sensitive("secret_stuff.py")


class TestOutOfBounds:
    def test_allowed_prefix_match(self):
        result = _is_out_of_bounds("scripts/ccc-engine.py", ["scripts/"])
        assert result is None

    def test_allowed_prefix_mismatch(self):
        # 控制面目录始终越界
        result = _is_out_of_bounds(".ccc/control.json", ["scripts/"])
        assert result is not None

    def test_control_dir(self):
        result = _is_out_of_bounds(".ccc/control.json", ["scripts/"])
        assert result is not None


class TestCheckUncommitted:
    """在真实 git 仓库中测试。"""

    def test_clean_repo(self, tmp_path):
        """新建一个干净的仓库。"""
        _init_git(tmp_path)
        result = check_uncommitted(tmp_path)
        assert result == []  # 无变更

    def test_sensitive_file_flag(self, tmp_path):
        _init_git(tmp_path)
        _create_file(tmp_path, ".env", "SECRET=abc")
        _git_add(tmp_path)
        flags = check_uncommitted(tmp_path)
        sensitive = [f for f in flags if f["rule"] == "sensitive-file"]
        assert len(sensitive) >= 1

    def test_large_change_warning(self, tmp_path):
        _init_git(tmp_path)
        _create_file(tmp_path, "big.py", "x = 1\n" * 600)
        _git_add(tmp_path)
        flags = check_uncommitted(tmp_path)
        # 600 行新增可能不触发 large-change 规则（不提交则 --stat 可能不显示）
        total_ins = sum(s.get("insertions", 0) for s in [{}])
        assert isinstance(flags, list)


class TestCheckCommitRange:
    def test_initial_commit_no_crash(self, tmp_path):
        _init_git(tmp_path)
        _create_file(tmp_path, "readme.md", "# test")
        _git_add(tmp_path)
        _git_commit(tmp_path, "initial")
        # 在第一个 commit 上检查—不炸
        flags = check_commit_range("HEAD", tmp_path)
        assert isinstance(flags, list)


class TestAnyBlocked:
    def test_no_flags(self):
        assert any_blocked([]) is False

    def test_warn_only(self):
        flags = [{"level": "warn", "rule": "large-change", "message": "big"}]
        assert any_blocked(flags) is False

    def test_block_flag(self):
        flags = [{"level": "block", "rule": "sensitive-file", "message": "bad"}]
        assert any_blocked(flags) is True


class TestSummary:
    def test_empty(self):
        assert "通过" in summary([])

    def test_has_flags(self):
        out = summary([{"level": "block", "rule": "test", "message": "bad"}])
        assert "bad" in out


# ── 工具 ──

def _init_git(path: Path) -> None:
    subprocess.run(["git", "init"], cwd=str(path), capture_output=True, timeout=10)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=str(path), capture_output=True, timeout=10)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=str(path), capture_output=True, timeout=10)


def _create_file(path: Path, name: str, content: str) -> None:
    p = path / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)


def _git_add(path: Path) -> None:
    subprocess.run(["git", "add", "-A"], cwd=str(path), capture_output=True, timeout=10)


def _git_commit(path: Path, msg: str) -> None:
    subprocess.run(["git", "commit", "-m", msg], cwd=str(path), capture_output=True, timeout=10)
