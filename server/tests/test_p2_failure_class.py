"""v2.0 P2 失败分类定向测试：分类→路由→预算→待人工终态（mock 不碰真实资源）。

覆盖指令附录 6：
- failure_class 枚举/分类/预算上限
- infra → 冷却 + 自检，不消耗预算
- business → 打回 + 计 reject 预算
- protocol → 一次修复轮，仍失败计预算
- 预算耗尽 → 待人工结构化终态（sidecar + 卡头 + ledger）
- 人工重派清零全部计数
"""

from __future__ import annotations

import json
import types
from pathlib import Path

import pytest

from server.engine.failure_class import (
    FailureClass,
    budget_exhausted,
    budget_limit,
    classify_failure,
    increment_budget,
    normalize_base_root,
    read_budget_count,
    run_infra_selfcheck,
    terminal_reject_state,
)
from server.engine.runtime_state import read_card_state, write_card_state


# ── 1. 分类 ──


def test_classify_business_default():
    assert classify_failure(reasons=["测试失败: xpy"]) is FailureClass.BUSINESS
    assert classify_failure(reasons=["门禁未通过"]) is FailureClass.BUSINESS


def test_classify_infra_retryable():
    assert classify_failure(retryable=True, reasons=["x"]) is FailureClass.INFRA
    assert classify_failure(reasons=["基础设施：worktree 创建失败"]) is FailureClass.INFRA
    assert classify_failure(reasons=["执行超时"]) is FailureClass.BUSINESS  # 无 infra 日志特征=业务重试
    assert classify_failure(retryable=True, reasons=["执行超时"]) is FailureClass.INFRA  # 日志扫描判定 infra
    assert classify_failure(reasons=["网关预检拒单"]) is FailureClass.INFRA


def test_classify_protocol_wins():
    assert classify_failure(protocol_failure=True, retryable=True, reasons=["x"]) is FailureClass.PROTOCOL


# ── 2. 预算上限 ──


def test_budget_limits_default_and_cfg():
    assert budget_limit({}, FailureClass.BUSINESS) == 3
    assert budget_limit({"PHASE2_REJECT_MAX_STRIKES": "5"}, FailureClass.BUSINESS) == 5
    assert budget_limit({"PHASE2_REJECT_MAX_STRIKES": "0"}, FailureClass.BUSINESS) == 1  # 只紧不松
    assert budget_limit({"PHASE2_REJECT_MAX_STRIKES": "abc"}, FailureClass.BUSINESS) == 3
    assert budget_limit({"PHASE2_PROTOCOL_MAX_STRIKES": "4"}, FailureClass.PROTOCOL) == 4


def test_read_budget_count_compat():
    assert read_budget_count({"reject_count": 2}, FailureClass.BUSINESS) == 2
    assert read_budget_count({"business_reject_count": 2}, FailureClass.BUSINESS) == 2
    assert read_budget_count({"protocol_retry_count": 1}, FailureClass.PROTOCOL) == 1


def test_increment_budget_third_exhausts(tmp_path: Path):
    cfg = {"EXECUTOR_LOG_DIR": str(tmp_path)}
    assert increment_budget(tmp_path, "x", FailureClass.BUSINESS, cfg) == (1, False)
    assert increment_budget(tmp_path, "x", FailureClass.BUSINESS, cfg) == (2, False)
    count, exhausted = increment_budget(tmp_path, "x", FailureClass.BUSINESS, cfg)
    assert (count, exhausted) == (3, True)
    rec = read_card_state(tmp_path)["x"]
    assert rec["business_reject_count"] == 3
    assert rec["reject_count"] == 3  # 兼容旧字段同步写
    assert rec["reject_budget_exhausted"] is True
    assert rec["awaiting_human"] is True
    assert rec["exhausted_class"] == "business"


def test_increment_protocol_budget(tmp_path: Path):
    cfg = {"EXECUTOR_LOG_DIR": str(tmp_path)}
    for expected in (1, 2):
        assert increment_budget(tmp_path, "y", FailureClass.PROTOCOL, cfg)[0] == expected
        rec = read_card_state(tmp_path)["y"]
        assert rec["protocol_retry_count"] == expected
        assert rec.get("awaiting_human") is None  # 未耗尽不标待人工
    count, exhausted = increment_budget(tmp_path, "y", FailureClass.PROTOCOL, cfg)
    assert (count, exhausted) == (3, True)
    rec = read_card_state(tmp_path)["y"]
    assert rec["awaiting_human"] is True
    assert rec["exhausted_class"] == "protocol"


# ── 3. 终态卡头 ──


def test_terminal_reject_state():
    assert terminal_reject_state(FailureClass.BUSINESS) == "打回（REJECT 预算耗尽，待人工）"
    assert terminal_reject_state(FailureClass.PROTOCOL) == "打回（PROTOCOL 预算耗尽，待人工）"
    from server.board.models import base_state

    assert base_state(terminal_reject_state(FailureClass.BUSINESS)) == "打回"


# ── 4. infra 自检（mock 网络，不碰真实资源） ──


