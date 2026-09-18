"""F5：派发路径不得清零 retry 预算——异常重试永动机（2026-09-18）。

复现证据（sidecar cards.jsonl 原文）：
    13:51:49Z {"id":"xy079","state":"待分派","retry_count":1,"reason":"退出码非 0: 64…"}
    13:53:45Z {"id":"xy079","state":"执行中","retry_count":0}   ← 派发把预算清零
    13:57:42Z {"id":"xy079","state":"待分派","retry_count":1,…64}
    13:59:42Z {"id":"xy079","state":"执行中","retry_count":0}   ← 再清零

根因：``_fail_retry_or_reject`` 重试分支写完 retry_count 后立刻
``clear_card_state`` → 追加 ``state=null``，而 ``read_card_state`` 遇 state=null
把该卡记录整体 pop（连 retry_count 一起失效）；下一轮派发 ``save_work`` 用
失效后的 0 预算重派 → 每次失败都从 0 起、3/3 上限永不触顶（rc=64 一轮 4-6 分钟，
无限烧执行窗）。
修复：重试分支不再 clear（预算继承）；打回出口维持 clear + 重写预算标记
（F1 挂人工闸依赖）。预算清零只留正式出口：成功收单进机审、
人审正规重派（transition API / redispatch-card.sh）。

用例：
1. 失败→retry=1→再派发：预算仍为 1，不被派发路径清零；
2. 连续失败至 max：终态=打回 + reject_budget_exhausted/awaiting_human，不再自动派发；
3. retry 跨派发递增 1→2→3 无归零；
4. 正向：正规人审重派（transition 写 retry_count=0）预算清零不回归。
"""

from __future__ import annotations

from pathlib import Path

from server.engine import main as engine_main
from server.engine.runtime_state import clear_card_state, read_card_state, write_card_state
from server.engine.store import InMemoryBoardStore
from server.engine.task import State, Work


MAX_R = 3


def _cfg(tmp_path: Path) -> dict[str, str]:
    return {
        "EXECUTOR_LOG_DIR": str(tmp_path / "logs"),
        "EXECUTOR_MAX_RETRIES": str(MAX_R),
        "EXECUTOR_RETRY_BACKOFF_SECONDS": "1",
    }


def _log(tmp_path: Path) -> Path:
    return tmp_path / "logs"


def _seed(store: InMemoryBoardStore, wid: str, retry: int = 0) -> Work:
    """seed 一张执行中卡（worker 异常时的 in-flight 态）。"""
    w = Work(id=wid, role="开发执行体", card_path=f"docs/dispatch/tst/{wid}.md")
    w.transition(State.RUNNING)
    w.retry_count = retry
    store.seed(w)
    return w


def _fail(w: Work, store: InMemoryBoardStore, tmp_path: Path) -> bool:
    """模拟一轮执行失败 → _fail_retry_or_reject（rc=64 现场）。"""
    return engine_main._fail_retry_or_reject(
        w, store, ["退出码非 0: 64"], _cfg(tmp_path), _log(tmp_path)
    )


def _dispatch_cycle(w: Work, store: InMemoryBoardStore, tmp_path: Path) -> None:
    """模拟下一轮派发：回待分派 → 占槽标执行中 → save_work 持久化 sidecar。

    真实派发路径（run_once 的 submit gate）就是 transition(RUNNING) + store.save_work；
    有 log_dir 时 FileBoardStore.save_work 写 sidecar（state=执行中 + retry_count）。
    本函数复现该持久化语义，用 stub pool 避免真实线程回写竞态。
    """
    w.transition(State.RUNNING)
    store.save_work(w)
    write_card_state(_log(tmp_path), w.id, state=w.state.value, retry_count=w.retry_count)


def _sidecar_retry(tmp_path: Path, wid: str) -> int:
    """读 sidecar 该卡当前 retry_count（字段合并后的真值，派发时的输入）。"""
    return int((read_card_state(_log(tmp_path)).get(wid) or {}).get("retry_count") or 0)


def _sidecar_state(tmp_path: Path, wid: str) -> object:
    return (read_card_state(_log(tmp_path)).get(wid) or {}).get("state")


def _run_to_exhaustion(tmp_path: Path, wid: str = "xy079") -> tuple[InMemoryBoardStore, Work]:
    """驱动一张卡到预算触顶：MAX_R 次失败回待分派，第 MAX_R+1 次失败打回。

    每次失败后走一轮派发（预算继承），最后断言 retry 单调递增无归零。
    """
    store = InMemoryBoardStore()
    w = _seed(store, wid, retry=0)
    for expected in range(1, MAX_R + 1):
        assert _fail(w, store, tmp_path) is True, f"第 {expected} 次失败应回待分派重试"
        assert w.retry_count == expected, f"retry 应为 {expected}，实际 {w.retry_count}"
        assert _sidecar_retry(tmp_path, wid) == expected, "sidecar 应保留递增后的 retry"
        _dispatch_cycle(w, store, tmp_path)  # 再派发：预算不得被清零
        assert _sidecar_retry(tmp_path, wid) == expected, "派发路径不得清零 retry_count"
    # 达上限：retry_count == MAX_R，判定不再满足 retry_count < max_r → 打回
    assert _fail(w, store, tmp_path) is False, "第 MAX_R+1 次失败应打回"
    assert w.state is State.REJECTED
    return store, w


