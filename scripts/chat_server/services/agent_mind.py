"""Desktop Agent 项目心智 L1 — 观察脑编译 + 决策脑落盘。

权威：2017 `<ws>/.ccc/agent-mind/`（与 board 同权威）。
契约：docs/product/loop-engineer-authority.md · 双层心智
- L1a observed：系统编译（board / git / daily / weekly）
- L1b decided：Agent/人经 Hub PUT（schema 校验）
- digest：≤2KB 注入稿；live board 仍优先于本 digest
"""

from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import hub_lens

SCHEMA_VERSION = "1"
DIGEST_MAX_CHARS = 2000
DECIDED_LIST_MAX = 40
DECIDED_ITEM_MAX_CHARS = 400
_CACHE_TTL_S = 45.0
_digest_cache: dict[str, tuple[float, dict[str, Any]]] = {}

ALLOWED_DECIDED_KEYS = (
    "goals",
    "constraints",
    "open_questions",
    "architecture_choices",
)
FORBIDDEN_DECIDED_SUBSTRINGS = (
    "enable engine",
    "invent",
    "set_mode",
    "control.json",
    "擅自 enable",
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def mind_dir(root: Path) -> Path:
    return Path(root) / ".ccc" / "agent-mind"


def observed_path(root: Path) -> Path:
    return mind_dir(root) / "observed.json"


def decided_path(root: Path) -> Path:
    return mind_dir(root) / "decided.json"


def digest_path(root: Path) -> Path:
    return mind_dir(root) / "digest.md"


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    tmp.replace(path)


def _latest_report_headline(reports_dir: Path, prefixes: tuple[str, ...]) -> str | None:
    if not reports_dir.is_dir():
        return None
    candidates: list[Path] = []
    for pref in prefixes:
        candidates.extend(reports_dir.glob(f"{pref}*"))
    files = [p for p in candidates if p.is_file() and p.suffix in (".md", ".json")]
    if not files:
        return None
    latest = max(files, key=lambda p: p.stat().st_mtime)
    try:
        text = latest.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    # 取首个非空、非标题装饰行
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("```"):
            continue
        s = re.sub(r"^#+\s*", "", s).strip()
        if s:
            return f"{latest.name}: {s[:180]}"
    return latest.name


def compile_observed(root: Path, *, project_id: str) -> dict[str, Any]:
    """从权威仓现场编译 L1a（不依赖 Agent 散文）。"""
    root = Path(root)
    board = hub_lens.collect_board(root, project_id=project_id)
    git = hub_lens.collect_git_summary(root, project_id=project_id)
    reports = root / ".ccc" / "reports"
    daily_h = _latest_report_headline(reports, ("daily-review-", "docs-review-"))
    weekly_h = _latest_report_headline(reports, ("weekly-",))

    counts = board.get("counts") or {}
    inflight = board.get("inflight") or []
    inflight_epics = [
        {
            "id": str(x.get("id") or ""),
            "title": str(x.get("title") or "")[:120],
            "column": str(x.get("column") or ""),
        }
        for x in inflight[:12]
        if isinstance(x, dict)
    ]

    released_dir = root / ".ccc" / "board" / "released"
    recent_releases: list[str] = []
    if released_dir.is_dir():
        files = sorted(
            released_dir.glob("*.jsonl"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for p in files[:5]:
            recent_releases.append(p.stem)

    risks: list[str] = []
    if git.get("dirty"):
        risks.append(f"工作区脏 {git.get('dirty_count') or 0} 处")
    if int(counts.get("abnormal") or 0) > 0:
        risks.append(f"abnormal={counts.get('abnormal')}")
    if not board.get("ok", True) and board.get("error"):
        risks.append(str(board.get("error"))[:120])

    observed = {
        "schema_version": SCHEMA_VERSION,
        "project_id": project_id,
        "as_of": _now_iso(),
        "board_counts": counts,
        "board_summary": str(board.get("summary") or "")[:240],
        "inflight_epics": inflight_epics,
        "recent_releases": recent_releases,
        "daily_review_headline": daily_h,
        "weekly_review_headline": weekly_h,
        "git_short_status": {
            "branch": git.get("branch"),
            "dirty": bool(git.get("dirty")),
            "dirty_count": git.get("dirty_count") or 0,
            "recent_commits": (git.get("recent_commits") or [])[:3],
        },
        "risks": risks[:8],
    }
    _atomic_write_json(observed_path(root), observed)
    return observed


def load_decided(root: Path) -> dict[str, Any]:
    data = _load_json(decided_path(root))
    if not data:
        return {
            "schema_version": SCHEMA_VERSION,
            "goals": [],
            "constraints": [],
            "open_questions": [],
            "architecture_choices": [],
            "updated_at": None,
            "updated_by": None,
        }
    out = {
        "schema_version": str(data.get("schema_version") or SCHEMA_VERSION),
        "goals": [],
        "constraints": [],
        "open_questions": [],
        "architecture_choices": [],
        "updated_at": data.get("updated_at"),
        "updated_by": data.get("updated_by"),
    }
    for k in ALLOWED_DECIDED_KEYS:
        raw = data.get(k) or []
        if not isinstance(raw, list):
            continue
        cleaned: list[str] = []
        for item in raw:
            s = str(item).strip()
            if s:
                cleaned.append(s[:DECIDED_ITEM_MAX_CHARS])
            if len(cleaned) >= DECIDED_LIST_MAX:
                break
        out[k] = cleaned
    return out


def _validate_decided_item(text: str) -> None:
    low = text.lower()
    for bad in FORBIDDEN_DECIDED_SUBSTRINGS:
        if bad.lower() in low:
            raise ValueError(f"decided item forbidden content: {bad}")


def merge_decided(
    root: Path,
    patch: dict[str, Any],
    *,
    updated_by: str = "desktop-agent",
) -> dict[str, Any]:
    """字段级 upsert：同名字段整表替换（经清洗）；禁止投 backlog / 改 L0。"""
    cur = load_decided(root)
    by = (updated_by or "desktop-agent").strip() or "desktop-agent"
    if by not in ("desktop-agent", "human", "hub"):
        by = "desktop-agent"

    for k in ALLOWED_DECIDED_KEYS:
        if k not in patch:
            continue
        raw = patch.get(k)
        if not isinstance(raw, list):
            raise ValueError(f"{k} must be a list of strings")
        cleaned: list[str] = []
        for item in raw:
            s = str(item).strip()
            if not s:
                continue
            _validate_decided_item(s)
            cleaned.append(s[:DECIDED_ITEM_MAX_CHARS])
            if len(cleaned) >= DECIDED_LIST_MAX:
                break
        cur[k] = cleaned

    cur["schema_version"] = SCHEMA_VERSION
    cur["updated_at"] = _now_iso()
    cur["updated_by"] = by
    _atomic_write_json(decided_path(root), cur)
    # 使 digest 缓存失效
    pid = str(patch.get("project_id") or "")
    for key in list(_digest_cache.keys()):
        if key.startswith(f"{root}:") or (pid and key.endswith(f":{pid}")):
            _digest_cache.pop(key, None)
    return cur


def format_digest(
    *,
    project_id: str,
    observed: dict[str, Any],
    decided: dict[str, Any],
) -> str:
    lines = [
        f"【项目心智 L1 · digest · project={project_id} · as_of={observed.get('as_of') or ''}】",
        "新鲜度：live board / lens git > 本 digest 观察脑 > 决策脑 > 聊天 resume。冲突以 board 为准。",
        "L0 不变核不可改；本块只含 L1。禁止 invent / 擅自 enable Engine。",
    ]
    counts = observed.get("board_counts") or {}
    if counts:
        parts = [f"{k}={v}" for k, v in counts.items() if v]
        lines.append("看板：" + (", ".join(parts) if parts else "空板"))
    summary = str(observed.get("board_summary") or "").strip()
    if summary:
        lines.append(summary[:200])
    inflight = observed.get("inflight_epics") or []
    if inflight:
        lines.append("在飞：")
        for x in inflight[:8]:
            lines.append(
                f"- [{x.get('column')}] {x.get('id')}: {x.get('title')}"
            )
    git = observed.get("git_short_status") or {}
    if git:
        dirty = "脏" if git.get("dirty") else "净"
        lines.append(
            f"git: {git.get('branch')} · {dirty}({git.get('dirty_count') or 0})"
        )
        commits = git.get("recent_commits") or []
        if commits:
            lines.append("最近提交：" + " | ".join(str(c)[:60] for c in commits[:2]))
    if observed.get("daily_review_headline"):
        lines.append("日报：" + str(observed["daily_review_headline"])[:160])
    if observed.get("weekly_review_headline"):
        lines.append("周报：" + str(observed["weekly_review_headline"])[:160])
    risks = observed.get("risks") or []
    if risks:
        lines.append("风险：" + "；".join(str(r)[:80] for r in risks[:4]))

    for label, key in (
        ("目标", "goals"),
        ("约束", "constraints"),
        ("开放问题", "open_questions"),
        ("架构取舍", "architecture_choices"),
    ):
        items = decided.get(key) or []
        if items:
            lines.append(f"{label}：")
            for it in items[:6]:
                lines.append(f"- {it}")

    text = "\n".join(lines).strip() + "\n"
    if len(text) > DIGEST_MAX_CHARS:
        text = text[: DIGEST_MAX_CHARS - 20].rstrip() + "\n…(截断)\n"
    return text


def build_digest(
    root: Path,
    *,
    project_id: str,
    use_cache: bool = True,
    persist: bool = True,
) -> dict[str, Any]:
    root = Path(root)
    cache_key = f"{root.resolve()}:{project_id}"
    now = time.monotonic()
    if use_cache and cache_key in _digest_cache:
        ts, cached = _digest_cache[cache_key]
        if now - ts < _CACHE_TTL_S:
            return cached

    observed = compile_observed(root, project_id=project_id)
    decided = load_decided(root)
    digest_text = format_digest(
        project_id=project_id, observed=observed, decided=decided
    )
    if persist:
        dpath = digest_path(root)
        dpath.parent.mkdir(parents=True, exist_ok=True)
        dpath.write_text(digest_text, encoding="utf-8")

    payload = {
        "ok": True,
        "project_id": project_id,
        "as_of": observed.get("as_of"),
        "digest": digest_text,
        "observed": observed,
        "decided": decided,
    }
    _digest_cache[cache_key] = (now, payload)
    return payload


def clear_digest_cache() -> None:
    _digest_cache.clear()
