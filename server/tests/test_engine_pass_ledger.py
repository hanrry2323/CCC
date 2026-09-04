"""机审通过路径必须写 machine_audit_pass 批准真值账本（2026-08-20 事故回归）。

事故：mx054/mx055 机审通过（分支卡机审区=通过），但 engine 通过路径
（已通过跳过/补提交）不写 machine_audit_pass ledger → 8-16 后合入门禁
「机审 provenance」拦截，合入被拒。根修：通过出口统一调幂等 helper。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from server.board.audit_ledger import has_action, load_ledger
from server.engine.dispatch import ExecutorRegistry, load_registry
from server.engine.main import (
    _record_machine_audit_pass,
    _run_machine_audit_after_writeback,
)
from server.engine.task import Work


@pytest.fixture
def ledger_file(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("server.board.audit_ledger._ledger_path", lambda d=None: tmp_path / "ledger.jsonl")
    return tmp_path / "ledger.jsonl"


def _work(card_path: str = "/x/docs/dispatch/mx/mx099-task.md") -> Work:
    return Work(id="mx099", role="开发执行体", executor="OpenCode", card_path=card_path)


def _registry_with_acceptor(tmp_path: Path) -> ExecutorRegistry:
    """批E：_run_machine_audit_after_writeback 直取注册表「验收席」行，测试注入真实注册表。"""
    import json

    reg_file = tmp_path / "executors.json"
    reg_file.write_text(
        json.dumps(
            {
                "executors": [
                    {
                        "角色": "验收席",
                        "分类": "可后台 CLI",
                        "当前绑定": "后段 CC CLI（claude wrapper，主链 phase2）",
                        "命令": "/tmp/cc-auditor.sh",
                        "参数模板": "{card_path} {work_id} {worktree} {role} {biz_worktree}",
                        "工作目录": "",
                        "worktree_base": "",
                        "备注": "test",
                        "worker_id": "W1",
                        "注入提示": False,
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return load_registry(reg_file)


def test_record_machine_audit_pass_writes_ledger(ledger_file) -> None:
    _record_machine_audit_pass(_work())
    assert has_action("machine_audit_pass", "mx099")


def test_record_machine_audit_pass_idempotent(ledger_file) -> None:
    _record_machine_audit_pass(_work())
    _record_machine_audit_pass(_work())
    rows = [
        r for r in load_ledger(ledger_file) if r.get("action") == "machine_audit_pass" and r.get("object_id") == "mx099"
    ]
    assert len(rows) == 1


def test_pass_skip_path_records_ledger(ledger_file, monkeypatch) -> None:
    """已通过跳过出口（mx055 实际路径）必须写 machine_audit_pass。"""
    called = []
    monkeypatch.setattr(
        "server.engine.main._record_machine_audit_pass", lambda w, source="engine-audit": called.append((w.id, source))
    )
    monkeypatch.setattr("server.engine.main._worktree_hint_for", lambda *a, **k: None)
    monkeypatch.setattr("server.engine.main._audit_evidence_passed", lambda *a, **k: True)
    ok, problems, audited = _run_machine_audit_after_writeback(_work(), None, {}, Path("/tmp/logs"), 300)
    assert ok is True and audited is False
    assert any(cid == "mx099" for cid, _ in called)


def test_pass_worktree_path_records_ledger(ledger_file, monkeypatch, tmp_path: Path) -> None:
    """分支路径通过（机审 agent 已写机审区）也必须写 machine_audit_pass。"""
    card = tmp_path / "docs" / "dispatch" / "mx" / "mx099-task.md"
    card.parent.mkdir(parents=True)
    card.write_text(
        "# 卡\n\n## 维护区\n\n1. 方案同步：[是] 说明\n2. 教训沉淀：[无]\n3. 档案：[否]\n4. 线路图：[否]\n",
        encoding="utf-8",
    )
    called = []
    monkeypatch.setattr(
        "server.engine.main._record_machine_audit_pass", lambda w, source="engine-audit": called.append((w.id, source))
    )
    monkeypatch.setattr("server.engine.main._worktree_hint_for", lambda *a, **k: str(tmp_path))
    monkeypatch.setattr("server.engine.main._worktree_branch_tip", lambda *a, **k: None)
    monkeypatch.setattr("server.engine.main._worktree_card_candidate", lambda hint, path: card)
    monkeypatch.setattr("server.engine.main._dispatch_and_collect", lambda *a, **k: (True, []))
    monkeypatch.setattr("server.engine.main._append_machine_audit_pass", lambda *a, **k: True)
    monkeypatch.setattr("server.engine.main._pin_audit_commit", lambda *a, **k: None)
    monkeypatch.setattr("server.engine.main._commit_and_push_worktree_card", lambda *a, **k: True)
    monkeypatch.setattr(
        "server.engine.main._audit_evidence_passed",
        lambda *a, **k: False,
    )
    work = _work(card_path=str(card))
    ok, problems, audited = _run_machine_audit_after_writeback(work, _registry_with_acceptor(tmp_path), {}, tmp_path / "logs", 300)
    assert ok is True
    assert any(cid == "mx099" for cid, _ in called)


def test_pass_prod_card_path_records_ledger(ledger_file, monkeypatch, tmp_path: Path) -> None:
    """生产卡兜底通过路径（已移除主仓 fallback，该测试现在预期返回 False 并阻断）。"""
    card = tmp_path / "mx099-task.md"
    card.write_text("# 卡\n", encoding="utf-8")
    called = []
    monkeypatch.setattr(
        "server.engine.main._record_machine_audit_pass", lambda w, source="engine-audit": called.append((w.id, source))
    )
    monkeypatch.setattr("server.engine.main._worktree_hint_for", lambda *a, **k: None)
    monkeypatch.setattr("server.engine.main._dispatch_and_collect", lambda *a, **k: (True, []))
    monkeypatch.setattr("server.engine.main._append_machine_audit_pass", lambda *a, **k: True)
    monkeypatch.setattr("server.engine.main._audit_evidence_passed", lambda *a, **k: False)
    work = _work(card_path=str(card))
    ok, problems, audited = _run_machine_audit_after_writeback(work, _registry_with_acceptor(tmp_path), {}, tmp_path / "logs", 300)
    assert ok is False
    assert "禁止 fallback 生产卡" in problems[0]


def test_branch_audit_requires_ledger_not_card_text(monkeypatch, tmp_path: Path) -> None:
    """P0 硬化：branch_card_audit_passed 卡文「机审：通过」但账本无记录 → 不算通过。

    对应假关闭复发风险：执行体在分支卡里写「结论：通过」伪造，看板/ready 队列不得再信纯文本。
    """
    from server.web.audit_evidence import branch_card_audit_passed

    class _R:
        returncode = 0
        stdout = "# 任务卡 xy200 · fake\n\n## 机审区\n\n> 结论：通过\n"

    monkeypatch.setattr(
        "subprocess.run",
        lambda *a, **k: _R(),
    )
    # 空账本（无 machine_audit_pass 记录）
    monkeypatch.setattr("server.board.audit_ledger._ledger_path", lambda d=None: tmp_path / "empty.jsonl")
    (tmp_path / "empty.jsonl").write_text("", encoding="utf-8")
    assert branch_card_audit_passed(Path("."), "docs/dispatch/xy/xy200.md", "codex/xy200-fake") is False, \
        "卡文写通过但账本无记录 → 必须 False（防假关闭）"

    # 账本有该卡 machine_audit_pass → True
    ledger = tmp_path / "ledger.jsonl"
    ledger.write_text(
        '{"ts":"2026-08-16T00:00:00Z","action":"machine_audit_pass","object_id":"xy200","source":"engine"}\n',
        encoding="utf-8",
    )
    monkeypatch.setattr("server.board.audit_ledger._ledger_path", lambda d=None: ledger)
    # 清两个缓存（ledger path 变了 + branch 缓存要重算）
    from server.board.audit_ledger import _pass_ids_cache
    from server.web import audit_evidence as _ae

    _pass_ids_cache["key"] = None
    _pass_ids_cache["ids"] = None
    _ae._branch_cache.clear()
    assert branch_card_audit_passed(Path("."), "docs/dispatch/xy/xy200.md", "codex/xy200-fake") is True, \
        "账本有 machine_audit_pass → True"
