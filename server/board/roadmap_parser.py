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
            current_milestone = {
                "title": line[4:].strip(),
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
