"""轻量 Skill 目录扫描 — Hub 转任务卡 chips 用（软偏好，非 MCP）。"""

from __future__ import annotations

import re
from pathlib import Path

_NAME_RE = re.compile(r"^name:\s*(.+)$", re.M | re.I)
_DESC_RE = re.compile(r"^description:\s*(.+)$", re.M | re.I)


def _parse_skill_md(path: Path) -> dict | None:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")[:4000]
    except OSError:
        return None
    name = None
    m = _NAME_RE.search(text)
    if m:
        name = m.group(1).strip().strip("\"'")
    desc = ""
    dm = _DESC_RE.search(text)
    if dm:
        desc = dm.group(1).strip().strip("\"'")[:160]
    skill_id = path.parent.name
    if not skill_id or skill_id.startswith("."):
        return None
    return {
        "id": skill_id,
        "name": name or skill_id,
        "description": desc,
        "path": str(path.parent),
    }


def _scan_root(root: Path, source: str, out: dict[str, dict], limit: int = 80) -> None:
    if not root.is_dir() or len(out) >= limit:
        return
    # direct: root/*/SKILL.md
    try:
        children = sorted(root.iterdir(), key=lambda p: p.name.lower())
    except OSError:
        return
    for child in children:
        if len(out) >= limit:
            break
        if not child.is_dir() or child.name.startswith("."):
            continue
        skill_md = child / "SKILL.md"
        if skill_md.is_file():
            parsed = _parse_skill_md(skill_md)
            if parsed and parsed["id"] not in out:
                parsed["source"] = source
                out[parsed["id"]] = parsed
        # nested: root/ccc-protocol/skills/*/SKILL.md
        nested = child / "skills"
        if nested.is_dir():
            _scan_root(nested, f"{source}/{child.name}", out, limit=limit)


def discover_skills(
    *,
    project_path: str | Path | None = None,
    ccc_home: str | Path | None = None,
    limit: int = 60,
) -> list[dict]:
    """扫描常见 skill 目录，按 id 去重，返回 [{id,name,description,source,path}]。"""
    home = Path.home()
    ccc = Path(ccc_home) if ccc_home else Path(__file__).resolve().parents[1]
    out: dict[str, dict] = {}
    roots: list[tuple[Path, str]] = [
        (ccc / "skills", "ccc"),
        (home / ".claude" / "skills", "claude"),
        (home / ".agents" / "skills", "agents"),
    ]
    if project_path:
        pp = Path(project_path)
        roots.append((pp / ".claude" / "skills", "project"))
        roots.append((pp / "skills", "project"))
    for root, source in roots:
        _scan_root(root, source, out, limit=limit)
    # 稳定排序：ccc 角色 skill 靠前，其余按 name
    def sort_key(item: dict) -> tuple:
        sid = item["id"]
        pri = 0 if sid.startswith("ccc-") else 1
        return (pri, item.get("name", sid).lower())

    return sorted(out.values(), key=sort_key)[:limit]


def format_skill_hints_block(skills: list[str] | None, note: str = "") -> str:
    """软偏好段落；空则返回空串。"""
    clean = []
    for s in skills or []:
        t = str(s).strip()
        if t and t not in clean:
            clean.append(t[:80])
        if len(clean) >= 5:
            break
    note_s = (note or "").strip()[:400]
    if not clean and not note_s:
        return ""
    lines = [
        "## Skill 偏好（软提示，非硬约束）",
        "用户希望执行时优先参考下列 Skill；若与本 phase 的 plan / scope 冲突，"
        "以 plan 与 scope 为准：",
    ]
    for s in clean:
        lines.append(f"- `{s}`")
    if note_s:
        lines.append(f"补充说明：{note_s}")
    lines.append("")
    return "\n".join(lines) + "\n"
