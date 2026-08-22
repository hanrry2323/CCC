"""test_engine_dispatch — 注册表读取 + 派发决策 + 命令构造。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from server.engine.dispatch import (
    DispatchDecision,
    ExecutorEntry,
    ExecutorRegistry,
    build_command,
    decide,
    decide_work,
    load_registry,
)
from server.engine.task import Work

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = PROJECT_ROOT / "server" / "config" / "executors.example.json"


def _registry(entries: list[tuple[str, str, str]]) -> ExecutorRegistry:
    """构造临时注册表（role, category, binding）。"""
    return ExecutorRegistry(
        tuple(
            ExecutorEntry(role=role, category=category, binding=binding, note="") for role, category, binding in entries
        )
    )


def _write_registry(tmp_path: Path, executors: list[dict]) -> Path:
    """写临时 executors.json；executors 为 dict 列表。"""
    p = tmp_path / "executors.json"
    p.write_text(
        json.dumps({"version": "2", "executors": executors}, ensure_ascii=False),
        encoding="utf-8",
    )
    return p


def _cli_entry(
    role: str = "开发执行体",
    command: str = "echo",
    args_template: str = "work={work_id} card={card_path}",
    workdir: str = "",
) -> ExecutorEntry:
    return ExecutorEntry(
        role=role,
        category="可后台 CLI",
        binding="test",
        note="",
        command=command,
        args_template=args_template,
        workdir=workdir,
    )


class TestWorkerIdAddressing:
    """2026-08-10 标签寻址：执行体字段支持 W 号（W4 等）映射到 worker_id。"""

    def _reg_with_worker_ids(self) -> ExecutorRegistry:
        return ExecutorRegistry(
            (
                ExecutorEntry(role="开发执行体", category="可后台 CLI", binding="OpenCode", note="", worker_id="W4"),
                ExecutorEntry(role="开发执行体", category="可后台 CLI", binding="Claude Code", note="", worker_id="W2"),
                ExecutorEntry(role="验收席", category="可后台 CLI", binding="Claude Code", note="", worker_id="W1"),
            )
        )

    def test_cli_entry_for_worker_id(self) -> None:
        reg = self._reg_with_worker_ids()
        entry = reg.cli_entry_for_worker_id("W4")
        assert entry is not None and entry.binding == "OpenCode"
        assert reg.cli_entry_for_worker_id("W9") is None

    def test_cli_entry_for_binding_accepts_worker_id(self) -> None:
        reg = self._reg_with_worker_ids()
        entry = reg.cli_entry_for_binding("W4")
        assert entry is not None and entry.binding == "OpenCode"
        entry2 = reg.cli_entry_for_binding("OpenCode")
        assert entry2 is not None and entry2.binding == "OpenCode"

    def test_role_for_binding_accepts_worker_id(self) -> None:
        reg = self._reg_with_worker_ids()
        assert reg.role_for_binding("W4") == "开发执行体"
        assert reg.role_for_binding("W1") == "验收席"
        assert reg.role_for_binding("OpenCode") == "开发执行体"

    def test_rows_for_worker_id(self) -> None:
        reg = self._reg_with_worker_ids()
        rows = reg.rows_for_worker_id("W2")
        assert len(rows) == 1 and rows[0].binding == "Claude Code"


class TestLoadRegistry:
    """注册表加载与 §7 校验。"""

    def test_example_registry_loads(self) -> None:
        reg = load_registry(REGISTRY_PATH)
        # 开发(OpenCode) + 维护 + 管理 + Claude/OpenCode 双验收席 + DSH 只读 = 6 行
        assert len(reg.entries) == 6
        cli = reg.cli_entry_for_role("开发执行体")
        assert cli is not None
        # S3（2026-08-22）：开发执行体切 DSH（wrapper 自读提示，注入关闭）
        assert cli.binding == "DSH（S3 切换 · 2026-08-22）"
        assert cli.command == "scripts/dsh-executor.sh"
        assert cli.args_template == "{card_path} {work_id} {worktree} {role}"
        assert cli.inject_hint is False
        cc = reg.cli_entry_for_binding("Claude Code")
        assert cc is not None
        assert cc.role == "验收席"  # F5 定稿：开发仅 OpenCode，Claude Code 为机审验收席
        # 验收席绑定为可后台 CLI（机审）
        acc_rows = [e for e in reg.entries if e.role == "验收席"]
        assert {e.binding for e in acc_rows} == {"Claude Code", "OpenCode"}
        assert all(e.category == "可后台 CLI" for e in acc_rows)
        assert all(e.command for e in acc_rows)

    def test_missing_fields_rejected(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.json"
        bad.write_text('{"executors": [{"角色": "开发执行体"}]}', encoding="utf-8")
        with pytest.raises(ValueError, match="缺字段"):
            load_registry(bad)

    def test_invalid_category_rejected(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.json"
        bad.write_text(
            json.dumps(
                {"executors": [{"角色": "x", "分类": "非法值", "当前绑定": "y", "备注": ""}]},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="分类"):
            load_registry(bad)

    def test_file_not_found(self) -> None:
        with pytest.raises(FileNotFoundError):
            load_registry("/tmp/nonexistent_registry_xyz.json")

    def test_cli_row_requires_command(self, tmp_path: Path) -> None:
        """可后台 CLI 行命令为空 → ValueError（参数模板允许空，表示无参数）。"""
        bad = _write_registry(
            tmp_path,
            [
                {
                    "角色": "开发执行体",
                    "分类": "可后台 CLI",
                    "当前绑定": "OpenCode",
                    "命令": "",
                    "参数模板": "",
                    "工作目录": "",
                    "备注": "",
                }
            ],
        )
        with pytest.raises(ValueError, match="缺派发字段"):
            load_registry(bad)

    def test_cli_row_empty_template_allowed(self, tmp_path: Path) -> None:
        """可后台 CLI 行参数模板为空合法（命令无参数场景，如 false）。"""
        p = _write_registry(
            tmp_path,
            [
                {
                    "角色": "开发执行体",
                    "分类": "可后台 CLI",
                    "当前绑定": "demo",
                    "命令": "false",
                    "参数模板": "",
                    "工作目录": "",
                    "备注": "",
                }
            ],
        )
        reg = load_registry(p)
        assert reg.cli_entry_for_role("开发执行体").command == "false"

    def test_cli_row_unknown_placeholder_rejected(self, tmp_path: Path) -> None:
        """参数模板含未知占位符 → ValueError。"""
        bad = _write_registry(
            tmp_path,
            [
                {
                    "角色": "开发执行体",
                    "分类": "可后台 CLI",
                    "当前绑定": "OpenCode",
                    "命令": "echo",
                    "参数模板": "{unknown_placeholder}",
                    "工作目录": "",
                    "备注": "",
                }
            ],
        )
        with pytest.raises(ValueError, match="未知占位符"):
            load_registry(bad)

    def test_manual_gui_row_does_not_require_command(self, tmp_path: Path) -> None:
        """手动 GUI 行不要求命令/参数模板（留空合法）。"""
        p = _write_registry(
            tmp_path,
            [
                {
                    "角色": "开发执行体",
                    "分类": "手动 GUI",
                    "当前绑定": "Trae",
                    "命令": "",
                    "参数模板": "",
                    "工作目录": "",
                    "备注": "",
                }
            ],
        )
        reg = load_registry(p)
        assert len(reg.entries) == 1


class TestDecide:
    """派发决策两分支 + 不派发。"""

    def test_auto_for_dev_role(self) -> None:
        """开发执行体含「可后台 CLI」行 → AUTO。"""
        reg = load_registry(REGISTRY_PATH)
        assert decide("开发执行体", reg) is DispatchDecision.AUTO

    def test_auto_for_ops_role(self) -> None:
        """维护执行体（可后台 CLI）→ AUTO。"""
        reg = load_registry(REGISTRY_PATH)
        assert decide("维护执行体", reg) is DispatchDecision.AUTO

    def test_manual_for_gui_only_role(self) -> None:
        """角色仅「手动 GUI」行 → MANUAL（挂起等人）。"""
        reg = _registry([("开发执行体", "手动 GUI", "Trae")])
        assert decide("开发执行体", reg) is DispatchDecision.MANUAL

    def test_not_dispatchable_for_staff(self) -> None:
        """管理席（分类「—」）→ 不派发；验收席现为可后台 CLI（机审）→ AUTO。"""
        reg = load_registry(REGISTRY_PATH)
        assert decide("管理席", reg) is DispatchDecision.NONE
        assert decide("验收席", reg) is DispatchDecision.AUTO

    def test_not_dispatchable_unknown_role(self) -> None:
        """未知角色 → 不派发。"""
        reg = load_registry(REGISTRY_PATH)
        assert decide("不存在的角色", reg) is DispatchDecision.NONE


class TestDecideWork:
    """T39：卡头执行体绑定优先派发决策。

    覆盖用例：① Trae 手动 GUI 但角色含 CLI 行 → MANUAL；
    ② Claude Code CLI → AUTO；②b 已退役 OpenCode 名 → 回退角色 AUTO；
    ③ Codex（—）→ NONE；④ 无 executor → 回退角色 AUTO；
    ⑤ 未知 executor → 回退角色决策；⑥+ 现有回归。
    """

    def test_trae_manual_gui_even_if_role_has_cli(self, tmp_path: Path) -> None:
        """① 卡头 Trae（手动 GUI）但角色含 CLI 行 → MANUAL（本地注册表；模板已停用 Trae）。"""
        reg_path = _write_registry(
            tmp_path,
            [
                {
                    "角色": "开发执行体",
                    "分类": "手动 GUI",
                    "当前绑定": "Trae",
                    "命令": "",
                    "参数模板": "",
                    "工作目录": "",
                    "备注": "测试用",
                },
                {
                    "角色": "开发执行体",
                    "分类": "可后台 CLI",
                    "当前绑定": "Claude Code",
                    "命令": "claude",
                    "参数模板": "-p {card_path}",
                    "工作目录": "",
                    "备注": "",
                },
            ],
        )
        reg = load_registry(reg_path)
        work = Work(id="t39-1", role="开发执行体", executor="Trae")
        assert decide_work(work, reg) is DispatchDecision.MANUAL

    def test_unknown_trae_falls_back_without_example_row(self) -> None:
        """模板无 Trae 行时，卡头绑 Trae → 未知绑定回退角色（开发执行体仍 AUTO）。"""
        reg = load_registry(REGISTRY_PATH)
        work = Work(id="t39-1b", role="开发执行体", executor="Trae")
        assert decide_work(work, reg) is DispatchDecision.AUTO

    def test_claude_code_binding_auto(self) -> None:
        """② 卡头 Claude Code（可后台 CLI）→ AUTO（真实拉起）。"""
        reg = load_registry(REGISTRY_PATH)
        work = Work(id="t39-2", role="开发执行体", executor="Claude Code")
        assert decide_work(work, reg) is DispatchDecision.AUTO

    def test_retired_opencode_binding_falls_back_to_role(self) -> None:
        """②b OpenCode 已退出 example 注册表 → 未知绑定回退角色决策（开发执行体仍 AUTO）。"""
        reg = load_registry(REGISTRY_PATH)
        work = Work(id="t39-2b", role="开发执行体", executor="OpenCode")
        assert decide_work(work, reg) is DispatchDecision.AUTO

    def test_codex_staff_binding_none(self) -> None:
        """③ 卡头 Codex（分类「—」管理/验收席）→ NONE 不派发。"""
        reg = load_registry(REGISTRY_PATH)
        work = Work(id="t39-3", role="管理席", executor="Codex")
        assert decide_work(work, reg) is DispatchDecision.NONE

    def test_no_executor_falls_back_to_role_auto(self) -> None:
        """④ 无 executor（空串）→ 回退 decide(role)；开发执行体 → AUTO。"""
        reg = load_registry(REGISTRY_PATH)
        work = Work(id="t39-4", role="开发执行体", executor="")
        assert decide_work(work, reg) is DispatchDecision.AUTO

    def test_unknown_executor_falls_back_to_role(self) -> None:
        """⑤ 未知 executor（不在注册表）→ 回退 decide(role)。

        role=开发执行体 → AUTO；role=管理席 → NONE；role=空 → NONE。
        """
        reg = load_registry(REGISTRY_PATH)
        # 已知角色 + 未知执行体 → 沿用角色决策
        assert decide_work(Work(id="t39-5a", role="开发执行体", executor="GhostTool"), reg) is DispatchDecision.AUTO
        assert decide_work(Work(id="t39-5b", role="管理席", executor="GhostTool"), reg) is DispatchDecision.NONE
        # 空角色 + 未知执行体 → NONE
        assert decide_work(Work(id="t39-5c", role="", executor="GhostTool"), reg) is DispatchDecision.NONE

    def test_no_executor_unknown_role_none(self) -> None:
        """④ 补充：无 executor + 未知角色 → NONE（回退路径）。"""
        reg = load_registry(REGISTRY_PATH)
        work = Work(id="t39-4b", role="幽灵角色", executor="")
        assert decide_work(work, reg) is DispatchDecision.NONE

    def test_decide_work_consistent_with_decide_when_no_executor(self) -> None:
        """⑥ 回归：无 executor 时 decide_work 与 decide 结果一致（不破坏 T32 行为）。"""
        reg = load_registry(REGISTRY_PATH)
        for role in ("开发执行体", "维护执行体", "管理席", "验收席", "未知角色"):
            work = Work(id=f"reg-{role}", role=role, executor="")
            assert decide_work(work, reg) is decide(role, reg)

    def test_manual_dispatch_not_dispatched(self) -> None:
        """⑦ T53：卡头「派发：manual」→ NONE（管理席派发，Engine 不自动拉，保持待分派）。

        即使执行体绑定（Claude Code）是可后台 CLI，manual 卡也不得被 Engine 自动拉起
        （消灭 T48/T49/T50 假「执行中」）。
        """
        reg = load_registry(REGISTRY_PATH)
        work = Work(id="t53-manual", role="维护执行体", executor="Claude Code", dispatch="manual")
        assert decide_work(work, reg) is DispatchDecision.NONE

    def test_engine_dispatch_auto(self) -> None:
        """⑧ T53：卡头「派发：engine」（缺省）→ 按绑定正常 AUTO 派发。"""
        reg = load_registry(REGISTRY_PATH)
        work = Work(id="t53-engine", role="维护执行体", executor="Claude Code", dispatch="engine")
        assert decide_work(work, reg) is DispatchDecision.AUTO

    def test_epic_not_dispatched(self) -> None:
        """T57: Epic cards are not dispatched (decide_work returns NONE)."""
        reg = load_registry(REGISTRY_PATH)
        work = Work(id="t57-epic", role="开发执行体", executor="OpenCode", type="epic")
        assert decide_work(work, reg) is DispatchDecision.NONE

    def test_project_level_executor_isolation(self) -> None:
        """T57: Project-level executor isolation in ExecutorRegistry and decide_work."""
        from server.engine.dispatch import ExecutorRegistry, ExecutorEntry, decide_work

        entry_global = ExecutorEntry(
            role="开发执行体", category="可后台 CLI", binding="OpenCode", note="", command="opencode", project=""
        )
        entry_qb = ExecutorEntry(
            role="开发执行体", category="可后台 CLI", binding="QBExecutor", note="", command="qb-exec", project="qb"
        )

        reg = ExecutorRegistry((entry_global, entry_qb))

        # 1. Global card (no project specified) -> should match global entry
        work_global = Work(id="t57-global", role="开发执行体", executor="OpenCode", project="")
        assert decide_work(work_global, reg) is DispatchDecision.AUTO

        # 2. qb project card -> matches qb specific entry
        work_qb = Work(id="t57-qb", role="开发执行体", executor="QBExecutor", project="qb")
        assert decide_work(work_qb, reg) is DispatchDecision.AUTO

        # 3. qb project card with global executor -> should fallback to global if project specific binding not found
        work_qb_global_exec = Work(id="t57-qb-fallback", role="开发执行体", executor="OpenCode", project="qb")
        assert decide_work(work_qb_global_exec, reg) is DispatchDecision.AUTO

        # 4. other project card requesting QBExecutor -> should NOT match qb-specific entry.
        # If there is no global entry for the role, it must return NONE.
        reg_no_global = ExecutorRegistry((entry_qb,))
        work_other_qb_exec = Work(id="t57-other", role="开发执行体", executor="QBExecutor", project="other")
        assert decide_work(work_other_qb_exec, reg_no_global) is DispatchDecision.NONE


class TestBuildCommand:
    """命令构造（占位符替换 + argv 向量）。"""

    def test_renders_all_placeholders(self) -> None:
        """四个占位符全部替换。"""
        entry = _cli_entry(args_template="--dir {workdir} --card {card_path} --role {role} {work_id}")
        cmd = build_command(
            entry,
            work_id="w1",
            role="开发执行体",
            card_path="/path/T1.md",
            default_workdir="/data",
        )
        assert cmd == [
            "echo",
            "--dir",
            "/data",
            "--card",
            "/path/T1.md",
            "--role",
            "开发执行体",
            "w1",
        ]

    def test_uses_entry_workdir_over_default(self) -> None:
        """entry.workdir 非空时优先用 entry.workdir。"""
        entry = _cli_entry(args_template="{workdir}", workdir="/custom")
        cmd = build_command(entry, work_id="w1", role="r", card_path="", default_workdir="/data")
        assert cmd == ["echo", "/custom"]

    def test_uses_default_workdir_when_entry_empty(self) -> None:
        """entry.workdir 留空时用 default_workdir。"""
        entry = _cli_entry(args_template="{workdir}", workdir="")
        cmd = build_command(entry, work_id="w1", role="r", card_path="", default_workdir="/data")
        assert cmd == ["echo", "/data"]

    def test_unknown_placeholder_kept_literal(self) -> None:
        """未知占位符（绕过校验时）保留原样，不抛 KeyError。"""
        # 直接构造 ExecutorEntry 绕过 load_registry 校验
        entry = ExecutorEntry(
            role="r",
            category="可后台 CLI",
            binding="b",
            note="",
            command="echo",
            args_template="{unknown}",
            workdir="",
        )
        cmd = build_command(entry, work_id="w1", role="r", card_path="", default_workdir="")
        assert cmd == ["echo", "{unknown}"]

    def test_rejects_non_cli_entry(self) -> None:
        """手动 GUI 行调用 build_command → ValueError。"""
        entry = ExecutorEntry(
            role="r",
            category="手动 GUI",
            binding="b",
            note="",
            command="echo",
            args_template="x",
            workdir="",
        )
        with pytest.raises(ValueError, match="仅适用于可后台 CLI"):
            build_command(entry, work_id="w1", role="r", card_path="", default_workdir="")

    def test_rejects_empty_command(self) -> None:
        """命令为空 → ValueError。"""
        entry = ExecutorEntry(
            role="r",
            category="可后台 CLI",
            binding="b",
            note="",
            command="",
            args_template="x",
            workdir="",
        )
        with pytest.raises(ValueError, match="命令为空"):
            build_command(entry, work_id="w1", role="r", card_path="", default_workdir="")

    def test_quoted_args_split_correctly(self) -> None:
        """含引号的参数模板被 shlex 正确拆分。"""
        entry = _cli_entry(args_template='-p "请按任务卡 {card_path} 完成 {work_id}"')
        cmd = build_command(entry, work_id="w1", role="r", card_path="/path/T1.md", default_workdir="/data")
        assert cmd == ["echo", "-p", "请按任务卡 /path/T1.md 完成 w1"]

    def test_build_command_with_worktree(self) -> None:
        """参数模板含 {worktree} 且传入 worktree 时能正确渲染。"""
        entry = _cli_entry(args_template='--dir {worktree} -p "完成 {work_id}"')
        cmd = build_command(
            entry,
            work_id="T64",
            role="r",
            card_path="/path/T64.md",
            default_workdir="/data",
            worktree="/Users/fan/program/ccc-dev-ws-t64",
        )
        assert cmd == ["echo", "--dir", "/Users/fan/program/ccc-dev-ws-t64", "-p", "完成 T64"]


class TestDshExecutor:
    """S3：DSH 开发执行体——build_command + inject_hint 跳过（wrapper 自读提示）。"""

    def test_dsh_executor_builds_positional_argv(self) -> None:
        """dsh-executor.sh 位置参数模板正确构建 argv（card_path work_id worktree role）。"""
        entry = ExecutorEntry(
            role="开发执行体",
            category="可后台 CLI",
            binding="dsh",
            note="",
            command="scripts/dsh-executor.sh",
            args_template="{card_path} {work_id} {worktree} {role}",
            workdir="",
            inject_hint=False,
        )
        cmd = build_command(
            entry,
            work_id="dshtest1",
            role="开发执行体",
            card_path="docs/dispatch/ccc/ccc001.md",
            default_workdir="/data",
            worktree="/tmp/wt/dshtest1",
        )
        assert cmd == [
            "scripts/dsh-executor.sh",
            "docs/dispatch/ccc/ccc001.md",
            "dshtest1",
            "/tmp/wt/dshtest1",
            "开发执行体",
        ]

    def test_registry_loads_inject_hint_from_json(self, tmp_path) -> None:
        """JSON「注入提示」字段 → ExecutorEntry.inject_hint（DSH wrapper 关闭注入）。"""
        import json as _json

        from server.engine.dispatch import load_registry

        cfg = tmp_path / "executors.json"
        cfg.write_text(_json.dumps({
            "version": "2",
            "executors": [{
                "角色": "开发执行体",
                "分类": "可后台 CLI",
                "当前绑定": "DSH",
                "命令": "scripts/dsh-executor.sh",
                "参数模板": "{card_path} {work_id} {worktree} {role}",
                "工作目录": "",
                "worktree_base": "",
                "注入提示": False,
                "备注": "DSH 开发执行体",
            }]
        }, ensure_ascii=False), encoding="utf-8")
        reg = load_registry(cfg)
        entry = reg.cli_entry_for_role("开发执行体")
        assert entry.command == "scripts/dsh-executor.sh"
        assert entry.inject_hint is False
