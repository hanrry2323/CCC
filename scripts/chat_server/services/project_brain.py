"""项目脑包编译 — CLAUDE + profile + 规划文 + decided 摘要。

契约：docs/product/project-agent-brain.md · qb 样板舰队标准
不新造 TODO.md；规划文由 CLAUDE 索引或 DEV_PLAN* 探测。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from . import agent_mind

CLAUDE_MAX = 2000
PROFILE_MAX = 1000
PLAN_MAX = 1500
BRAIN_MAX = 4500

_PLAN_INDEX_RE = re.compile(
    r"规划\s*/?\s*未来待办\s*\|\s*`?([^`|\n]+)`?",
    re.I,
)
_PLAN_SSOT_RE = re.compile(
    r"规划\s*SSOT\s*=\s*`?([^\s`|]+)`?",
    re.I,
)


def _read_capped(path: Path, cap: int) -> str:
    if not path.is_file():
        return ""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    text = text.strip()
    if len(text) > cap:
        return text[: cap - 20].rstrip() + "\n…(截断)\n"
    return text


def resolve_plan_path(root: Path, claude_text: str) -> str | None:
    """Return relative plan doc path if found."""
    root = Path(root)
    for rx in (_PLAN_INDEX_RE, _PLAN_SSOT_RE):
        m = rx.search(claude_text or "")
        if m:
            rel = m.group(1).strip().strip("`").strip()
            if rel and (root / rel).is_file():
                return rel
    # qb / common defaults
    for cand in (
        "docs/DEV_PLAN_v1.1.md",
        "docs/DEV_PLAN.md",
        "DEV_PLAN.md",
        "docs/ROADMAP.md",
        "ROADMAP.md",
    ):
        if (root / cand).is_file():
            return cand
    # glob DEV_PLAN*
    docs = root / "docs"
    if docs.is_dir():
        hits = sorted(docs.glob("DEV_PLAN*.md"))
        if hits:
            return str(hits[0].relative_to(root))
    return None


def compile_brain(root: Path, *, project_id: str) -> dict[str, Any]:
    """Compile project brain packet for Desktop inject."""
    root = Path(root)
    claude = _read_capped(root / "CLAUDE.md", CLAUDE_MAX)
    if not claude:
        for alt in (root / "AGENTS.md", root / ".claude" / "CLAUDE.md"):
            claude = _read_capped(alt, CLAUDE_MAX)
            if claude:
                break
    profile = _read_capped(root / ".ccc" / "profile.md", PROFILE_MAX)
    plan_rel = resolve_plan_path(root, claude)
    plan_text = _read_capped(root / plan_rel, PLAN_MAX) if plan_rel else ""

    decided = agent_mind.load_decided(root)
    unfinished = agent_mind.unfinished_product_goals(decided)
    goal_lines = [agent_mind.goal_display(g) for g in unfinished[:6]]
    constraints = [
        str(c)[:200] for c in (decided.get("constraints") or [])[:5] if str(c).strip()
    ]

    lines = [
        f"【项目脑包 · project={project_id}】",
        "新鲜度：live board > 本脑包 > 聊天 resume。代码细节须透镜核实。",
        "规划文=未来待办；看板=开发过程；禁止平行 TODO.md 主路径。",
    ]
    if claude:
        lines.append("—— CLAUDE ——")
        lines.append(claude)
    if profile:
        lines.append("—— profile ——")
        lines.append(profile)
    if plan_rel:
        lines.append(f"—— 规划文 ({plan_rel}) ——")
        lines.append(plan_text or "(空)")
    elif project_id and project_id != "ccc":
        lines.append("—— 规划文 ——")
        lines.append("(未找到；请在 CLAUDE 项目脑索引声明规划路径)")
    if goal_lines:
        lines.append("—— decided 未完成目标 ——")
        for g in goal_lines:
            lines.append(f"- {g}")
    if constraints:
        lines.append("—— decided 约束 ——")
        for c in constraints:
            lines.append(f"- {c}")

    text = "\n".join(lines).strip() + "\n"
    if len(text) > BRAIN_MAX:
        text = text[: BRAIN_MAX - 20].rstrip() + "\n…(截断)\n"

    return {
        "ok": True,
        "project_id": project_id,
        "brain": text,
        "brain_meta": {
            "claude_chars": len(claude),
            "profile_chars": len(profile),
            "plan_path": plan_rel,
            "plan_chars": len(plan_text),
            "unfinished_goals": len(unfinished),
            "constraint_count": len(constraints),
        },
    }
