"""Desktop Agent 项目心智 L1 — 观察脑编译 + 决策脑落盘。

权威：2017 `<ws>/.ccc/agent-mind/`（与 board 同权威）。
契约：docs/product/loop-engineer-authority.md · 双层心智 · LPSN · S
- L1a observed：系统编译（board / git / daily / weekly）
- L1b decided：Agent/人经 Hub PUT（schema 校验）；goals 可含 exit_condition / status
- digest：≤2KB 注入稿；live board 仍优先于本 digest
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import hub_lens

SCHEMA_VERSION = "1.1"
DIGEST_MAX_CHARS = 2000
BRAIN_SOFT_CAP = 3500
DECIDED_LIST_MAX = 40
DECIDED_ITEM_MAX_CHARS = 400
_CACHE_TTL_S = 45.0
_digest_cache: dict[str, tuple[float, dict[str, Any]]] = {}

ALLOWED_DECIDED_KEYS = (
    "goals",
    "constraints",
    "open_questions",
    "architecture_choices",
    "transfer_lessons",
)
TRANSFER_LESSONS_MAX = 12
TRANSFER_LESSON_HINT_MAX = 240
GOAL_STATUSES = frozenset({"planned", "dispatched", "probed", "stable", "abandoned"})
FORBIDDEN_DECIDED_SUBSTRINGS = (
    "enable engine",
    "invent",
    "set_mode",
    "control.json",
    "擅自 enable",
)
_PIPELINE_ONLY_GOAL_RE = re.compile(
    r"^(管道可空转|对齐基线|pipeline.?idle|空板可转|仅对齐)$",
    re.IGNORECASE,
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
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("```"):
            continue
        s = re.sub(r"^#+\s*", "", s).strip()
        if s:
            return f"{latest.name}: {s[:180]}"
    return latest.name


def _goal_id_from_text(text: str) -> str:
    return "g-" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:10]


def normalize_goal(item: Any) -> dict[str, Any] | None:
    """Upgrade string goals to {id,text,exit_condition,status}; accept dicts."""
    if isinstance(item, str):
        text = item.strip()
        if not text:
            return None
        return {
            "id": _goal_id_from_text(text),
            "text": text[:DECIDED_ITEM_MAX_CHARS],
            "exit_condition": "",
            "status": "planned",
        }
    if not isinstance(item, dict):
        return None
    text = str(item.get("text") or item.get("goal") or "").strip()
    if not text:
        return None
    status = str(item.get("status") or "planned").strip().lower()
    if status not in GOAL_STATUSES:
        status = "planned"
    gid = str(item.get("id") or "").strip() or _goal_id_from_text(text)
    exit_c = str(item.get("exit_condition") or item.get("probe") or "").strip()
    return {
        "id": gid[:64],
        "text": text[:DECIDED_ITEM_MAX_CHARS],
        "exit_condition": exit_c[:DECIDED_ITEM_MAX_CHARS],
        "status": status,
    }


def goal_display(g: dict[str, Any] | str) -> str:
    if isinstance(g, str):
        return g
    text = str(g.get("text") or "")
    st = str(g.get("status") or "planned")
    exit_c = str(g.get("exit_condition") or "").strip()
    bit = f"[{st}] {text}"
    if exit_c:
        bit += f" · exit=`{exit_c[:80]}`"
    return bit


def unfinished_product_goals(decided: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for g in decided.get("goals") or []:
        if isinstance(g, str):
            ng = normalize_goal(g)
            if ng:
                out.append(ng)
            continue
        if not isinstance(g, dict):
            continue
        st = str(g.get("status") or "planned").lower()
        if st in ("stable", "abandoned"):
            continue
        ng = normalize_goal(g)
        if ng:
            out.append(ng)
    return out


def next_product_goal(decided: dict[str, Any]) -> dict[str, Any] | None:
    """Prefer discussable/closable goals; skip in-flight dispatched-only."""
    unfinished = unfinished_product_goals(decided)
    for g in unfinished:
        st = str(g.get("status") or "planned").lower()
        if st != "dispatched":
            return g
    return None


def _validate_decided_item(text: str) -> None:
    low = text.lower()
    for bad in FORBIDDEN_DECIDED_SUBSTRINGS:
        if bad.lower() in low:
            raise ValueError(f"decided item forbidden content: {bad}")


def _validate_goals_list(goals: list[Any]) -> list[dict[str, Any]]:
    cleaned: list[dict[str, Any]] = []
    for item in goals:
        ng = normalize_goal(item)
        if not ng:
            continue
        _validate_decided_item(ng["text"])
        if ng.get("exit_condition"):
            _validate_decided_item(ng["exit_condition"])
        cleaned.append(ng)
        if len(cleaned) >= DECIDED_LIST_MAX:
            break
    # Soft: sole goal must not be pipeline-only with no exit
    if len(cleaned) == 1:
        only = cleaned[0]
        if _PIPELINE_ONLY_GOAL_RE.match(only["text"].strip()) and not only.get(
            "exit_condition"
        ):
            raise ValueError(
                "sole goal cannot be pipeline-idle / 对齐基线 without exit_condition"
            )
    return cleaned


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
        risks.append(f"abnormal={counts.get('abnormal')} → 本会话 hub_repair")
    if not board.get("ok", True) and board.get("error"):
        risks.append(str(board.get("error"))[:120])
    # Exhausted / board-repair nudge for Agent self-heal training
    try:
        from chat_server.services.board_repair import list_blockers

        bl = list_blockers(root)
        ex_n = len(bl.get("exhausted") or [])
        if ex_n:
            risks.append(f"exhausted={ex_n} → failure_pack+优化定稿")
    except Exception as exc:  # noqa: BLE001
        import logging
        logging.getLogger("ccc.agent_mind").warning(
            "list_blockers for observed risks failed: %s", exc
        )

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
            "transfer_lessons": [],
            "updated_at": None,
            "updated_by": None,
        }
    out = {
        "schema_version": str(data.get("schema_version") or SCHEMA_VERSION),
        "goals": [],
        "constraints": [],
        "open_questions": [],
        "architecture_choices": [],
        "transfer_lessons": [],
        "updated_at": data.get("updated_at"),
        "updated_by": data.get("updated_by"),
    }
    raw_goals = data.get("goals") or []
    if isinstance(raw_goals, list):
        for item in raw_goals:
            ng = normalize_goal(item)
            if ng:
                # preserve existing id when loading strings would re-id — prefer stable
                if isinstance(item, dict) and item.get("id"):
                    ng["id"] = str(item["id"])[:64]
                out["goals"].append(ng)
            if len(out["goals"]) >= DECIDED_LIST_MAX:
                break
    for k in ("constraints", "open_questions", "architecture_choices"):
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
    out["transfer_lessons"] = _normalize_transfer_lessons(
        data.get("transfer_lessons") or []
    )
    return out


def _normalize_transfer_lessons(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        epic_id = str(item.get("epic_id") or "").strip()[:128]
        bucket = str(item.get("bucket") or "").strip()[:64]
        hint = str(item.get("hint") or "").strip()[:TRANSFER_LESSON_HINT_MAX]
        if not (epic_id or bucket or hint):
            continue
        out.append(
            {
                "ts": str(item.get("ts") or "")[:40],
                "epic_id": epic_id,
                "bucket": bucket or "other",
                "title_snip": str(item.get("title_snip") or "")[:80],
                "hint": hint,
                "bad_pattern": str(item.get("bad_pattern") or "")[:160],
                "good_fix": str(item.get("good_fix") or "")[:160],
                "source": str(item.get("source") or "system")[:32],
            }
        )
        if len(out) >= TRANSFER_LESSONS_MAX:
            break
    return out


def append_transfer_lesson(
    root: Path,
    *,
    epic_id: str = "",
    bucket: str = "other",
    title_snip: str = "",
    hint: str = "",
    bad_pattern: str = "",
    good_fix: str = "",
    source: str = "system",
) -> dict[str, Any]:
    """System-compiled epic craft lesson (not invent). Cap TRANSFER_LESSONS_MAX, newest first."""
    root = Path(root)
    cur = load_decided(root)
    lesson = {
        "ts": _now_iso(),
        "epic_id": str(epic_id or "").strip()[:128],
        "bucket": str(bucket or "other").strip()[:64] or "other",
        "title_snip": str(title_snip or "").strip()[:80],
        "hint": str(hint or "").strip()[:TRANSFER_LESSON_HINT_MAX],
        "bad_pattern": str(bad_pattern or "").strip()[:160],
        "good_fix": str(good_fix or "").strip()[:160],
        "source": str(source or "system").strip()[:32] or "system",
    }
    if not (lesson["hint"] or lesson["bucket"] or lesson["epic_id"]):
        return cur
    # Dedup same epic+bucket within recent
    existing = [
        x
        for x in (cur.get("transfer_lessons") or [])
        if not (
            x.get("epic_id") == lesson["epic_id"]
            and x.get("bucket") == lesson["bucket"]
            and lesson["epic_id"]
        )
    ]
    cur["transfer_lessons"] = ([lesson] + existing)[:TRANSFER_LESSONS_MAX]
    cur["schema_version"] = SCHEMA_VERSION
    cur["updated_at"] = _now_iso()
    cur["updated_by"] = "hub"
    _atomic_write_json(decided_path(root), cur)
    for key in list(_digest_cache.keys()):
        if key.startswith(f"{root}:"):
            _digest_cache.pop(key, None)
    return cur


def merge_decided(
    root: Path,
    patch: dict[str, Any],
    *,
    updated_by: str = "desktop-agent",
) -> dict[str, Any]:
    """字段级 upsert：同名字段整表替换（经清洗）；禁止投 backlog / 改 L0。"""
    cur = load_decided(root)
    by = (updated_by or "desktop-agent").strip() or "desktop-agent"
    if by not in ("desktop-agent", "human", "hub", "regress", "system"):
        by = "desktop-agent"

    if "goals" in patch:
        raw = patch.get("goals")
        if not isinstance(raw, list):
            raise ValueError("goals must be a list of strings or goal objects")
        cur["goals"] = _validate_goals_list(raw)

    for k in ("constraints", "open_questions", "architecture_choices"):
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
    pid = str(patch.get("project_id") or "")
    for key in list(_digest_cache.keys()):
        if key.startswith(f"{root}:") or (pid and key.endswith(f":{pid}")):
            _digest_cache.pop(key, None)
    return cur


def mark_goal_status(
    root: Path,
    goal_id: str,
    status: str,
    *,
    updated_by: str = "human",
) -> dict[str, Any]:
    """Set one goal's status (intent_stable / abandoned / probed)."""
    status = (status or "").strip().lower()
    if status not in GOAL_STATUSES:
        raise ValueError(f"invalid goal status: {status}")
    cur = load_decided(root)
    found = False
    for g in cur.get("goals") or []:
        if isinstance(g, dict) and str(g.get("id")) == goal_id:
            g["status"] = status
            found = True
            break
    if not found:
        raise ValueError(f"goal not found: {goal_id}")
    return merge_decided(
        root,
        {"goals": cur["goals"]},
        updated_by=updated_by,
    )


