"""卡校验门测试（ccc-plan-053 阶段2）：DSH 产卡派发前五项校验 + 非法卡作废留痕。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from server.engine.card_gate import validate_card
from server.engine.dispatch import load_registry
from server.engine.main import run_once
from server.engine.store import InMemoryBoardStore
from server.engine.task import State, Work

VALID_CARD = """# 任务卡 tst995 · 卡校验门测试卡

> 关联：ccc-plan-053 · 执行体：DSH · 验收：Claude Code · 状态：待分派 · 派发：engine · 项目：tst · 日期：2026-08-29

## 目标

验证卡校验门放行合法 DSH 卡。

## 实现要求

最小实现，走真实 run_once 派发链。

## 红线

不碰运行面与账本。

## 范围

- card-gate-scope.txt

## 步骤

1. 派发执行（产物：echo 输出日志）。

## 验收标准

1. run_once 摘要 dispatched == 1。
"""

INVALID_CARD = """# 任务卡 tst996 · 故意缺字段卡

> 关联：ccc-plan-053 · 执行体：DSH · 状态：待分派

## 目标

缺验收标准/派发/项目/日期/范围，应被拦截。
"""


def _write_registry(tmp_path: Path) -> Path:
    """最小执行体注册表（echo 占位命令，禁止生产引用）。"""
    reg_path = tmp_path / "executors.json"
    reg_path.write_text(
        json.dumps(
            {
                "version": "2",
                "executors": [
                    {
                        "角色": "开发执行体",
                        "分类": "可后台 CLI",
                        "当前绑定": "demo",
                        "命令": "echo",
                        "参数模板": "work={work_id}",
                        "工作目录": "",
                        "worktree_base": "",
                        "备注": "测试夹具",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return reg_path


def _base_cfg(tmp_path: Path) -> dict[str, str]:
    return {
        "DATA_DIR": str(tmp_path),
        "EXECUTOR_LOG_DIR": str(tmp_path / "logs"),
        "EXECUTOR_TIMEOUT_SECONDS": "5",
        "EXECUTOR_MAX_CONCURRENT": "1",
        "EXECUTOR_PROBE_URL": "",
    }


@pytest.fixture()
def gate_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """隔离环境：cwd=仓库根夹具、ledger 指向 tmp（不污染生产账本）。"""
    (tmp_path / "card-gate-scope.txt").write_text("scope\n", encoding="utf-8")
    monkeypatch.setenv("CCC_AUDIT_LEDGER", str(tmp_path / "ledger.jsonl"))
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_valid_dsh_card_passes_gate_and_dispatches(gate_env: Path) -> None:
    """合法 DSH 卡过门入池：run_once 正常派发（无 card_gate 拦截）。"""
    reg = load_registry(str(_write_registry(gate_env)))
    store = InMemoryBoardStore()
    card = gate_env / "tst995-gate-e2e.md"
    card.write_text(VALID_CARD, encoding="utf-8")
    store.seed(Work(id="tst995", role="开发执行体", card_path=str(card)))

    summary = run_once(reg, store, _base_cfg(gate_env))
    assert summary["dispatched"] == 1, summary
    # wait=True 模式 echo 即时完成：过门派发且收单回写 = 全链放行
    assert summary["collected"] == 1, summary
    assert [w.id for w in store.list_work(state=State.DONE)] == ["tst995"]
    assert not (gate_env / "logs" / "alerts" / "card-gate.txt").exists()


def test_invalid_dsh_card_voided_with_ledger_alert(gate_env: Path) -> None:
    """故意缺字段卡被拒：作废出池 + ledger card_gate_reject 告警留痕。"""
    reg = load_registry(str(_write_registry(gate_env)))
    store = InMemoryBoardStore()
    card = gate_env / "tst996-gate-bad.md"
    card.write_text(INVALID_CARD, encoding="utf-8")
    store.seed(Work(id="tst996", role="开发执行体", card_path=str(card)))

    summary = run_once(reg, store, _base_cfg(gate_env))
    assert summary["dispatched"] == 0, summary
    voided = store.list_work(state=State.VOIDED)
    assert [w.id for w in voided] == ["tst996"]
    assert any("卡校验门拦截" in p for p in voided[0].problems)

    ledger_rows = [
        json.loads(line)
        for line in (gate_env / "ledger.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    rejects = [r for r in ledger_rows if r.get("action") == "card_gate_reject"]
    assert len(rejects) == 1, ledger_rows
    assert rejects[0]["object_id"] == "tst996"
    assert "卡头缺必填字段" in rejects[0]["detail"]
    assert "验收标准" in rejects[0]["detail"]
    alert = (gate_env / "logs" / "alerts" / "card-gate.txt").read_text(encoding="utf-8")
    assert "tst996" in alert


def test_non_dsh_card_bypasses_gate(gate_env: Path) -> None:
    """非 DSH 卡（存量格式）不受新校验门约束，正常派发。"""
    reg = load_registry(str(_write_registry(gate_env)))
    store = InMemoryBoardStore()
    card = gate_env / "tst997-legacy-format.md"
    card.write_text(
        "# 任务卡 tst997 · 存量格式\n"
        "> 关联：TEST · 执行体：demo · 状态：待分派 · 日期：2026-08-06\n\n"
        "## 目标\nx\n",
        encoding="utf-8",
    )
    store.seed(Work(id="tst997", role="开发执行体", card_path=str(card)))

    summary = run_once(reg, store, _base_cfg(gate_env))
    assert summary["dispatched"] == 1, summary


def test_validate_card_prefix_and_scope_checks(gate_env: Path) -> None:
    """单元：前缀不在 registry / 范围路径不存在 / 日期格式各有对应问题项。"""
    card = gate_env / "zzz999-bad-prefix.md"
    card.write_text(
        VALID_CARD.replace("tst995", "zzz999").replace("项目：tst", "项目：zzz").replace("日期：2026-08-29", "日期：08/29/26").replace(
            "- card-gate-scope.txt", "- no/such/path.txt"
        ),
        encoding="utf-8",
    )
    problems = validate_card(card, repo_root=gate_env)
    assert any("不在项目 registry" in p for p in problems)
    assert any("范围路径不存在: no/such/path.txt" in p for p in problems)
    assert any("日期格式" in p for p in problems)


def test_forbidden_prefix_card_is_rejected_before_dispatch(gate_env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A5：手工放入禁用前缀卡时，card gate 拒单并写入作废状态。"""
    from server.engine import card_gate

    card = gate_env / "ccc001-forbidden.md"
    card.write_text(VALID_CARD.replace("tst995", "ccc001").replace("项目：tst", "项目：ccc"), encoding="utf-8")
    monkeypatch.setattr(card_gate, "forbidden_prefixes", lambda: frozenset({"ccc"}))
    store = InMemoryBoardStore()
    work = Work(id="ccc001", role="开发执行体", card_path=str(card))
    store.seed(work)

    result = card_gate.enforce_card_gate(work, store, gate_env / "logs")

    assert result.passed is False
    assert result.reason == "card_gate_forbidden"
    assert work.state is State.VOIDED
    assert any("禁卡表" in problem for problem in work.problems)


def test_forbidden_prefix_is_filtered_from_file_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A5：store.list_work 与 card gate 同源过滤禁用前缀卡。"""
    from server.board import registry as registry_mod
    from server.engine import store as store_mod
    from server.engine.dispatch import ExecutorRegistry

    dispatch = tmp_path / "dispatch" / "ccc"
    dispatch.mkdir(parents=True)
    card = dispatch / "ccc002-forbidden.md"
    card.write_text(VALID_CARD.replace("tst995", "ccc002").replace("项目：tst", "项目：ccc"), encoding="utf-8")
    monkeypatch.setattr(registry_mod, "forbidden_prefixes", lambda: frozenset({"ccc"}))
    registry = ExecutorRegistry(())
    file_store = store_mod.FileBoardStore(tmp_path / "dispatch", registry)

    assert file_store.list_work() == []
