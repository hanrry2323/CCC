"""ccc089：审计 infra 冷却重审「~76s 循环」复现（加速形态）。

复现命题（候选 b 证实）：机审 dispatch 在拉起会话**之前**早退（如 worktree
创建失败）时——
1. 每轮机审仍经 ``_run_machine_audit_after_writeback`` 的 infra 出口追加一条
   ``record_audit(kind="infra")`` 台账行；
2. ``{id}.audit.log`` 全程未被创建/改写（静态）——早退点在日志句柄打开之前；
3. 无任何子进程会话启动痕迹（无 launch event、无 child marker 刷新）；
4. 冷却到期判定放行后循环复发：冷却只是延迟器，不消除根因（加速形态下稳定重现）。

夹具走真实代码路径：仅令 ``git worktree add`` 真实失败（目标父目录是文件），
不 mock dispatch/记账/冷却任何一环。
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from server.engine.dispatch import ExecutorEntry, ExecutorRegistry
from server.engine.main import _infra_cooldown_active, _run_audit_worker
from server.engine.runtime_state import read_card_state, write_card_state
from server.engine.store import InMemoryBoardStore
from server.engine.task import State, Work

CARD_TEXT = """# 任务卡 ccc999 · ccc089 复现夹具

> 状态：已回写 · 项目：ccc · 执行体：DSH

## 目标

