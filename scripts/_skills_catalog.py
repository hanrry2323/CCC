"""轻量 Skill 目录扫描 — Hub 转任务卡 chips 用（软偏好，非 MCP）。"""

from __future__ import annotations

import re
from pathlib import Path

_NAME_RE = re.compile(r"^name:\s*(.+)$", re.M | re.I)
# Single-line description, or folded/block scalar start (>- / > / |-)
_DESC_LINE_RE = re.compile(r"^description:\s*(.*)$", re.M | re.I)

# Engine role skills — not task preference chips by default
_ENGINE_IDS = frozenset({
    "ccc-product",
    "ccc-dev",
    "ccc-reviewer",
    "ccc-tester",
    "ccc-ops",
    "ccc-kb",
    "ccc-regress",
})

_COMMON_IDS = frozenset({
    "codebase-memory",
    "planning-with-files",
    "daily-snapshot",
    "test-verify",
})


def _unfold_yaml_description(text: str) -> str:
    """Parse YAML description, including folded `>-` / `>` blocks."""
    dm = _DESC_LINE_RE.search(text)
    if not dm:
        return ""
    rest = (dm.group(1) or "").strip()
    if rest in (">-", ">", "|-", "|", ">+", "|+"):
        # Collect following indented lines until a less-indented key or blank+key
        start = dm.end()
        lines: list[str] = []
        for line in text[start:].splitlines():
            if not line.strip():
                if lines:
                    break
                continue
            if line.startswith(" ") or line.startswith("\t"):
                lines.append(line.strip())
            else:
                break
        return " ".join(lines).strip()[:160]
    return rest.strip().strip("\"'")[:160]


def _classify(skill_id: str) -> tuple[str, bool]:
    """Return (tier, hub_visible)."""
    if skill_id in _ENGINE_IDS or (
        skill_id.startswith("ccc-") and skill_id != "ccc-protocol"
    ):
        return "engine", False
    if skill_id in _COMMON_IDS:
        return "common", True
    return "specialized", True


def _parse_skill_md(path: Path) -> dict | None:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")[:4000]
    except OSError:
        return None
    name = None
    m = _NAME_RE.search(text)
    if m:
        name = m.group(1).strip().strip("\"'")
    desc = _unfold_yaml_description(text)
    skill_id = path.parent.name
    if not skill_id or skill_id.startswith("."):
        return None
    tier, hub_visible = _classify(skill_id)
    return {
        "id": skill_id,
        "name": name or skill_id,
        "description": desc,
        "path": str(path.parent),
        "tier": tier,
        "hub_visible": hub_visible,
    }


def _scan_root(root: Path, source: str, out: dict[str, dict], limit: int = 80) -> None:
    if not root.is_dir() or len(out) >= limit:
        return
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
        nested = child / "skills"
        if nested.is_dir():
            _scan_root(nested, f"{source}/{child.name}", out, limit=limit)


def discover_skills(
    *,
    project_path: str | Path | None = None,
    ccc_home: str | Path | None = None,
    limit: int = 60,
    include_engine: bool = False,
) -> list[dict]:
    """扫描常见 skill 目录，按 id 去重。

    默认隐藏 Engine 角色（ccc-*），可用 include_engine=True 显示。
    """
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

    items = list(out.values())
    if not include_engine:
        items = [s for s in items if s.get("hub_visible", True)]

    def sort_key(item: dict) -> tuple:
        tier = item.get("tier") or "specialized"
        tier_pri = {"common": 0, "specialized": 1, "engine": 2}.get(tier, 1)
        return (tier_pri, item.get("name", item["id"]).lower())

    return sorted(items, key=sort_key)[:limit]


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
