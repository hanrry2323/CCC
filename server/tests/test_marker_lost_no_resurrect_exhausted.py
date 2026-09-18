"""F6：「运行标记丢失自动重派」回收环不得复活已挂人工卡（2026-09-18）。

复现证据（2026-09-18 23:20–23:26，xy079）：外脑直写 ``awaiting_human=true`` 挂人工后，
下一心跳仍被复活重派——``reclaim_orphaned_running``（RUNNING 且 ``.running`` 缺失、
对应 log 最后修改超 60s → transition TODO 重派）不读 sidecar 挂人工标记。

根因：两闸门洞叠加——
1. F1 闸（``_fail_retry_or_reject`` 内）拦截后只 ``return False`` 不落显式态，卡保持
   RUNNING；``_run_auto_worker`` finally 清掉 ``.running`` 标记 → 逃逸窗口；
2. 回收环不查 sidecar，按「标记丢失 + 旧 log」判死回收。

修复：两闸共用 ``_card_awaiting_human`` helper（禁复制判定逻辑）——
回收环 transition TODO 之前查挂人工标记，真则不回收不重派；F1 闸拦截时同时把
work 落成显式打回态（对齐既有「打回」状态机用语，不新增状态）。

用例：
1. 负向（sidecar awaiting_human + RUNNING + 无 .running + log 超 60s）→ 不转 TODO、
   仍 RUNNING、回收计数 0、日志含「保持现状不回收」；
2. 正向（正常在途卡标记丢失）→ 仍走原回收路径回待分派，防回归；
3. F1 闸拦截时把 RUNNING 落成显式打回态（防 RUNNING+丢标记逃逸窗口）。
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from server.engine.main import (
    _card_awaiting_human,
    _fail_retry_or_reject,
    reclaim_orphaned_running,
)
from server.engine.runtime_state import read_card_state, write_card_state
from server.engine.store import InMemoryBoardStore
from server.engine.task import State, Work


def _log(caplog: pytest.LogCaptureFixture, text: str) -> list[str]:
    return [r.message for r in caplog.records if text in r.message]


def _aging_log(log_dir: Path, wid: str, age_s: int = 120) -> Path:
    """造一个最后修改时间超过回收阈值的日志文件（回收环要求 age>=60s 才判标记真丢）。"""
    log_path = log_dir / f"{wid}.log"
    log_path.write_text(f"{wid} worker session (marker lost)\n", encoding="utf-8")
    past = time.time() - age_s
    os.utime(log_path, (past, past))
    return log_path


class TestMarkerLostNoResurrect:
    """F6 回收环挂人工闸：挂人工卡标记丢失不得被自动重派复活。"""

    def test_awaiting_human_card_not_reclaimed_after_marker_loss(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """负向：awaiting_human + RUNNING + 无 .running（log 超 60s）→ 不转 TODO、日志「保持现状不回收」。"""
        store = InMemoryBoardStore()
        w = Work(id="xy079", role="开发执行体", state=State.RUNNING)
        store.seed(w)
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        # 复现现场：外脑直写挂人工标记，运行标记缺失，日志陈旧
        write_card_state(
            log_dir,
            "xy079",
            reject_budget_exhausted=True,
            awaiting_human=True,
            exhausted_class="business",
        )
        _aging_log(log_dir, "xy079")
        assert not (log_dir / "xy079.running").exists()

        with caplog.at_level("ERROR", logger="ccc.engine"):
            n = reclaim_orphaned_running(store, log_dir)

        assert n == 0  # 不回收、不重派
        assert w.state is State.RUNNING  # 保持现状，未转 TODO
        assert not store.list_work(state=State.TODO), "挂人工卡不得回待分派"
        assert _log(caplog, "保持现状不回收"), "日志应含「保持现状不回收」"
        # 挂人工标记未被机器路径改写（只许人审通道解冻）
        rt = read_card_state(log_dir).get("xy079") or {}
        assert rt.get("awaiting_human") is True
        assert rt.get("reject_budget_exhausted") is True

    def test_normal_inflight_card_still_reclaimed(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """正向：正常在途卡标记丢失仍走原回收路径（回待分派重派），防回归。"""
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
        assert _log(caplog, "回收缺失标记的孤儿执行中"), "正常在途卡应仍走原回收路径"
        assert not _log(caplog, "保持现状不回收"), "正常在途卡不应命中挂人工闸"

    def test_awaiting_helper_shared_by_both_gates(self, tmp_path: Path) -> None:
        """两闸共用判定 helper：无 log_dir / 无标记 / 单标记各情形返回一致语义。"""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        assert _card_awaiting_human(None, "any") is False  # 无 sidecar 根目录
        assert _card_awaiting_human(log_dir, "absent") is False  # 无标记
        write_card_state(log_dir, "only-budget", reject_budget_exhausted=True)
        assert _card_awaiting_human(log_dir, "only-budget") is True
        write_card_state(log_dir, "only-awaiting", awaiting_human=True)
        assert _card_awaiting_human(log_dir, "only-awaiting") is True
        write_card_state(log_dir, "negative", awaiting_human=False, reject_budget_exhausted=False)
        assert _card_awaiting_human(log_dir, "negative") is False


class TestGateLandsExplicitState:
    """F6 二：F1 闸拦截时把 work 落成显式打回态，杜绝 RUNNING+丢标记逃逸窗口。"""

    def test_gate_lands_rejected_from_running(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """RUNNING 的挂人工卡收到 worker 异常 → 落显式打回态，不再保持 RUNNING。"""
        store = InMemoryBoardStore()
        w = Work(id="xy079", role="开发执行体", state=State.RUNNING)
        store.seed(w)
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        write_card_state(log_dir, "xy079", awaiting_human=True, reject_budget_exhausted=True)

        with caplog.at_level("ERROR", logger="ccc.engine"):
            retried = _fail_retry_or_reject(
                w,
                store,
                ["worker 异常: push 超时"],
                {"EXECUTOR_MAX_RETRIES": "3"},
                log_dir,
            )

        assert retried is False
        assert w.state is State.REJECTED  # 显式打回态，杜绝 RUNNING+丢标记逃逸
        assert w.retry_count == 0  # 不消耗重试预算
        assert store.list_work(state=State.RUNNING) == []
        assert _log(caplog, "保持待人工")
        # save_work 写回的流程态不得吞掉挂人工标记（append-only 按字段合并）
        rt = read_card_state(log_dir).get("xy079") or {}
        assert rt.get("awaiting_human") is True
        assert rt.get("reject_budget_exhausted") is True

    def test_gate_idempotent_when_already_rejected(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """已在打回终态 → 闸内不重复转移（幂等），保持原问题清单语义。"""
        store = InMemoryBoardStore()
        w = Work(id="xy078", role="开发执行体", state=State.TODO)
        w.transition(State.RUNNING)
        w.transition(State.REJECTED, problems=["打回（预置）"])
        store.seed(w)
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        write_card_state(log_dir, "xy078", awaiting_human=True)

        with caplog.at_level("ERROR", logger="ccc.engine"):
            retried = _fail_retry_or_reject(
                w, store, ["worker 异常: 非法状态转移"], {"EXECUTOR_MAX_RETRIES": "3"}, log_dir,
            )

        assert retried is False
        assert w.state is State.REJECTED
