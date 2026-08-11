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
