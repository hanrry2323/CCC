"""Worker 路由决策单测（ccc-plan-020 执行计划 v2 · A 轨第 2 项）。

覆盖（老板指定）：
1. 派发：scheduler + 执行体：W9 → REMOTE（不本地拉起）【clw020 事故回归】
2. 派发：REMOTE + W9 → REMOTE
3. W1-W4 各自命中（worker_id 对齐，决策路径认 W 号，修 RC4）
4. 本地执行体（OpenCode/Claude Code）→ AUTO（向后兼容）
5. 派发：manual → NONE（管理席派发）
6. REMOTE 卡未认领 → 状态保持待分派（非执行中，防假执行中）
"""

from __future__ import annotations

from pathlib import Path

from server.engine.dispatch import DispatchDecision, ExecutorEntry, ExecutorRegistry, decide_work
from server.engine.main import run_once
from server.engine.store import InMemoryBoardStore
from server.engine.task import State, Work


def _registry() -> ExecutorRegistry:
    """构造含 W1-W4（本地）+ W9（远端）的注册表。"""
    entries = [
        ExecutorEntry(
            role="开发执行体",
            category="可后台 CLI",
            binding="OpenCode",
            note="W4 本地",
            command="echo",
            worker_id="W4",
            transport="local",
        ),
        ExecutorEntry(
            role="开发执行体",
            category="可后台 CLI",
            binding="Claude Code",
            note="W2 本地",
            command="echo",
            worker_id="W2",
            transport="local",
        ),
        ExecutorEntry(
            role="开发执行体",
            category="可后台 CLI",
            binding="OpenCode",
            note="W9 远端",
            command="",
            worker_id="W9",
            transport="git",
        ),
        ExecutorEntry(
            role="验收席",
            category="可后台 CLI",
            binding="Claude Code",
            note="W1 本地",
            command="echo",
            worker_id="W1",
            transport="local",
        ),
    ]
    return ExecutorRegistry(tuple(entries))


def _work(wid: str, executor: str = "", dispatch: str = "engine") -> Work:
    return Work(
        id=wid,
        role="开发执行体",
        card_path=f"docs/dispatch/clw/{wid}.md",
        executor=executor,
        dispatch=dispatch,
    )


class TestDecideWorkRemote:
    """REMOTE 决策态：scheduler/W9 → REMOTE，不本地拉起。"""

    def test_scheduler_dispatch_w9_is_remote(self) -> None:
        """clw020 事故回归：派发 scheduler + 执行体 W9 → REMOTE（不本地拉起）。"""
        w = _work("clw020", executor="W9", dispatch="scheduler")
        assert decide_work(w, _registry()) is DispatchDecision.REMOTE

    def test_remote_dispatch_w9_is_remote(self) -> None:
        w = _work("c1", executor="W9", dispatch="remote")
        assert decide_work(w, _registry()) is DispatchDecision.REMOTE

    def test_scheduler_dispatch_no_executor_is_remote(self) -> None:
        """派发 scheduler 无执行体 → REMOTE（scheduler 语义=远端 Worker 认领）。"""
        w = _work("c2", executor="", dispatch="scheduler")
        assert decide_work(w, _registry()) is DispatchDecision.REMOTE

    def test_w9_executor_is_remote_even_with_local_binding_row(self) -> None:
        """执行体 W9（远端）→ REMOTE，即使注册表有本地 OpenCode 行也不回退角色（修 RC4）。"""
        w = _work("c3", executor="W9", dispatch="engine")
        assert decide_work(w, _registry()) is DispatchDecision.REMOTE

    def test_local_worker_id_hits_auto(self) -> None:
        """W4（本地可后台 CLI）→ AUTO（本地拉起，向后兼容）。"""
        w = _work("c4", executor="W4", dispatch="engine")
        assert decide_work(w, _registry()) is DispatchDecision.AUTO

    def test_tool_name_still_auto(self) -> None:
        """工具名（OpenCode/Claude Code）→ AUTO（不变）。"""
        w = _work("c5", executor="OpenCode", dispatch="engine")
        assert decide_work(w, _registry()) is DispatchDecision.AUTO

    def test_manual_dispatch_is_none(self) -> None:
        w = _work("c6", executor="W9", dispatch="manual")
        assert decide_work(w, _registry()) is DispatchDecision.NONE


