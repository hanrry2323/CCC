"""board.prompt — phase / role prompt 拼装（纯函数，无副作用）。"""
from __future__ import annotations

from typing import Optional, Sequence


def build_dev_phase_prompt(
    task_id: str,
    phase_num: int,
    plan_content: str,
    *,
    scope: Optional[Sequence[str]] = None,
    pytest_failure: str = "",
    skill_hints: str = "",
) -> str:
    """F-PROMPT-01 + v0.41.1: 强制 scope 白名单 + 可选 pytest 失败回灌 + Skill 软偏好。"""
    scope_list = [str(s).strip() for s in (scope or []) if str(s).strip()]
    if scope_list:
        scope_block = (
            "## 文件白名单 scope（硬约束）\n"
            "只允许修改下列路径；改其他文件视为失败：\n"
            + "\n".join(f"- `{p}`" for p in scope_list)
            + "\n\n"
        )
    else:
        scope_block = (
            "## 文件白名单 scope（硬约束）\n"
            "本 phase **未提供 scope** — 只改 plan 明确点名的文件；"
            "禁止全仓扫改；不确定则停手并在 notes 说明。\n\n"
        )

    fail_block = ""
    if pytest_failure and pytest_failure.strip():
        fail_block = (
            "## 上次 pytest 失败（必须先修）\n"
            "以下是测试门失败摘要。本轮优先修复这些错误，再做其它改动。\n\n"
            f"```\n{pytest_failure.strip()[-3000:]}\n```\n\n"
        )

    skill_block = ""
    if skill_hints and skill_hints.strip():
        skill_block = skill_hints.strip() + "\n\n"

    return (
        f"# CCC 执行任务: {task_id}\n\n"
        f"## 当前 Phase（强制）\n"
        f"- **只做 Phase {phase_num}**，不得实现其他 phase 的需求\n"
        f"- 不得修改不属于本 phase 白名单的文件\n"
        f"- 完成定义仅对本 phase 生效；其他 phase 留给后续调度\n"
        f"- 你是执行器（弱模型友好）：按清单改文件，不要重写 plan，不要发明新需求\n\n"
        f"{scope_block}"
        f"{fail_block}"
        f"{skill_block}"
        f"## Plan（全文供参考；执行范围仍以本 phase 为准）\n\n{plan_content}\n\n"
        f"## 完成定义（仅 Phase {phase_num}）\n"
        f"1. 仅实现 Phase {phase_num} 对应需求\n"
        f"2. 跑本 phase 相关测试（如有）\n"
        f"3. 提交一个 commit（message 含 `{task_id}` 与 `phase={phase_num}`）\n"
        f"4. 确认代码无语法错误\n"
        f"5. 不超出 scope 白名单，且不提前做后续 phase\n"
    )


def build_dev_phase_prompt_with_hint(
    task_id: str,
    phase_num: int,
    plan_content: str,
    size_hint: str = "",
    *,
    scope: Optional[Sequence[str]] = None,
    pytest_failure: str = "",
    skill_hints: str = "",
) -> str:
    base = build_dev_phase_prompt(
        task_id,
        phase_num,
        plan_content,
        scope=scope,
        pytest_failure=pytest_failure,
        skill_hints=skill_hints,
    )
    if not size_hint:
        return base
    marker = f"## Plan（全文供参考；执行范围仍以本 phase 为准）\n\n{plan_content}\n\n"
    if marker in base:
        return base.replace(marker, marker + f"{size_hint}\n", 1)
    return base + size_hint
