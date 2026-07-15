"""board.prompt — phase / role prompt 拼装（纯函数，无副作用）。"""
from __future__ import annotations


def build_dev_phase_prompt(task_id: str, phase_num: int, plan_content: str) -> str:
    """F-PROMPT-01: 强制只做当前 phase（Engine / board 共用）。"""
    return (
        f"# CCC 执行任务: {task_id}\n\n"
        f"## 当前 Phase（强制）\n"
        f"- **只做 Phase {phase_num}**，不得实现其他 phase 的需求\n"
        f"- 不得修改不属于本 phase 白名单的文件\n"
        f"- 完成定义仅对本 phase 生效；其他 phase 留给后续调度\n\n"
        f"## Plan（全文供参考；执行范围仍以本 phase 为准）\n\n{plan_content}\n\n"
        f"## 完成定义（仅 Phase {phase_num}）\n"
        f"1. 仅实现 Phase {phase_num} 对应需求\n"
        f"2. 跑本 phase 相关测试（如有）\n"
        f"3. 提交一个 commit（message 含 `{task_id}` 与 `phase={phase_num}`）\n"
        f"4. 确认代码无语法错误\n"
        f"5. 不超出 plan 文件白名单，且不提前做后续 phase\n"
    )


def build_dev_phase_prompt_with_hint(
    task_id: str, phase_num: int, plan_content: str, size_hint: str = ""
) -> str:
    base = build_dev_phase_prompt(task_id, phase_num, plan_content)
    if not size_hint:
        return base
    # 插入 size_hint 到 Plan 段落后
    marker = f"## Plan（全文供参考；执行范围仍以本 phase 为准）\n\n{plan_content}\n\n"
    if marker in base:
        return base.replace(marker, marker + f"{size_hint}\n", 1)
    return base + size_hint
