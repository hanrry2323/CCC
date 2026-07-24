"""Desktop Agent 板务白名单 — 清残卡 / 剪幽灵轨 / 有限 reopen。

契约：docs/product/loop-engineer-authority.md「Desktop 板务白名单」
禁止写业务源码；禁止 invent。审计写入 ~/.ccc/stats/board-repair.jsonl
"""

from __future__ import annotations

import json
import logging
import os
import shutil
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
_INFLIGHT_COLS = frozenset({"planned", "in_progress", "testing", "verified"})
_STUCK_SPLIT = frozenset({"running", "planned", "active"})


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


def list_stuck_running_epics(workspace: Path) -> list[dict[str, Any]]:
    """epic 已标 running/planned，但无在途子卡（子卡缺失/已 released/已归档）。

    Engine 只扇出 pending；这类卡会占活跃 backlog 却永不推进——运维必须沉底，
    禁止只会说「回业务对话重下」。
    """
    store = FileBoardStore(workspace)
    stuck: list[dict[str, Any]] = []
    for t in store.list_tasks("backlog", include_hidden=False):
        if (t.get("card_kind") or "") != "epic":
            continue
        ss = str(t.get("split_status") or "").strip().lower()
        if ss not in _STUCK_SPLIT:
            continue
        tid = str(t.get("id") or "")
        if not tid:
            continue
        kids = [str(k) for k in (t.get("child_ids") or []) if str(k).strip()]
        kid_cols: list[str] = []
        inflight = False
        for kid in kids:
            kcol = store.resolve_task_column(kid)
            if kcol is None:
                col2, _ = store.find_task(kid)
                kcol = col2
            label = kcol or "missing"
            kid_cols.append(label)
            if label in _INFLIGHT_COLS:
                inflight = True
                break
        if inflight:
            continue
        # pending 无子卡 = 等扇出，不是 stuck；running/planned 无在途 = 孤儿
        reason = "orphan_no_inflight"
        if not kids:
            reason = "running_without_children"
        elif all(c == "missing" for c in kid_cols):
            reason = "children_missing"
        elif any(c == "missing" for c in kid_cols) and all(
            c in ("missing", "released", "abnormal") for c in kid_cols
        ):
            reason = "children_partial_missing"
        stuck.append(
            {
                "id": tid,
                "column": "backlog",
                "title": str(t.get("title") or tid)[:80],
                "card_kind": "epic",
                "split_status": ss,
                "reason": reason,
                "child_cols": kid_cols[:12],
            }
        )
    return stuck


def settle_stuck_epics(
    workspace: Path,
    project_id: str,
    *,
    reason: str = "desktop_settle_stuck_running",
) -> dict[str, Any]:
    """把孤儿 running epic 标 done + ui_hidden，并剪幽灵轨。"""
    store = FileBoardStore(workspace)
    stuck = list_stuck_running_epics(workspace)
    settled: list[str] = []
    purged: list[dict[str, Any]] = []
    for item in stuck:
        tid = item["id"]
        note = ((store.find_task(tid)[1] or {}).get("note") or "").strip()
        fields = {
            "split_status": "done",
            "ui_hidden": True,
            "note": (note + f"\n[board-repair] settle_stuck: {reason}").strip(),
        }
        if store.patch_task(tid, fields):
            settled.append(tid)
            purged.append(purge_flow_for_epic(project_id, tid))
    return {
        "stuck_before": stuck,
        "settled": settled,
        "purged": purged,
        "count": len(settled),
    }


def list_blockers(workspace: Path) -> dict[str, Any]:
    """只读：列出挡 ready 的残卡（含孤儿 running epic）。"""
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
    stuck_running = list_stuck_running_epics(workspace)
    return {
        "abnormal": abnormal,
        "failed_epics": failed_epics,
        "done_visible_epics": done_visible,
        "stuck_running_epics": stuck_running,
        "blocker_count": len(abnormal) + len(failed_epics) + len(stuck_running),
    }


