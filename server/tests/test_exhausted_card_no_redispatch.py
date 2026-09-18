"""F1：已挂人工卡不得被 worker 异常路径自动重派（2026-09-18）。

复现证据（engine.stderr.log 06:56）：xy078 reject 预算耗尽挂人工
（awaiting_human=true, reject_budget_exhausted=true）后，任何 worker 异常
都走 ``_fail_retry_or_reject`` 的重试分支，把已挂人工的卡打回待分派继续烧配额：
    [INFO] 失败回待分派重试: work=xy078 retry=1/3 退避=60s   ← 挂人工态被自动复活

根因：main.py 原 ``work.retry_count < max_r`` 重试分支只看 retry_count，
不消费 sidecar 的 ``awaiting_human``/``reject_budget_exhausted`` 标记。
修复：重试分支之前加「挂人工闸」——读 ``runtime_state.read_card_state``，
两标记任一为真 → 不转 TODO、不重试、保持打回态，日志含「保持待人工」。
语义对齐既有判例：熔断挂起=只许人审通道（redispatch-card.sh / transition API）
解冻，机器路径永不自愈。

用例：
1. 负向（挂人工卡 + worker 异常）→ 仍 REJECTED、retry_count 不增、日志含「保持待人工」；
2. 正向（未挂卡走原重试路径）→ 回待分派重试不回归。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from server.engine.main import _fail_retry_or_reject, clear_retry_backoff, retry_backoff_active
from server.engine.runtime_state import read_card_state, write_card_state
from server.engine.store import InMemoryBoardStore
from server.engine.task import State, Work


def _seed_work(store: InMemoryBoardStore, wid: str, state: State = State.RUNNING) -> Work:
    """seed 一张卡：默认执行中（worker 异常时 in-flight）；挂人工复现即打回终态。

    状态机契约 §2：待分派 → 打回 非法，须经执行中转跳（RUNNING 合法目标含 REJECTED）。
    """
    w = Work(id=wid, role="开发执行体", card_path=f"docs/dispatch/tst/{wid}.md")
    w.transition(State.RUNNING)
    if state is not State.RUNNING:
        w.transition(state, problems=["预置终态"])  # 打回必附问题清单
    store.seed(w)
    return w


def _log(caplog: pytest.LogCaptureFixture, text: str) -> list[str]:
    return [r.message for r in caplog.records if text in r.message]


class TestExhaustedCardNoRedispatch:
    """F1 挂人工闸：预算耗尽卡收到 worker 异常不得自动重派。"""

    def test_awaiting_human_card_keeps_rejected_no_redispatch(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """负向：sidecar awaiting_human=true + worker 异常 → 保持打回、不重试、日志「保持待人工」。"""
        store = InMemoryBoardStore()
        # 复现现场：卡已打回终态（REJECT 预算耗尽，待人工）
        w = _seed_work(store, "xy078", state=State.REJECTED)
        # 预算耗尽出口已写侧卡标记（main.py _write_reject_budget_markers 语义）
        write_card_state(
            tmp_path,
            "xy078",
            reject_budget_exhausted=True,
            awaiting_human=True,
            exhausted_class="business",
        )

        with caplog.at_level("ERROR", logger="ccc.engine"):
            retried = _fail_retry_or_reject(
                w, store, ["worker 异常: 非法状态转移: 打回 → 已回写"],
                {"EXECUTOR_MAX_RETRIES": "3"}, tmp_path,
            )

        assert retried is False  # 不转 TODO、不重试
        assert w.state is State.REJECTED  # 保持打回态
        assert w.retry_count == 0  # retry_count 不增
        assert _log(caplog, "保持待人工"), "日志应含「保持待人工」"
        # 挂人工标记未被机器路径改写（只许人审通道解冻）
        rt = read_card_state(tmp_path).get("xy078") or {}
        assert rt.get("awaiting_human") is True
        assert rt.get("reject_budget_exhausted") is True

    def test_reject_budget_exhausted_card_keeps_rejected(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """负向变体：reject_budget_exhausted=true（awaiting_human 已清）同样不重派。"""
        store = InMemoryBoardStore()
        w = _seed_work(store, "xy077", state=State.REJECTED)
        write_card_state(tmp_path, "xy077", reject_budget_exhausted=True)

        with caplog.at_level("ERROR", logger="ccc.engine"):
            retried = _fail_retry_or_reject(
                w, store, ["worker 异常: push 超时"], {"EXECUTOR_MAX_RETRIES": "3"}, tmp_path,
            )

        assert retried is False
        assert w.state is State.REJECTED
        assert w.retry_count == 0
        assert _log(caplog, "保持待人工")

    def test_normal_card_still_retries(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        """正向：未挂卡走原重试路径不回归（回待分派 + retry_count 递增 + 指数退避）。"""
        store = InMemoryBoardStore()
        w = _seed_work(store, "tst101")

        with caplog.at_level("INFO", logger="ccc.engine"):
            retried = _fail_retry_or_reject(
                w, store, ["测试失败"], {"EXECUTOR_MAX_RETRIES": "3"}, tmp_path,
            )

        try:
            assert retried is True  # 回待分派重试
            assert w.state is State.TODO
            assert w.retry_count == 1
            assert not _log(caplog, "保持待人工"), "正常卡不应命中挂人工闸"
            # 退避生效（防旋不回归）
            assert retry_backoff_active("tst101")
        finally:
            clear_retry_backoff("tst101")
