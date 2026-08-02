"""执行体注册表读取 + 派发决策（契约 §7 → §2）。

只做编排决策，不真拉执行体；「模拟拉起」由 main 写日志（T4 前）。

用法：
    from server.engine.dispatch import load_registry, decide, DispatchDecision

    reg = load_registry(cfg["EXECUTOR_REGISTRY_PATH"])
    decision = decide(work.role, reg)
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

# 契约 §7：分类只允许「可后台 CLI」/「手动 GUI」；管理席/验收席不做执行，分类「—」
VALID_CATEGORIES: frozenset[str] = frozenset({"可后台 CLI", "手动 GUI", "—"})
# 契约 §7：注册表每行字段
REQUIRED_FIELDS: frozenset[str] = frozenset({"角色", "分类", "当前绑定", "备注"})


class DispatchDecision(str, Enum):
    """派发决策。"""

    AUTO = "auto"      # 可后台 CLI → Engine 自动拉起（T4 前模拟）
    MANUAL = "manual"  # 手动 GUI → 挂起等人
    NONE = "none"      # 管理席/验收席（分类「—」）/未知角色 → 不派发


@dataclass(frozen=True)
class ExecutorEntry:
    """注册表一行（契约 §7 字段）。"""

    role: str
    category: str
    binding: str
    note: str


@dataclass(frozen=True)
class ExecutorRegistry:
    """契约 §7 注册表。"""

    entries: tuple[ExecutorEntry, ...]

    def rows_for_role(self, role: str) -> list[ExecutorEntry]:
        """返回该角色下的全部注册行（开发执行体可有多行）。"""
        return [e for e in self.entries if e.role == role]


def load_registry(path: Path | str) -> ExecutorRegistry:
    """从 executors.json 加载注册表；校验 §7 字段与分类合法。

    Raises:
        FileNotFoundError: 注册表文件不存在。
        ValueError: JSON 解析失败、缺字段或分类非法。
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
        entries.append(
            ExecutorEntry(
                role=raw["角色"],
                category=category,
                binding=raw["当前绑定"],
                note=raw["备注"],
            )
        )
    return ExecutorRegistry(tuple(entries))


def decide(role: str, registry: ExecutorRegistry) -> DispatchDecision:
    """按注册表分类做派发决策（契约 §7 → §2）。

    - 角色命中「可后台 CLI」行 → AUTO（Engine 自动拉起）
    - 无 CLI 行但命中「手动 GUI」行 → MANUAL（挂起等人）
    - 其余（席行「—」/ 未知角色）→ NONE（不派发）
    """
    rows = registry.rows_for_role(role)
    if any(r.category == "可后台 CLI" for r in rows):
        return DispatchDecision.AUTO
    if any(r.category == "手动 GUI" for r in rows):
        return DispatchDecision.MANUAL
    return DispatchDecision.NONE
