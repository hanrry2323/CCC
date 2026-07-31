"""L1 planned 意图卡 → gate → backlog epic + wake Engine.

Agent 自动投链 / 口述下达后：右栏 planned 不得长期停尸——系统必须推进代办。
"""

from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path
from typing import Any

from . import agent_mind
from . import transfer_gate

_log = logging.getLogger("ccc.intent_promote")

_THIN_SCOPE_RE = re.compile(
    r"按验收探针所在模块最小改|（按验收|最小改）",
    re.I,
)
_PROSE_EXIT_RE = re.compile(
    r"^(探针脚本|完成|可重放|报告落盘|regress)",
    re.I,
)


def _goal_title(g: dict[str, Any]) -> str:
    text = str(g.get("text") or g.get("title") or g.get("goal") or "").strip()
    return text[:80] if text else "意图卡"


def _goal_acceptance(g: dict[str, Any]) -> list[str]:
    exit_c = str(g.get("exit_condition") or g.get("probe") or "").strip()
    if exit_c:
        return [exit_c]
    return []


def _exit_has_strong_probe(exit_c: str) -> bool:
    try:
        from _intent_probe import extract_probe_commands
        from _acceptance_strength import is_strong_enough

        cmds = extract_probe_commands(exit_c) or []
        if not cmds and exit_c.strip():
            cmds = [exit_c.strip()]
        ok, _ = is_strong_enough(cmds, require_strong=True)
        return bool(ok)
    except Exception:
        return False


def _is_thin_boilerplate_plan(plan_md: str) -> bool:
    """True when plan has no real path scope — Agent must emit full ccc-transfer."""
    text = plan_md or ""
    has_path = bool(
        re.search(
            r"(?m)^-\s+[`\"]?[A-Za-z0-9_./-]+\.(py|md|sh|json|ts|js)",
            text,
        )
    )
    if has_path:
        return False
    if _THIN_SCOPE_RE.search(text):
        return True
    if "禁薄 plan" in text or "写明真实路径" in text:
        return True
    return False


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
    scope_lines: list[str] = []
    for m in re.finditer(
        r"(?:^|[\s`])([A-Za-z0-9_./-]+\.(?:py|md|sh|json))",
        goal_text,
    ):
        p = m.group(1)
        if p not in scope_lines:
            scope_lines.append(p)
        if len(scope_lines) >= 5:
            break
    if scope_lines:
        scope_block = "\n".join(f"- {p}" for p in scope_lines)
    else:
        scope_block = (
            "- （需 Agent 在 ccc-transfer 写明真实路径；禁薄 plan 进 OpenCode）"
        )
    plan_md = (
        f"# {title}\n\n"
        f"## 目标\n{goal_text}\n\n"
        f"## 范围\n{scope_block}\n\n"
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
        "skill_ref": "skills/write-code",
        "prompt_ref": "prompts/write-code-prompt",
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


def find_inflight_epic_for_goal(
    root: Path, goal: dict[str, Any]
) -> str | None:
    """Return epic id if same L1 goal / title already on active board."""
    try:
        import json

        title = _goal_title(goal)
        gid = str(goal.get("id") or "").strip()
        goal_text = str(goal.get("text") or goal.get("title") or title).strip()
        board = Path(root) / ".ccc" / "board"
        for col in (
            "backlog",
            "planned",
            "in_progress",
            "testing",
            "verified",
        ):
            d = board / col
            if not d.is_dir():
                continue
            for p in d.glob("*.jsonl"):
                try:
                    line = p.read_text(encoding="utf-8", errors="replace").splitlines()[
                        0
                    ]
                    t = json.loads(line)
                except Exception:
                    continue
                if not isinstance(t, dict) or t.get("ui_hidden"):
                    continue
                if str(t.get("card_kind") or "epic") == "work":
                    continue
                if gid and str(t.get("l1_goal_id") or "") == gid:
                    return str(t.get("id") or p.stem)
                tt = str(t.get("title") or "")
                if title and (title[:40] in tt or tt[:40] in title):
                    return str(t.get("id") or p.stem)
                if goal_text and tt and (
                    goal_text[:32] in tt or tt[:32] in goal_text
                ):
                    return str(t.get("id") or p.stem)
    except Exception as exc:  # noqa: BLE001
        _log.debug("find_inflight_epic: %s", exc)
    return None


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
        inflight = find_inflight_epic_for_goal(root, g)
        if inflight:
            rows.append(
                {
                    "goal_id": g.get("id"),
                    "title": _goal_title(g),
                    "ok": True,
                    "idempotent": True,
                    "epic_id": inflight,
                    "errors": [],
                    "payload": None,
                    "fix_hint": None,
                }
            )
            continue

        exit_c = str(g.get("exit_condition") or "").strip()
        if not _exit_has_strong_probe(exit_c) or _PROSE_EXIT_RE.match(exit_c):
            rows.append(
                {
                    "goal_id": g.get("id"),
                    "title": _goal_title(g),
                    "ok": False,
                    "errors": [
                        {
                            "code": "acceptance_weak",
                            "message": "exit_condition 非强探针（散文/弱）",
                            "fix_hint": (
                                "exit_condition 写成 "
                                "`.venv/bin/python -m pytest -q <本卡测>`；"
                                "禁止散文。出完整 ccc-transfer。"
                            ),
                        }
                    ],
                    "fix_hint": "补强探针后再 promote；或让 Agent 出完整 ccc-transfer。",
                }
            )
            continue

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

        if _is_thin_boilerplate_plan(str(payload.get("plan_md") or "")):
            rows.append(
                {
                    "goal_id": g.get("id"),
                    "title": payload["title"],
                    "ok": False,
                    "errors": [
                        {
                            "code": "plan_scope_too_wide",
                            "message": "promote 薄 plan（无真实路径）禁止进 OpenCode",
                            "fix_hint": (
                                "请 Agent 出完整 ```ccc-transfer```，"
                                "plan_md ## 范围写真实文件路径。"
                            ),
                        }
                    ],
                    "fix_hint": "薄 plan 拒推；改出完整 ccc-transfer。",
                }
            )
            continue

        ok, errors = transfer_gate.validate_transfer_payload(
            payload, workspace=root
        )
        if ok:
            n_err = transfer_gate.check_next_intent_gate(payload, root)
            if n_err:
                ok = False
                errors = [n_err]
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
