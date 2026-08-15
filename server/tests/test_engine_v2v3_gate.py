"""V2/V3/V4 修复测试：派发 tip 产物门禁 + 空提交信号打回（2026-08-10 主执行窗口）。"""

from __future__ import annotations

import subprocess
from pathlib import Path

from server.engine.main import (
    _claim_running_marker,
    _detect_empty_commit_signal,
    _marker_dispatch_tip,
    _refresh_running_marker_child,
    _worktree_has_new_commit,
)


def _make_repo(tmp_path: Path) -> tuple[Path, Path]:
    """造临时 git 仓：main(C1) + 派生子分支 codex/w + worktree。"""
    repo = tmp_path / "main"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    subprocess.run(["git", "-C", repo, "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", repo, "config", "user.name", "t"], check=True)
    (repo / "a.txt").write_text("1", encoding="utf-8")
    subprocess.run(["git", "-C", repo, "add", "."], check=True)
    subprocess.run(["git", "-C", repo, "commit", "-qm", "C1"], check=True)
    subprocess.run(["git", "-C", repo, "update-ref", "refs/remotes/origin/main", "main"], check=True)
    subprocess.run(["git", "-C", repo, "branch", "codex/w"], check=True)
    wt = tmp_path / "wt"
    subprocess.run(["git", "-C", repo, "worktree", "add", "-q", str(wt), "codex/w"], check=True)
    return repo, wt


class TestV2ProductGateTip:
    """V2：产物门禁以派发 tip 为基准，防「派发后他人合入 → 未写码也误判有产物」。"""

    def test_has_new_commit_with_tip(self, tmp_path: Path) -> None:
        repo, wt = _make_repo(tmp_path)
        tip1 = subprocess.run(
            ["git", "-C", repo, "rev-parse", "main"], capture_output=True, text=True, check=True
        ).stdout.strip()
        (wt / "a.txt").write_text("2", encoding="utf-8")
        subprocess.run(["git", "-C", wt, "add", "."], check=True)
        subprocess.run(["git", "-C", wt, "commit", "-qm", "C2"], check=True)
        assert _worktree_has_new_commit(str(wt), since_ref=tip1) is True
        assert _worktree_has_new_commit(str(wt), since_ref="HEAD") is False

    def test_other_merge_does_not_fake_product(self, tmp_path: Path) -> None:
        """执行体未写码：以派发 tip 为基准时，他人合入不产生「新产物」。"""
        repo, wt = _make_repo(tmp_path)
        dispatch_tip = subprocess.run(
            ["git", "-C", repo, "rev-parse", "main"], capture_output=True, text=True, check=True
        ).stdout.strip()
        (repo / "b.txt").write_text("other", encoding="utf-8")
        subprocess.run(["git", "-C", repo, "add", "."], check=True)
        subprocess.run(["git", "-C", repo, "commit", "-qm", "C3-other"], check=True)
        subprocess.run(["git", "-C", repo, "update-ref", "refs/remotes/origin/main", "main"], check=True)
        assert _worktree_has_new_commit(str(wt), since_ref=dispatch_tip) is False

    def test_marker_tip_roundtrip(self, tmp_path: Path) -> None:
        """派发 tip 写入 marker → 子进程 refresh 保留 → 读取一致。"""
        repo, _ = _make_repo(tmp_path)
        tip = subprocess.run(
            ["git", "-C", repo, "rev-parse", "main"], capture_output=True, text=True, check=True
        ).stdout.strip()
        log_dir = tmp_path / "logs"
        _claim_running_marker(log_dir, "w1", main_repo=repo)
        assert _marker_dispatch_tip(log_dir, "w1") == tip
        _refresh_running_marker_child(log_dir, "w1", child_pid=99999)
        assert _marker_dispatch_tip(log_dir, "w1") == tip

    def test_marker_no_tip_without_repo(self, tmp_path: Path) -> None:
        log_dir = tmp_path / "logs"
        _claim_running_marker(log_dir, "w2")
        assert _marker_dispatch_tip(log_dir, "w2") is None


class TestV3EmptyCommitSignal:
    """V3：空提交信号必须判失败（禁止假成功）。"""

    def test_detect_empty_commit_signal(self, tmp_path: Path) -> None:
        log = tmp_path / "w.log"
        log.write_text("done\nnothing to commit, working tree clean\n", encoding="utf-8")
        assert _detect_empty_commit_signal(log) is True
        log.write_text("error: could not commit\nnothing to commit, working tree clean\n", encoding="utf-8")
        assert _detect_empty_commit_signal(log) is False
        log.write_text("normal exit 0\n", encoding="utf-8")
        assert _detect_empty_commit_signal(log) is False
        assert _detect_empty_commit_signal(tmp_path / "missing.log") is False

    def test_empty_signal_long_log_tail(self, tmp_path: Path) -> None:
        log = tmp_path / "w.log"
        log.write_text("nothing to commit\n" * 500, encoding="utf-8")
        assert _detect_empty_commit_signal(log) is True


class TestV6AuditCommitPin:
    """V6：机审信封钉被审 commit（approve 侧据此拦机审后漂移）。"""

    def test_pin_audit_commit(self, tmp_path: Path) -> None:
        from server.engine.main import _pin_audit_commit

        card = tmp_path / "w.md"
        card.write_text(
            "## 回写区\nx\n\n## 机审区\n\n机审：通过\n来源：engine-audit\n证据：ok\n",
            encoding="utf-8",
        )
        assert _pin_audit_commit(str(card), "abcdef1234567890abcdef") is True
        text = card.read_text(encoding="utf-8")
        assert "机审：通过（被审 abcdef123456）" in text

    def test_pin_idempotent(self, tmp_path: Path) -> None:
        from server.engine.main import _pin_audit_commit

        card = tmp_path / "w.md"
        card.write_text("## 机审区\n\n机审：通过（被审 abcdef123456）\n", encoding="utf-8")
        assert _pin_audit_commit(str(card), "deadbeef00") is True
        text = card.read_text(encoding="utf-8")
        assert text.count("被审 ") == 1
        assert "deadbeef00" not in text

    def test_pin_no_sha_noop(self, tmp_path: Path) -> None:
        from server.engine.main import _pin_audit_commit

        card = tmp_path / "w.md"
        card.write_text("## 机审区\n\n机审：通过\n", encoding="utf-8")
        assert _pin_audit_commit(str(card), "") is True
        assert card.read_text(encoding="utf-8").count("被审 ") == 0

    def test_pin_no_verdict_noop(self, tmp_path: Path) -> None:
        from server.engine.main import _pin_audit_commit

        card = tmp_path / "w.md"
        card.write_text("## 机审区\n\n机审：不通过\n", encoding="utf-8")
        assert _pin_audit_commit(str(card), "abcdef123456") is True
        assert card.read_text(encoding="utf-8").count("被审 ") == 0
