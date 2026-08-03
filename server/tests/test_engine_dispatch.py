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
    load_registry,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = PROJECT_ROOT / "server" / "config" / "executors.example.json"


def _registry(entries: list[tuple[str, str, str]]) -> ExecutorRegistry:
    """构造临时注册表（role, category, binding）。"""
    return ExecutorRegistry(
        tuple(
            ExecutorEntry(role=role, category=category, binding=binding, note="")
            for role, category, binding in entries
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


class TestLoadRegistry:
    """注册表加载与 §7 校验。"""

    def test_example_registry_loads(self) -> None:
        reg = load_registry(REGISTRY_PATH)
        assert len(reg.entries) == 5
        # 开发执行体含可后台 CLI 行，且有命令字段
        cli = reg.cli_entry_for_role("开发执行体")
        assert cli is not None
        assert cli.command == "opencode"
        assert "{work_id}" in cli.args_template

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
        """管理席 / 验收席（分类「—」）→ 不派发。"""
        reg = load_registry(REGISTRY_PATH)
        assert decide("管理席", reg) is DispatchDecision.NONE
        assert decide("验收席", reg) is DispatchDecision.NONE

    def test_not_dispatchable_unknown_role(self) -> None:
        """未知角色 → 不派发。"""
        reg = load_registry(REGISTRY_PATH)
        assert decide("不存在的角色", reg) is DispatchDecision.NONE


class TestBuildCommand:
    """命令构造（占位符替换 + argv 向量）。"""

    def test_renders_all_placeholders(self) -> None:
        """四个占位符全部替换。"""
        entry = _cli_entry(
            args_template="--dir {workdir} --card {card_path} --role {role} {work_id}"
        )
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
        cmd = build_command(
            entry, work_id="w1", role="r", card_path="", default_workdir="/data"
        )
        assert cmd == ["echo", "/custom"]

    def test_uses_default_workdir_when_entry_empty(self) -> None:
        """entry.workdir 留空时用 default_workdir。"""
        entry = _cli_entry(args_template="{workdir}", workdir="")
        cmd = build_command(
            entry, work_id="w1", role="r", card_path="", default_workdir="/data"
        )
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
        cmd = build_command(
            entry, work_id="w1", role="r", card_path="/path/T1.md", default_workdir="/data"
        )
        assert cmd == ["echo", "-p", "请按任务卡 /path/T1.md 完成 w1"]
