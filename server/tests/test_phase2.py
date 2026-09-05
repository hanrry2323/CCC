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


def _written_audit_env(tmp_path: Path, card_id: str = "tst997") -> tuple[Path, dict]:
    """构造新机审契约前置：已回写主仓卡 + log_dir 执行结果工件。"""
    card_file = tmp_path / f"{card_id}.md"
    card_file.write_text(
        "> 状态：已回写 · 项目：tst\n\n## 维护区\n- 说明：测试\n",
        encoding="utf-8",
    )
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    (log_dir / f"{card_id}-ccc-result.md").write_text("result", encoding="utf-8")
    cfg = {"EXECUTOR_LOG_DIR": str(log_dir)}
    return card_file, cfg


def test_audit_retry_success(monkeypatch, tmp_path: Path) -> None:
    calls = {"n": 0}
    card_file, cfg = _written_audit_env(tmp_path)

    def fake_run(card, card_path, branch, cfg, timeout):
        calls["n"] += 1
        if calls["n"] == 3:
            (tmp_path / "logs" / "tst997-audit-verdict.md").write_text("机审：通过\n", encoding="utf-8")
            return 0, "审计完成", ""
        return 1, "", "429 quota"

    monkeypatch.setattr(phase2, "_run_dsh_auditor", fake_run)
    monkeypatch.setattr(phase2.time, "sleep", lambda s: None)
    monkeypatch.setattr(phase2, "preflight_gateway", lambda **k: (True, "preflight mocked"))
    res = phase2.audit_card({"id": "tst997"}, card_file, "codex/x", cfg, audit_driver="real")
    assert res["verdict"] == "PASS"
    assert res["attempts"] == 3
    assert calls["n"] == 3


def test_audit_retry_exhaust(monkeypatch, tmp_path: Path) -> None:
    calls = {"n": 0}
    card_file, cfg = _written_audit_env(tmp_path)

    def fake_run(card, card_path, branch, cfg, timeout):
        calls["n"] += 1
        return 1, "", "429 quota"

    monkeypatch.setattr(phase2, "_run_dsh_auditor", fake_run)
    monkeypatch.setattr(phase2.time, "sleep", lambda s: None)
    monkeypatch.setattr(phase2, "preflight_gateway", lambda **k: (True, "preflight mocked"))
    res = phase2.audit_card({"id": "tst997"}, card_file, "codex/x", cfg, audit_driver="real")
    assert res["verdict"] == "ERROR"
    assert res["attempts"] == 3
    assert "429" in res["reasons"]


def test_audit_prerequisites_missing_result_artifacts(tmp_path: Path) -> None:
    """前置失败：主仓卡已回写但执行结果工件缺失 → fail-fast（不盲目重试）。"""
    card_file, cfg = _written_audit_env(tmp_path)
    (tmp_path / "logs" / "tst997-ccc-result.md").unlink()
    ok, reason = phase2._audit_prerequisites({"id": "tst997"}, card_file, cfg)
    assert not ok
    assert "执行结果工件缺失" in reason


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


def test_branch_in_main_uses_origin_main(monkeypatch) -> None:
    """C-7：合入判定必须以 origin/main 为基准，而非本地 main。"""
    calls: list[list[str]] = []

    def fake_git(cmd, cwd=None):  # noqa: A002
        calls.append(list(cmd))
        return _ok_rc(0)

    monkeypatch.setattr(phase2, "git", fake_git)
    assert phase2._branch_in_main("codex/tst-a") is True
    assert ["merge-base", "--is-ancestor", "origin/codex/tst-a", "origin/main"] in calls


