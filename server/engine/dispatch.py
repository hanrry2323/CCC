"""执行体注册表读取 + 派发决策 + 命令构造（契约 §7 → §2）。

负责编排决策：按注册表分类决定派发方式（可后台 CLI → 自动拉起 / 手动 GUI → 挂起等人）。
真实拉起执行体由 main.py 的派发管道执行；本模块只产出命令向量。

用法：
    from server.engine.dispatch import load_registry, decide, build_command, DispatchDecision

    reg = load_registry(cfg["EXECUTOR_REGISTRY_PATH"])
    decision = decide(work.role, reg)
    if decision is DispatchDecision.AUTO:
        entry = reg.cli_entry_for_role(work.role)
        cmd = build_command(entry, work, card_path="/path/card.md", default_workdir=cfg["DATA_DIR"])
        # cmd = ["opencode", "--dir", "/data", "-p", "请按任务卡 /path/card.md 完成 work w1"]
"""

from __future__ import annotations

import json
import logging
import shlex
from dataclasses import dataclass
from enum import Enum

try:
    from enum import StrEnum
except ImportError:
    class StrEnum(str, Enum):  # noqa: UP042
        pass

from pathlib import Path
from string import Formatter
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from server.engine.task import Work

logger = logging.getLogger("ccc.engine.dispatch")

# 契约 §7：分类只允许「可后台 CLI」/「手动 GUI」；管理席/验收席不做执行，分类「—」
VALID_CATEGORIES: frozenset[str] = frozenset({"可后台 CLI", "手动 GUI", "—"})
# 契约 §7：注册表每行必填字段
REQUIRED_FIELDS: frozenset[str] = frozenset({"角色", "分类", "当前绑定", "备注"})
# 「可后台 CLI」行必填的派发字段（T32 真实派发闭环）
CLI_REQUIRED_FIELDS: frozenset[str] = frozenset({"命令", "参数模板"})
# build_command 支持的占位符（参数模板里允许引用）
ALLOWED_PLACEHOLDERS: frozenset[str] = frozenset({"work_id", "card_path", "role", "workdir"})


class DispatchDecision(StrEnum):
    """派发决策。"""

    AUTO = "auto"      # 可后台 CLI → Engine 自动拉起
    MANUAL = "manual"  # 手动 GUI → 挂起等人
    NONE = "none"      # 管理席/验收席（分类「—」）/未知角色 → 不派发


@dataclass(frozen=True)
class ExecutorEntry:
    """注册表一行（契约 §7 字段 + T32 派发字段）。

    Attributes:
        role: 角色（如「开发执行体」）。
        category: 分类（「可后台 CLI」/「手动 GUI」/「—」）。
        binding: 当前绑定工具名（如 OpenCode）。
        note: 备注。
        command: 启动命令（可后台 CLI 必填，如 `opencode`）。
        args_template: 参数模板，含 {work_id}/{card_path}/{role}/{workdir} 占位符。
        workdir: 工作目录（留空则用 config 的 DATA_DIR）。
        project: 项目级绑定（按项目隔离）。
    """

    role: str
    category: str
    binding: str
    note: str
    command: str = ""
    args_template: str = ""
    workdir: str = ""
    project: str = ""