def _run_to_reject_once(tmp_path: Path, store: InMemoryBoardStore, w: Work) -> None:
    """run_once 语义的事件线：

    一张 RUNNING 卡失败 → 回待分派（retry++）→ 再派发占槽 → 失败 → … → 达上限打回。
    返回时 work 处于 REJECTED 终态。
    """
    for _ in range(MAX_R + 1):
        if _fail(w, store, tmp_path):
            # 回待分派 → 走一轮派发占槽（预算继承）
            w.transition(State.RUNNING)
            continue
        break
    else:
        raise AssertionError(f"{w.id} 未能在 MAX_R+1 次失败内打回")
    assert w.state is State.REJECTED


def _accumulate_business_rejects(tmp_path: Path, wid: str, target: int) -> Work:
    """驱动 business reject 预算到 target：每轮「打回 → 人审重派（清零重试预算）」。

    返回最新一张 RUNNING 卡（供下一轮失败触发）。
    """
    store = InMemoryBoardStore()
    w = _seed(store, wid, retry=0)
    for reject_n in range(1, target):
        _run_to_reject_once(tmp_path, store, w)
        # 人审重派：清重试预算，保留 business 计数递增（真实 transition 语义）
        clear_card_state(_log(tmp_path), wid)
        write_card_state(
            _log(tmp_path), wid, state="待分派", retry_count=0,
            reject_count=reject_n, business_reject_count=reject_n,
            reject_budget_exhausted=False,
        )
        w = _seed(store, wid, retry=0)
    return w


class TestRetryBudgetSurvivesRedispatch:
    """F5 core：派发不得清零 retry 预算。"""

    def test_failure_preserves_retry_in_sidecar(self, tmp_path: Path) -> None:
        """失败→retry=1：sidecar 仍含 retry_count=1（F5 根因修复——重试出口不再 clear）。"""
        store = InMemoryBoardStore()
        w = _seed(store, "xy079", retry=0)
        assert _fail(w, store, tmp_path) is True
        assert w.retry_count == 1
        # 关键断言：重试出口不再 clear → 记录保留 retry_count（F5 根因）
        rec = read_card_state(_log(tmp_path)).get("xy079") or {}
        assert rec.get("retry_count") == 1, rec

    def test_redispatch_keeps_budget(self, tmp_path: Path) -> None:
        """失败→retry=1→再派发：预算仍为 1，不会被派发路径清零（同族病灶第四例）。"""
        store = InMemoryBoardStore()
        w = _seed(store, "xy080", retry=0)
        assert _fail(w, store, tmp_path) is True
        assert _sidecar_retry(tmp_path, "xy080") == 1, "重试出口应保留 retry=1"
        _dispatch_cycle(w, store, tmp_path)
        # 派发路径写入「执行中」时预算继承（此前此行为 0，导致 3/3 永不触顶）
        assert _sidecar_retry(tmp_path, "xy080") == 1, "派发路径不得清零 retry_count"
        assert _sidecar_state(tmp_path, "xy080") == "执行中"

    def test_retry_increments_across_dispatches(self, tmp_path: Path) -> None:
        """连续失败：retry 跨派发递增 1→2→3 无归零，达上限打回不再自动派发。"""
        store, w = _run_to_exhaustion(tmp_path)
        assert w.retry_count == MAX_R
        assert w.state is State.REJECTED
        # 打回终态：sidecar 流程态失效（null），无残留可再派的待分派态
        assert _sidecar_state(tmp_path, "xy079") is None, "打回终态不得残留流程态"

    def test_budget_exhausted_marks_awaiting_human(self, tmp_path: Path) -> None:
        """business reject 预算触顶 → 终态=打回 + reject_budget_exhausted/awaiting_human。

        business reject 预算与 retry 预算分离：3 次「打回」（每次 reject_count+1，
        其间人审重派清零 retry）才触顶挂人工。
        """
        # 驱动到第 2 次 reject（bill=2，未耗尽）→ 第 3 次打回触顶挂人工
        w = _accumulate_business_rejects(tmp_path, "xy082", target=3)
        # 第 3 次打回 → reject_budget_exhausted + awaiting_human
        store = InMemoryBoardStore()
        store.seed(w)
        _run_to_reject_once(tmp_path, store, w)
        rec = read_card_state(_log(tmp_path)).get("xy082") or {}
        assert w.state is State.REJECTED
        assert rec.get("reject_budget_exhausted") is True, rec
        assert rec.get("awaiting_human") is True, rec
        # 挂人工闸：再派 worker 异常不得重派（机器永不自愈）
        assert engine_main._fail_retry_or_reject(
            w, store, ["worker 异常: 再失败"], _cfg(tmp_path), _log(tmp_path)
        ) is False, "挂人工卡不得被机器重派"

    def test_manual_redispatch_resets_budget(self, tmp_path: Path) -> None:
        """正向：正规人审重派（transition 写 retry_count=0）预算清零不回归。"""
        # 先跑满重试到打回（retry 触顶），模拟 xy079 现场
        _, w = _run_to_exhaustion(tmp_path, wid="xy083")
        assert w.state is State.REJECTED
        assert w.retry_count == MAX_R, "打回前 retry 应为 MAX_R"
        # 人审重派：web transition 语义（clear + 写 state=待分派, retry_count=0 + 预算归零）
        clear_card_state(_log(tmp_path), "xy083")
        write_card_state(
            _log(tmp_path),
            "xy083",
            state="待分派",
            retry_count=0,
            reject_count=0,
            reject_budget_exhausted=False,
            business_reject_count=0,
            protocol_retry_count=0,
            awaiting_human=False,
            redispatch="2026-09-18T00:00:00Z",
        )
        rec = read_card_state(_log(tmp_path)).get("xy083") or {}
        assert rec.get("retry_count") == 0, "人审重派后预算应清零"
        assert rec.get("state") == "待分派"
        assert rec.get("awaiting_human") is False
        assert rec.get("reject_budget_exhausted") is False