def test_merge_push_failure_is_retryable(monkeypatch, tmp_path: Path) -> None:
    """C-7：合并已落本地但 push 失败时返回补推标记，不推进终态。"""
    calls: list[list[str]] = []

    def fake_git(cmd, cwd=None):  # noqa: A002
        calls.append(list(cmd))
        if cmd[:2] == ["push", "origin"] and cmd[-1] == "main":
            return _ok_rc(1, stderr="network down")
        if cmd[:1] == ["rev-parse"]:
            return _ok_rc(0, stdout="main")
        return _ok_rc(0)

    monkeypatch.setattr(phase2, "git", fake_git)
    ok, reason = phase2.merge_branch_to_main("codex/tst-a", card_id="tst1", cfg={"EXECUTOR_LOG_DIR": str(tmp_path)})
    assert ok is False
    assert "PUSH_NEEDS_RETRY" in reason
    assert ["push", "origin", "main"] in calls


def test_merge_conflict_second_strike_opens_circuit(monkeypatch, tmp_path: Path) -> None:
    """C-5：同卡连续两次合入冲突后熔断，返回打回标记。"""
    calls: list[list[str]] = []

    def fake_git(cmd, cwd=None):  # noqa: A002
        calls.append(list(cmd))
        if cmd[:1] == ["merge"]:
            return _ok_rc(1, stderr="CONFLICT (content): merge conflict")
        if cmd[:1] == ["status"]:
            return _ok_rc(0, stdout="UU docs/dispatch/tst/tst1.md\\n")
        if cmd[:1] == ["rev-parse"]:
            return _ok_rc(0, stdout="main")
        return _ok_rc(0)

    monkeypatch.setattr(phase2, "git", fake_git)
    cfg = {"EXECUTOR_LOG_DIR": str(tmp_path)}
    first = phase2.merge_branch_to_main("codex/tst-a", card_id="tst1", cfg=cfg)
    second = phase2.merge_branch_to_main("codex/tst-a", card_id="tst1", cfg=cfg)
    assert "CONFLICT_CIRCUIT_OPEN" not in first[1]
    assert "CONFLICT_CIRCUIT_OPEN" in second[1]


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
    # wrapper 型卡无代码分支，不触发分支清理。
    assert push_deletes == []
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


def test_web_host_injected_env_points_to_lan(monkeypatch) -> None:
    """WEB_HOST 注入（plist 环境变量 192.168.3.116）→ 探活 host 指向内网地址。"""
    monkeypatch.setenv("WEB_HOST", "192.168.3.116")
    monkeypatch.delenv("WEB_PORT", raising=False)
    assert phase2._web_host({}) == "192.168.3.116"


def test_web_host_fallback_loopback() -> None:
    """无 WEB_HOST（本地/测试模式）→ 回落 127.0.0.1，127.0.0.1 语义不破坏。"""
    cfg = {"WEB_HOST": ""}
    assert phase2._web_host(cfg) == "127.0.0.1"


def _fake_auditor(tmp_path: Path) -> str:
    """创建真实存在的假 auditor.sh 供 _run_dsh_auditor 通过文件检查。"""
    p = tmp_path / "fake-dsh-auditor.sh"
    p.write_text("#!/bin/bash\n", encoding="utf-8")
    p.chmod(0o755)
    return str(p)


def test_dsh_auditor_accepts_empty_worktree_contract(monkeypatch, tmp_path: Path) -> None:
    """新契约：auditor 调用不要求业务 worktree，空值不再失败。"""
    card_file = tmp_path / "tst998.md"
    card_file.write_text("# 任务卡 tst998\n", encoding="utf-8")
    monkeypatch.setattr(phase2, "_current_branch", lambda: "main")
    monkeypatch.setattr(phase2, "cli_env", lambda: {})
    monkeypatch.setattr(phase2.subprocess, "run", lambda *args, **kwargs: _ok_rc(0))
    rc, out, err = phase2._run_dsh_auditor(
        {"id": "tst998", "project": "tst"}, card_file, "", {"DSH_AUDITOR_BIN": _fake_auditor(tmp_path)}, 900
    )
    assert rc == 0