def _preserve_failure_evidence(workspace: Path, task_id: str) -> dict[str, Any]:
    """归档现场证据到 quarantines/<tid>/board-repair/；永不截断 failures.jsonl。"""
    tid = (task_id or "").strip()
    if not tid:
        return {"ok": False, "copied": []}
    root = Path(workspace) / ".ccc"
    dst = root / "quarantines" / tid / "board-repair"
    copied: list[str] = []
    try:
        dst.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return {"ok": False, "error": str(exc)[:200], "copied": []}

    candidates: list[Path] = []
    for sub, name in (
        ("pids", f"{tid}.review_fail.md"),
        ("pids", f"{tid}.short_path_fails"),
        ("reports", f"{tid}.report.md"),
        ("reports", f"{tid}.result.json"),
        ("reports", f"{tid}.review.md"),
        ("verdicts", f"{tid}.verdict.md"),
        ("plans", f"{tid}.plan.md"),
        ("phases", f"{tid}.phases.json"),
    ):
        candidates.append(root / sub / name)
    # board jsonl snapshot（列无关：find）
    board = root / "board"
    if board.is_dir():
        for col_dir in board.iterdir():
            if not col_dir.is_dir():
                continue
            p = col_dir / f"{tid}.jsonl"
            if p.is_file():
                candidates.append(p)

    for src in candidates:
        if not src.is_file():
            continue
        try:
            target = dst / src.name
            shutil.copy2(src, target)
            copied.append(str(target.relative_to(root)))
        except OSError as exc:
            _log.warning("preserve evidence %s: %s", src, exc)

    # 摘本卡 failures.jsonl 行（保留全量账本；另存切片方便工单）
    failures = root / "stats" / "failures.jsonl"
    if failures.is_file():
        try:
            lines = [
                ln
                for ln in failures.read_text(encoding="utf-8", errors="replace").splitlines()
                if tid in ln
            ]
            if lines:
                slice_p = dst / "failures-slice.jsonl"
                slice_p.write_text("\n".join(lines) + "\n", encoding="utf-8")
                copied.append(str(slice_p.relative_to(root)))
        except OSError as exc:
            _log.warning("preserve failures slice %s: %s", tid, exc)

    meta = {
        "task_id": tid,
        "preserved_at": time.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
        "copied": copied,
        "note": "board-repair archive; failures.jsonl SSOT untouched",
    }
    try:
        (dst / "manifest.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError:
        pass
    return {"ok": True, "copied": copied, "dir": str(dst)}


def archive_tasks(
    workspace: Path,
    task_ids: list[str] | None = None,
    *,
    reason: str = "desktop_board_repair",
) -> dict[str, Any]:
    """隐藏残卡：abnormal / failed epic（及显式 task_ids）。数据保留，ui_hidden=true。

    failed epic 同时标 split_status=done（放弃），避免再计入活跃风险。
    隐藏前把 report/verdict/review_fail 等拷入 quarantines/<tid>/board-repair/；
    **不删** `.ccc/stats/failures.jsonl`。
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
    evidence: list[dict[str, Any]] = []
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
        evidence.append(_preserve_failure_evidence(workspace, tid))
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
    return {
        "hidden": hidden,
        "skipped": skipped,
        "count": len(hidden),
        "evidence": evidence,
    }


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
    """一体：归档 abnormal+failed → 沉底孤儿 running → hide done → 剪幽灵轨。"""
    blockers = list_blockers(workspace)
    epic_ids = [
        x["id"] for x in blockers["failed_epics"]
    ] + [
        x["id"]
        for x in blockers["abnormal"]
        if x.get("card_kind") == "epic"
    ] + [
        x["id"] for x in blockers.get("stuck_running_epics") or []
    ]

    archived = archive_tasks(workspace, reason=reason)
    settled = settle_stuck_epics(workspace, project_id, reason=reason)
    # 显式再藏 abnormal 列（archive 无 id 时已覆盖）
    done_hide = hide_done_epics(workspace)

    purged: list[dict[str, Any]] = list(settled.get("purged") or [])
    seen: set[str] = {x["id"] for x in (settled.get("stuck_before") or []) if x.get("id")}
    for row in purged:
        eid = str((row or {}).get("epic_id") or "")
        if eid:
            seen.add(eid)
    for eid in epic_ids + archived.get("hidden", []):
        if eid in seen:
            continue
        # 只 purge 看起来像 epic 的 id，或曾在 failed/abnormal/stuck 列表
        if eid in {x["id"] for x in blockers["failed_epics"]} or eid in {
            x["id"] for x in blockers["abnormal"] if x.get("card_kind") == "epic"
        } or eid in {
            x["id"] for x in blockers.get("stuck_running_epics") or []
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
    wake: dict[str, Any] | None = None
    try:
        from _engine_wake import ensure_engine_for_task

        wake = ensure_engine_for_task(
            task_id=f"board-repair-{project_id}",
            reason="board_repair_clear_blockers",
            workspace=workspace,
            workspace_name=project_id,
        )
    except Exception as exc:  # noqa: BLE001 — 运维路径：唤醒失败不挡清板
        wake = {"ok": False, "error": f"{type(exc).__name__}: {exc}"[:200]}

    return {
        "before": blockers,
        "archived": archived,
        "settled_stuck": settled,
        "hide_done": done_hide,
        "purged": purged,
        "after": after,
        "engine_wake": wake,
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
