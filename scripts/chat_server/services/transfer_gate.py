"""转任务聊透门禁 — Desktop Transfer Gate（仅允许写 epic）。

契约：docs/product/transfer-gate.md · LPSN P/N
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

VALID_EXECUTOR_INTENTS = frozenset(
    {"opencode", "python", "ollama", "cli", "auto"}
)
VALID_FEASIBILITY = frozenset({"ok", "blocked"})


def _intent_probe():
    scripts = Path(__file__).resolve().parents[2]
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    import _intent_probe as mod

    return mod


def validate_transfer_payload(
    body: dict[str, Any],
    *,
    workspace: Path | str | None = None,
) -> tuple[bool, list[dict]]:
    """返回 (ok, errors)。errors 项为 {code, message}。"""
    errors: list[dict] = []
    if not isinstance(body, dict):
        return False, [{"code": "invalid_body", "message": "JSON object required"}]

    # Agent 常写长标题；软裁到 80，空才拒（避免 outbox 耗尽仍无人感知）
    title = str(body.get("title") or "").strip()
    if len(title) > 80:
        title = title[:80].rstrip()
        body["title"] = title
    if not title:
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

    ip = _intent_probe()
    hygiene = ip.is_hygiene_transfer(body)
    if not hygiene and acc_ok:
        # 分查 acceptance / plan：plan 内「## 验收」编号列表不得盖掉顶部 acceptance 子弹
        acc_norm = normalize_acceptance(acceptance)
        has_probe = bool(
            ip.extract_probe_commands(acc_norm)
            or ip.extract_probe_commands(plan_md)
        )
        if not has_probe:
            errors.append(
                {
                    "code": "missing_intent_probe",
                    "message": (
                        "业务 epic 的验收须含 ≥1 条可重放意图探针"
                        "（如 DRY_RUN=true .venv/bin/python … / python3 … / pytest）"
                    ),
                }
            )

    if workspace and not hygiene:
        n_err = check_next_intent_gate(body, Path(workspace))
        if n_err:
            errors.append(n_err)

    return (len(errors) == 0), errors


def check_next_intent_gate(body: dict[str, Any], workspace: Path) -> dict | None:
    """If L1 has unfinished product goals, require supersede/abandon for new product epic."""
    if body.get("supersede_goals") is True or body.get("intent_supersede") is True:
        return None
    if str(body.get("abandon_prior") or "").strip().lower() in ("1", "true", "yes"):
        return None
    try:
        from chat_server.services import agent_mind
    except ImportError:
        try:
            from . import agent_mind
        except ImportError:
            return None

    decided = agent_mind.load_decided(Path(workspace))
    unfinished = agent_mind.unfinished_product_goals(decided)
    if not unfinished:
        return None
    blob = (
        str(body.get("title") or "")
        + " "
        + str(body.get("goal") or "")
    ).lower()
    for g in unfinished:
        text = str(g.get("text") or "").lower()
        if text and text[:24] in blob:
            return None
    titles = ", ".join(
        str(g.get("text") or g.get("id") or "")[:40] for g in unfinished[:3]
    )
    return {
        "code": "intent_not_stable",
        "message": (
            f"同仓仍有未达 intent_stable 的产品目标（{titles}）。"
            "先确认稳定/放弃，或传 supersede_goals=true / abandon_prior=true 后再开下一意图。"
        ),
    }


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

    bump = body.get("bump_version") is True
    human_note = str(body.get("human_note") or "").strip()
    parts = [
        "## Transfer Gate",
        f"- pipeline: {pipeline}",
        f"- executor_intent: {intent}",
        "- feasibility: ok",
        f"- bump_version: {'true' if bump else 'false'}",
    ]
    if skills_s:
        parts.append(f"- skills_hint: {skills_s}")
    if human_note:
        parts.extend(["", "## 人工备注", human_note])
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


def resolve_complexity(body: dict[str, Any]) -> str:
    """归一 complexity；多步回归/冒烟禁止落 small（否则扇出强制单卡易 hang）。"""
    raw = str(body.get("complexity") or "medium").strip().lower()
    if raw in ("sm",):
        raw = "small"
    if raw not in ("small", "medium", "large"):
        raw = "medium"
    if raw != "small":
        return raw

    title = str(body.get("title") or "")
    goal = str(body.get("goal") or "")
    plan = str(body.get("plan_md") or "")
    acceptance = body.get("acceptance") or []
    if not isinstance(acceptance, list):
        acceptance = [acceptance]
    acc_lines = [str(a) for a in acceptance if str(a).strip()]
    blob = f"{title}\n{goal}\n{plan}\n" + "\n".join(acc_lines)

    cmdish = 0
    for s in acc_lines:
        if any(
            tok in s
            for tok in (
                "python ",
                "python3 ",
                "pytest",
                "bash ",
                "DRY_RUN",
                "startup_check",
                "&&",
                "exit",
                ".venv/",
            )
        ):
            cmdish += 1

    multi_markers = (
        "startup_check",
        "pytest",
        "data_engine",
        "order_gateway",
        "三件套",
        "回归冒烟",
        "回归烟测",
        "回归测试",
    )
    hits = sum(1 for m in multi_markers if m in blob)
    if cmdish >= 3 or hits >= 3:
        return "medium"
    return raw


def resolve_executor_intent(body: dict[str, Any]) -> str:
    """归一执行面。卫生卡 / 机械意图探针强制 python。"""
    intent = str(body.get("executor_intent") or "opencode").strip().lower()
    pipeline = str(body.get("pipeline") or "").strip().lower()
    title = str(body.get("title") or "").strip().lower()
    goal = str(body.get("goal") or "").strip().lower()
    blob = f"{pipeline} {title} {goal}"
    acc = normalize_acceptance(body.get("acceptance")).lower()
    plan = str(body.get("plan_md") or "").lower()
    blob_full = f"{blob} {acc} {plan}"

    ip = _intent_probe()
    hygiene = ip.is_hygiene_transfer(body) or any(
        k in blob
        for k in (
            "git add",
            "单 commit",
            "committer",
        )
    )
    # LPSN 机械探针：整卡都是探针种子时才强制 python（勿因验收里顺带一条探针就锁死整 epic）
    title_l = title.lower()
    probe_epic = any(
        k in title_l
        for k in (
            "paper_intent_probe",
            "意图探针",
            "纸面探针",
            "script-seed",
            "intent-probe",
        )
    ) or (
        "探针" in title
        and not any(k in title for k in ("模块", "功能", "实现", "文档", "计数"))
    )
    if (hygiene or probe_epic) and intent in ("opencode", "auto", ""):
        return "python"

    if intent == "auto":
        if "python" in pipeline or pipeline in ("py", "script"):
            return "python"
        if "ollama" in pipeline:
            return "ollama"
        if pipeline in ("cli", "shell", "ops"):
            return "cli"
        return "opencode"
    return intent if intent in VALID_EXECUTOR_INTENTS else "opencode"