class TestRemoteNoFakeRunning:
    """防假执行中：REMOTE 卡未认领 → 保持待分派，非执行中。"""

    def _run_once_with_remote(self, tmp_path: Path) -> InMemoryBoardStore:
        store = InMemoryBoardStore()
        w = _work("clw020", executor="W9", dispatch="scheduler")
        store.seed(w)
        cfg = {
            "EXECUTOR_LOG_DIR": str(tmp_path / "logs"),
            "EXECUTOR_TIMEOUT_SECONDS": "5",
            "EXECUTOR_MAX_CONCURRENT": "1",
            "EXECUTOR_MAX_AUDIT_CONCURRENT": "1",
            "EXECUTOR_INFRA_COOLDOWN_SECONDS": "600",
            "EXECUTOR_PROBE_URL": "",
        }
        run_once(_registry(), store, cfg, wait=True)
        return store

    def test_remote_card_stays_todo_until_claimed(self, tmp_path: Path) -> None:
        """REMOTE 卡未认领 → 状态保持待分派（TODO），不是执行中。"""
        store = self._run_once_with_remote(tmp_path)
        works = [w for w in store.list_work() if w.id == "clw020"]
        assert works, "clw020 卡应存在"
        w = works[0]
        assert w.state is State.TODO, f"REMOTE 卡未认领应保持待分派，实际={w.state.value}"


class TestClaimProtocol:
    """认领协议收单（ccc-plan-020 v2）：认领态/收单/超时回收。"""

    def _write_card(self, tmp_path: Path, cid: str, executor: str, dispatch: str, state: str, claim: str = "", claim_ts: str = "2026-08-11T00:00:00Z") -> Path:
        d = tmp_path / "docs" / "dispatch" / "clw"
        d.mkdir(parents=True, exist_ok=True)
        card = d / f"{cid}.md"
        header = f"> 关联：· 执行体：{executor} · 状态：{state} · 派发：{dispatch} · 项目：clw"
        if claim:
            header += f" · 认领：{claim} · 认领时间：{claim_ts}"
        card.write_text(f"# 任务卡 {cid}\n\n{header}\n\n## 目标\n任务。\n", encoding="utf-8")
        return card

    def _run_once(self, tmp_path: Path, dispatch_rel: str = "docs/dispatch") -> dict:
        store = InMemoryBoardStore()
        dispatch_abs = str(tmp_path / dispatch_rel)
        cfg = {
            "EXECUTOR_LOG_DIR": str(tmp_path / "logs"),
            "DISPATCH_DIR": dispatch_abs,
            "EXECUTOR_TIMEOUT_SECONDS": "5",
            "EXECUTOR_MAX_CONCURRENT": "1",
            "EXECUTOR_MAX_AUDIT_CONCURRENT": "1",
            "EXECUTOR_INFRA_COOLDOWN_SECONDS": "600",
            "EXECUTOR_PROBE_URL": "",
        }
        return run_once(_registry(), store, cfg, wait=True)

    def test_claimed_card_keeps_in_flight(self, tmp_path: Path) -> None:
        """有认领 + 状态=待分派 + 未超时 → in_flight（Worker 执行中）。"""
        from datetime import datetime, timezone

        now_ts = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        self._write_card(tmp_path, "rc1", "W9", "scheduler", "待分派", claim="W9", claim_ts=now_ts)
        summary = self._run_once(tmp_path)
        assert summary["claim_in_flight"] == 1
        assert summary["claim_collected"] == 0

    def test_unclaimed_remote_stays_todo(self, tmp_path: Path) -> None:
        """无认领 → 保持待分派（不标执行中），in_flight=0。"""
        self._write_card(tmp_path, "rc2", "W9", "scheduler", "待分派")
        summary = self._run_once(tmp_path)
        assert summary["claim_in_flight"] == 0
        assert summary["claim_collected"] == 0

    def test_reclaimed_after_timeout(self, tmp_path: Path) -> None:
        """认领超时（claim_ts 超 timeout）→ 回收认领（reclaimed），卡回待分派。"""
        card = self._write_card(tmp_path, "rc3", "W9", "scheduler", "待分派", claim="W9")
        # claim_ts 是 2026-08-11T00:00:00Z（过去很久），EXECUTOR_TIMEOUT=5s → 必超时
        summary = self._run_once(tmp_path)
        assert summary["claim_reclaimed"] == 1
        assert summary["claim_in_flight"] == 0
        # 卡头认领字段已被清（超时回收）
        text = card.read_text(encoding="utf-8")
        assert "认领：" not in text.split("\n")[2]


