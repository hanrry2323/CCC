"""server.git_sync：ff-only / dispatch-checkout 自动对齐。"""

from __future__ import annotations

import logging
import os
import subprocess
import time
from pathlib import Path

from server import git_sync
from server.git_sync import (
    _align_grace_seconds,
    _force_align_dispatch,
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
    def test_none_cfg_default_on(self, monkeypatch) -> None:
        monkeypatch.delenv("CCC_AUTO_PULL", raising=False)
        assert auto_pull_enabled(None) is True

    def test_partial_cfg_off(self) -> None:
        """单测残缺 cfg（无键）→ 关，避免误 fetch。"""
        assert auto_pull_enabled({}) is False

    def test_explicit_on(self) -> None:
        assert auto_pull_enabled({"CCC_AUTO_PULL": "1"}) is True

    def test_explicit_off(self) -> None:
        assert auto_pull_enabled({"CCC_AUTO_PULL": "0"}) is False


def test_force_align_skipped_when_card_state_locked(tmp_path: Path) -> None:
    """写入持锁中 git_sync 触发 → 跳过对齐，卡改动完好（B1 必修）。"""
    from server.engine.card_state_store import protected_git_lock

    bare = tmp_path / "bare.git"
    subprocess.run(["git", "init", "--bare", str(bare)], check=True, capture_output=True)
    local = tmp_path / "local"
    _init_repo(local)
    _git(local, "remote", "add", "origin", str(bare))
    _git(local, "push", "-u", "origin", "main")

    # 远端推进（预期触发本地 ff 失败 + force-checkout 路径）
    other = tmp_path / "other"
    subprocess.run(["git", "clone", str(bare), str(other)], check=True, capture_output=True)
    _git(other, "config", "user.email", "t@example.com")
    _git(other, "config", "user.name", "t")
    (other / "docs" / "dispatch" / "b.md").write_text("# b remote\n", encoding="utf-8")
    _git(other, "add", "docs/dispatch/b.md")
    _git(other, "commit", "-m", "advance remote")
    _git(other, "push", "origin", "main")
    # 注：merged.fetch 路径下本地 main 尚未消费 b.md，b 的存在不影响本测试意图。

    # 本地构建一笔待提交的卡改动
    (local / "docs" / "dispatch" / "a.md").write_text("# a in-progress\n", encoding="utf-8")
    with protected_git_lock(local, blocking=True):
        summary = sync_origin_main(local, remote="origin", branch="main")
        assert summary["ok"] is False, "持锁期间对齐不得声称成功"
        assert summary["method"] == "blocked", summary
        # 锁内提交中的卡改动必须完好（不被 checkout -f / reset 覆盖）
        assert (local / "docs" / "dispatch" / "a.md").read_text(encoding="utf-8") == "# a in-progress\n"
    # 持锁期间本轮不对本地工作树做任何对齐 checkout 与 untracked 删除
    # （对齐是否完成由方法字段 blocked 表示；合并进度归远端 ref，不归本地工作树）


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

    def test_force_sync_cards_from_main(self, tmp_path: Path) -> None:
        """本地脏卡不再可信：ff 受阻时强制以 main 为准覆盖（主树=main 镜像）。"""
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

        # 本地旧卡状态（不再可信）→ 强制对齐 main
        (local / "docs" / "dispatch" / "a.md").write_text("# a local dirty\n", encoding="utf-8")

        summary = sync_origin_main(local, remote="origin", branch="main")
        assert summary["method"] == "dispatch-checkout"
        assert (local / "docs" / "dispatch" / "c.md").is_file()
        assert "docs/dispatch/a.md" in summary.get("updated", [])
        assert (local / "docs" / "dispatch" / "a.md").read_text(encoding="utf-8") == "# a remote\n"


class TestForceAlignGraceWindow:
    """未跟踪 .md 新卡对齐宽限窗：mtime 新鲜不清除只告警，超窗才移除（ccc091）。"""

    def _repo(self, tmp_path: Path) -> Path:
        repo = tmp_path / "repo"
        _init_repo(repo)
        return repo

    def test_fresh_untracked_card_not_removed(self, tmp_path: Path, monkeypatch, caplog) -> None:
        """宽限窗内（默认 300s）的未跟踪新卡：不移除，告警一次且同文件去重。"""
        monkeypatch.setattr(git_sync, "_GRACE_WARNED", set())
        monkeypatch.delenv("CCC_ALIGN_GRACE_SECONDS", raising=False)
        repo = self._repo(tmp_path)
        new_card = repo / "docs" / "dispatch" / "ccc099-new-card.md"
        new_card.write_text("# fresh untracked card\n", encoding="utf-8")

        with caplog.at_level(logging.WARNING, logger="ccc.git_sync"):
            result = _force_align_dispatch(repo, "main", "docs/dispatch")
            assert result == {"removed": 0, "grace_kept": 1}
            assert new_card.is_file()  # 未被静默清除
            msgs = [r.getMessage() for r in caplog.records if "疑似出卡未提交" in r.getMessage()]
            assert len(msgs) == 1
            assert "ccc099-new-card.md" in msgs[0]  # 告警含文件名
            # 第二轮对齐：同文件去重，不再重复告警，卡仍保留
            result2 = _force_align_dispatch(repo, "main", "docs/dispatch")
            assert result2 == {"removed": 0, "grace_kept": 1}
            assert new_card.is_file()
            msgs2 = [r.getMessage() for r in caplog.records if "疑似出卡未提交" in r.getMessage()]
            assert len(msgs2) == 1

    def test_stale_untracked_card_removed(self, tmp_path: Path, monkeypatch) -> None:
        """超宽限窗仍存在的未跟踪卡：按原逻辑移除。"""
        monkeypatch.setattr(git_sync, "_GRACE_WARNED", set())
        monkeypatch.delenv("CCC_ALIGN_GRACE_SECONDS", raising=False)
        repo = self._repo(tmp_path)
        old_card = repo / "docs" / "dispatch" / "ccc098-stale.md"
        old_card.write_text("# stale untracked card\n", encoding="utf-8")
        stale_ts = time.time() - 3600.0  # 1 小时前，远超默认 300s 宽限
        os.utime(old_card, (stale_ts, stale_ts))

        result = _force_align_dispatch(repo, "main", "docs/dispatch")
        assert result == {"removed": 1, "grace_kept": 0}
        assert not old_card.exists()

    def test_grace_seconds_env_override(self, tmp_path: Path, monkeypatch) -> None:
        """CCC_ALIGN_GRACE_SECONDS=0 关闭宽限窗：新鲜未跟踪卡立即移除。"""
        monkeypatch.setattr(git_sync, "_GRACE_WARNED", set())
        monkeypatch.setenv("CCC_ALIGN_GRACE_SECONDS", "0")
        repo = self._repo(tmp_path)
        fresh = repo / "docs" / "dispatch" / "ccc097-fresh.md"
        fresh.write_text("# fresh\n", encoding="utf-8")

        assert _align_grace_seconds() == 0.0
        result = _force_align_dispatch(repo, "main", "docs/dispatch")
        assert result["removed"] == 1
        assert not fresh.exists()

    def test_future_mtime_card_removed_when_grace_disabled(self, tmp_path: Path, monkeypatch) -> None:
        """未来 mtime（时钟偏斜）钳制为 0：宽限窗关闭时仍立即移除（机审席 F1 修复）。"""
        monkeypatch.setattr(git_sync, "_GRACE_WARNED", set())
        monkeypatch.setenv("CCC_ALIGN_GRACE_SECONDS", "0")
        repo = self._repo(tmp_path)
        future_card = repo / "docs" / "dispatch" / "ccc096-future.md"
        future_card.write_text("# future mtime\n", encoding="utf-8")
        future_ts = time.time() + 3600.0  # 1 小时后的未来 mtime
        os.utime(future_card, (future_ts, future_ts))

        result = _force_align_dispatch(repo, "main", "docs/dispatch")
        assert result == {"removed": 1, "grace_kept": 0}
        assert not future_card.exists()

    def test_grace_seconds_env_parsing(self, monkeypatch) -> None:
        """env 解析：缺省 300s；非法值回退缺省；负值按 0。"""
        monkeypatch.delenv("CCC_ALIGN_GRACE_SECONDS", raising=False)
        assert _align_grace_seconds() == 300.0
        monkeypatch.setenv("CCC_ALIGN_GRACE_SECONDS", "45")
        assert _align_grace_seconds() == 45.0
        monkeypatch.setenv("CCC_ALIGN_GRACE_SECONDS", "not-a-number")
        assert _align_grace_seconds() == 300.0
        monkeypatch.setenv("CCC_ALIGN_GRACE_SECONDS", "-3")
        assert _align_grace_seconds() == 0.0
