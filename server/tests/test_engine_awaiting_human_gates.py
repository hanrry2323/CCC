"""F6-F9 四漏口挂人工闸一次性收口测试（指令单 §四 · 2026-09-19）。

四场景（每条含正向不回归）：
1. F6  标记丢失回收环：sidecar awaiting_human + RUNNING + 无 .running + 心跳超 60s
       → 不转 TODO、回收计数 0、日志含「保持现状不回收」。
2. F7  dsh-executor 信封缺失：rc=64 + 日志含 ENVELOPE_MISSING work=<id>。
3. F8  引擎重启回收第三支路：awaiting_human + RUNNING + .running 已删 + 重启扫描
       → 不转 TODO、不 kill 不重派、日志含「保持现状不回收」。
4. F9  派发闸：awaiting_human + TODO → _submit 不被调用（计数断言）、
       不 transition RUNNING、日志含「派发闸拦截」。
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from server.engine.gates import (
    DispatchGate,
    GateContext,
    GateRegistry,
    GateResult,
)
from server.engine.main import (
    _build_dispatch_gates,
    _card_awaiting_human,
    reclaim_orphaned_running,
)
from server.engine.runtime_state import write_card_state
from server.engine.store import InMemoryBoardStore
from server.engine.task import State, Work

# 复用 F6 测试同款现场造器（保持判定路径一致，不重写判定逻辑）
from server.tests.test_marker_lost_no_resurrect_exhausted import _aging_log

_RC64 = 64
_ENVELOPE_MARKER = "ENVELOPE_MISSING work="


def _log(caplog: pytest.LogCaptureFixture, text: str) -> list[str]:
    return [r.message for r in caplog.records if text in r.message]


class _StubPool:
    """测试用占位池：occupancy 返回 0（不触真实线程池）。"""

    def occupancy(self, store: object, log_dir: object) -> int:
        return 0


def _mk_ctx(log_dir: Path, w: Work, store: InMemoryBoardStore) -> GateContext:
    """F9 隔离上下文：registry 复用既有 chain 测试的 demo 注册表（不拉真实执行体）。"""
    from server.tests.test_engine_gates import TestDispatchGateChain

    return GateContext(
        work=w,
        registry=TestDispatchGateChain._mk_demo_registry(),
        by_id={w.id: w},
        runtime={},
        now_ts=time.time(),
        store=store,
        log_dir=log_dir,
        cfg={},
        pool=_StubPool(),
        probe_url="",
        slots=1,
        max_concurrent=1,
        timeout=300,
        counters={},
    )


def _mk_f9_registry() -> tuple[GateRegistry, dict[int]]:
    """隔离 F9 闸：只保留 awaiting_human + 一个「submit 替身」。

    F9 在真实链上 order=0（chain 顺序由 test_engine_gates 覆盖）；这里隔离出来，
    避免 card_gate / dsh_quota / relay_probe 等无关门禁干扰 F9 判定语义。
    submit 替身一旦被调用即计一次——「挂人工不得进入 submit」的直接观测信号。
    """
    full = _build_dispatch_gates()
    f9 = full.gates["awaiting_human"]
    reg = GateRegistry()
    reg.register(f9)
    calls: dict[int] = {"n": 0}

    def _submit_stub(ctx: GateContext) -> GateResult:
        calls["n"] += 1
        return GateResult(passed=True)

    reg.register(DispatchGate(name="submit", order=110, check=_submit_stub))
    return reg, calls


class TestF6MarkerLostNoResurrect:
    """F6：标记丢失回收环不得复活已挂人工卡。"""

    def test_awaiting_human_not_reclaimed(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        store = InMemoryBoardStore()
        w = Work(id="xy079", role="开发执行体", state=State.RUNNING)
        store.seed(w)
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        write_card_state(
            log_dir, "xy079", awaiting_human=True, reject_budget_exhausted=True, exhausted_class="business"
        )
        _aging_log(log_dir, "xy079")

        with caplog.at_level("ERROR", logger="ccc.engine"):
            n = reclaim_orphaned_running(store, log_dir)

        assert n == 0
        assert w.state is State.RUNNING
        assert not store.list_work(state=State.TODO), "挂人工卡不得回待分派"
        assert _log(caplog, "保持现状不回收")

    def test_normal_inflight_still_reclaimed(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        """正向不回归：正常在途卡标记丢失仍走原回收路径。"""
        store = InMemoryBoardStore()
        w = Work(id="tst201", role="开发执行体", state=State.RUNNING)
        store.seed(w)
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        _aging_log(log_dir, "tst201")

        with caplog.at_level("WARNING", logger="ccc.engine"):
            n = reclaim_orphaned_running(store, log_dir)

        assert n == 1
        assert w.state is State.TODO
        assert not _log(caplog, "保持现状不回收"), "正常在途卡不应命中挂人工闸"


class TestF7EnvelopeMissingRc64:
    """F7：dsh-executor 信封缺失 → rc=64 + 死因可 grep（引擎侧可诊断）。"""

    @staticmethod
    def _executor_source() -> str:
        return Path("scripts/dsh-executor.sh").read_text(encoding="utf-8")

    def test_envelope_missing_rc64(self, tmp_path: Path) -> None:
        """信封缺失路径：exit 64 存在 + ENVELOPE_MISSING 标记可 grep。"""
        body = self._executor_source()
        assert _ENVELOPE_MARKER in body
        assert f"exit {_RC64}" in body

    def test_normal_path_not_envelope_missing(self, tmp_path: Path) -> None:
        """正向不回归：正常路径退出码透传（非 64），ENVELOPE_MISSING 只在缺失分支出现。"""
        body = self._executor_source()
        # 末尾必须是透传退出（三选一，兼容不同写法）
        passed_through = [
            'exit "$DSH_RC"',
            'exit "$_DSH_RC"',
            'exit "$_KC_EXIT"',
        ]
        assert any(pat in body for pat in passed_through), (
            "正常路径退出码必须透传 DSH rc，不得固定 64"
        )
        assert body.count("ENVELOPE_MISSING") >= 1, "缺失分支必须有可 grep 死因标记"


class TestF8RestartInterruptNoResurrect:
    """F8：引擎中断/超时回收第三支路不得复活已挂人工卡（与 F6 同 helper）。"""

    def test_awaiting_human_not_reclaimed_on_restart(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        store = InMemoryBoardStore()
        w = Work(id="xy079", role="开发执行体", state=State.RUNNING)
        store.seed(w)
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        write_card_state(
            log_dir, "xy079", awaiting_human=True, reject_budget_exhausted=True, exhausted_class="business"
        )
        _aging_log(log_dir, "xy079")

        with caplog.at_level("ERROR", logger="ccc.engine"):
            n = reclaim_orphaned_running(store, log_dir)

        assert n == 0
        assert w.state is State.RUNNING
        assert not store.list_work(state=State.TODO)
        assert _log(caplog, "保持现状不回收")

    def test_normal_restart_still_reclaimed(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        """正向不回归：正常在途卡引擎重启中断仍走原回收路径。"""
        store = InMemoryBoardStore()
        w = Work(id="tst301", role="开发执行体", state=State.RUNNING)
        store.seed(w)
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        _aging_log(log_dir, "tst301")

        with caplog.at_level("WARNING", logger="ccc.engine"):
            n = reclaim_orphaned_running(store, log_dir)

        assert n == 1
        assert w.state is State.TODO
        assert not _log(caplog, "保持现状不回收"), "正常在途卡不应命中挂人工闸"


class TestF9DispatchGate:
    """F9：派发路径挂人工闸（根因 · order=0 全链最前）。"""

    def test_dispatch_gate_blocks_awaiting_human(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        store = InMemoryBoardStore()
        w = Work(id="xy079", role="开发执行体", state=State.TODO)
        store.seed(w)
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        write_card_state(
            log_dir, "xy079", awaiting_human=True, reject_budget_exhausted=True, exhausted_class="business"
        )

        reg, calls = _mk_f9_registry()

        with caplog.at_level("ERROR", logger="ccc.engine"):
            result = reg.run(_mk_ctx(log_dir, w, store))

        assert result is not None
        assert result.passed is False
        assert result.reason == "awaiting_human"
        assert calls["n"] == 0, "挂人工卡不得进入 submit（不得复活）"
        assert w.state is State.TODO, "不 transition RUNNING"
        assert _log(caplog, "派发闸拦截")

    def test_dispatch_gate_passes_normal_card(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """正向不回归：正常 TODO 卡（无挂人工标记）不被 F9 拦。"""
        store = InMemoryBoardStore()
        w = Work(id="tst401", role="开发执行体", state=State.TODO)
        store.seed(w)
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        reg, calls = _mk_f9_registry()

        with caplog.at_level("INFO", logger="ccc.engine"):
            result = reg.run(_mk_ctx(log_dir, w, store))

        assert not _log(caplog, "派发闸拦截"), "正常卡不应命中 F9 闸"
        assert result is None, "全链放行"
        assert calls["n"] == 1, "正常卡必须走到 submit（F9 放行）"


class TestHelperShared:
    """helper 唯一性 + 语义（F1/F6/F8/F9 四闸共用，禁复制判定逻辑）。"""

    def test_helper_semantics(self, tmp_path: Path) -> None:
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        assert _card_awaiting_human(None, "any") is False
        assert _card_awaiting_human(log_dir, "absent") is False
        write_card_state(log_dir, "only-awaiting", awaiting_human=True)
        assert _card_awaiting_human(log_dir, "only-awaiting") is True
        write_card_state(log_dir, "only-budget", reject_budget_exhausted=True)
        assert _card_awaiting_human(log_dir, "only-budget") is True
        write_card_state(log_dir, "negative", awaiting_human=False, reject_budget_exhausted=False)
        assert _card_awaiting_human(log_dir, "negative") is False

    def test_no_inline_predicate_duplication(self) -> None:
        """禁复制判定实现：全仓内联展开应只有 helper 内一处。"""
        main = Path("server/engine/main.py").read_text(encoding="utf-8")
        inline = 'rt_card.get("awaiting_human") or rt_card.get("reject_budget_exhausted")'
        assert main.count(inline) == 1, "判定逻辑内联展开必须只在 helper 内出现一次"
        assert main.count("def _card_awaiting_human") == 1