class TestAuditRemoteCard:
    """机审 remote 适配（ccc-plan-020 v2）：无 worktree → 分支信封 git show 读机审区。"""

    @staticmethod
    def _make_git_repo(tmp_path: Path) -> Path:
        """建临时 git 仓：main + codex/clwX 分支（分支卡含机审区）。"""
        import subprocess

        repo = tmp_path / "repo"
        repo.mkdir(parents=True)
        def _run(*args: str) -> None:
            subprocess.run(list(args), cwd=repo, capture_output=True, check=True)
        _run("git", "init", "-q")
        _run("git", "config", "user.email", "t@t")
        _run("git", "config", "user.name", "t")
        # main 上的卡（无机审区）
        d = repo / "docs" / "dispatch" / "clw"
        d.mkdir(parents=True)
        card = d / "rcard.md"
        card.write_text(
            "# 任务卡 rcard\n\n> 关联：· 执行体：W9 · 状态：已回写 · 派发：scheduler · 项目：clw\n\n## 目标\n任务。\n",
            encoding="utf-8",
        )
        _run("git", "add", ".")
        _run("git", "commit", "-qm", "main card")
        _run("git", "branch", "codex/rcard")
        # codex 分支上的卡（含机审区）
        _run("git", "checkout", "-q", "codex/rcard")
        card.write_text(
            "# 任务卡 rcard\n\n> 关联：· 执行体：W9 · 状态：已回写 · 派发：scheduler · 项目：clw\n\n## 目标\n任务。\n\n## 机审区\n\n**机审：通过**\n",
            encoding="utf-8",
        )
        _run("git", "add", ".")
        _run("git", "commit", "-qm", "card with audit")
        _run("git", "checkout", "-q", "main")
        _run("git", "remote", "add", "origin", ".")
        # 让 origin/codex/rcard 存在
        subprocess.run(
            ["git", "update-ref", "refs/remotes/origin/codex/rcard", "HEAD", "--no-deref"],
            cwd=repo,
            check=True,
        )
        # origin/codex/rcard 应指向含机审区的 commit（切回分支取 tip）
        _run("git", "checkout", "-q", "codex/rcard")
        tip = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()
        subprocess.run(
            ["git", "update-ref", "refs/remotes/origin/codex/rcard", tip],
            cwd=repo,
            check=True,
        )
        _run("git", "checkout", "-q", "main")
        return repo

    def test_remote_card_audit_evidence_from_branch(self, tmp_path: Path) -> None:
        """remote 卡无 worktree → 分支信封 git show origin/codex/<card> 读机审区通过。"""
        from server.engine.main import _audit_evidence_passed

        repo = self._make_git_repo(tmp_path)
        w = _work("rcard", executor="W9", dispatch="scheduler")
        # worktree_hint 空（remote 无本地 worktree）+ main_repo 指向测试仓
        assert _audit_evidence_passed(w, "", main_repo=repo) is True

    def test_remote_card_no_audit_falls_back_to_prod(self, tmp_path: Path) -> None:
        """remote 分支无机审区 → 回退生产卡（main 卡也无 → False）。"""
        from server.engine.main import _audit_evidence_passed

        repo = tmp_path / "repo2"
        repo.mkdir(parents=True)
        import subprocess

        def _run(*args: str) -> None:
            subprocess.run(list(args), cwd=repo, capture_output=True, check=True)
        _run("git", "init", "-q")
        _run("git", "config", "user.email", "t@t")
        _run("git", "config", "user.name", "t")
        d = repo / "docs" / "dispatch" / "clw"
        d.mkdir(parents=True)
        card = d / "rcard2.md"
        card.write_text(
            "# 任务卡 rcard2\n\n> 关联：· 执行体：W9 · 状态：已回写 · 派发：scheduler · 项目：clw\n\n## 目标\n。\n",
            encoding="utf-8",
        )
        _run("git", "add", ".")
        _run("git", "commit", "-qm", "c")
        _run("git", "remote", "add", "origin", ".")
        w = _work("rcard2", executor="W9", dispatch="scheduler")
        assert _audit_evidence_passed(w, "", main_repo=repo) is False
