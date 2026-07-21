"""转任务聊透门禁 — Desktop Transfer Gate（仅允许写 epic）。

契约：docs/product/transfer-gate.md
"""

from __future__ import annotations

from typing import Any

VALID_EXECUTOR_INTENTS = frozenset(
    {"opencode", "python", "ollama", "cli", "auto"}
)
VALID_FEASIBILITY = frozenset({"ok", "blocked"})


def validate_transfer_payload(body: dict[str, Any]) -> tuple[bool, list[dict]]:
    """返回 (ok, errors)。errors 项为 {code, message}。"""
    errors: list[dict] = []
    if not isinstance(body, dict):
        return False, [{"code": "invalid_body", "message": "JSON object required"}]

    title = str(body.get("title") or "").strip()
    if not title or len(title) > 80:
        errors.append(
            {
                "code": "missing_title",
                "message": "需要 1–80 字可执行中文标题",
            }
        )

    goal = str(body.get("goal") or "").strip()
    if not goal:
        errors.append({"code": "missing_goal", "message": "需要明确目标（goal）"})

    acceptance = body.get("acceptance")
    if isinstance(acceptance, list):
        acc_ok = any(str(x or "").strip() for x in acceptance)
    else:
        acc_ok = bool(str(acceptance or "").strip())
    if not acc_ok:
        errors.append(
            {
                "code": "missing_acceptance",
                "message": "需要至少一条验收意图（acceptance）",
            }
        )

    pipeline = str(body.get("pipeline") or "").strip()
    if not pipeline:
        errors.append(
            {
                "code": "missing_pipeline",
                "message": "需要产线/项目执行意图（pipeline）",
            }
        )

    feasibility = str(body.get("feasibility") or "").strip().lower()
    if feasibility not in VALID_FEASIBILITY:
        errors.append(
            {
                "code": "feasibility_blocked",
                "message": "feasibility 必须为 ok 或 blocked",
            }
        )
    elif feasibility == "blocked":
        reason = str(body.get("feasibility_reason") or "").strip()
        errors.append(
            {
                "code": "feasibility_blocked",
                "message": reason or "Agent 评估不可执行（feasibility=blocked）",
            }
        )

    intent = str(body.get("executor_intent") or "opencode").strip().lower()
    if intent not in VALID_EXECUTOR_INTENTS:
        errors.append(
            {
                "code": "invalid_executor_intent",
                "message": f"未知执行面: {intent}",
            }
        )

    project_id = str(body.get("project_id") or body.get("project") or "").strip()
    if not project_id:
        errors.append(
            {
                "code": "project_not_dispatchable",
                "message": "缺少 project_id",
            }
        )

    plan_md = str(body.get("plan_md") or "").strip()
    if not plan_md:
        # soft: synthesize from goal/acceptance if missing
        pass

    return (len(errors) == 0), errors


def normalize_acceptance(acceptance: Any) -> str:
    if isinstance(acceptance, list):
        lines = [f"- {str(x).strip()}" for x in acceptance if str(x or "").strip()]
        return "\n".join(lines)
    return str(acceptance or "").strip()


def build_epic_description(body: dict[str, Any]) -> str:
    """拼 epic.description：含 gate 快照，供 Engine 扇出。"""
    goal = str(body.get("goal") or "").strip()
    acc = normalize_acceptance(body.get("acceptance"))
    pipeline = str(body.get("pipeline") or "").strip()
    intent = str(body.get("executor_intent") or "opencode").strip().lower()
    plan_md = str(body.get("plan_md") or "").strip()
    skills = body.get("skills_hint") or []
    if not isinstance(skills, list):
        skills = []
    skills_s = ", ".join(str(s) for s in skills if str(s).strip())

    parts = [
        "## Transfer Gate",
        f"- pipeline: {pipeline}",
        f"- executor_intent: {intent}",
        "- feasibility: ok",
    ]
    if skills_s:
        parts.append(f"- skills_hint: {skills_s}")
    parts.extend(["", "## 目标", goal, "", "## 验收", acc])
    if plan_md:
        parts.extend(["", "## Plan", plan_md])
    thread_id = str(body.get("thread_id") or "").strip()
    if thread_id:
        parts.extend(["", f"_thread_id: {thread_id}_"])
    return "\n".join(parts)[:10000]


def build_plan_md(body: dict[str, Any]) -> str:
    plan_md = str(body.get("plan_md") or "").strip()
    if plan_md:
        if not (
            "## 验收" in plan_md
            or "## 验证" in plan_md
            or "## Acceptance" in plan_md
        ):
            acc = normalize_acceptance(body.get("acceptance"))
            plan_md = plan_md.rstrip() + f"\n\n## 验收\n{acc}\n"
        return plan_md
    title = str(body.get("title") or "任务").strip()
    goal = str(body.get("goal") or "").strip()
    acc = normalize_acceptance(body.get("acceptance"))
    return (
        f"# Plan: {title}\n\n"
        f"## 目标\n{goal}\n\n"
        f"## 验收\n{acc}\n"
    )


def resolve_executor_intent(body: dict[str, Any]) -> str:
    intent = str(body.get("executor_intent") or "opencode").strip().lower()
    if intent == "auto":
        pipeline = str(body.get("pipeline") or "").strip().lower()
        if "python" in pipeline or pipeline in ("py", "script"):
            return "python"
        if "ollama" in pipeline:
            return "ollama"
        if pipeline in ("cli", "shell", "ops"):
            return "cli"
        return "opencode"
    return intent if intent in VALID_EXECUTOR_INTENTS else "opencode"