（ccc089 复现夹具卡，非真实任务）
"""


def _ledger_rows(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class Env:
    """复现环境句柄。"""

    def __init__(self, tmp_path: Path, cooldown_seconds: str) -> None:
        self.tmp_path = tmp_path
        self.ledger = tmp_path / "audit-ledger.jsonl"
        self.log_dir = tmp_path / "logs"
        self.log_dir.mkdir(parents=True)
        card_dir = tmp_path / "docs" / "dispatch"
        card_dir.mkdir(parents=True)
        self.card = card_dir / "ccc999-infra-loop.md"
        self.card.write_text(CARD_TEXT, encoding="utf-8")
        # 必败 worktree_base：目标父目录是普通文件 → git worktree add 真实失败。
        blocker = tmp_path / "blocker.txt"
        blocker.write_text("not a directory", encoding="utf-8")
        acceptor = ExecutorEntry(
            role="验收席",
            category="可后台 CLI",
            binding="Auditor",
            note="ccc089 复现夹具验收席",
            command="echo",
            worktree_base=str(blocker / "wt"),
        )
        self.registry = ExecutorRegistry((acceptor,))
        self.work = Work(id="ccc999", role="开发执行体", state=State.DONE, card_path=str(self.card))
        self.store = InMemoryBoardStore()
        self.store.seed(self.work)
        self.cfg = {
            "DATA_DIR": str(tmp_path / "data"),
            "EXECUTOR_INFRA_COOLDOWN_SECONDS": cooldown_seconds,
            "EXECUTOR_INFRA_COOLDOWN_MAX_SECONDS": "1800",
            # 放宽熔断上限以便观察多轮循环（生产默认 5 次会转待分派人工跟进）。
            "EXECUTOR_INFRA_MAX_STRIKES": "50",
        }

    def audit_log(self) -> Path:
        return self.log_dir / "ccc999.audit.log"

    def infra_rows(self) -> list[dict]:
        return [r for r in _ledger_rows(self.ledger) if r.get("kind") == "infra"]

    def run_worker_once(self) -> dict[str, int]:
        return _run_audit_worker(
            self.work,
            self.registry,
            self.store,
            self.cfg,
            self.log_dir,
            timeout=30,
        )


@pytest.fixture()
def fast_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Env:
    """加速形态：冷却 0s（立即到期），等价于把 76s 节奏压缩到连续轮次。"""
    env = Env(tmp_path, cooldown_seconds="0")
    monkeypatch.setenv("CCC_AUDIT_LEDGER", str(env.ledger))
    return env


@pytest.fixture()
def prod_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Env:
    """生产默认冷却 60s 形态（验证 ~76s ≈ 60s 冷却 + 扫描周期的节奏来源）。"""
    env = Env(tmp_path, cooldown_seconds="60")
    monkeypatch.setenv("CCC_AUDIT_LEDGER", str(env.ledger))
    return env


def test_infra_recorded_without_session_launch(fast_env: Env) -> None:
    """单轮：dispatch 拉起前早退仍记 infra 账，audit.log 静态、无会话痕迹。"""
    env = fast_env
    outcome = env.run_worker_once()

    # 1. infra 记账发生且恰一条
    rows = env.infra_rows()
    assert len(rows) == 1, f"期望恰 1 条 infra 行，实际 {len(rows)}"
    row = rows[0]
    assert row["conclusion"] == "不通过"
    assert row["source"] == "engine"
    assert "基础设施" in (row["reasons"] or [""])[0], row["reasons"]

    # 2. audit.log 从未被创建（静态）——早退点在日志句柄打开之前
    assert not env.audit_log().exists(), "audit.log 不应被创建（无会话启动）"

    # 3. worker 口径为 infra（进冷却分支，不打回、不算业务失败）
    assert outcome.get("infra") == 1, outcome
    assert outcome.get("failed") == 0 and outcome.get("collected") == 0
    # 卡保持已回写（phase=audit 冷却语义）
    assert env.work.state is State.DONE

    # 4. sidecar 记录冷却临时态与 strikes=1
    rt = read_card_state(env.log_dir).get("ccc999") or {}
    assert int(rt.get("infra_count") or 0) == 1
    assert rt.get("infra_cooldown_until")


def test_infra_loop_repeats_each_cooldown_expiry(fast_env: Env) -> None:
    """循环复现（加速形态）：每轮冷却到期重审评估都再追加一条 infra 行。

    即 ccc081「ledger 以固定节奏重复追加 infra 行」的机制本体：记账每轮 +1、
    audit.log 始终静态、会话从未拉起。默认 max_strikes=5 时循环被熔断打断
    （转待分派人工跟进）；本测试放宽至上限以观察持续循环形态。
    """
    env = fast_env
    rounds = 4
    for i in range(1, rounds + 1):
        outcome = env.run_worker_once()
        rows = env.infra_rows()
        assert len(rows) == i, f"第 {i} 轮后期望 {i} 条 infra 行，实际 {len(rows)}"
        assert outcome.get("infra") == 1, f"第 {i} 轮 outcome={outcome}"
        assert not env.audit_log().exists(), f"第 {i} 轮 audit.log 仍不应存在"
        assert env.work.state is State.DONE, f"第 {i} 轮卡应保持已回写"

    # 每条 infra 行 reason 一致（同一根因反复记账），ts 单调递增
    reasons = {r["reasons"][0] for r in env.infra_rows()}
    assert len(reasons) == 1
    ts_list = [datetime.fromisoformat(r["ts"].replace("Z", "+00:00")) for r in env.infra_rows()]
    assert ts_list == sorted(ts_list)


def test_cooldown_gate_delays_then_releases(prod_env: Env) -> None:
    """76s 型节奏来源：60s 冷却内门禁拦卡，到期判定放行即复发第二条。"""
    env = prod_env
    t0 = datetime.now(timezone.utc)
    env.run_worker_once()
    assert len(env.infra_rows()) == 1

    rt = read_card_state(env.log_dir).get("ccc999") or {}
    until = datetime.fromisoformat((rt.get("infra_cooldown_until") or "").replace("Z", "+00:00"))
    delta = (until - t0).total_seconds()
    assert 50 <= delta <= 70, f"首轮冷却应≈60s（指数退避基数），实测 {delta}s"

    # 冷却期内：_audit_round 门禁（main.py infra_cooldown gate）判定拦截
    # （_infra_cooldown_active 第一参为全量 runtime dict：{card_id: rec}）
    assert _infra_cooldown_active({"ccc999": rt}, "ccc999", now_ts=t0.timestamp() + 10)

    # 模拟冷却到期（真实时间推进的等价操作：sidecar until 回拨到过去）
    expired = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(
        timespec="seconds"
    ).replace("+00:00", "Z")
    write_card_state(env.log_dir, "ccc999", infra_cooldown_until=expired)
    rt2 = read_card_state(env.log_dir).get("ccc999") or {}
    assert not _infra_cooldown_active({"ccc999": rt2}, "ccc999")

    # 到期 → 重审评估放行 → 同一根因再次记账（第 2 条 infra 行，audit.log 仍静态）
    env.run_worker_once()
    assert len(env.infra_rows()) == 2
    assert not env.audit_log().exists()


def test_max_strikes_breaks_loop_to_todo(fast_env: Env) -> None:
    """熔断边界：strikes 达 EXECUTOR_INFRA_MAX_STRIKES 后不再冷却续跑（回待分派）。

    注意时序：infra 记账发生在 ``_run_machine_audit_after_writeback`` 内部，
    先于 worker 的 strikes 判定——故达上限那一轮本身也已记账（第 3 条）。
    真实引擎经 ``_audit_round`` 只挑 DONE 卡进机审队列，卡转待分派后循环收敛；
    若生产观察到 DONE 卡 infra 行无限持续，即为本卡定位的循环本体。
    """
    env = fast_env
    env.cfg["EXECUTOR_INFRA_MAX_STRIKES"] = "3"
    outcomes = [env.run_worker_once() for _ in range(3)]
    # 前 2 次：冷却续跑（infra=1）；第 3 次 next_strikes>=3 → 转 TODO 不再冷却
    assert outcomes[0].get("infra") == 1
    assert outcomes[1].get("infra") == 1
    assert outcomes[2].get("failed") == 1, outcomes[2]
    assert env.work.state is State.TODO
    # 达上限轮已记账（记账先于 strikes 判定）：3 轮共 3 条
    assert len(env.infra_rows()) == 3
    # 收敛边界：DONE 卡已不在队列——真实引擎的 _audit_round 只挑 DONE 卡，
    # 故卡转待分派后不会再进机审队列（循环就此收敛）
    assert env.store.list_work(state=State.DONE) == []
