"""sidecar 生命周期契约单测（ccc-plan-021 · A 轨平台根治）。

覆盖：
1. 成功出口 → clear sidecar（无在途残留）
2. 业务打回 → clear sidecar（磁盘终态权威）
3. manual/W 号不可自愈执行体 → 立即 clear sidecar（clw019 挂死根因）
4. 可自愈重试 → 只写 retry_count、清流程态
5. 收敛器：孤儿记录清除 + 终态残留清除 + 保留 infra 冷却
"""

from __future__ import annotations

import pytest

from pathlib import Path

from server.engine.main import _fail_retry_or_reject, _is_manual_or_remote_executor
from server.engine.runtime_state import clear_card_state, read_card_state, write_card_state
from server.engine.store import InMemoryBoardStore
from server.engine.task import State, Work


def _seed_work(store: InMemoryBoardStore, wid: str, executor: str = "demo") -> Work:
    card = f"docs/dispatch/clw/{wid}.md"
    w = Work(id=wid, role="开发执行体", card_path=card, executor=executor)
    store.seed(w)
    return w


class TestSidecarLifecycle:
    """契约四象限：write/clear 语义 + 谁负责。"""

    def test_success_exit_clears_sidecar(self, tmp_path: Path) -> None:
        """成功收单后 sidecar 无流程态残留（clear_card_state 写 null 失效）。"""
        write_card_state(tmp_path, "c1", state="待分派", retry_count=1, reason="执行失败")
        assert read_card_state(tmp_path).get("c1", {}).get("state") == "待分派"

        clear_card_state(tmp_path, "c1")
        # null 失效语义：read 后该卡无 state
        rec = read_card_state(tmp_path).get("c1")
        assert rec is None or rec.get("state") is None

    def test_reject_exit_clears_sidecar(self, tmp_path: Path) -> None:
        """业务打回（重试用尽）后 sidecar 清空，磁盘卡为终态权威。"""
        store = InMemoryBoardStore()
        w = _seed_work(store, "c2")
        w.transition(State.RUNNING)  # 合法路径：执行中 → 打回
        w.retry_count = 3  # 模拟已达上限
        write_card_state(tmp_path, "c2", state="待分派", retry_count=3, reason="业务不通过")

        retried = _fail_retry_or_reject(w, store, ["业务不通过"], {"EXECUTOR_MAX_RETRIES": "3"}, tmp_path)
        assert retried is False  # 已打回
        assert w.state is State.REJECTED
        # sidecar 已清（null 失效）
        rec = read_card_state(tmp_path).get("c2")
        assert rec is None or rec.get("state") is None

    def test_manual_executor_rejects_immediately_and_clears(self, tmp_path: Path) -> None:
        """manual 执行体（不可自愈）打回 → 立即 clear sidecar，不进重试预算。"""
        store = InMemoryBoardStore()
        w = _seed_work(store, "c3", executor="W9")
        w.transition(State.RUNNING)  # 合法路径：执行中 → 打回
        w.retry_count = 0
        write_card_state(tmp_path, "c3", state="已回写", retry_count=0)

        retried = _fail_retry_or_reject(w, store, ["manual 未接单"], {"EXECUTOR_MAX_RETRIES": "3"}, tmp_path)
        assert retried is False
        assert w.state is State.REJECTED  # 直接打回，不重试
        assert w.retry_count == 0  # 未消耗重试预算
        rec = read_card_state(tmp_path).get("c3")
        assert rec is None or rec.get("state") is None  # sidecar 已清

    def test_manual_detector(self) -> None:
        """_is_manual_or_remote_executor 识别 manual / W 号。"""
        store = InMemoryBoardStore()
        assert _is_manual_or_remote_executor(_seed_work(store, "m1", executor="manual")) is True
        assert _is_manual_or_remote_executor(_seed_work(store, "m2", executor="W9")) is True
        assert _is_manual_or_remote_executor(_seed_work(store, "m3", executor="OpenCode")) is False
        assert _is_manual_or_remote_executor(_seed_work(store, "m4", executor="Claude Code")) is False
        assert _is_manual_or_remote_executor(_seed_work(store, "m5", executor="")) is False

    def test_retryable_writes_retry_count_clears_state(self, tmp_path: Path) -> None:
        """可自愈重试：写 retry_count、清流程态（sidecar 不存流程终态）。"""
        store = InMemoryBoardStore()
        w = _seed_work(store, "c4")
        w.transition(State.RUNNING)  # 合法路径：执行中 → 待分派重试
        w.retry_count = 1
        write_card_state(tmp_path, "c4", state="执行中", retry_count=1)

        retried = _fail_retry_or_reject(w, store, ["超时"], {"EXECUTOR_MAX_RETRIES": "3"}, tmp_path)
        assert retried is True  # 回待分派重试
        assert w.state is State.TODO
        assert w.retry_count == 2
        # sidecar：retry_count 记录在，但 state 已清
        rec = read_card_state(tmp_path).get("c4")
        assert rec is None or rec.get("state") is None
        if rec:
            assert rec.get("retry_count") == 2


