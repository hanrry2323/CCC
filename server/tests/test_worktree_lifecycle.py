"""测试 worktree 及本地残留分支生命周期管理。"""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

from server.engine.task import State, Work
from server.engine.dispatch import ExecutorRegistry, ExecutorEntry
from server.engine.store import InMemoryBoardStore
from server.engine.main import _cleanup_closed_worktrees, _dispatch_and_collect


def test_cleanup_closed_worktrees_lifecycle(tmp_path: Path):
    """测试 _cleanup_closed_worktrees 生命周期回收规则：

    1. hp001: 已关闭卡 -> 自动回收 worktree (clean) 且删除本地分支 (merged)
    2. hp002: 打回卡 (含脏改动) -> 允许 --force 强删 worktree；不删本地分支
    3. hp003: 待分派卡且远端分支已删 -> 自动回收 worktree (clean)，删除本地分支
    4. hp004: 执行中卡且仍在运行 -> 保护，不予强删 worktree
    """
    store = InMemoryBoardStore()
    store.seed(
        Work(id="hp001", role="开发执行体", state=State.CLOSED, card_path="docs/dispatch/hp/hp001-test.md"),
        Work(id="hp002", role="开发执行体", state=State.REJECTED, card_path="docs/dispatch/hp/hp002-test.md"),
        Work(id="hp003", role="开发执行体", state=State.TODO, card_path="docs/dispatch/hp/hp003-test.md"),
        Work(id="hp004", role="开发执行体", state=State.TODO, card_path="docs/dispatch/hp/hp004-test.md"),
    )

    entry = ExecutorEntry(
        role="开发执行体",
        category="可后台 CLI",
        binding="demo",
        note="test",
        command="echo",
        worktree_base="/fake/base"
    )
    registry = ExecutorRegistry((entry,))

    log_dir = tmp_path / "logs"
    log_dir.mkdir(parents=True)
    # hp004 is currently running
    (log_dir / "hp004.running").write_text("pid=123", encoding="utf-8")

    with patch("server.git_sync.resolve_repo_root", return_value=Path("/fake/main_repo")), \
         patch("server.engine.main.get_worktree_path") as mock_get_wt, \
         patch("pathlib.Path.is_dir", return_value=True), \
         patch("subprocess.run") as mock_run:

         mock_get_wt.side_effect = lambda base, cid: f"/fake/base/{cid}"

         def fake_run(args, **kwargs):
             cmd = " ".join(args) if isinstance(args, list) else args
             m = MagicMock()
             m.returncode = 0
             m.stdout = ""
             m.stderr = ""

             if "status --porcelain" in cmd:
                 # hp002 has dirty edits
                 if "hp002" in cmd:
                     m.stdout = "M modified_file.py\n"
                 else:
                     m.stdout = ""
             elif "show-ref --verify" in cmd:
                 # Simulate remote branches for hp003 and hp001 do not exist
                 if "hp003" in cmd or "hp001" in cmd:
                     m.returncode = 1
                 else:
                     m.returncode = 0
             elif "branch --list" in cmd:
                     # Simulate local branches
                     m.stdout = "  codex/hp001-test\n  codex/hp002-test\n  codex/hp003-test\n"
             elif "merge-base" in cmd:
                 m.returncode = 0
             return m

         mock_run.side_effect = fake_run

         cleaned_count = _cleanup_closed_worktrees(store, registry, {}, log_dir)

         calls = [" ".join(c[0][0]) if isinstance(c[0][0], list) else c[0][0] for c in mock_run.call_args_list]

         # 验证 worktree 回收
         remove_hp001 = any("worktree remove" in c and "/fake/base/hp001" in c and "--force" not in c for c in calls)
         remove_hp002_force = any("worktree remove" in c and "/fake/base/hp002" in c and "--force" in c for c in calls)
         remove_hp003 = any("worktree remove" in c and "/fake/base/hp003" in c and "--force" not in c for c in calls)
         remove_hp004 = any("worktree remove" in c and "/fake/base/hp004" in c for c in calls)

         assert remove_hp001 is True, "hp001 (Closed) should be reaped cleanly"
         assert remove_hp002_force is True, "hp002 (Rejected & dirty) should be force reaped"
         assert remove_hp003 is True, "hp003 (Todo & remote deleted) should be reaped cleanly"
         assert remove_hp004 is False, "hp004 (running) must be protected"

         # 验证本地分支清理
         branch_deletions = [c for c in calls if "branch" in c and "-D" in c]
         assert any("hp001-test" in c for c in branch_deletions) is True, "hp001 branch should be deleted (merged)"
         assert any("hp002-test" in c for c in branch_deletions) is False, "hp002 branch should be kept (remote exists)"
         assert any("hp003-test" in c for c in branch_deletions) is True, "hp003 branch should be deleted (remote deleted)"


def test_dispatch_and_collect_retry_reset_on_failure(tmp_path: Path):
    """测试重试时不复用脏 worktree 规则。"""
    card_dir = tmp_path / "docs" / "dispatch" / "xy"
    card_dir.mkdir(parents=True)
    card_file = card_dir / "xy101-retry.md"
    card_file.write_text(
        "# 任务卡 xy101 · 测试\n"
        "> 关联：TEST · 执行体：demo · 验收：Codex · 状态：执行中 · 日期：2026-08-08\n",
        encoding="utf-8"
    )

    entry = ExecutorEntry(
        role="开发执行体",
        category="可后台 CLI",
        binding="demo",
        note="test",
        command="echo",
        worktree_base="/fake/base"
    )
    registry = ExecutorRegistry((entry,))

    work = Work(id="xy101", role="开发执行体", state=State.RUNNING, card_path=str(card_file))
    log_dir = tmp_path / "logs"
    log_dir.mkdir()

    with patch("server.git_sync.resolve_repo_root", return_value=Path("/fake/main_repo")), \
         patch("server.engine.main.get_worktree_path", return_value="/fake/base/xy101"), \
         patch("pathlib.Path.exists", return_value=True), \
         patch("subprocess.run") as mock_run, \
         patch("server.engine.main.build_command", return_value=["echo", "test"]):

         def fake_run(args, **kwargs):
             m = MagicMock()
             m.returncode = 0
             m.stdout = ""
             m.stderr = ""
             if "status --porcelain" in " ".join(args):
                 m.stdout = ""  # Clean status after reset
             return m
         mock_run.side_effect = fake_run

         cfg = {"DISPATCH_DIR": str(tmp_path / "docs" / "dispatch")}
         _dispatch_and_collect(work, registry, cfg, log_dir, timeout=30)

         calls = [" ".join(c[0][0]) for c in mock_run.call_args_list if isinstance(c[0][0], list)]

         # 因为没有成功收单的日志或 sidecar 状态，应当执行 checkout 或 worktree clean/remove
         has_reset = any("checkout -- ." in c for c in calls)
         has_clean = any("clean -fd" in c for c in calls)

         assert has_reset is True or any("worktree remove" in c for c in calls)