def test_dsh_auditor_decodes_invalid_utf8_output(monkeypatch, tmp_path: Path) -> None:
    """验收席输出含非法 UTF-8 时替换解码，并继续解析 verdict。"""
    card_file = tmp_path / "tst995.md"
    card_file.write_text("# 任务卡 tst995\n", encoding="utf-8")
    monkeypatch.setattr(phase2, "_current_branch", lambda: "main")
    monkeypatch.setattr(phase2, "cli_env", lambda: {})
    monkeypatch.setattr(
        phase2.subprocess,
        "run",
        lambda *args, **kwargs: _ok_rc(
            0,
            stdout=b"noise-\xef\xff\nPHASE2_VERDICT: PASS\n",
            stderr=b"warning-\xef\xfe",
        ),
    )

    rc, out, err = phase2._run_dsh_auditor(
        {"id": "tst995", "project": "tst"}, card_file, "", {"DSH_AUDITOR_BIN": _fake_auditor(tmp_path)}, 900
    )

    assert rc == 0
    assert "�" in out
    assert "�" in err
    assert phase2._claude_verdict_from_output(out) == "PASS"


def test_dsh_auditor_reads_command_from_registry(monkeypatch, tmp_path: Path) -> None:
    """批E 定向：注册表换命令 → phase2 用新命令（插座单源）。

    cfg 注入 tmp 注册表，验收席「命令」指向临时 wrapper；_run_dsh_auditor
    应以注册表命令拉起（不再写死 dsh-auditor.sh）。
    """
    card_file = tmp_path / "tst997.md"
    card_file.write_text("# 任务卡 tst997\n", encoding="utf-8")
    fake = _fake_auditor(tmp_path)
    reg_file = tmp_path / "executors.json"
    reg_file.write_text(
        json.dumps(
            {
                "executors": [
                    {
                        "角色": "验收席",
                        "分类": "可后台 CLI",
                        "当前绑定": "后段 CC CLI（主链 phase2 自动）",
                        "命令": fake,
                        "参数模板": "{card_path} {work_id} {worktree} {role} {biz_worktree}",
                        "工作目录": "",
                        "worktree_base": "",
                        "备注": "测试注册表",
                        "worker_id": "W1",
                        "注入提示": False,
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(phase2, "_current_branch", lambda: "main")
    monkeypatch.setattr(phase2, "cli_env", lambda: {})
    calls: list[list[str]] = []
    monkeypatch.setattr(
        phase2.subprocess,
        "run",
        lambda args, **kwargs: calls.append(list(args)) or _ok_rc(0),
    )
    business_worktree = tmp_path / "business-worktree"
    business_worktree.mkdir()
    rc, out, err = phase2._run_dsh_auditor(
        {"id": "tst997", "project": "tst", "worktree": str(business_worktree)},
        card_file,
        "",
        {"EXECUTOR_REGISTRY_PATH": str(reg_file)},
        900,
    )
    assert rc == 0
    assert calls and calls[0][0] == fake, f"应使用注册表命令 {fake}，实际 {calls[0] if calls else 'no call'}"
    # 参数模板保持：card_path work_id card worktree role biz_worktree
    assert calls[0][1:] == [str(card_file), "tst997", str(business_worktree), "验收席", str(business_worktree)]


def test_dsh_auditor_passes_derived_biz_worktree_when_card_omits_it(monkeypatch, tmp_path: Path) -> None:
    """卡未带 worktree 时，第 5 位仍传入按项目隔离根推导的业务 worktree。"""
    card_file = tmp_path / "tst994.md"
    card_file.write_text("# 任务卡 tst994\n", encoding="utf-8")
    fake = _fake_auditor(tmp_path)
    business_worktree = tmp_path / "business-worktree"
    business_worktree.mkdir()
    monkeypatch.setattr(phase2, "_worktree_for", lambda project, work_id: str(business_worktree))
    monkeypatch.setattr(phase2, "_current_branch", lambda: "main")
    monkeypatch.setattr(phase2, "cli_env", lambda: {})
    calls: list[list[str]] = []
    monkeypatch.setattr(
        phase2.subprocess,
        "run",
        lambda args, **kwargs: calls.append(list(args)) or _ok_rc(0),
    )
    rc, out, err = phase2._run_dsh_auditor(
        {"id": "tst994", "project": "xy"},
        card_file,
        "",
        {"DSH_AUDITOR_BIN": fake},
        900,
    )
    assert rc == 0
    assert calls[0][1:] == [str(card_file), "tst994", "__CCC_EMPTY__", "验收席", str(business_worktree)]


def test_dsh_auditor_registry_read_failure_falls_back(monkeypatch, tmp_path: Path) -> None:
    """批E 定向：注册表读取失败 → 回退默认 auditor 路径 + 不硬断。"""
    card_file = tmp_path / "tst996.md"
    card_file.write_text("# 任务卡 tst996\n", encoding="utf-8")
    monkeypatch.setattr(phase2, "_repo_root", lambda: tmp_path)
    fake_default = tmp_path / "scripts" / "dsh-auditor.sh"
    fake_default.parent.mkdir(parents=True, exist_ok=True)
    fake_default.write_text("#!/bin/bash\n", encoding="utf-8")
    fake_default.chmod(0o755)
    monkeypatch.setattr(phase2, "_current_branch", lambda: "main")
    monkeypatch.setattr(phase2, "cli_env", lambda: {})
    monkeypatch.setattr(phase2.subprocess, "run", lambda *args, **kwargs: _ok_rc(0))
    rc, out, err = phase2._run_dsh_auditor(
        {"id": "tst996", "project": "tst"},
        card_file,
        "",
        {"EXECUTOR_REGISTRY_PATH": str(tmp_path / "missing-registry.json")},
        900,
    )
    assert rc == 0


def test_dsh_auditor_branch_drift_restores(monkeypatch, tmp_path: Path) -> None:
    """A4 加固：auditor 返回后发现主仓分支漂移，恢复原分支并报告失败。"""
    card_file = tmp_path / "tst999.md"
    card_file.write_text("# 任务卡 tst999\n", encoding="utf-8")
    worktree = tmp_path / "wt"
    worktree.mkdir()
    (worktree / "tst999.md").write_text("# 任务卡 tst999\n", encoding="utf-8")
    monkeypatch.setattr(phase2, "_repo_root", lambda: tmp_path)
    branch_calls = {"n": 0}

    def drifting_branch():
        branch_calls["n"] += 1
        return "main" if branch_calls["n"] == 1 else "codex/tst999"

    monkeypatch.setattr(phase2, "_current_branch", drifting_branch)
    calls = []
    monkeypatch.setattr(phase2, "git", lambda args, cwd=None: calls.append(args) or _ok_rc())
    monkeypatch.setattr(phase2.subprocess, "run", lambda *args, **kwargs: _ok_rc(0))
    card = {"id": "tst999", "project": "tst999", "worktree": str(worktree)}
    rc, out, err = phase2._run_dsh_auditor(
        card, card_file, "codex/tst999", {"DSH_AUDITOR_BIN": _fake_auditor(tmp_path)}, 900
    )
    assert rc == 127
    assert "分支漂移" in err
    assert ["checkout", "main"] in calls


def test_branch_written_skips_main_rejected_card(monkeypatch) -> None:
    """main 已打回的卡不应从 codex 分支信封重捞。"""
    card_md = (
        "# 任务卡 tst997 · Phase2 E2E\n"
        "> 关联：测试 · 执行体：DSH · 验收：Claude Code · 状态：已回写 · 派发：engine · 项目：tst · 日期：2026-08-28\n"
    )
    rejected_main = card_md.replace("状态：已回写", "状态：打回（CC 审核不通过）")

    def fake_git(cmd, cwd=None):  # noqa: A002
        if cmd[0] == "for-each-ref":
            return _ok_rc(0, stdout="refs/remotes/origin/codex/tst997-phase2-e2e\n")
        if cmd[:3] == ["diff", "--name-only", "origin/main"]:
            return _ok_rc(0, stdout="docs/dispatch/tst/tst997-phase2-e2e.md\n")
        if cmd[0] == "show" and cmd[1].startswith("origin/main:"):
            return _ok_rc(0, stdout=rejected_main)
        if cmd[0] == "show":
            return _ok_rc(0, stdout=card_md)
        return _ok_rc(1)

    monkeypatch.setattr(phase2, "git", fake_git)
    assert phase2._list_branch_written_cards() == []


def test_probe_failure_does_not_increment_strikes(monkeypatch, tmp_path: Path) -> None:
    """网关探针失败只写 480s 冷却，不增加 strikes。"""
    card_file, cfg = _written_audit_env(tmp_path)
    writes: list[dict] = []

    monkeypatch.setattr(phase2, "_audit_cooldown_active", lambda card_id, cfg: False)
    monkeypatch.setattr(
        "server.engine.runtime_state.write_card_state",
        lambda log_dir, card_id, **kwargs: writes.append(kwargs),
    )
    monkeypatch.setattr(phase2, "set_card_state", lambda *args, **kwargs: True)
    monkeypatch.setattr(phase2, "git", lambda cmd, cwd=None: _ok_rc(0, stdout="main"))
    result = phase2._record_audit_failure(
        {"id": "tst997"}, card_file, cfg, "dsh-key-check: 探针不可用（PROBE_UNAVAILABLE）", count_strike=False
    )
    assert result == "cooldown"
    assert writes[-1]["infra_count"] == 0
    until = writes[-1]["infra_cooldown_until"]
    from datetime import datetime, timezone

    remaining = datetime.fromisoformat(until.replace("Z", "+00:00")) - datetime.now(timezone.utc)
    assert 470 <= remaining.total_seconds() <= 481


def test_deploy_failure_keeps_card_written(monkeypatch, tmp_path: Path) -> None:
    """探活失败发生在关闭前，卡必须保留已回写。"""
    card_file, card = _mk_card(tmp_path)
    states: list[str] = []

    monkeypatch.setattr(phase2, "git", lambda cmd, cwd=None: _ok_rc(0, stdout="main"))
    monkeypatch.setattr(phase2, "_branch_in_main", lambda branch: False)
    monkeypatch.setattr(phase2, "deploy_and_probe", lambda cfg: (False, "health unavailable"))
    monkeypatch.setattr(phase2, "set_card_state", lambda path, state, verdict, reasons: states.append(state) or True)
    monkeypatch.setattr("server.board.audit_ledger.record_action", lambda *args, **kwargs: None)
    result = phase2.process_one(card, {}, audit_driver="mock:pass")
    assert result["result"] == "deploy_failed"
    assert states == ["已回写（部署失败）"]
    assert "状态：已回写" in card_file.read_text(encoding="utf-8")


def test_audit_success_clears_strikes(monkeypatch, tmp_path: Path) -> None:
    """真实审计产出结论后清零历史 strikes。"""
    card_file, cfg = _written_audit_env(tmp_path)
    writes: list[dict] = []
    verdict = tmp_path / "logs" / "tst997-audit-verdict.md"

    def fake_run(card, card_path, branch, cfg, timeout):
        verdict.write_text("机审：通过\n", encoding="utf-8")
        return 0, "审计完成", ""

    monkeypatch.setattr(phase2, "preflight_gateway", lambda **kwargs: (True, "ok"))
    monkeypatch.setattr(phase2, "_run_dsh_auditor", fake_run)
    monkeypatch.setattr(phase2, "_current_branch", lambda: "main")
    monkeypatch.setattr(phase2, "cli_env", lambda: {})
    monkeypatch.setattr(
        "server.engine.runtime_state.write_card_state",
        lambda log_dir, card_id, **kwargs: writes.append(kwargs),
    )
    result = phase2.audit_card({"id": "tst997"}, card_file, "codex/x", cfg)
    assert result["verdict"] == "PASS"
    assert writes[-1] == {"infra_count": 0, "infra_cooldown_until": "1970-01-01T00:00:00Z"}