def _goal_matches_transfer(goal: dict[str, Any], title: str, goal_text: str) -> bool:
    blob = f"{title} {goal_text}".lower()
    text = str(goal.get("text") or "").lower()
    if text and text[:24] in blob:
        return True
    if text and blob[:24] and blob[:24] in text:
        return True
    return False


def maybe_seed_goal_from_transfer(
    root: Path,
    body: dict[str, Any],
    *,
    updated_by: str = "hub",
) -> dict[str, Any] | None:
    """T1: after product transfer succeeds, mark matching L1 goal dispatched (or seed).

    Hygiene / ops / .ccc-only transfers are skipped. Never writes stable.
    Matching unfinished goal → status=dispatched (hide from FlowRail).
    New seed → dispatched (just transferred, not「待讨论」).
    """
    try:
        from _intent_probe import extract_probe_commands, is_hygiene_transfer
    except ImportError:
        try:
            from scripts._intent_probe import (  # type: ignore
                extract_probe_commands,
                is_hygiene_transfer,
            )
        except ImportError:
            return None

    if is_hygiene_transfer(body):
        return None
    pipeline = str(body.get("pipeline") or "").strip().lower()
    if pipeline in ("ops", "hygiene", "board_ops", "board"):
        return None

    title = str(body.get("title") or "").strip()
    goal_text = str(body.get("goal") or title).strip()
    if not title and not goal_text:
        return None

    acc = body.get("acceptance")
    if isinstance(acc, list):
        acc_blob = "\n".join(f"- {x}" for x in acc if str(x or "").strip())
    else:
        acc_blob = str(acc or "")
    probes = extract_probe_commands(acc_blob) or extract_probe_commands(
        str(body.get("plan_md") or "")
    )
    exit_c = probes[0] if probes else ""

    epic_id = str(
        body.get("epic_id") or body.get("task_id") or body.get("id") or ""
    ).strip()

    decided = load_decided(root)
    goals = list(decided.get("goals") or [])

    # Match existing unfinished → mark dispatched (do not duplicate)
    for i, raw in enumerate(goals):
        g = normalize_goal(raw) if not isinstance(raw, dict) else raw
        if not isinstance(g, dict):
            continue
        st = str(g.get("status") or "planned").lower()
        if st in ("stable", "abandoned"):
            continue
        if not _goal_matches_transfer(g, title, goal_text):
            continue
        # patch in place (keep list slot)
        if isinstance(goals[i], dict):
            goals[i]["status"] = "dispatched"
            if epic_id:
                goals[i]["linked_epic_id"] = epic_id[:128]
            if exit_c and not str(goals[i].get("exit_condition") or "").strip():
                goals[i]["exit_condition"] = exit_c[:DECIDED_ITEM_MAX_CHARS]
            updated = normalize_goal(goals[i])
        else:
            updated = normalize_goal(
                {
                    **g,
                    "status": "dispatched",
                    **({"linked_epic_id": epic_id[:128]} if epic_id else {}),
                }
            )
            goals[i] = updated
        if not updated:
            return None
        merge_decided(root, {"goals": goals}, updated_by=updated_by)
        return updated

    # supersede: abandon prior unfinished when requested
    if body.get("supersede_goals") is True or body.get("intent_supersede") is True:
        for g in goals:
            if isinstance(g, dict) and str(g.get("status") or "") in (
                "planned",
                "dispatched",
                "probed",
            ):
                g["status"] = "abandoned"

    seeded = normalize_goal(
        {
            "text": title or goal_text,
            "exit_condition": exit_c,
            "status": "dispatched",
            **({"linked_epic_id": epic_id[:128]} if epic_id else {}),
        }
    )
    if not seeded:
        return None
    # normalize_goal drops unknown keys — re-attach linked_epic_id if needed
    if epic_id:
        seeded["linked_epic_id"] = epic_id[:128]
    goals.append(seeded)
    merge_decided(root, {"goals": goals}, updated_by=updated_by)
    return seeded