class TestConverger:
    """收敛器：孤儿清除 / 终态残留清除 / 保留 infra 冷却。"""

    def _run_converge(self, tmp_path: Path, store: InMemoryBoardStore) -> None:
        """模拟 run_once 开头的收敛器逻辑（提取自 engine.run_once）。"""
        runtime = read_card_state(tmp_path)
        if not runtime:
            return
        all_works = {w.id: w for w in store.list_work()}
        for cid in list(runtime.keys()):
            rec = runtime[cid]
            w = all_works.get(cid)
            if w is None:
                clear_card_state(tmp_path, cid)
                continue
            if rec.get("state") in (State.DONE.value, State.REJECTED.value, State.CLOSED.value):
                if rec.get("infra_cooldown_until"):
                    continue
                clear_card_state(tmp_path, cid)
            elif rec.get("state") == State.TODO.value and w.state is State.REJECTED:
                # sidecar 待分派但磁盘已打回（双源漂移）→ 清除
                clear_card_state(tmp_path, cid)

    def test_orphan_cleared(self, tmp_path: Path) -> None:
        """孤儿 sidecar（不对应任何卡）→ 收敛器清除。"""
        store = InMemoryBoardStore()
        write_card_state(tmp_path, "ghost", state="待分派", reason="孤儿")
        assert read_card_state(tmp_path).get("ghost") is not None

        self._run_converge(tmp_path, store)
        assert read_card_state(tmp_path).get("ghost") is None

    def test_terminal_state_residual_cleared(self, tmp_path: Path) -> None:
        """终态残留（磁盘已打回，sidecar 仍待分派）→ 收敛器清除。"""
        store = InMemoryBoardStore()
        w = _seed_work(store, "c5")
        w.transition(State.RUNNING)
        w.transition(State.REJECTED, problems=["打回"])
        store.save_work(w)
        write_card_state(tmp_path, "c5", state="待分派", reason="残留")

        self._run_converge(tmp_path, store)
        assert read_card_state(tmp_path).get("c5") is None

    def test_infra_cooldown_preserved(self, tmp_path: Path) -> None:
        """infra 冷却记录（带 infra_cooldown_until）→ 收敛器保留。"""
        store = InMemoryBoardStore()
        w = _seed_work(store, "c6")
        write_card_state(
            tmp_path,
            "c6",
            state="已回写",
            infra_cooldown_until="2026-08-11T23:59:59Z",
            infra_count=1,
        )

        self._run_converge(tmp_path, store)
        rec = read_card_state(tmp_path).get("c6")
        assert rec is not None
        assert rec.get("infra_cooldown_until") == "2026-08-11T23:59:59Z"


def test_trigger_scheduled_ops_immediate(tmp_path) -> None:
    """定时运维触发：无「定时」字段的 scheduler 卡首次扫描即触发（2026-08-11）。"""
    from server.engine.observer import trigger_scheduled_ops

    dispatch = tmp_path / "dispatch" / "ops"
    dispatch.mkdir(parents=True)
    log = tmp_path / "logs"
    log.mkdir(parents=True)
    (dispatch / "ops001-immediate.md").write_text(
        "# 任务卡 ops001\n\n> 关联：ccc · 执行体：W9 · 状态：待分派 · 派发：scheduler\n", encoding="utf-8"
    )
    cfg = {
        "SCHEDULER_DISPATCH_DIR": str(tmp_path / "dispatch"),
        "EXECUTOR_LOG_DIR": str(log),
    }
    ok, summary = trigger_scheduled_ops(cfg)
    assert ok
    assert any("ops001" in t for t in summary["triggered"])


