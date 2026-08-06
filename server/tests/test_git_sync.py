"""server.git_sync：ff-only / dispatch-checkout 自动对齐。"""

from __future__ import annotations

import subprocess
from pathlib import Path

from server.git_sync import (
    auto_pull_enabled,
    resolve_repo_root,
    sync_origin_main,
)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _init_repo(path: Path) -> None:
    path.mkdir(parents=True)
    _git(path, "init")
    _git(path, "config", "user.email", "t@example.com")
    _git(path, "config", "user.name", "t")
    (path / "docs" / "dispatch").mkdir(parents=True)
    (path / "docs" / "dispatch" / "a.md").write_text("# a\n", encoding="utf-8")
    _git(path, "add", "docs/dispatch/a.md")
    _git(path, "commit", "-m", "seed")
    _git(path, "branch", "-M", "main")


class TestResolveRepoRoot:
    def test_dispatch_path(self, tmp_path: Path) -> None:
        d = tmp_path / "docs" / "dispatch"
        d.mkdir(parents=True)
        assert resolve_repo_root(d) == tmp_path.resolve()


class TestAutoPullEnabled:
    def test_default_on(self, monkeypatch) -> None:
        monkeypatch.delenv("CCC_AUTO_PULL", raising=False)
        assert auto_pull_enabled({}) is True

    def test_explicit_off(self, monkeypatch) -> None:
        monkeypatch.setenv("CCC_AUTO_PULL", "0")
        assert auto_pull_enabled({}) is False


class TestSyncOriginMain:
    def test_ff_only(self, tmp_path: Path) -> None:
        bare = tmp_path / "bare.git"
        subprocess.run(["git", "init", "--bare", str(bare)], check=True, capture_output=True)
        local = tmp_path / "local"
        _init_repo(local)
        _git(local, "remote", "add", "origin", str(bare))
        _git(local, "push", "-u", "origin", "main")

        other = tmp_path / "other"
        subprocess.run(
            ["git", "clone", str(bare), str(other)],
            check=True,
            capture_output=True,
        )
        _git(other, "config", "user.email", "t@example.com")
        _git(other, "config", "user.name", "t")
        (other / "docs" / "dispatch" / "b.md").write_text("# b\n", encoding="utf-8")
        _git(other, "add", "docs/dispatch/b.md")
        _git(other, "commit", "-m", "add b")
        _git(other, "push", "origin", "main")

        summary = sync_origin_main(local, remote="origin", branch="main")
        assert summary["ok"] is True
        assert summary["method"] == "ff-only"
        assert (local / "docs" / "dispatch" / "b.md").is_file()

    def test_dirty_skips_local_card_but_gets_new(self, tmp_path: Path) -> None:
        bare = tmp_path / "bare.git"
        subprocess.run(["git", "init", "--bare", str(bare)], check=True, capture_output=True)
        local = tmp_path / "local"
        _init_repo(local)
        _git(local, "remote", "add", "origin", str(bare))
        _git(local, "push", "-u", "origin", "main")

        other = tmp_path / "other"
        subprocess.run(["git", "clone", str(bare), str(other)], check=True, capture_output=True)
        _git(other, "config", "user.email", "t@example.com")
        _git(other, "config", "user.name", "t")
        (other / "docs" / "dispatch" / "a.md").write_text("# a remote\n", encoding="utf-8")
        (other / "docs" / "dispatch" / "c.md").write_text("# c\n", encoding="utf-8")
        _git(other, "add", "docs/dispatch/a.md", "docs/dispatch/c.md")
        _git(other, "commit", "-m", "remote edits")
        _git(other, "push", "origin", "main")

        # 本地 Engine 正在改 a.md → dirty
        (local / "docs" / "dispatch" / "a.md").write_text("# a local dirty\n", encoding="utf-8")

        summary = sync_origin_main(local, remote="origin", branch="main")
        assert summary["method"] == "dispatch-checkout"
        assert (local / "docs" / "dispatch" / "c.md").is_file()
        assert "docs/dispatch/a.md" in summary.get("skipped_dirty", [])
        assert (local / "docs" / "dispatch" / "a.md").read_text(encoding="utf-8") == "# a local dirty\n"