@dataclass(frozen=True)
class ExecutorRegistry:
    """契约 §7 注册表。"""

    entries: tuple[ExecutorEntry, ...]

    def rows_for_role(self, role: str, project: str = "") -> list[ExecutorEntry]:
        """返回该角色下的全部注册行（开发执行体可有多行）。优先匹配项目。"""
        role_entries = [e for e in self.entries if e.role == role]
        if project:
            proj_entries = [e for e in role_entries if e.project == project]
            if proj_entries:
                return proj_entries
        return [e for e in role_entries if not e.project]

    def rows_for_binding(self, tool_name: str, project: str = "") -> list[ExecutorEntry]:
        """返回与工具名（卡头「执行体」绑定）匹配的全部注册行（T39）。优先匹配项目。"""
        binding_entries = [e for e in self.entries if e.binding == tool_name]
        if project:
            proj_entries = [e for e in binding_entries if e.project == project]
            if proj_entries:
                return proj_entries
        return [e for e in binding_entries if not e.project]

    def cli_entry_for_role(self, role: str, project: str = "") -> ExecutorEntry | None:
        """返回该角色的首个「可后台 CLI」行；无则 None。优先匹配项目。"""
        rows = self.rows_for_role(role, project=project)
        for e in rows:
            if e.category == "可后台 CLI":
                return e
        return None

    def cli_entry_for_binding(self, tool_name: str, project: str = "") -> ExecutorEntry | None:
        """返回与工具名匹配的首个「可后台 CLI」行；无则 None（T39）。优先匹配项目。"""
        rows = self.rows_for_binding(tool_name, project=project)
        for e in rows:
            if e.category == "可后台 CLI":
                return e
        return None

    def role_for_binding(self, tool_name: str, project: str = "") -> str | None:
        """反向查找：工具名 → 角色（优先可后台 CLI 行）。优先匹配项目。"""
        rows = self.rows_for_binding(tool_name, project=project)
        for e in rows:
            if e.category == "可后台 CLI":
                return e.role
        for e in rows:
            return e.role
        return None


class _SafeFormatDict(dict):
    """format_map 缺键时保留占位符原样，不抛 KeyError。"""

    def __missing__(self, key: str) -> str:  # type: ignore[override]
        return "{" + key + "}"


def load_registry(path: Path | str) -> ExecutorRegistry:
    """从 executors.json 加载注册表；校验 §7 字段 + 分类合法 + 可后台 CLI 行派发字段。

    Raises:
        FileNotFoundError: 注册表文件不存在。
        ValueError: JSON 解析失败、缺字段、分类非法、或可后台 CLI 行缺命令/参数模板。
    """
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"executor registry not found: {p}")
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"executor registry 解析失败: {p} ({exc})") from exc
    executors = data.get("executors")
    if not isinstance(executors, list):
        raise ValueError(f"executor registry 缺少 executors 数组: {p}")
    entries: list[ExecutorEntry] = []
    for idx, raw in enumerate(executors):
        missing = REQUIRED_FIELDS - raw.keys()
        if missing:
            raise ValueError(f"executors[{idx}] 缺字段: {sorted(missing)}")
        category = raw["分类"]
        if category not in VALID_CATEGORIES:
            raise ValueError(
                f"executors[{idx}] 分类 '{category}' 非法 "
                f"(allowed: {sorted(VALID_CATEGORIES)})"
            )
        command = raw.get("命令", "")
        args_template = raw.get("参数模板", "")
        workdir = raw.get("工作目录", "")
        # 可后台 CLI 行必须有命令（参数模板允许空，表示无参数）
        if category == "可后台 CLI":
            if not command:
                raise ValueError(
                    f"executors[{idx}] 可后台 CLI 行缺派发字段: ['命令']"
                )
            # 校验参数模板占位符合法（模板非空时）
            if args_template:
                _validate_placeholders(args_template, idx)
        entries.append(
            ExecutorEntry(
                role=raw["角色"],
                category=category,
                binding=raw["当前绑定"],
                note=raw["备注"],
                command=command,
                args_template=args_template,
                workdir=workdir,
                project=raw.get("项目", ""),
            )
        )
    return ExecutorRegistry(tuple(entries))


def _validate_placeholders(template: str, idx: int) -> None:
    """校验参数模板里的占位符都在 ALLOWED_PLACEHOLDERS 内。"""
    for _literal, field_name, _spec, _conv in Formatter().parse(template):
        if field_name and field_name not in ALLOWED_PLACEHOLDERS:
            raise ValueError(
                f"executors[{idx}] 参数模板含未知占位符 '{field_name}' "
                f"(allowed: {sorted(ALLOWED_PLACEHOLDERS)})"
            )


