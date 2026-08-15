"""roadmap.md 业务线路解析器（2026-08-12 · 线路图页面升级）。

从 docs/roadmap.md 解析「业务线路（<prefix>）」段，关联卡真实状态，输出：
- 按项目分区的业务线路（标题/挂账/关联方案/卡表格/意向）
- 卡进度 vs 卡真实状态的漂移标记（复用 normalize_state 语义）
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

# 与 observer.scan_findings 的 normalize_state 语义一致
_STATE_ALIASES = {
    "closed": {"已合入", "已关闭", "已完成", "已交付", "released", "closed", "delivered"},
    "verified": {"已回写", "verified", "testing", "待验收", "机审"},
    "in_progress": {"执行中", "in_progress", "开发中"},
    "pending": {"待分派", "pending", "planned"},
}


def normalize_state(s: str) -> str:
    s = (s or "").strip()
    for bucket, aliases in _STATE_ALIASES.items():
        if s in aliases:
            return bucket
    return s


def parse_business_lines(md: str) -> list[dict[str, Any]]:
    """解析 roadmap.md 的业务线路段。

    返回 [{project, title, milestones: [{title, cards: [{card_id, intent, progress}]}]}]
    """
    sections: list[dict[str, Any]] = []
    current_project: str | None = None
    current_milestone: dict[str, Any] | None = None

    for raw in md.splitlines():
        line = raw.strip()
        if line.startswith("## 业务线路（"):
            m = re.match(r"##\s*业务线路[（(]([^）)]+)[）)]", line)
            if m:
                current_project = m.group(1).strip()
                current_milestone = None
                sections.append({"project": current_project, "milestones": []})
            continue
        if not current_project:
            continue
        if line.startswith("### "):
            title = line[4:].strip()
            # 从标题提取日期（2026-08-07 挂账 / 2026-08-07 · xxx）
            date_m = re.search(r"20\d{2}-\d{2}-\d{2}", title)
            current_milestone = {
                "title": title,
                "date": date_m.group(0) if date_m else "",
                "cards": [],
            }
            sections[-1]["milestones"].append(current_milestone)
            continue
        if current_milestone is not None:
            # 卡表格行：| **clw001** | 意图 | 进度 |
            cm = re.match(r"\|\s*\*\*([a-z]{2,4}\d{3})\*\*\s*\|\s*([^|]+)\|\s*([^|]+)\s*\|", line)
            if cm:
                current_milestone["cards"].append(
                    {
                        "card_id": cm.group(1).strip(),
                        "intent": cm.group(2).strip(),
                        "progress": cm.group(3).strip(),
                    }
                )

    return sections


def attach_card_states(
    sections: list[dict[str, Any]], cards_by_id: dict[str, str], by_project: dict[str, str]
) -> list[dict[str, Any]]:
    """关联卡真实状态，标漂移。

    cards_by_id: {card_id_lower: real_state}
    by_project: {card_id_lower: project}
    """
    for section in sections:
        for mile in section.get("milestones", []):
            for card in mile.get("cards", []):
                cid = card["card_id"]
                real = cards_by_id.get(cid.lower())
                if real is None:
                    card["real_state"] = None
                    card["drift"] = False
                    card["missing"] = True
                    continue
                card["real_state"] = real
                card["project"] = by_project.get(cid.lower(), section["project"])
                # 漂移：roadmap 进度 vs 卡真实状态
                p = normalize_state(card.get("progress", ""))
                r = normalize_state(real)
                card["drift"] = bool(p) and bool(r) and p != r
    return sections


def load_roadmap_sections(
    roadmap_path: Path,
    cards_by_id: dict[str, str] | None = None,
    by_project: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """加载并解析 roadmap.md 业务线路，关联卡状态（供 /board/roadmap 用）。"""
    if not roadmap_path.exists():
        return []
    md = roadmap_path.read_text(encoding="utf-8", errors="replace")
    sections = parse_business_lines(md)
    if cards_by_id is not None:
        sections = attach_card_states(sections, cards_by_id, by_project or {})
    return sections


def card_group(progress: str, real_state: str | None) -> str:
    """卡 → 状态分组（已完成/进行中/待开发/风险）。

    优先级：风险（漂移/缺失）> 已完成 > 进行中 > 待开发。
    """
    p = progress or ""
    r = normalize_state(real_state or "")
    pn = normalize_state(p)
    if pn == "closed" or r == "closed":
        return "done"
    if pn in ("in_progress", "verified") or r in ("in_progress", "verified"):
        return "doing"
    return "planned"


def project_detail(
    sections: list[dict[str, Any]], project: str
) -> dict[str, Any] | None:
    """单项目线路图数据：里程碑 + 卡分组统计 + 风险列表（供二级页/SVG 渲染）。"""
    for s in sections:
        if s.get("project") == project:
            cards = [
                c for m in s.get("milestones", []) for c in m.get("cards", [])
            ]
            groups = {"done": [], "doing": [], "planned": []}
            risks = []
            for c in cards:
                g = card_group(c.get("progress", ""), c.get("real_state"))
                groups[g].append(c)
                if c.get("drift"):
                    risks.append({"type": "drift", "card_id": c.get("card_id"), "detail": "roadmap 进度与卡状态不一致"})
                if c.get("missing"):
                    risks.append({"type": "missing", "card_id": c.get("card_id"), "detail": "卡文件不存在"})
            return {
                "project": project,
                "milestones": s.get("milestones", []),
                "groups": {k: v for k, v in groups.items()},
                "counts": {k: len(v) for k, v in groups.items()},
                "risks": risks,
            }
    return None
