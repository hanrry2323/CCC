"""项目脑包编译 — CLAUDE + profile + 规划文 + decided 摘要。

契约：docs/product/project-agent-brain.md · qb 样板舰队标准
不新造 TODO.md；规划文由 CLAUDE 索引或 DEV_PLAN* 探测。
规划文按 decided.goals 关键词优先抽相关 ## 节（禁止永远只取文件头）。
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
PLAN_INDEX_MAX = 40

_PLAN_INDEX_RE = re.compile(
    r"规划\s*/?\s*未来待办\s*\|\s*`?([^`|\n]+)`?",
    re.I,
)
_PLAN_SSOT_RE = re.compile(
    r"规划\s*SSOT\s*=\s*`?([^\s`|]+)`?",
    re.I,
)
_HEADING_RE = re.compile(r"^(#{1,3})\s+(.+?)\s*$", re.M)
_TOKEN_RE = re.compile(r"[\w\u4e00-\u9fff]{2,}", re.U)


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


def extract_plan_sections(text: str) -> list[tuple[str, str, str]]:
    """Return [(level_marks, title, body), ...] including preamble as ('', '', body)."""
    text = text or ""
    matches = list(_HEADING_RE.finditer(text))
    if not matches:
        return [("", "", text.strip())] if text.strip() else []
    out: list[tuple[str, str, str]] = []
    if matches[0].start() > 0:
        pre = text[: matches[0].start()].strip()
        if pre:
            out.append(("", "(前言)", pre))
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        out.append((m.group(1), m.group(2).strip(), body))
    return out


def plan_index_titles(text: str, *, limit: int = PLAN_INDEX_MAX) -> list[str]:
    titles: list[str] = []
    for marks, title, _ in extract_plan_sections(text):
        if not title or title == "(前言)":
            continue
        prefix = marks or "##"
        titles.append(f"{prefix} {title}")
        if len(titles) >= limit:
            break
    return titles


def _goal_keywords(unfinished: list[Any], decided: dict[str, Any]) -> list[str]:
    blobs: list[str] = []
    for g in unfinished[:8]:
        blobs.append(agent_mind.goal_display(g))
        if isinstance(g, dict):
            blobs.append(str(g.get("text") or ""))
            blobs.append(str(g.get("exit_condition") or ""))
    for c in (decided.get("constraints") or [])[:5]:
        blobs.append(str(c))
    raw = " ".join(blobs).lower()
    tokens = [t for t in _TOKEN_RE.findall(raw) if len(t) >= 2]
    # de-dupe preserve order; drop ultra-common noise
    stop = {
        "the",
        "and",
        "for",
        "with",
        "true",
        "false",
        "python",
        "scripts",
        "test",
        "tests",
        "exit",
        "condition",
        "status",
        "planned",
        "禁止",
        "必须",
        "完成",
        "目标",
    }
    seen: set[str] = set()
    out: list[str] = []
    for t in tokens:
        tl = t.lower()
        if tl in stop or tl in seen:
            continue
        seen.add(tl)
        out.append(tl)
        if len(out) >= 24:
            break
    return out


def _score_section(title: str, body: str, keywords: list[str]) -> int:
    hay = f"{title}\n{body}".lower()
    score = 0
    for kw in keywords:
        if kw and kw in hay:
            score += 3 if kw in title.lower() else 1
    return score


def read_plan_smart(
    path: Path,
    *,
    cap: int = PLAN_MAX,
    keywords: list[str] | None = None,
) -> tuple[str, list[str]]:
    """Goal-anchored plan excerpt + full chapter index."""
    if not path.is_file():
        return "", []
    try:
        full = path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return "", []
    index = plan_index_titles(full)
    keywords = keywords or []
    if not keywords or len(full) <= cap:
        text = full if len(full) <= cap else full[: cap - 20].rstrip() + "\n…(截断)\n"
        return text, index

    sections = extract_plan_sections(full)
    scored: list[tuple[int, int, tuple[str, str, str]]] = []
    for i, sec in enumerate(sections):
        marks, title, body = sec
        scored.append((_score_section(title, body, keywords), -i, sec))
    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)

    # Prefer positive matches; always keep at least one chunk
    chosen = [s for s in scored if s[0] > 0][:8] or scored[:3]
    # Restore document order among chosen
    chosen_secs = [s[2] for s in sorted(chosen, key=lambda x: -x[1])]

    chunks: list[str] = []
    total = 0
    for marks, title, body in chosen_secs:
        if title == "(前言)":
            block = body
        else:
            block = f"{marks or '##'} {title}\n{body}".strip()
        if not block:
            continue
        room = cap - total - 40
        if room <= 80:
            break
        if len(block) > room:
            block = block[: room - 12].rstrip() + "\n…(截断)\n"
        chunks.append(block)
        total += len(block) + 2
    text = "\n\n".join(chunks).strip() + "\n"
    if not text.strip():
        text = full[: cap - 20].rstrip() + "\n…(截断)\n"
    return text, index


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

    decided = agent_mind.load_decided(root)
    unfinished = agent_mind.unfinished_product_goals(decided)
    keywords = _goal_keywords(unfinished, decided)
    plan_text = ""
    plan_index: list[str] = []
    if plan_rel:
        plan_text, plan_index = read_plan_smart(
            root / plan_rel, cap=PLAN_MAX, keywords=keywords
        )

    modules_line = ""
    try:
        from . import hub_lens as _hl

        mod = _hl.collect_module_index(root, project_id=project_id)
        modules_line = str(mod.get("summary_line") or "").strip()
    except Exception:
        modules_line = ""

    goal_lines = [agent_mind.goal_display(g) for g in unfinished[:6]]
    constraints = [
        str(c)[:200] for c in (decided.get("constraints") or [])[:5] if str(c).strip()
    ]

    lines = [
        f"【项目脑包 · project={project_id}】",
        "新鲜度：live board > 本脑包 > 聊天 resume。代码细节须透镜核实。",
        "规划文=未来待办；看板=开发过程；禁止平行 TODO.md 主路径。",
    ]
    if modules_line:
        lines.append(modules_line)
    if claude:
        lines.append("—— CLAUDE ——")
        lines.append(claude)
    if profile:
        lines.append("—— profile ——")
        lines.append(profile)
    if plan_rel:
        lines.append(f"—— 规划文 ({plan_rel}) ——")
        if plan_index:
            idx_show = "；".join(plan_index[:24])
            if len(plan_index) > 24:
                idx_show += "；…"
            lines.append(f"plan_index: {idx_show}")
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
        # Prefer keeping modules + plan_index + goals; trim CLAUDE/profile first-ish by hard cut
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
            "plan_index": plan_index,
            "modules_line": modules_line,
            "goal_keywords": keywords[:12],
            "unfinished_goals": len(unfinished),
            "constraint_count": len(constraints),
        },
    }
