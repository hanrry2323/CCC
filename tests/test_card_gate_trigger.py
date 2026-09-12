"""T-CCC-PLUGIN-01 序1：card_gate 触发条件集合化后，跨机执行体 PI@195 走五项校验。

验证点：
1. 执行体=PI@195 的合法卡 → 通过 gate（不再像单值等值时被静默跳过）。
2. 执行体=PI@195 的非法卡（缺实现要求 / 范围路径不存在）→ 拦截。
3. 执行体=DSH 老卡行为不变（老用例全绿，此处保一个门禁判据）。
4. 未受管执行体（CC@195 等）→ 仍直接放行。
5. 与 executors.json 槽位一致性：注册表含 PI@195。

风格对齐 server/tests/test_card_gate.py 的 fixture/断言方式。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from server.engine.card_gate import enforce_card_gate, validate_card
from server.engine.store import InMemoryBoardStore
from server.engine.task import State, Work


def _card_text(
    *,
    executor: str,
    title: str = "tst981 · PI@195 合法卡",
    state: str = "待分派",
    project: str = "tst",
    scope: str = "card-gate-scope.txt",
    with_impl: bool = True,
    with_acceptance: bool = True,
) -> str:
    """生成符合五项校验的卡文本；参数化可构造非法卡。"""
    impl = "## 实现要求\n\n最小实现，走真实校验门。\n\n" if with_impl else ""
    acceptance = (
        "## 验收标准\n\n1. gate 返回 passed。\n"
        if with_acceptance
        else ""
    )
    return (
        f"# 任务卡 {title}\n\n"
        f"> 关联：ccc-plan-053 · 执行体：{executor} · 验收：Claude Code · 状态：{state} · 派发：engine · 项目：{project} · 日期：2026-09-12\n\n"
        "## 目标\n\n验证 PI@195 卡过校验门。\n\n"
        f"{impl}"
        "## 红线\n\n不碰运行面与账本。\n\n"
        f"## 范围\n\n- {scope}\n\n"
        "## 步骤\n\n1. 派发执行。\n\n"
        f"{acceptance}"
    )


def _write_registry(tmp_path: Path, include_pi195: bool = True) -> Path:
    """最小执行体注册表（含 PI@195 槽位时用 echo 占位，禁止生产引用）。"""
    executors = [
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
    ]
    if include_pi195:
        executors.append(
            {
                "角色": "开发执行体-195",
                "分类": "可后台 CLI",
                "当前绑定": "PI@195",
                "命令": "echo",
                "参数模板": "{card_path} {work_id} {worktree} {role} {biz_worktree}",
                "工作目录": "",
                "worktree_base": "",
                "备注": "测试夹具",
                "worker_id": "PI@195",
                "注入提示": False,
            }
        )
    reg_path = tmp_path / "executors.json"
    reg_path.write_text(
        json.dumps({"version": "2", "executors": executors}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return reg_path


def _bindings(reg_path: Path) -> list[str]:
    from server.engine.dispatch import load_registry

    return [e.binding for e in load_registry(str(reg_path)).entries]


@pytest.fixture()
def gate_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """隔离环境：cwd=仓库根夹具、ledger 指向 tmp（不污染生产账本）。"""
    (tmp_path / "card-gate-scope.txt").write_text("scope\n", encoding="utf-8")
    monkeypatch.setenv("CCC_AUDIT_LEDGER", str(tmp_path / "ledger.jsonl"))
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _seed_work(card: Path, executor: str) -> Work:
    return Work(id=card.stem, role="开发执行体", card_path=str(card), executor=executor)


def test_pi195_valid_card_passes_gate(gate_env: Path) -> None:
    """执行体=PI@195 的合法卡 → passed（此前单值等值会静默跳过，走不到五项校验）。"""
    card = gate_env / "tst981-valid-pi195.md"
    card.write_text(_card_text(executor="PI@195"), encoding="utf-8")
    work = _seed_work(card, "PI@195")

    result = enforce_card_gate(work, InMemoryBoardStore(), gate_env / "logs", repo_root=gate_env)

    assert result.passed is True
    assert work.state is not State.VOIDED
    assert not (gate_env / "logs" / "alerts" / "card-gate.txt").exists()


def test_pi195_valid_card_passes_five_checks_unit(gate_env: Path) -> None:
    """单元层：PI@195 合法卡经 validate_card 返回空问题清单（五项校验真实生效）。"""
    card = gate_env / "tst981-unit-valid.md"
    card.write_text(_card_text(executor="PI@195"), encoding="utf-8")

    problems = validate_card(card, repo_root=gate_env)

    assert problems == []


def test_pi195_missing_impl_section_is_rejected(gate_env: Path) -> None:
    """执行体=PI@195 的非法卡（缺实现要求）→ 拦截。"""
    card = gate_env / "tst982-missing-impl.md"
    card.write_text(_card_text(executor="PI@195", title="tst982 · 缺实现要求", with_impl=False), encoding="utf-8")
    work = _seed_work(card, "PI@195")

    result = enforce_card_gate(work, InMemoryBoardStore(), gate_env / "logs", repo_root=gate_env)

    assert result.passed is False
    assert result.reason == "card_gate"
    assert work.state is State.VOIDED
    assert any("实现要求" in p for p in work.problems)
    assert any("卡校验门拦截" in p for p in work.problems)
    assert (gate_env / "logs" / "alerts" / "card-gate.txt").exists()


def test_pi195_scope_path_missing_is_rejected(gate_env: Path) -> None:
    """执行体=PI@195 的非法卡（范围路径不存在）→ 拦截。"""
    card = gate_env / "tst983-bad-scope.md"
    card.write_text(
        _card_text(executor="PI@195", title="tst983 · 范围路径不存在", scope="no/such/path.txt"),
        encoding="utf-8",
    )
    work = _seed_work(card, "PI@195")

    result = enforce_card_gate(work, InMemoryBoardStore(), gate_env / "logs", repo_root=gate_env)

    assert result.passed is False
    assert result.reason == "card_gate"
    assert work.state is State.VOIDED
    assert any("范围路径不存在" in p for p in work.problems)


def test_dsh_legacy_behavior_unchanged(gate_env: Path) -> None:
    """执行体=DSH 老卡行为不变：合法放行 / 非法拦截（与老用例同判据）。"""
    card = gate_env / "tst984-dsh-valid.md"
    card.write_text(_card_text(executor="DSH", title="tst984 · DSH 合法卡"), encoding="utf-8")
    work = _seed_work(card, "DSH")

    assert enforce_card_gate(work, InMemoryBoardStore(), gate_env / "logs", repo_root=gate_env).passed is True

    bad = gate_env / "tst985-dsh-bad.md"
    bad.write_text(_card_text(executor="DSH", title="tst985 · DSH 缺实现要求", with_impl=False), encoding="utf-8")
    work2 = _seed_work(bad, "DSH")
    res2 = enforce_card_gate(work2, InMemoryBoardStore(), gate_env / "logs", repo_root=gate_env)

    assert res2.passed is False
    assert res2.reason == "card_gate"
    assert work2.state is State.VOIDED


def test_unmanaged_executor_cc195_still_passes(gate_env: Path) -> None:
    """未受管执行体（CC@195）不在受管集合 → 仍直接放行（存量/测试夹具语义不变）。"""
    card = gate_env / "tst986-cc195.md"
    card.write_text(
        _card_text(
            executor="CC@195",
            title="tst986 · 未受管 CC@195",
            with_impl=False,
            with_acceptance=False,
            scope="no/such/path.txt",
        ),
        encoding="utf-8",
    )
    work = _seed_work(card, "CC@195")

    result = enforce_card_gate(work, InMemoryBoardStore(), gate_env / "logs", repo_root=gate_env)

    assert result.passed is True
    assert work.state is not State.VOIDED


def test_registry_contains_pi195_slot(tmp_path: Path) -> None:
    """executors.json 注册表含 PI@195 槽位（配套变更一致性）。"""
    reg_path = _write_registry(tmp_path, include_pi195=True)

    assert "PI@195" in _bindings(reg_path)
