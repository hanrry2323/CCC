"""测试 C 调度韧性（指数退避、连续失败熔断、成功清零与配置熔断阈值）。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from server.engine.task import State, Work
from server.engine.dispatch import ExecutorRegistry, ExecutorEntry
from server.engine.store import InMemoryBoardStore
from server.engine.main import _hold_infra_failure, _run_auto_worker


def test_exponential_backoff(tmp_path: Path):
    """测试指数退避冷却时间计算以及封顶：
    strikes=1 -> 60s
    strikes=2 -> 120s
    strikes=3 -> 240s
    strikes=4 -> 480s
    strikes=6 -> 封顶 1800s
    """
    store = InMemoryBoardStore()
    work = Work(id="xy999", role="开发执行体", state=State.RUNNING, card_path="/tmp/xy999.md")
    store.seed(work)

    cfg = {
        "EXECUTOR_INFRA_COOLDOWN_SECONDS": "60",
        "EXECUTOR_INFRA_COOLDOWN_MAX_SECONDS": "1800"
    }

    # strikes=1
    with patch("server.engine.runtime_state.write_card_state") as mock_write:
        _hold_infra_failure(store, work, tmp_path, ["502 bad gateway"], cfg, phase="run", infra_count=1)
        args, kwargs = mock_write.call_args
        until_dt = datetime.fromisoformat(kwargs["infra_cooldown_until"].replace("Z", "+00:00"))
        diff = (until_dt - datetime.now(timezone.utc)).total_seconds()
        assert 50 <= diff <= 70

    # strikes=2
    with patch("server.engine.runtime_state.write_card_state") as mock_write:
        _hold_infra_failure(store, work, tmp_path, ["502 bad gateway"], cfg, phase="run", infra_count=2)
        args, kwargs = mock_write.call_args
        until_dt = datetime.fromisoformat(kwargs["infra_cooldown_until"].replace("Z", "+00:00"))
        diff = (until_dt - datetime.now(timezone.utc)).total_seconds()
        assert 110 <= diff <= 130

    # strikes=3
    with patch("server.engine.runtime_state.write_card_state") as mock_write:
        _hold_infra_failure(store, work, tmp_path, ["502 bad gateway"], cfg, phase="run", infra_count=3)
        args, kwargs = mock_write.call_args
        until_dt = datetime.fromisoformat(kwargs["infra_cooldown_until"].replace("Z", "+00:00"))
        diff = (until_dt - datetime.now(timezone.utc)).total_seconds()
        assert 230 <= diff <= 250

    # strikes=4
    with patch("server.engine.runtime_state.write_card_state") as mock_write:
        _hold_infra_failure(store, work, tmp_path, ["502 bad gateway"], cfg, phase="run", infra_count=4)
        args, kwargs = mock_write.call_args
        until_dt = datetime.fromisoformat(kwargs["infra_cooldown_until"].replace("Z", "+00:00"))
        diff = (until_dt - datetime.now(timezone.utc)).total_seconds()
        assert 470 <= diff <= 490

    # strikes=6 (exceeds max 1800 cap)
    with patch("server.engine.runtime_state.write_card_state") as mock_write:
        _hold_infra_failure(store, work, tmp_path, ["502 bad gateway"], cfg, phase="run", infra_count=6)
        args, kwargs = mock_write.call_args
        until_dt = datetime.fromisoformat(kwargs["infra_cooldown_until"].replace("Z", "+00:00"))
        diff = (until_dt - datetime.now(timezone.utc)).total_seconds()
        assert 1790 <= diff <= 1810


def test_run_stage_infra_continuous_failure_and_melt_down(tmp_path: Path):
    """测试 RUN 阶段连续 5 次基础设施失败触发熔断强制打回：
    1. 前 4 次失败：回 State.TODO，写 sidecar 冷却
    2. 第 5 次失败：触发熔断，状态变为 State.REJECTED 强行打回
    3. problems 携带「连续失败」和「强制打回」标记
    """
    store = InMemoryBoardStore()
    work = Work(id="xy101", role="开发执行体", state=State.RUNNING, card_path="/tmp/xy101.md")
    store.seed(work)

    entry = ExecutorEntry(role="开发执行体", category="可后台 CLI", binding="demo", note="test", command="echo")
    reg = ExecutorRegistry((entry,))

    cfg = {
        "EXECUTOR_INFRA_MAX_STRIKES": "5",
        "EXECUTOR_INFRA_COOLDOWN_SECONDS": "60",
        "EXECUTOR_INFRA_COOLDOWN_MAX_SECONDS": "1800"
    }

    # 1. 模拟前 4 次失败（每次 sidecar 的 infra_count 会依次增加）
    for strike in range(0, 4):
        # 每次重置状态为 RUNNING 以确保转换合法
        work.state = State.RUNNING
        with patch("server.engine.main._dispatch_and_collect", return_value=(False, ["503 Service Unavailable"])), \
             patch("server.engine.main.is_retryable_failure", return_value=(True, "503 Service Unavailable")), \
             patch("server.engine.runtime_state.read_card_state", return_value={"xy101": {"infra_count": strike}}), \
             patch("server.engine.runtime_state.write_card_state") as mock_write:

             outcome = _run_auto_worker(work, reg, store, cfg, tmp_path, timeout=30)
             assert outcome.get("infra") == 1
             assert work.state == State.TODO  # 回待分派冷却中
             assert mock_write.call_args[1]["infra_count"] == strike + 1

    # 2. 模拟第 5 次失败，应该熔断打回
    work.state = State.RUNNING
    with patch("server.engine.main._dispatch_and_collect", return_value=(False, ["503 Service Unavailable"])), \
             patch("server.engine.main.is_retryable_failure", return_value=(True, "503 Service Unavailable")), \
             patch("server.engine.runtime_state.read_card_state", return_value={"xy101": {"infra_count": 4}}), \
             patch("server.engine.runtime_state.write_card_state") as mock_write:

         outcome = _run_auto_worker(work, reg, store, cfg, tmp_path, timeout=30)
         assert "infra" not in outcome
         assert work.state == State.REJECTED  # 强制打回！

         # 验证 problems 标记
         assert any("连续失败" in p and "强制打回" in p for p in work.problems)
         # sidecar 契约（ccc-plan-021）：熔断打回出口 clear sidecar，磁盘终态权威
         args = mock_write.call_args
         assert args is None  # 熔断出口不再写 write_card_state（改为 clear）


def test_run_success_clears_infra_count(tmp_path: Path):
    """测试收单成功时，sidecar 中的 infra_count 被清零。"""
    store = InMemoryBoardStore()
    work = Work(id="xy102", role="开发执行体", state=State.RUNNING, card_path="/tmp/xy102.md")
    store.seed(work)

    entry = ExecutorEntry(role="开发执行体", category="可后台 CLI", binding="demo", note="test", command="echo")
    reg = ExecutorRegistry((entry,))

    with patch("server.engine.main._dispatch_and_collect", return_value=(True, [])), \
         patch("server.engine.runtime_state.clear_card_state") as mock_clear:

         outcome = _run_auto_worker(work, reg, store, {}, tmp_path, timeout=30)
         assert outcome["collected"] == 1
         assert work.state == State.DONE

         # sidecar 契约（ccc-plan-021）：成功出口 clear sidecar，不写 infra_count=0
         mock_clear.assert_called_once()
         args = mock_clear.call_args
         assert "xy102" in str(args)