def match_goal_for_probes(
    decided: dict[str, Any],
    *,
    title: str = "",
    probes: list[str] | None = None,
) -> dict[str, Any] | None:
    """Find unfinished goal matching task title or probe exit_condition."""
    probes = probes or []
    unfinished = unfinished_product_goals(decided)
    title_l = (title or "").lower()
    for g in unfinished:
        text = str(g.get("text") or "").lower()
        if text and title_l and (text[:24] in title_l or title_l[:24] in text):
            return g
        exit_c = str(g.get("exit_condition") or "").strip()
        if exit_c and any(exit_c in p or p in exit_c for p in probes):
            return g
    return unfinished[0] if len(unfinished) == 1 else None


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
        "released/VERSION 只到 code_landed；意图完成须探针+regress+intent_stable。",
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

    goals = decided.get("goals") or []
    unfinished = unfinished_product_goals(decided)
    nxt = next_product_goal(decided)
    if nxt:
        lines.append(
            f"【下一产品目标 · next_product_goal】{goal_display(nxt)}"
        )
    if unfinished:
        lines.append("未完成产品目标（优先推进，勿抢卫生/烟测）：")
        for g in unfinished[:6]:
            lines.append(f"- {goal_display(g)}")
    stable = [
        g
        for g in goals
        if isinstance(g, dict) and str(g.get("status")) == "stable"
    ]
    if stable:
        lines.append("已稳定意图：")
        for g in stable[:4]:
            lines.append(f"- {goal_display(g)}")

    for label, key in (
        ("约束", "constraints"),
        ("开放问题", "open_questions"),
        ("架构取舍", "architecture_choices"),
    ):
        items = decided.get(key) or []
        if items:
            lines.append(f"{label}：")
            for it in items[:6]:
                lines.append(f"- {it}")

    lessons = decided.get("transfer_lessons") or []
    if lessons:
        lines.append("近期定卡教训（必读 · 勿重复同构失败）：")
        for les in lessons[:5]:
            if not isinstance(les, dict):
                continue
            bucket = les.get("bucket") or "?"
            hint = (les.get("hint") or les.get("good_fix") or "")[:120]
            snip = les.get("title_snip") or les.get("epic_id") or ""
            lines.append(f"- [{bucket}] {snip}: {hint}".rstrip(": "))

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
    brain_payload: dict[str, Any] = {
        "brain": "",
        "brain_meta": {},
    }
    # 编排运维 ccc：不灌业务规划脑包
    if (project_id or "").strip().lower() != "ccc":
        try:
            from . import project_brain as _pb

            brain_payload = _pb.compile_brain(root, project_id=project_id)
        except Exception:
            brain_payload = {"ok": False, "brain": "", "brain_meta": {}}
    brain_text = str(brain_payload.get("brain") or "").strip()
    if brain_text:
        # digest 仍短；brain 单独字段供 sidecar 拼接（总注入有帽）
        combined = digest_text.rstrip() + "\n\n" + brain_text
        if len(combined) > DIGEST_MAX_CHARS + BRAIN_SOFT_CAP:
            combined = combined[: DIGEST_MAX_CHARS + BRAIN_SOFT_CAP - 20].rstrip() + "\n…(截断)\n"
        inject_text = combined
    else:
        inject_text = digest_text

    if persist:
        dpath = digest_path(root)
        dpath.parent.mkdir(parents=True, exist_ok=True)
        dpath.write_text(digest_text, encoding="utf-8")

    payload = {
        "ok": True,
        "project_id": project_id,
        "as_of": observed.get("as_of"),
        "digest": digest_text,
        "brain": brain_text,
        "brain_meta": brain_payload.get("brain_meta") or {},
        "inject": inject_text,
        "observed": observed,
        "decided": decided,
        "next_product_goal": next_product_goal(decided),
        "unfinished_goals": unfinished_product_goals(decided),
    }
    _digest_cache[cache_key] = (now, payload)
    return payload


def clear_digest_cache() -> None:
    _digest_cache.clear()
