"""phase2 后半段闭环单测（hermetic：mock git/claude/deploy，不碰真实仓与 LLM）。"""

from __future__ import annotations

import json
import subprocess
import types
from pathlib import Path

import pytest

from server.engine import phase2


def _ok_rc(rc: int = 0, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(["git"], rc, stdout=stdout, stderr=stderr)


def _mk_card(tmp_path: Path, state: str = "已回写") -> tuple[Path, dict]:
    card_file = tmp_path / "tst997-phase2-e2e.md"
    card_file.write_text(
        "# 任务卡 tst997-phase2-e2e · Phase2 E2E\n"
        f"> 关联：测试 · 执行体：DSH · 验收：Claude Code · 状态：{state} · 派发：engine · 项目：tst · 日期：2026-08-28\n\n"
        "## 目标\n验证后半段闭环。\n\n"
        "## 实现\n仅卡文件。\n\n"
        "## 范围\ndocs/dispatch/tst/tst997-phase2-e2e.md\n\n"
        "## 门禁\n- 测试：python3 -c \"print('gate-ok')\"\n\n"
        "## 维护区\n- 维护说明：测试卡\n",
        encoding="utf-8",
    )
    card = {"id": "tst997", "state": state, "title": "Phase2 E2E", "project": "tst", "path": str(card_file)}
    return card_file, card


def test_verdict_parsing_pass() -> None:
    out = "前面噪声\nPHASE2_VERDICT: PASS\n理由：符合范围，无风险。\n"
    assert phase2._claude_verdict_from_output(out) == "PASS"


def test_verdict_parsing_reject() -> None:
    out = "PHASE2_VERDICT: REJECT\n理由：范围越界。\n"
    assert phase2._claude_verdict_from_output(out) == "REJECT"


def test_verdict_parsing_chinese() -> None:
    assert phase2._claude_verdict_from_output("结论：通过\nok") == "PASS"
    assert phase2._claude_verdict_from_output("结论：不通过\n") == "REJECT"
    assert phase2._claude_verdict_from_output("无关内容") is None


def test_audit_retry_success(monkeypatch) -> None:
    calls = {"n": 0}

    def fake_run(bin, prompt, timeout):  # noqa: A002
        calls["n"] += 1
        if calls["n"] < 3:
            return 1, "", "429 quota"
        return 0, "PHASE2_VERDICT: PASS\nok", ""

    monkeypatch.setattr(phase2, "_run_claude", fake_run)
    monkeypatch.setattr(phase2.time, "sleep", lambda s: None)
    monkeypatch.setattr(phase2, "preflight_gateway", lambda **k: (True, "preflight mocked"))
    res = phase2.audit_card({"id": "tst997"}, Path("x.md"), "codex/x", {}, audit_driver="real")
    assert res["verdict"] == "PASS"
    assert res["attempts"] == 3
    assert calls["n"] == 3


def test_audit_retry_exhaust(monkeypatch) -> None:
    calls = {"n": 0}

    def fake_run(bin, prompt, timeout):  # noqa: A002
        calls["n"] += 1
        return 1, "", "429 quota"

    monkeypatch.setattr(phase2, "_run_claude", fake_run)
    monkeypatch.setattr(phase2.time, "sleep", lambda s: None)
    monkeypatch.setattr(phase2, "preflight_gateway", lambda **k: (True, "preflight mocked"))
    res = phase2.audit_card({"id": "tst997"}, Path("x.md"), "codex/x", {}, audit_driver="real")
    assert res["verdict"] == "ERROR"
    assert res["attempts"] == 3
    assert "429" in res["reasons"]


def test_audit_mock_drivers() -> None:
    assert phase2.audit_card({}, Path("x.md"), "b", {}, "mock:pass")["verdict"] == "PASS"
    assert phase2.audit_card({}, Path("x.md"), "b", {}, "mock:reject")["verdict"] == "REJECT"
    assert phase2.audit_card({}, Path("x.md"), "b", {}, "mock:error")["verdict"] == "ERROR"


def test_set_card_state_rewrites_and_appends(tmp_path: Path) -> None:
    card_file, _ = _mk_card(tmp_path)
    assert phase2.set_card_state(card_file, "已关闭", "PASS", "ok") is True
    text = card_file.read_text(encoding="utf-8")
    assert "状态：已关闭" in text
    assert "## 机审区" in text
    assert "结论：通过" in text


def test_set_card_state_reject(tmp_path: Path) -> None:
    card_file, _ = _mk_card(tmp_path)
    assert phase2.set_card_state(card_file, "打回（CC 审核不通过）", "REJECT", "范围越界") is True
    text = card_file.read_text(encoding="utf-8")
    assert "状态：打回（CC 审核不通过）" in text
    assert "结论：不通过" in text


def test_run_card_gates_ok_and_fail(tmp_path: Path) -> None:
    card_file, _ = _mk_card(tmp_path)
    assert phase2.run_card_gates(card_file) == []
    bad = tmp_path / "bad.md"
    bad.write_text("## 门禁\n- 测试：python3 -c 'import sys; sys.exit(1)'\n", encoding="utf-8")
    fails = phase2.run_card_gates(bad)
    assert len(fails) == 1
    assert "失败" in fails[0]


def test_list_branch_written_cards(monkeypatch) -> None:
    """分支信封：origin/codex/tst997-* 分支卡=已回写 且 main 未关闭 → 待消费。"""
    card_md = (
        "# 任务卡 tst997 · Phase2 E2E\n"
        "> 关联：测试 · 执行体：DSH · 验收：Claude Code · 状态：已回写 · 派发：engine · 项目：tst · 日期：2026-08-28\n\n"
        "## 目标\nx\n"
    )

    def fake_git(cmd, cwd=None):  # noqa: A002
        if cmd[0] == "for-each-ref":
            return _ok_rc(0, stdout="refs/remotes/origin/codex/tst997-phase2-e2e\n")
        if cmd[:3] == ["diff", "--name-only", "origin/main"]:
            return _ok_rc(0, stdout="docs/dispatch/tst/tst997-phase2-e2e.md\n")
        if cmd[0] == "show" and "tst997" in cmd[1]:
            return _ok_rc(0, stdout=card_md)
        if cmd[:2] == ["merge-base", "--is-ancestor"]:
            return _ok_rc(1)  # 分支未合入 main
        return _ok_rc(0)

    monkeypatch.setattr(phase2, "git", fake_git)
    cards = phase2._list_branch_written_cards()
    assert len(cards) == 1
    assert cards[0]["id"] == "tst997"
    assert cards[0]["branch"] == "codex/tst997-phase2-e2e"
    assert cards[0]["path_rel"] == "docs/dispatch/tst/tst997-phase2-e2e.md"


def test_process_one_reject_does_not_block(monkeypatch, tmp_path: Path) -> None:
    card_file, card = _mk_card(tmp_path)
    ledger_rows: list[dict] = []
    recorded: list[dict] = []

    def fake_record_action(action, object_id, source="", detail=""):  # noqa: A002
        recorded.append({"action": action, "object_id": object_id, "detail": detail})

    def fake_git(cmd, cwd=None):  # noqa: A002
        if cmd[:2] == ["merge-base", "--is-ancestor"]:
            return _ok_rc(1)  # 分支不在 main
        if cmd[:1] == ["rev-parse"]:
            return _ok_rc(0, stdout="main")
        return _ok_rc(0)

    monkeypatch.setattr(phase2, "git", fake_git)
    monkeypatch.setattr(phase2, "_branch_in_main", lambda b: False)
    monkeypatch.setattr("server.board.audit_ledger.record_action", fake_record_action)
    res = phase2.process_one(card, {}, audit_driver="mock:reject")
    assert res["result"] == "rejected"
    assert "打回" in card_file.read_text(encoding="utf-8")
    assert any(r["action"] == "phase2_reject" for r in recorded)


def test_process_one_pass_closed(monkeypatch, tmp_path: Path) -> None:
    card_file, card = _mk_card(tmp_path)
    recorded: list[dict] = []

    def fake_record_action(action, object_id, source="", detail=""):  # noqa: A002
        recorded.append({"action": action, "object_id": object_id, "detail": detail})

    def fake_git(cmd, cwd=None):  # noqa: A002
        if cmd[:2] == ["merge-base", "--is-ancestor"]:
            return _ok_rc(1)
        if cmd[:1] == ["rev-parse"]:
            return _ok_rc(0, stdout="main")
        return _ok_rc(0)

    monkeypatch.setattr(phase2, "git", fake_git)
    monkeypatch.setattr(phase2, "_branch_in_main", lambda b: False)
    monkeypatch.setattr(phase2, "deploy_and_probe", lambda cfg: (True, "web :7788 /health 响应正常"))
    monkeypatch.setattr("server.board.audit_ledger.record_action", fake_record_action)
    monkeypatch.setenv("CCC_DATA_DIR", str(tmp_path))
    res = phase2.process_one(card, {"DISPATCH_DIR": str(tmp_path)}, audit_driver="mock:pass")
    assert res["result"] == "closed"
    text = card_file.read_text(encoding="utf-8")
    assert "状态：已关闭" in text
    assert "结论：通过" in text
    assert any(r["action"] == "phase2_pass" for r in recorded)
    # 打回修复：唯一索引须反映终态（phase2 关闭链路写回唯一索引）。
    # pytest 下 get_index_path 走 PYTEST_CURRENT_TEST 隔离分支 → <dispatch>/cards.index.jsonl。
    idx = tmp_path / "cards.index.jsonl"
    assert idx.is_file(), "phase2 关闭后唯一索引未刷新"
    entry = next(
        (json.loads(ln) for ln in idx.read_text(encoding="utf-8").splitlines() if ln.strip()),
        None,
    )
    assert entry is not None and entry["id"] == "tst997-phase2-e2e"  # 卡标题 token 即 id
    assert entry["state"] == "已关闭"


def test_process_one_audit_fail_keeps_card(monkeypatch, tmp_path: Path) -> None:
    card_file, card = _mk_card(tmp_path)
    recorded: list[dict] = []

    def fake_record_action(action, object_id, source="", detail=""):  # noqa: A002
        recorded.append({"action": action, "object_id": object_id, "detail": detail})

    monkeypatch.setattr(phase2, "git", lambda cmd, cwd=None: _ok_rc(1))
    monkeypatch.setattr(phase2, "_branch_in_main", lambda b: False)
    monkeypatch.setattr("server.board.audit_ledger.record_action", fake_record_action)
    res = phase2.process_one(card, {}, audit_driver="mock:error")
    assert res["result"] == "audit_failed"
    # 卡保留已回写（不静默丢卡）
    assert "状态：已回写" in card_file.read_text(encoding="utf-8")
    assert any(r["action"] == "phase2_audit_fail" for r in recorded)


def test_delete_merged_branch_cleans_local_and_remote(monkeypatch) -> None:
    """分支已并入 main → 本地+远端都删（任务四）。"""
    calls: list[list[str]] = []

    def fake_git(cmd, cwd=None):  # noqa: A002
        calls.append(list(cmd))
        return _ok_rc(0)

    monkeypatch.setattr(phase2, "git", fake_git)
    ok, problems = phase2.delete_merged_branch("codex/tst-a")
    assert ok, problems
    assert problems == []
    assert ["push", "origin", "--delete", "codex/tst-a"] in calls
    assert ["branch", "-d", "codex/tst-a"] in calls


def test_delete_merged_branch_keeps_unmerged(monkeypatch) -> None:
    """未确认并入 main → 保守保留，绝不动远端。"""
    calls: list[list[str]] = []

    def fake_git(cmd, cwd=None):  # noqa: A002
        calls.append(list(cmd))
        if cmd[:2] == ["merge-base", "--is-ancestor"]:
            return _ok_rc(1)
        return _ok_rc(0)

    monkeypatch.setattr(phase2, "git", fake_git)
    ok, problems = phase2.delete_merged_branch("codex/tst-b")
    assert not ok
    assert any("保守保留" in p for p in problems)
    assert not any(c[:1] == ["push"] for c in calls)


def test_delete_merged_branch_alerts_on_remote_delete_fail(monkeypatch) -> None:
    """远端删除失败 → 返回 False + 明细（调用方留痕告警，禁止静默）。"""

    def fake_git(cmd, cwd=None):  # noqa: A002
        if cmd[:1] == ["push"]:
            return subprocess.CompletedProcess(args=cmd, returncode=1, stdout="", stderr="remote ref does not exist")
        return _ok_rc(0)

    monkeypatch.setattr(phase2, "git", fake_git)
    ok, problems = phase2.delete_merged_branch("codex/tst-c")
    assert not ok
    assert any("远端分支删除失败" in p for p in problems)


def test_process_one_pass_closed_cleans_branch(monkeypatch, tmp_path: Path) -> None:
    """合入收尾成功路径：phase2_pass 后触发分支清理；成功则无 phase2_alert。"""
    card_file, card = _mk_card(tmp_path)
    recorded: list[dict] = []
    push_deletes: list[list[str]] = []

    def fake_record_action(action, object_id, source="", detail=""):  # noqa: A002
        recorded.append({"action": action, "object_id": object_id, "detail": detail})

    def fake_git(cmd, cwd=None):  # noqa: A002
        if cmd[:2] == ["merge-base", "--is-ancestor"]:
            return _ok_rc(0)  # 分支已并入 main → 允许删
        if cmd[:1] == ["push"] and "--delete" in cmd:
            push_deletes.append(list(cmd))
            return _ok_rc(0)
        if cmd[:1] == ["rev-parse"]:
            return _ok_rc(0, stdout="main")
        return _ok_rc(0)

    monkeypatch.setattr(phase2, "git", fake_git)
    monkeypatch.setattr(phase2, "_branch_in_main", lambda b: False)
    monkeypatch.setattr(phase2, "deploy_and_probe", lambda cfg: (True, "web :7788 /health 响应正常"))
    monkeypatch.setattr("server.board.audit_ledger.record_action", fake_record_action)
    monkeypatch.setenv("CCC_DATA_DIR", str(tmp_path))
    res = phase2.process_one(card, {"DISPATCH_DIR": str(tmp_path)}, audit_driver="mock:pass")
    assert res["result"] == "closed"
    assert res["branch_cleanup"] == "ok"
    assert any(c[:1] == ["push"] and "--delete" in c for c in push_deletes)
    assert not any(r["action"] == "phase2_alert" for r in recorded)
    assert "状态：已关闭" in card_file.read_text(encoding="utf-8")


def test_worktree_dirty_problems_ignores_untracked(monkeypatch) -> None:
    """untracked 不算脏；已跟踪改动才算（任务五）。"""

    def fake_git(cmd, cwd=None):  # noqa: A002
        return _ok_rc(0, stdout=" M server/x.py\n?? new-file.txt\n")

    monkeypatch.setattr(phase2, "git", fake_git)
    problems = phase2.worktree_dirty_problems()
    assert problems == [" M server/x.py"]


def test_consume_once_skips_when_dirty(monkeypatch, tmp_path: Path) -> None:
    """工作区脏 → 整轮跳过 + phase2_alert 留痕，卡不被消费（禁止静默卡死）。"""
    recorded: list[dict] = []
    _, card = _mk_card(tmp_path)

    def fake_git(cmd, cwd=None):  # noqa: A002
        if cmd[:1] == ["status"]:
            return _ok_rc(0, stdout=" M docs/dispatch/tst/x.md\n")
        return _ok_rc(0)

    def fail_process_one(*a, **k):  # noqa: A002
        raise AssertionError("脏工作区下不应消费任何卡")

    monkeypatch.setattr(phase2, "git", fake_git)
    monkeypatch.setattr(phase2, "list_written_cards", lambda d: [card])
    monkeypatch.setattr(phase2, "process_one", fail_process_one)
    monkeypatch.setattr("server.board.audit_ledger.record_action", lambda *a, **k: recorded.append({"action": a[0], "detail": a[3] if len(a) > 3 else k.get("detail", "")}))
    stats = phase2.consume_once(tmp_path, {})
    assert stats["skipped_dirty"] == 1
    assert stats["closed"] == 0
    assert any(r["action"] == "phase2_alert" and "工作区脏" in r["detail"] for r in recorded)


def test_consume_once_proceeds_when_clean(monkeypatch, tmp_path: Path) -> None:
    """工作区干净（含 untracked）→ 正常消费，不误伤。"""
    _, card = _mk_card(tmp_path)

    def fake_git(cmd, cwd=None):  # noqa: A002
        if cmd[:1] == ["status"]:
            return _ok_rc(0, stdout="?? untracked.log\n")
        return _ok_rc(0)

    monkeypatch.setattr(phase2, "git", fake_git)
    monkeypatch.setattr(phase2, "list_written_cards", lambda d: [card])
    monkeypatch.setattr(phase2, "process_one", lambda c, cfg, audit_driver="real": {"id": c["id"], "result": "closed"})
    stats = phase2.consume_once(tmp_path, {})
    assert stats["closed"] == 1
    assert "skipped_dirty" not in stats
