"""角色锁 — 阶段 ↔ 执行器 硬约束（架构对齐 2026-07-19）。

契约：docs/runbooks/orchestration-flow.md · 红线 6（角色不互串）

锁定的执行器映射：
  product   → claude-code   （扇出 work，不写码）
  dev       → opencode      （写码，不扇出）
  reviewer  → claude-code   （语义审查，不写码）
  tester    → pytest        （跑验收，不写码）
  ops       → claude-code   （健康检查，不动 board）
  kb        → git           （tag + changelog）
  regress   → pytest        （回测）

对话面（M1 sidecar）= loop-code；不在此锁内（不在 2017 Engine 调度）。

用法：各角色入口处 `assert_role_executor("product", "claude-code")`；
环境变量 `CCC_ROLE_LOCK_BYPASS=1` 可绕过（仅限本地调试，CI 禁用）。
"""

from __future__ import annotations

import os
from typing import FrozenSet

# 角色 → 允许的执行器集合（单元素 = 硬锁；多元素 = 允许的备选）
ROLE_EXECUTOR_LOCK: dict[str, FrozenSet[str]] = {
    "product": frozenset({"claude-code", "claude"}),
    "dev": frozenset({"opencode"}),
    "reviewer": frozenset({"claude-code", "claude"}),
    "tester": frozenset({"pytest"}),
    "ops": frozenset({"claude-code", "claude"}),
    "kb": frozenset({"git"}),
    "regress": frozenset({"pytest"}),
}

# 对话面执行器（M1 sidecar）— 不参与 Engine 调度，单独声明
DIALOGUE_EXECUTOR = "loop-code"


class RoleLockViolation(RuntimeError):
    """角色使用了未锁定的执行器。"""


def assert_role_executor(role: str, executor: str) -> None:
    """断言 `role` 允许使用 `executor`；违例抛 RoleLockViolation。

    `CCC_ROLE_LOCK_BYPASS=1` 时仅 warn 不抛（调试用）。
    """
    if os.environ.get("CCC_ROLE_LOCK_BYPASS") == "1":
        return
    allowed = ROLE_EXECUTOR_LOCK.get(role)
    if allowed is None:
        raise RoleLockViolation(f"unknown role: {role!r}")
    if executor not in allowed:
        raise RoleLockViolation(
            f"role {role!r} requires executor in {sorted(allowed)}, got {executor!r}"
        )


def is_role_executor_allowed(role: str, executor: str) -> bool:
    allowed = ROLE_EXECUTOR_LOCK.get(role)
    if allowed is None:
        return False
    return executor in allowed