def decide(role: str, registry: ExecutorRegistry, project: str = "") -> DispatchDecision:
    """按注册表分类做派发决策（契约 §7 → §2）。

    - 角色命中「可后台 CLI」行 → AUTO（Engine 自动拉起）
    - 无 CLI 行但命中「手动 GUI」行 → MANUAL（挂起等人）
    - 其余（席行「—」/ 未知角色）→ NONE（不派发）
    """
    rows = registry.rows_for_role(role, project=project)
    if any(r.category == "可后台 CLI" for r in rows):
        return DispatchDecision.AUTO
    if any(r.category == "手动 GUI" for r in rows):
        return DispatchDecision.MANUAL
    return DispatchDecision.NONE


def decide_work(work: Work, registry: ExecutorRegistry) -> DispatchDecision:
    """按卡头「执行体」绑定优先做派发决策（T39）。

    解决 T38 插曲：卡头指定手动 GUI 执行体（如 Trae）时，不应因角色含 CLI 行而自动拉起。

    决策顺序：
    1. 有 `work.executor`（卡头指定执行体）→ 按 binding 找注册表行：
       - 命中行含「可后台 CLI」→ AUTO；
       - 仅命中「手动 GUI」→ MANUAL；
       - 仅命中「—」（管理/验收席）→ NONE；
       - 未命中任何行（未知执行体）→ 回退 `decide(work.role, registry)`。
    2. 无 `work.executor`（卡未指定执行体）→ 回退 `decide(work.role, registry)`（现行为不变）。

    Args:
        work: 待派发的 work 卡（含 executor / dispatch 字段）。
        registry: 执行体注册表。

    Returns:
        DispatchDecision.AUTO / MANUAL / NONE。
    """
    if work.type == "epic":
        logger.info("Epic 卡不派发: work=%s", work.id)
        return DispatchDecision.NONE
    # T53：卡头「派发：manual」→ 管理席派发，Engine 不自动拉，保持待分派（消灭假「执行中」）。
    if work.dispatch == "manual":
        logger.info("manual 卡由管理席派发，Engine 不自动拉: work=%s", work.id)
        return DispatchDecision.NONE
    if work.executor:
        rows = registry.rows_for_binding(work.executor, project=work.project)
        if rows:
            if any(r.category == "可后台 CLI" for r in rows):
                return DispatchDecision.AUTO
            if any(r.category == "手动 GUI" for r in rows):
                return DispatchDecision.MANUAL
            return DispatchDecision.NONE
        # 未命中 binding → 回退角色决策（未知执行体）
    return decide(work.role, registry, project=work.project)


def build_command(
    entry: ExecutorEntry,
    work_id: str,
    role: str,
    card_path: str,
    default_workdir: str,
) -> list[str]:
    """按注册表条目的命令 + 参数模板生成 argv 向量（绝不写死工具名）。

    Args:
        entry: 注册表「可后台 CLI」行。
        work_id: work 标识。
        role: 角色名。
        card_path: 任务卡路径。
        default_workdir: entry.workdir 留空时用此值（来自 config 的 DATA_DIR）。

    Returns:
        argv 列表，如 `["opencode", "--dir", "/data", "-p", "请按..."]`。

    Raises:
        ValueError: entry 不是可后台 CLI 行、或命令为空。
    """
    if entry.category != "可后台 CLI":
        raise ValueError(
            f"build_command 仅适用于可后台 CLI 行，收到分类 '{entry.category}'"
        )
    if not entry.command:
        raise ValueError("可后台 CLI 行命令为空，无法构造启动命令")

    workdir = entry.workdir or default_workdir
    rendered = entry.args_template.format_map(
        _SafeFormatDict(
            work_id=work_id,
            card_path=card_path,
            role=role,
            workdir=workdir,
        )
    )
    args = shlex.split(rendered)
    return [entry.command, *args]