def test_trigger_scheduled_ops_deferred(tmp_path) -> None:
    """定时运维触发：定时未到的 scheduler 卡保持 pending（2026-08-11）。"""
    from server.engine.observer import trigger_scheduled_ops

    dispatch = tmp_path / "dispatch" / "ops"
    dispatch.mkdir(parents=True)
    log = tmp_path / "logs"
    log.mkdir(parents=True)
    (dispatch / "ops003-notyet.md").write_text(
        "# 任务卡 ops003\n\n> 关联：ccc · 执行体：W9 · 状态：待分派 · 派发：scheduler · 定时：23:59\n",
        encoding="utf-8",
    )
    cfg = {
        "SCHEDULER_DISPATCH_DIR": str(tmp_path / "dispatch"),
        "EXECUTOR_LOG_DIR": str(log),
    }
    ok, summary = trigger_scheduled_ops(cfg)
    assert ok
    assert any("ops003" in p for p in summary["pending"])
    assert not summary["triggered"]


class TestBranchEnvelopeAuthority:
    """2026-08-12：终态权威补齐——磁盘 main 镜像 + sidecar 清除后，远端 codex 分支信封为真值。

    收单成功后 sidecar 按契约清除，磁盘卡（main 镜像）仍是待分派；
    若不读分支信封，engine 会把已回写卡误判重派、机审永远扫不到（mx035 三连循环根因）。
    """

    def _make_repo_with_branch_card(self, tmp_path: Path, state: str) -> tuple[Path, dict]:
        import subprocess

        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "T"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "t@e"], cwd=repo, check=True, capture_output=True)
        card = "docs/dispatch/mx/mx999-flow-test.md"
        p = repo / card
        p.parent.mkdir(parents=True)
        p.write_text(
            f"# 任务卡 mx999-flow-test · flow test\n\n> 关联：mx-plan-002 · 执行体：OpenCode · 验收：OpenCode · 状态：{state} · 项目：mx\n\n## 目标\nx\n\n## 维护区\n\n1. **方案同步**：[是]\n   - 说明：a\n2. **教训沉淀**：[有]\n   - 说明：b\n3. **档案/README**：[否]\n   - 说明：c\n4. **线路图**：[否]\n   - 说明：d\n",
            encoding="utf-8",
        )
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-qm", "card"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "branch", "codex/mx999-flow-test"], cwd=repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "update-ref", "refs/remotes/origin/codex/mx999-flow-test", "codex/mx999-flow-test"],
            cwd=repo,
            check=True,
            capture_output=True,
        )
        # 模拟执行体回写：分支卡已回写，main 卡仍待分派
        p.write_text(
            p.read_text(encoding="utf-8").replace("状态：已回写", "状态：待分派").replace("状态：打回", "状态：待分派"),
            encoding="utf-8",
        )
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-qm", "main-stale"], cwd=repo, check=True, capture_output=True)
        return repo, {"id": "mx999", "path": card, "state": "待分派", "executor": "OpenCode"}

    def test_branch_envelope_reads_writeback_state(self, tmp_path: Path) -> None:
        from server.engine.store import _branch_envelope_state

        repo, entry = self._make_repo_with_branch_card(tmp_path, "已回写")
        state = _branch_envelope_state(repo, entry)
        assert state == "已回写"

    def test_branch_envelope_missing_branch_returns_empty(self, tmp_path: Path) -> None:
        from server.engine.store import _branch_envelope_state

        repo, entry = self._make_repo_with_branch_card(tmp_path, "已回写")
        entry2 = dict(entry)
        entry2["path"] = "docs/dispatch/mx/mx888-nobranch.md"
        assert _branch_envelope_state(repo, entry2) == ""

    def test_file_store_merges_branch_envelope(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """磁盘待分派 + sidecar 空 + 分支已回写 → list_work(DONE) 命中（不再误重派）。"""
        import subprocess

        from server.engine.store import FileBoardStore

        repo, entry = self._make_repo_with_branch_card(tmp_path, "已回写")
        dispatch_dir = repo / "docs" / "dispatch"
        # 索引由 loader 生成（磁盘 main 卡待分派）
        monkeypatch.chdir(repo)
        # 用 InMemory registry（空注册表即可，role 反查允许空）
        from server.engine.dispatch import ExecutorRegistry

        reg = ExecutorRegistry(())
        store = FileBoardStore(dispatch_dir, reg, log_dir=tmp_path / "logs")
        done = store.list_work(state=State.DONE)
        assert any(w.id == "mx999-flow-test" for w in done)
        # 待分派队列不应再包含 mx999
        todo = store.list_work(state=State.TODO)
        assert all(w.id != "mx999-flow-test" for w in todo)