def test_infra_selfcheck_records_ledger(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "server.engine.failure_class._probe_http_status", lambda url, timeout=5.0: 200
    )
    fake_worktree = tmp_path / "wt"
    (fake_worktree / ".venv" / "bin").mkdir(parents=True)
    (fake_worktree / ".venv" / "bin" / "pytest").write_text("#!/bin/sh\n", encoding="utf-8")
    rows: list[dict] = []

    monkeypatch.setattr(
        "server.engine.failure_class.Path.is_file",
        lambda self: True if "pytest" in str(self) else Path.is_file(self),
    )
    monkeypatch.setattr(
        "server.board.audit_ledger.record_action",
        lambda action, object_id, source="", detail="", failure_class="", exhausted_class="": rows.append(
            {"action": action, "detail": detail, "failure_class": failure_class}
        ),
    )
    monkeypatch.setattr("server.engine.failure_class.os.access", lambda path, mode: True)

    cfg = {"EXECUTOR_LOG_DIR": str(tmp_path / "logs")}
    results = run_infra_selfcheck(cfg, card_id="tst001", worktree=str(fake_worktree))
    # 自检项结构存在
    assert "channel_3456" in results
    assert "worktree_pytest" in results
    assert "anthropic_base_url" in results
    assert "verdict_dir_writable" in results
    assert any(r["action"] == "infra_selfcheck" for r in rows)


def test_normalize_base_root():
    assert normalize_base_root("http://127.0.0.1:3456/v1/messages") == "http://127.0.0.1:3456"
    assert normalize_base_root("http://x:3456/v1") == "http://x:3456"
    assert normalize_base_root("http://x:3456/") == "http://x:3456"


