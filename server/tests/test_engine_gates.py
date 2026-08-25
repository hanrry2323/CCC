"""GateRegistry 派发门禁框架单测（P1 框架 + P3 全链接线回归）。

覆盖：
1. 框架：register 重名拒绝 / ordered 排序 / requires 环与未注册校验 / run 依赖短路。
2. 单 gate：装配前 7 门禁 + submit 原子占槽（P3 接线后运行）。
3. run_once 回归：计数器口径（P3 接线后运行）。
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

from server.engine.gates import DispatchGate, GateContext, GateRegistry, GateResult
from server.engine.main import _build_dispatch_gates, _load_registry_cached
from server.engine.store import InMemoryBoardStore
from server.engine.task import State, Work


class _StubPool:
    """测试用占位池：occupancy 返回 0（不触真实线程池）。"""

    def occupancy(self, store: object, log_dir: object) -> int:
        return 0

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


# ── 框架单测（P1） ──


def _called_tracker() -> list[str]:
    return []


def _mk_gate(name: str, order: int, requires: tuple[str, ...] = (), tracker: list[str] | None = None) -> DispatchGate:
    def _check(ctx: GateContext) -> GateResult:
        if tracker is not None:
            tracker.append(name)
        return GateResult(passed=True)

    return DispatchGate(name=name, order=order, check=_check, requires=requires)


def _mk_ctx() -> GateContext:
    work = Work(id="w1", role="开发执行体")
    return GateContext(
        work=work,
        registry=None,
        by_id={},
        runtime={},
        now_ts=0.0,
        store=None,  # type: ignore[arg-type]  # 框架单测不触 store
        log_dir=Path("/tmp/ccc-gates-test"),
        cfg={},
        pool=None,  # type: ignore[arg-type]
        probe_url="",
        slots=1,
        max_concurrent=1,
        timeout=300,
    )


class TestGateRegistryFramework:
    def test_register_and_ordered_sorted(self) -> None:
        reg = GateRegistry()
        reg.register(_mk_gate("parent_closed", order=40))
        reg.register(_mk_gate("decision", order=70))
        reg.register(_mk_gate("infra_cooldown", order=10))
        names = [g.name for g in reg.ordered()]
        assert names == ["infra_cooldown", "parent_closed", "decision"]

    def test_register_duplicate_rejected(self) -> None:
        reg = GateRegistry()
        reg.register(_mk_gate("a", order=10))
        with pytest.raises(ValueError, match="duplicate gate"):
            reg.register(_mk_gate("a", order=20))

    def test_ordered_rejects_unknown_requires(self) -> None:
        reg = GateRegistry()
        reg.register(_mk_gate("a", order=10, requires=("ghost",)))
        with pytest.raises(ValueError, match="ghost"):
            reg.ordered()

    def test_ordered_rejects_dependency_cycle(self) -> None:
        reg = GateRegistry()
        reg.register(_mk_gate("a", order=10, requires=("b",)))
        reg.register(_mk_gate("b", order=20, requires=("a",)))
        with pytest.raises(ValueError, match="依赖未先序"):
            reg.ordered()

    def test_requires_must_precede(self) -> None:
        reg = GateRegistry()
        reg.register(_mk_gate("a", order=20, requires=("b",)))
        reg.register(_mk_gate("b", order=10))
        # b 先序注册（order 10）→ a 依赖满足，合法
        assert [g.name for g in reg.ordered()] == ["b", "a"]

    def test_run_passes_all_gates_returns_none(self) -> None:
        tracker = _called_tracker()
        reg = GateRegistry()
        reg.register(_mk_gate("a", order=10, tracker=tracker))
        reg.register(_mk_gate("b", order=20, requires=("a",), tracker=tracker))
        assert reg.run(_mk_ctx()) is None
        assert tracker == ["a", "b"]

    def test_run_short_circuit_on_first_block(self) -> None:
        """首个阻断门禁后，依赖它的门禁不被调用。"""
        tracker = _called_tracker()

        def _block(ctx: GateContext) -> GateResult:
            tracker.append("block")
            return GateResult(passed=False, reason="blocked")

        def _after(ctx: GateContext) -> GateResult:
            tracker.append("after")
            return GateResult(passed=True)

        reg = GateRegistry()
        reg.register(DispatchGate(name="block", order=10, check=_block))
        reg.register(DispatchGate(name="after", order=20, check=_after, requires=("block",)))
        res = reg.run(_mk_ctx())
        assert res is not None
        assert res.passed is False
        assert res.reason == "blocked"
        assert tracker == ["block"]  # after 未被调用

    def test_run_dependency_satisfied_then_after_called(self) -> None:
        tracker = _called_tracker()

        def _pass(ctx: GateContext) -> GateResult:
            tracker.append("pass")
            return GateResult(passed=True)

        def _after(ctx: GateContext) -> GateResult:
            tracker.append("after")
            return GateResult(passed=True)

        reg = GateRegistry()
        reg.register(DispatchGate(name="pass", order=10, check=_pass))
        reg.register(DispatchGate(name="after", order=20, check=_after, requires=("pass",)))
        assert reg.run(_mk_ctx()) is None
        assert tracker == ["pass", "after"]


# ── 派发门禁链集成（P3 全链接线） ──


class TestDispatchGateChain:
    """_build_dispatch_gates() 装配的门禁链行为（run_once 派发决策部分）。"""

    @staticmethod
    def _mk_demo_registry() -> Any:
        """demo 执行体注册表（echo 命令，不拉真实执行体）。"""
        from server.engine.dispatch import load_registry

        reg_data = {
            "version": "2",
            "executors": [
                {
                    "角色": "开发执行体",
                    "分类": "可后台 CLI",
                    "当前绑定": "demo",
                    "命令": "echo",
                    "参数模板": "work={work_id}",
                    "工作目录": "",
                    "备注": "测试夹具",
                }
            ],
        }
        import json
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "executors.json"
            p.write_text(json.dumps(reg_data, ensure_ascii=False), encoding="utf-8")
            return load_registry(p)

    def _mk_chain_ctx(
        self,
        work: Work,
        by_id: dict[str, Work] | None = None,
        store: InMemoryBoardStore | None = None,
        slots: int = 1,
        runtime: dict | None = None,
        registry: Any | None = None,
    ) -> GateContext:
        store = store or InMemoryBoardStore()
        return GateContext(
            work=work,
            registry=registry if registry is not None else self._mk_demo_registry(),
            by_id=by_id or {work.id: work},
            runtime=runtime or {},
            now_ts=1000.0,
            store=store,
            log_dir=Path("/tmp/ccc-gates-chain"),
            cfg={},
            pool=_StubPool(),  # type: ignore[arg-type]  # 不触真实线程池
            probe_url="",
            slots=slots,
            max_concurrent=1,
            timeout=300,
        )

    def test_gate_chain_11_ordered(self) -> None:
        """13 个门禁装配成功且顺序正确（ccc083 新增 retry_backoff/short_session_breaker）。"""
        reg = _build_dispatch_gates()
        names = [g.name for g in reg.ordered()]
        assert names == [
            "infra_cooldown",
            "retry_backoff",
            "short_session_breaker",
            "worktree_card_copy",
            "accepted_card",
            "parent_closed",
            "depends_closed",
            "dependency_cycle",
            "decision",
            "slot_available",
            "biz_isolation",
            "relay_probe",
            "submit",
        ]

    def test_infra_cooldown_blocks(self) -> None:
        work = Work(id="w1", role="开发执行体")
        # _infra_cooldown_active 期望 ISO 时间戳字符串；now_ts=1000 → 未来时间必然冷却
        future_iso = "2999-01-01T00:00:00+00:00"
        ctx = self._mk_chain_ctx(work, runtime={"w1": {"infra_cooldown_until": future_iso}})
        reg = _build_dispatch_gates()
        res = reg.run(ctx)
        assert res is not None
        assert res.passed is False
        assert res.reason == "infra_cooldown"
        assert ctx.counters == {}  # infra 冷却不计数

    def test_parent_blocks_increments_counter(self) -> None:
        parent = Work(id="p1", role="开发执行体", state=State.RUNNING)
        child = Work(id="w1", role="开发执行体", parent="p1")
        store = InMemoryBoardStore()
        store.seed(parent, child)
        ctx = self._mk_chain_ctx(child, by_id={"p1": parent, "w1": child}, store=store)
        reg = _build_dispatch_gates()
        res = reg.run(ctx)
        assert res is not None
        assert res.passed is False
        assert ctx.counters.get("parent_skips") == 1

    def test_depends_blocks_increments_counter(self) -> None:
        dep = Work(id="d1", role="开发执行体", state=State.TODO)
        work = Work(id="w1", role="开发执行体", depends_on=["d1"])
        ctx = self._mk_chain_ctx(work, by_id={"d1": dep, "w1": work})
        reg = _build_dispatch_gates()
        res = reg.run(ctx)
        assert res is not None
        assert res.passed is False
        assert ctx.counters.get("dep_skips") == 1

    def test_dependency_cycle_blocks(self) -> None:
        """依赖已关闭但依赖链成环 → cycle gate 拦截（depends_closed 先放行）。"""
        w1 = Work(id="w1", role="开发执行体", depends_on=["w2"])
        w2 = Work(id="w2", role="开发执行体", depends_on=["w1"], state=State.CLOSED)
        ctx = self._mk_chain_ctx(w1, by_id={"w1": w1, "w2": w2})
        reg = _build_dispatch_gates()
        res = reg.run(ctx)
        assert res is not None
        assert res.passed is False
        assert ctx.counters.get("cycle_skips") == 1

    def test_decision_none_role_counts_none_skips(self) -> None:
        """未知角色（无注册行）→ NONE → none_skips。registry=None 时 decide 回退 none。"""
        work = Work(id="w1", role="未知角色")
        ctx = self._mk_chain_ctx(work)
        reg = _build_dispatch_gates()
        res = reg.run(ctx)
        assert res is not None
        assert res.passed is False
        # registry=None → rows_for_role 返回空 → decide() → NONE
        assert ctx.counters.get("none_skips") == 1

    def test_slot_exhausted_queues(self) -> None:
        """AUTO 决策 + slots=0 → queued。需 registry 返回 AUTO 行。"""
        # 用真实注册表（demo 命令）走 AUTO 分支
        import json

        reg_data = {
            "version": "2",
            "executors": [
                {
                    "角色": "开发执行体",
                    "分类": "可后台 CLI",
                    "当前绑定": "demo",
                    "命令": "echo",
                    "参数模板": "work={work_id}",
                    "工作目录": "",
                    "备注": "测试夹具",
                }
            ],
        }
        from server.engine.dispatch import ExecutorRegistry, load_registry
        from pathlib import Path as _Path

        import tempfile

        with tempfile.TemporaryDirectory() as td:
            p = _Path(td) / "executors.json"
            p.write_text(json.dumps(reg_data, ensure_ascii=False), encoding="utf-8")
            reg = load_registry(p)
            work = Work(id="w1", role="开发执行体")
            ctx = self._mk_chain_ctx(work, slots=0)
            ctx.registry = reg
            chain = _build_dispatch_gates()
            res = chain.run(ctx)
            assert res is not None
            assert res.passed is False
            assert ctx.counters.get("queued") == 1


# ── executors.json 热重载（P4 扩展） ──


class TestRegistryHotReload:
    def test_reload_on_mtime_change(self, tmp_path: Path) -> None:
        import json as _json

        p = tmp_path / "executors.json"
        p.write_text(
            _json.dumps(
                {
                    "version": "2",
                    "executors": [
                        {
                            "角色": "开发执行体",
                            "分类": "可后台 CLI",
                            "当前绑定": "demo",
                            "命令": "echo",
                            "参数模板": "work={work_id}",
                            "工作目录": "",
                            "备注": "v1",
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        reg1, mtime1 = _load_registry_cached(p, None)
        assert reg1 is not None and mtime1 is not None
        # mtime 未变 → 返回 None（复用）
        reg2, mtime2 = _load_registry_cached(p, mtime1)
        assert reg2 is None and mtime2 == mtime1
        # 改文件（mtime 变）→ 重新加载
        p.write_text(
            _json.dumps(
                {
                    "version": "2",
                    "executors": [
                        {
                            "角色": "开发执行体",
                            "分类": "可后台 CLI",
                            "当前绑定": "demo",
                            "命令": "echo",
                            "参数模板": "new={work_id}",
                            "工作目录": "",
                            "备注": "v2",
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        reg3, mtime3 = _load_registry_cached(p, mtime1)
        assert reg3 is not None
        assert mtime3 is not None and mtime3 != mtime1

    def test_invalid_file_keeps_last_registry(self, tmp_path: Path) -> None:
        import json as _json

        p = tmp_path / "executors.json"
        p.write_text(
            _json.dumps({"version": "2", "executors": []}, ensure_ascii=False),
            encoding="utf-8",
        )
        reg, mtime = _load_registry_cached(p, None)
        assert reg is not None and mtime is not None
        # 损坏文件 → 沿用旧 registry
        p.write_text("{bad json", encoding="utf-8")
        reg2, mtime2 = _load_registry_cached(p, mtime)
        assert reg2 is None
        assert mtime2 == mtime

    def test_missing_file_returns_none(self, tmp_path: Path) -> None:
        p = tmp_path / "nonexistent.json"
        reg, mtime = _load_registry_cached(p, None)
        assert reg is None and mtime is None
        # 传 None path
        reg2, mtime2 = _load_registry_cached(None, None)
        assert reg2 is None and mtime2 is None
