"""worktree dirty 文件数：无目录 / porcelain / 超时不炸。"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from server.web import worktree_dirty as wd


@pytest.fixture(autouse=True)
def _clear_cache():
    wd.clear_dirty_cache()
    yield
    wd.clear_dirty_cache()


def _init_git_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=path, check=True, capture_output=True)
    (path / "seed.txt").write_text("ok\n", encoding="utf-8")
    subprocess.run(["git", "add", "seed.txt"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "seed"], cwd=path, check=True, capture_output=True)


class TestCountDirtyFiles:
    def test_clean_repo_zero(self, tmp_path: Path) -> None:
        repo = tmp_path / "clean"
        _init_git_repo(repo)
        assert wd.count_dirty_files(repo) == 0

    def test_dirty_counts_porcelain_lines(self, tmp_path: Path) -> None:
        repo = tmp_path / "dirty"
        _init_git_repo(repo)
        (repo / "a.txt").write_text("a\n", encoding="utf-8")
        (repo / "b.txt").write_text("b\n", encoding="utf-8")
        (repo / "seed.txt").write_text("changed\n", encoding="utf-8")
        assert wd.count_dirty_files(repo) == 3

    def test_non_git_returns_none(self, tmp_path: Path) -> None:
        plain = tmp_path / "plain"
        plain.mkdir()
        (plain / "x").write_text("x", encoding="utf-8")
        assert wd.count_dirty_files(plain) is None

    def test_timeout_returns_none(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        repo = tmp_path / "slow"
        _init_git_repo(repo)

        def _boom(*_a, **_k):
            raise subprocess.TimeoutExpired(cmd="git", timeout=0.01)

        monkeypatch.setattr(subprocess, "run", _boom)
        assert wd.count_dirty_files(repo) is None


class TestResolveAndGet:
    def test_no_worktree_returns_none(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.delenv("EXECUTOR_REGISTRY_PATH", raising=False)
        monkeypatch.delenv("CCC_WORKTREE_BASE", raising=False)
        monkeypatch.delenv("CCC_CONFIG_ENV", raising=False)
        assert wd.resolve_worktree_dir("T99") is None
        assert wd.get_dirty_files("T99") is None

    def test_env_base_resolves_and_counts(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        base = tmp_path / "ccc-dev-ws"
        monkeypatch.setenv("CCC_WORKTREE_BASE", str(base))
        monkeypatch.delenv("EXECUTOR_REGISTRY_PATH", raising=False)
        wt = tmp_path / "ccc-dev-ws-t42"
        _init_git_repo(wt)
        (wt / "new.py").write_text("print(1)\n", encoding="utf-8")
        assert wd.resolve_worktree_dir("T42") == wt.resolve()
        assert wd.get_dirty_files("T42") == 1

    def test_registry_worktree_base(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        reg = tmp_path / "executors.json"
        reg.write_text(
            json.dumps(
                {
                    "executors": [
                        {
                            "角色": "开发执行体",
                            "分类": "可后台 CLI",
                            "当前绑定": "Claude Code",
                            "worktree_base": str(tmp_path / "ws-<task>"),
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        monkeypatch.setenv("EXECUTOR_REGISTRY_PATH", str(reg))
        monkeypatch.delenv("CCC_WORKTREE_BASE", raising=False)
        wt = tmp_path / "ws-t7"
        _init_git_repo(wt)
        (wt / "x.md").write_text("x\n", encoding="utf-8")
        assert wd.get_dirty_files("T7") == 1

    def test_config_env_fallback_registry(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """web 仅有 CCC_CONFIG_ENV 时，从 config.env 回落 registry + 相对路径。"""
        root = tmp_path / "CCC"
        cfg_dir = root / "server" / "config"
        cfg_dir.mkdir(parents=True)
        reg = cfg_dir / "executors.json"
        reg.write_text(
            json.dumps(
                {
                    "executors": [
                        {
                            "角色": "开发执行体",
                            "分类": "可后台 CLI",
                            "当前绑定": "OpenCode",
                            "worktree_base": str(tmp_path / "ws-<task>"),
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        # 最小可加载 config（必填键齐全）
        cfg = cfg_dir / "config.env"
        cfg.write_text(
            "\n".join(
                [
                    "ENGINE_PORT=1",
                    "BOARD_PORT=1",
                    "WEB_PORT=1",
                    "DATA_DIR=/tmp",
                    "LOG_DIR=/tmp",
                    "EXECUTOR_REGISTRY_PATH=server/config/executors.json",
                    f"CCC_WORKTREE_BASE={tmp_path / 'ws-<task>'}",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        monkeypatch.delenv("EXECUTOR_REGISTRY_PATH", raising=False)
        monkeypatch.delenv("CCC_WORKTREE_BASE", raising=False)
        monkeypatch.setenv("CCC_CONFIG_ENV", str(cfg))
        wt = tmp_path / "ws-ccc9"
        _init_git_repo(wt)
        (wt / "n.md").write_text("n\n", encoding="utf-8")
        assert wd.resolve_worktree_dir("ccc9") == wt.resolve()
        assert wd.get_dirty_files("ccc9") == 1

    def test_cache_ttl(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setenv("CCC_WORKTREE_BASE", str(tmp_path / "ccc-dev-ws"))
        wt = tmp_path / "ccc-dev-ws-t1"
        _init_git_repo(wt)
        assert wd.get_dirty_files("T1") == 0
        (wt / "extra.txt").write_text("e\n", encoding="utf-8")
        # 缓存命中 → 仍为 0
        assert wd.get_dirty_files("T1") == 0
        assert wd.get_dirty_files("T1", force=True) == 1


class TestLineChurn:
    def test_clean_repo_zero(self, tmp_path: Path) -> None:
        repo = tmp_path / "clean"
        _init_git_repo(repo)
        assert wd.count_line_churn(repo) == (0, 0)

    def test_modified_and_new_tracked(self, tmp_path: Path) -> None:
        repo = tmp_path / "churn"
        _init_git_repo(repo)
        (repo / "seed.txt").write_text("ok\nline2\n", encoding="utf-8")
        (repo / "new.txt").write_text("a\nb\n", encoding="utf-8")
        subprocess.run(["git", "add", "new.txt"], cwd=repo, check=True, capture_output=True)
        ins, dele = wd.count_line_churn(repo) or (None, None)
        assert ins is not None and dele is not None
        assert ins >= 3  # seed +1 line, new.txt 2 lines
        assert dele >= 0

    def test_metrics_includes_lines(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        base = tmp_path / "ccc-dev-ws"
        monkeypatch.setenv("CCC_WORKTREE_BASE", str(base))
        monkeypatch.delenv("EXECUTOR_REGISTRY_PATH", raising=False)
        wt = tmp_path / "ccc-dev-ws-t7"
        _init_git_repo(wt)
        (wt / "seed.txt").write_text("changed\n", encoding="utf-8")
        m = wd.get_worktree_metrics("T7", force=True)
        assert m["dirty_files"] == 1
        assert m["lines_insert"] is not None
        assert m["lines_delete"] is not None
        assert (m["lines_insert"] or 0) + (m["lines_delete"] or 0) >= 1