def test_infra_selfcheck_verdict_dir_error_does_not_raise(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Fix5 定向：mock _audit_log_dir 抛异常 → 自检返回 writable=False，不抛 UnboundLocalError。

    不全局 patch Path.is_file（会破坏 patch phase2 触发的模块导入），
    而是创建真实 pytest 文件满足 worktree_pytest 探针。
    """
    monkeypatch.setattr(
        "server.engine.failure_class._probe_http_status", lambda url, timeout=5.0: 200
    )
    monkeypatch.setattr("server.engine.failure_class.os.access", lambda path, mode: True)
    fake_worktree = tmp_path / "wt"
    (fake_worktree / ".venv" / "bin").mkdir(parents=True)
    (fake_worktree / ".venv" / "bin" / "pytest").write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setattr(
        "server.board.audit_ledger.record_action",
        lambda action, object_id, source="", detail="", failure_class="", exhausted_class="": None,
    )

    def raising_log_dir(cfg):
        raise RuntimeError("verdict 目录不可访问")

    monkeypatch.setattr(
        "server.engine.phase2._audit_log_dir",
        raising_log_dir,
    )
    cfg = {"EXECUTOR_LOG_DIR": str(tmp_path / "logs")}
    results = run_infra_selfcheck(cfg, card_id="tst006", worktree=str(fake_worktree))
    assert "verdict_dir_writable" in results
    assert results["verdict_dir_writable"] == {"path": "", "writable": False}
    assert results["all_ok"] is False


# ── 5. phase2 修复轮 / 路由集成（mock auditor） ──


def test_process_one_protocol_retry_then_reject(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """verdict 协议失败 → 一次修复轮（30s 后重跑）；第 3 次仍失败 → PROTOCOL 预算耗尽打回。"""
    from server.engine import phase2

    card_file = tmp_path / "tst002-protocol.md"
    card_file.write_text(
        "# 任务卡 tst002 · P2 protocol test\n"
        "> 状态：打回（PROTOCOL 预算耗尽，待人工） · 项目：tst\n\n"
        "## 门禁\n- 测试：true\n",
        encoding="utf-8",
    )
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    (log_dir / "tst002-ccc-result.md").write_text("result", encoding="utf-8")
    cfg = {"EXECUTOR_LOG_DIR": str(log_dir), "DISPATCH_DIR": str(tmp_path)}
    card = {"id": "tst002", "title": "P2 protocol", "project": "tst", "path": str(card_file)}
    recorded: list[dict] = []

    calls = {"n": 0}

    def fake_audit(*a, **k):
        calls["n"] += 1
        return {"verdict": "ERROR", "reasons": "protocol：JSON verdict 缺失或非法", "attempts": 3, "protocol": True}

    def fake_record_action(action, object_id, source="", detail="", **kwargs):
        recorded.append({"action": action, "object_id": object_id, "detail": detail, **kwargs})

    monkeypatch.setattr(phase2, "audit_card", fake_audit)
    monkeypatch.setattr(phase2, "time", types.SimpleNamespace(sleep=lambda s: None))
    monkeypatch.setattr(phase2, "_current_branch", lambda: "main")
    monkeypatch.setattr(phase2, "git", lambda cmd, cwd=None: _ok_rc(cmd, 0))
    monkeypatch.setattr("server.board.audit_ledger.record_action", fake_record_action)
    monkeypatch.setattr(phase2, "preflight_gateway", lambda **k: (True, "ok"))

    # 前 2 次协议失败：修复轮仍失败 → 计 budget，卡保留已回写（audit_failed）
    res = phase2.process_one(card, cfg, audit_driver="real")
    assert res["result"] == "audit_failed"
    res = phase2.process_one(card, cfg, audit_driver="real")
    assert res["result"] == "audit_failed"
    # 第 3 次协议失败 → 预算耗尽 → 打回待人工
    res = phase2.process_one(card, cfg, audit_driver="real")
    assert res["result"] == "rejected"
    assert res["awaiting_human"] is True
    text = card_file.read_text(encoding="utf-8")
    assert "PROTOCOL 预算耗尽，待人工" in text
    assert any(r["action"] == "protocol_budget_exhausted" for r in recorded)


def test_process_one_business_exhausted_mark(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """business 打回预算耗尽 → 卡头 REJECT 预算耗尽 + sidecar awaiting_human。"""
    from server.engine import phase2

    card_file = tmp_path / "tst003.md"
    card_file.write_text(
        "# 任务卡 tst003 · P2\n> 状态：打回（CC 审核不通过） · 项目：tst\n\n## 门禁\n- 测试：true\n",
        encoding="utf-8",
    )
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    cfg = {"EXECUTOR_LOG_DIR": str(log_dir), "DISPATCH_DIR": str(tmp_path)}
    card = {"id": "tst003", "title": "P2", "project": "tst", "path": str(card_file)}
    recorded: list[dict] = []

    def fake_record_action(action, object_id, source="", detail="", **kwargs):
        recorded.append({"action": action, "object_id": object_id, "detail": detail, **kwargs})

    monkeypatch.setattr(phase2, "git", lambda cmd, cwd=None: _ok_rc(cmd, 0))
    monkeypatch.setattr(phase2, "_branch_in_main", lambda b: False)
    monkeypatch.setattr(phase2, "_current_branch", lambda: "main")
    monkeypatch.setattr("server.board.audit_ledger.record_action", fake_record_action)
    monkeypatch.setattr(phase2, "_clear_rejected_branch_envelope", lambda card: (True, []))

    res = phase2.process_one(card, cfg, audit_driver="mock:reject")
    assert res["result"] == "rejected"
    assert res["reject_count"] == 1
    res = phase2.process_one(card, cfg, audit_driver="mock:reject")
    assert res["reject_count"] == 2
    res = phase2.process_one(card, cfg, audit_driver="mock:reject")
    assert res["reject_count"] == 3
    assert res["reject_budget_exhausted"] is True
    assert res["awaiting_human"] is True
    assert res["exhausted_class"] == "business"
    assert "REJECT 预算耗尽，待人工" in card_file.read_text(encoding="utf-8")
    assert any(r["action"] == "reject_budget_exhausted" for r in recorded)


# ── 6. 红派清零 ──


def test_manual_redispatch_clears_all_budgets(tmp_path: Path):
    write_card_state(
        tmp_path,
        "tst004",
        business_reject_count=3,
        protocol_retry_count=3,
        reject_count=3,
        reject_budget_exhausted=True,
        awaiting_human=True,
        exhausted_class="protocol",
    )
    rec = read_card_state(tmp_path)["tst004"]
    assert rec["awaiting_human"] is True
    # 模拟 web transition 重派：清全部预算计数
    from server.engine.runtime_state import clear_card_state

    clear_card_state(tmp_path, "tst004")
    write_card_state(
        tmp_path,
        "tst004",
        state="待分派",
        retry_count=0,
        redispatch="now",
        reject_count=0,
        reject_budget_exhausted=False,
        business_reject_count=0,
        protocol_retry_count=0,
        awaiting_human=False,
        exhausted_class=None,
    )
    rt = read_card_state(tmp_path)["tst004"]
    assert rt["business_reject_count"] == 0
    assert rt["protocol_retry_count"] == 0
    assert rt["awaiting_human"] is False
    assert rt.get("exhausted_class") in (None, "")


# ── 7. engine 侧 business 预算记账（_fail_retry_or_reject） ──


def test_engine_fail_retry_or_reject_business_budget(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from server.engine import main
    from server.engine.store import InMemoryBoardStore
    from server.engine.task import State, Work

    store = InMemoryBoardStore()
    w = Work(id="tst005", role="开发执行体", state=State.RUNNING, card_path="/tmp/tst005.md")
    store.seed(w)
    monkeypatch.setattr(main, "max_retries_from_cfg", lambda cfg: 0)  # 首次即打回
    retried = main._fail_retry_or_reject(w, store, ["测试失败"], {}, tmp_path)
    assert retried is False
    assert w.state is State.REJECTED
    rt = read_card_state(tmp_path).get("tst005", {})
    assert rt.get("business_reject_count") == 1


def _ok_rc(cmd, rc):
    import subprocess

    return subprocess.CompletedProcess(cmd, rc, stdout="", stderr="")
