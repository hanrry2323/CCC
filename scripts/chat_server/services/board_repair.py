"""Desktop Agent 板务白名单 — 清残卡 / 剪幽灵轨 / 有限 reopen。

契约：docs/product/loop-engineer-authority.md「Desktop 板务白名单」
禁止写业务源码；禁止 invent。审计写入 ~/.ccc/stats/board-repair.jsonl
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any

from _board_store import COLUMNS, FileBoardStore
from _task_reopen import reopen_task

from . import flow_events

_log = logging.getLogger("ccc.board_repair")

ALLOWED_ACTIONS = frozenset(
    {
        "status",
        "archive",
        "hide_done",
        "reopen",
        "purge_flow",
        "clear_blockers",
    }
)

_ARCHIVE_COLS = ("abnormal", "backlog", "planned", "in_progress", "testing", "verified")


def _audit_path() -> Path:
    raw = os.environ.get("CCC_BOARD_REPAIR_LOG", "").strip()
    if raw:
        return Path(raw)
    return Path.home() / ".ccc" / "stats" / "board-repair.jsonl"


def _audit(rec: dict[str, Any]) -> None:
    path = _audit_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
        **rec,
    }
    try:
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError as exc:
        _log.warning("board-repair audit write failed: %s", exc)


def list_blockers(workspace: Path) -> dict[str, Any]:
    """只读：列出挡 ready 的残卡。"""
    store = FileBoardStore(workspace)
    abnormal: list[dict[str, Any]] = []
    failed_epics: list[dict[str, Any]] = []
    done_visible: list[dict[str, Any]] = []
    for col in COLUMNS:
        for t in store.list_tasks(col, include_hidden=False):
            tid = str(t.get("id") or "")
            if not tid:
                continue
            kind = t.get("card_kind") or "work"
            ss = str(t.get("split_status") or "")
            item = {
                "id": tid,
                "column": col,
                "title": str(t.get("title") or tid)[:80],
                "card_kind": kind,
                "split_status": ss,
            }
            if col == "abnormal":
                abnormal.append(item)
            elif kind == "epic" and ss == "failed":
                failed_epics.append(item)
            elif kind == "epic" and ss == "done" and col == "backlog":
                done_visible.append(item)
    return {
        "abnormal": abnormal,
        "failed_epics": failed_epics,
        "done_visible_epics": done_visible,
        "blocker_count": len(abnormal) + len(failed_epics),
    }


def archive_tasks(
    workspace: Path,
    task_ids: list[str] | None = None,
    *,
    reason: str = "desktop_board_repair",
) -> dict[str, Any]:
    """隐藏残卡：abnormal / failed epic（及显式 task_ids）。数据保留，ui_hidden=true。

    failed epic 同时标 split_status=done（放弃），避免再计入活跃风险。
    """
    store = FileBoardStore(workspace)
    targets: list[tuple[str, dict]] = []
    if task_ids:
        for tid in task_ids:
            col, task = store.find_task(str(tid).strip())
            if col and task:
                targets.append((col, task))
    else:
        for col in _ARCHIVE_COLS:
            for t in store.list_tasks(col, include_hidden=False):
                kind = t.get("card_kind") or "work"
                ss = str(t.get("split_status") or "")
                if col == "abnormal" or (kind == "epic" and ss == "failed"):
                    targets.append((col, t))

    hidden: list[str] = []
    skipped: list[dict[str, str]] = []
    for col, task in targets:
        tid = str(task.get("id") or "")
        if not tid:
            continue
        if task.get("ui_hidden"):
            skipped.append({"id": tid, "reason": "already_hidden"})
            continue
        # 真在飞（planned/in_progress/testing）且非 abnormal/failed：须显式 id
        if (
            not task_ids
            and col in ("planned", "in_progress", "testing", "verified")
            and col != "abnormal"
        ):
            skipped.append({"id": tid, "reason": "active_inflight_needs_explicit_id"})
            continue
        fields: dict[str, Any] = {
            "ui_hidden": True,
            "note": ((task.get("note") or "") + f"\n[board-repair] {reason}").strip(),
        }
        if (task.get("card_kind") or "") == "epic" and str(
            task.get("split_status") or ""
        ) == "failed":
            fields["split_status"] = "done"
        if store.patch_task(tid, fields):
            hidden.append(tid)
            # abnormal 仍在 abnormal 列但 hidden → 活跃计数会跳过
        else:
            skipped.append({"id": tid, "reason": "patch_failed"})
    return {"hidden": hidden, "skipped": skipped, "count": len(hidden)}


def hide_done_epics(workspace: Path) -> dict[str, Any]:
    store = FileBoardStore(workspace)
    n = 0
    ids: list[str] = []
    for t in store.list_tasks("backlog", include_hidden=False):
        if t.get("card_kind") == "epic" and t.get("split_status") == "done":
            tid = str(t.get("id") or "")
            if tid and store.patch_task(tid, {"ui_hidden": True}):
                n += 1
                ids.append(tid)
    return {"hidden": n, "ids": ids}


def purge_flow_for_epic(project_id: str, epic_id: str) -> dict[str, Any]:
    """剪 last_epic / epic_history / flow-events 中该 epic。"""
    return flow_events.purge_epic_traces(project_id, epic_id)


def reopen(
    workspace: Path,
    task_id: str,
    *,
    to_col: str = "planned",
) -> dict[str, Any]:
    return reopen_task(workspace, task_id, to_col=to_col, wake=True)


def clear_blockers(
    workspace: Path,
    project_id: str,
    *,
    reason: str = "desktop_clear_blockers",
) -> dict[str, Any]:
    """一体：归档 abnormal+failed → hide done → 剪幽灵轨。"""
    blockers = list_blockers(workspace)
    epic_ids = [
        x["id"] for x in blockers["failed_epics"]
    ] + [
        x["id"]
        for x in blockers["abnormal"]
        if x.get("card_kind") == "epic"
    ]

    archived = archive_tasks(workspace, reason=reason)
    # 显式再藏 abnormal 列（archive 无 id 时已覆盖）
    done_hide = hide_done_epics(workspace)

    purged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for eid in epic_ids + archived.get("hidden", []):
        if eid in seen:
            continue
        # 只 purge 看起来像 epic 的 id，或曾在 failed/abnormal epic 列表
        if eid in {x["id"] for x in blockers["failed_epics"]} or eid in {
            x["id"] for x in blockers["abnormal"] if x.get("card_kind") == "epic"
        }:
            seen.add(eid)
            purged.append(purge_flow_for_epic(project_id, eid))

    # 若 last_epic 指向已隐藏卡，也清
    last = flow_events.load_last_epic(project_id)
    if last and last.get("epic_id"):
        eid = str(last["epic_id"])
        col, task = FileBoardStore(workspace).find_task(eid)
        if task and (task.get("ui_hidden") or str(task.get("split_status") or "") in (
            "done",
            "failed",
        )):
            if eid not in seen:
                purged.append(purge_flow_for_epic(project_id, eid))

    after = list_blockers(workspace)
    return {
        "before": blockers,
        "archived": archived,
        "hide_done": done_hide,
        "purged": purged,
        "after": after,
        "ready_hint": after["blocker_count"] == 0,
    }


def run_repair(
    *,
    action: str,
    workspace: Path,
    project_id: str,
    task_ids: list[str] | None = None,
    epic_id: str | None = None,
    to_col: str = "planned",
    reason: str = "desktop_agent",
    source: str = "desktop",
) -> dict[str, Any]:
    act = (action or "").strip().lower()
    if act not in ALLOWED_ACTIONS:
        return {
            "ok": False,
            "error": "invalid_action",
            "allowed": sorted(ALLOWED_ACTIONS),
        }
    if not workspace.is_dir() or not (workspace / ".ccc" / "board").is_dir():
        return {"ok": False, "error": "no_board", "workspace": str(workspace)}

    result: dict[str, Any]
    if act == "status":
        result = {"ok": True, "action": act, **list_blockers(workspace)}
    elif act == "archive":
        result = {
            "ok": True,
            "action": act,
            **archive_tasks(workspace, task_ids, reason=reason),
        }
    elif act == "hide_done":
        result = {"ok": True, "action": act, **hide_done_epics(workspace)}
    elif act == "reopen":
        tid = (task_ids or [None])[0] if task_ids else None
        if not tid:
            return {"ok": False, "error": "missing_task_id"}
        result = {"ok": True, "action": act, **reopen(workspace, str(tid), to_col=to_col)}
    elif act == "purge_flow":
        eid = epic_id or ((task_ids or [None])[0] if task_ids else None)
        if not eid:
            return {"ok": False, "error": "missing_epic_id"}
        result = {
            "ok": True,
            "action": act,
            **purge_flow_for_epic(project_id, str(eid)),
        }
    else:  # clear_blockers
        result = {
            "ok": True,
            "action": act,
            **clear_blockers(workspace, project_id, reason=reason),
        }

    _audit(
        {
            "action": act,
            "project_id": project_id,
            "workspace": str(workspace),
            "source": source,
            "reason": reason,
            "task_ids": task_ids or [],
            "epic_id": epic_id,
            "ok": result.get("ok", True),
            "summary": {
                k: result.get(k)
                for k in (
                    "count",
                    "hidden",
                    "blocker_count",
                    "ready_hint",
                    "engine_running",
                )
                if k in result
            },
        }
    )
    flow_events.append_event(
        "board_repair",
        {
            "project_id": project_id,
            "action": act,
            "source": source,
            "reason": reason,
            "task_ids": task_ids or [],
            "result_ok": bool(result.get("ok")),
        },
    )
    return result
