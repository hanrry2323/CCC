"""L1 planned 意图卡 → gate → backlog epic + wake Engine.

人点「转意图卡」后：右栏 planned 不得长期停尸——系统必须推进代办。
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any

from . import agent_mind
from . import transfer_gate

_log = logging.getLogger("ccc.intent_promote")


def _goal_title(g: dict[str, Any]) -> str:
    text = str(g.get("text") or g.get("title") or g.get("goal") or "").strip()
    return text[:80] if text else "意图卡"


def _goal_acceptance(g: dict[str, Any]) -> list[str]:
    exit_c = str(g.get("exit_condition") or g.get("probe") or "").strip()
    if exit_c:
        return [exit_c]
    return []


def build_transfer_payload_from_goal(
    project_id: str,
    goal: dict[str, Any],
    *,
    thread_id: str = "",
    supersede_goals: bool = False,
) -> dict[str, Any] | None:
    """Build Desktop transfer body from an L1 planned goal. None if unusable."""
    if not isinstance(goal, dict):
        return None
    st = str(goal.get("status") or "planned").lower()
    if st != "planned":
        return None
    title = _goal_title(goal)
    goal_text = str(goal.get("text") or goal.get("title") or title).strip()
    acc = _goal_acceptance(goal)
    if not acc:
        return None
    gid = str(goal.get("id") or "").strip()
    crid_src = f"{project_id}|{gid}|{title}|{acc[0]}"
    crid = "promote-" + hashlib.sha256(crid_src.encode()).hexdigest()[:16]
    plan_md = (
        f"# {title}\n\n"
        f"## 目标\n{goal_text}\n\n"
        f"## 范围\n- （按验收探针所在模块最小改）\n\n"
        f"## 步骤\n1. 按验收探针落地本卡意图\n\n"
        f"## 验收\n- {acc[0]}\n"
    )
    body: dict[str, Any] = {
        "project_id": project_id,
        "title": title,
        "goal": goal_text,
        "acceptance": acc,
        "pipeline": "dev",
        "feasibility": "ok",
        "feasibility_reason": "",
        "executor_intent": "opencode",
        "complexity": "medium",
        "bump_version": False,
        "plan_md": plan_md,
        "card_kind": "epic",
        "thread_id": thread_id or f"{project_id}::main",
        "client_request_id": crid,
    }
    if supersede_goals:
        body["supersede_goals"] = True
    if gid:
        body["l1_goal_id"] = gid
    return body


def list_promotable_planned(
    root: Path,
    *,
    goal_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    decided = agent_mind.load_decided(root)
    want = {str(x).strip() for x in (goal_ids or []) if str(x).strip()}
    out: list[dict[str, Any]] = []
    for g in decided.get("goals") or []:
        if not isinstance(g, dict):
            continue
        if str(g.get("status") or "").lower() != "planned":
            continue
        gid = str(g.get("id") or "").strip()
        if want and gid not in want:
            continue
        if not _goal_acceptance(g):
            continue
        out.append(g)
    return out


def dry_run_promote_payloads(
    project_id: str,
    root: Path,
    *,
    thread_id: str = "",
    goal_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Return list of {goal_id, title, ok, errors?, payload?} for UI / Agent."""
    rows: list[dict[str, Any]] = []
    planned = list_promotable_planned(root, goal_ids=goal_ids)
    for i, g in enumerate(planned):
        payload = build_transfer_payload_from_goal(
            project_id,
            g,
            thread_id=thread_id,
            supersede_goals=i > 0,
        )
        if not payload:
            rows.append(
                {
                    "goal_id": g.get("id"),
                    "title": _goal_title(g),
                    "ok": False,
                    "errors": [
                        {
                            "code": "missing_exit_condition",
                            "message": "planned 意图卡缺 exit_condition，无法过门",
                            "fix_hint": "补可重放 pytest/DRY_RUN 探针后再转。",
                        }
                    ],
                }
            )
            continue
        ok, errors = transfer_gate.validate_transfer_payload(payload)
        rows.append(
            {
                "goal_id": g.get("id"),
                "title": payload["title"],
                "ok": ok,
                "errors": errors if not ok else [],
                "fix_hint": (errors[0].get("fix_hint") if errors else None),
                "payload": payload if ok else None,
            }
        )
    return rows
