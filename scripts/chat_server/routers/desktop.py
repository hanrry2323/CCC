"""CCC Desktop API — 统一 Thread / 转任务门禁 / 流程事件。

契约：
- docs/product/ccc-desktop-architecture.md
- docs/product/transfer-gate.md
- docs/product/flow-events.md
"""

from __future__ import annotations

import json
import re
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from ..auth import check_auth
from ..services import flow_events
from ..services import session_store as store
from ..services import transfer_gate
from ..services.board_client import board_proxy
from .board import (
    _assert_dispatchable_workspace,
    _hub_ensure_engine,
    _merge_create_payload,
    _resolve_workspace,
    _workspace_root,
    _write_seed_artifacts,
)
from .projects import (
    PROJECT_TO_WORKSPACE,
    PROJECTS,
    default_project_id,
    get_project_path,
    reload_projects,
)

router = APIRouter(prefix="/api/desktop", tags=["desktop"])

_EPIC_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,80}$")


def _project_workspace(project_id: str) -> str:
    if not PROJECTS:
        reload_projects()
    if project_id not in PROJECTS:
        raise HTTPException(status_code=404, detail=f"unknown project: {project_id}")
    return PROJECT_TO_WORKSPACE.get(project_id, project_id)


def _assert_project_dispatchable(project_id: str) -> str:
    info = PROJECTS.get(project_id) if PROJECTS else None
    if not PROJECTS:
        reload_projects()
        info = PROJECTS.get(project_id)
    if not info:
        raise HTTPException(
            status_code=400,
            detail={
                "ok": False,
                "error": "project_not_dispatchable",
                "errors": [
                    {
                        "code": "project_not_dispatchable",
                        "message": f"未登记项目: {project_id}",
                    }
                ],
            },
        )
    if not info.get("engine_eligible", True) or (info.get("role") or "") == "orch":
        raise HTTPException(
            status_code=400,
            detail={
                "ok": False,
                "error": "project_not_dispatchable",
                "errors": [
                    {
                        "code": "project_not_dispatchable",
                        "message": "编排仓 / engine=false 不可下达",
                    }
                ],
            },
        )
    workspace = _project_workspace(project_id)
    _assert_dispatchable_workspace(workspace)
    return workspace


# ── Projects ──────────────────────────────────────────────


@router.get("/projects")
async def desktop_projects(request: Request):
    """项目树（仅统一 Desktop 视图）。"""
    check_auth(request)
    reload_projects()
    return {
        "ok": True,
        "projects": [
            {
                "id": pid,
                "name": info["name"],
                "path": info["path"],
                "workspace": PROJECT_TO_WORKSPACE.get(pid, pid),
                "role": info.get("role") or "app",
                "engine_eligible": bool(info.get("engine_eligible", True)),
            }
            for pid, info in PROJECTS.items()
        ],
        "default_project": default_project_id(),
        "server": "desktop",
    }


# ── Threads（统一会话，不暴露 Hub/Claude 双源）────────────


@router.get("/threads")
async def list_threads(request: Request, project_id: str = ""):
    check_auth(request)
    pid = (project_id or "").strip() or default_project_id()
    if pid not in PROJECTS:
        reload_projects()
    sessions = store.list_sessions(pid, include_tests=False)
    threads = [
        {
            "thread_id": s.get("session_id"),
            "title": s.get("title"),
            "updated_at": s.get("updated_at"),
            "project_id": pid,
        }
        for s in sessions
    ]
    return {"ok": True, "project_id": pid, "threads": threads}


@router.post("/threads")
async def create_thread(request: Request):
    check_auth(request)
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="JSON object required")
    pid = str(body.get("project_id") or body.get("project") or "").strip()
    if not pid:
        raise HTTPException(status_code=400, detail="project_id required")
    if pid not in PROJECTS:
        reload_projects()
    if pid not in PROJECTS:
        raise HTTPException(status_code=404, detail=f"unknown project: {pid}")
    # Validate path exists
    try:
        get_project_path(pid)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    tid = str(body.get("thread_id") or uuid.uuid4())
    title = str(body.get("title") or "New Chat").strip()[:80]
    store.save_session(
        tid,
        messages=[],
        project=pid,
        mode="chat",
        status="idle",
    )
    if title and title != "New Chat":
        store.rename_session(tid, pid, title)
    data = store.get_session(tid, pid) or {}
    return {
        "ok": True,
        "thread_id": tid,
        "project_id": pid,
        "title": data.get("title") or title,
    }


@router.get("/threads/{thread_id}")
async def get_thread(request: Request, thread_id: str, project_id: str = ""):
    check_auth(request)
    pid = (project_id or "").strip() or default_project_id()
    data = store.get_session(thread_id, pid)
    if data is None:
        raise HTTPException(status_code=404, detail="thread not found")
    return {
        "ok": True,
        "thread_id": data.get("session_id") or thread_id,
        "project_id": pid,
        "title": data.get("title"),
        "messages": data.get("messages") or [],
        "updated_at": data.get("updated_at"),
        "status": data.get("status"),
    }


@router.patch("/threads/{thread_id}")
async def rename_thread(request: Request, thread_id: str, project_id: str = ""):
    check_auth(request)
    pid = (project_id or "").strip() or default_project_id()
    body = await request.json()
    title = str((body or {}).get("title") or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="title required")
    data = store.rename_session(thread_id, pid, title)
    if data is None:
        raise HTTPException(status_code=404, detail="thread not found")
    return {"ok": True, "thread_id": thread_id, "title": data.get("title")}


@router.delete("/threads/{thread_id}")
async def delete_thread(request: Request, thread_id: str, project_id: str = ""):
    check_auth(request)
    pid = (project_id or "").strip() or default_project_id()
    store.delete_session(thread_id, pid)
    return {"ok": True}


# ── Transfer（硬门禁 → 仅 epic）───────────────────────────


def _make_epic_id(title: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", title.strip().lower()).strip("-")[:40]
    if not slug:
        slug = "epic"
    return f"{slug}-{uuid.uuid4().hex[:8]}"


@router.post("/transfer")
async def transfer_to_epic(request: Request):
    """聊透门禁通过后仅创建 backlog epic。"""
    check_auth(request)
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="JSON object required")

    ok, errors = transfer_gate.validate_transfer_payload(body)
    if not ok:
        return JSONResponse(
            status_code=400,
            content={
                "ok": False,
                "error": errors[0]["code"] if errors else "gate_failed",
                "errors": errors,
            },
        )

    project_id = str(body.get("project_id") or body.get("project") or "").strip()
    try:
        workspace = _assert_project_dispatchable(project_id)
    except HTTPException as exc:
        if isinstance(exc.detail, dict):
            return JSONResponse(status_code=400, content=exc.detail)
        raise

    title = str(body.get("title") or "").strip()[:80]
    epic_id = str(body.get("epic_id") or "").strip() or _make_epic_id(title)
    if not _EPIC_ID_RE.match(epic_id):
        return JSONResponse(
            status_code=400,
            content={
                "ok": False,
                "error": "invalid_epic_id",
                "errors": [
                    {"code": "invalid_epic_id", "message": "epic_id 非法"}
                ],
            },
        )

    executor_intent = transfer_gate.resolve_executor_intent(body)
    description = transfer_gate.build_epic_description(
        {**body, "executor_intent": executor_intent}
    )
    plan_md = transfer_gate.build_plan_md(body)

    note = json.dumps(
        {
            "transfer_gate": {
                "pipeline": body.get("pipeline"),
                "executor_intent": executor_intent,
                "feasibility": "ok",
                "skills_hint": body.get("skills_hint") or [],
                "thread_id": body.get("thread_id"),
            }
        },
        ensure_ascii=False,
    )

    task_body: dict[str, Any] = {
        "id": epic_id,
        "title": title,
        "description": description,
        "status": "backlog",
        "workspace": workspace,
        "card_kind": "epic",
        "split_status": "pending",
        "complexity": str(body.get("complexity") or "medium"),
        "note": note[:2000],
        "tags": ["desktop-transfer", f"exec:{executor_intent}"],
        # 禁止附带 phases：转任务只写 epic，由 Engine/product 扇出
    }

    resp = await board_proxy("POST", "/api/tasks", json_body=task_body)
    if resp.status_code not in (200, 201):
        try:
            detail = json.loads(
                resp.body.decode()
                if isinstance(resp.body, (bytes, bytearray))
                else resp.body
            )
        except Exception:
            detail = {"raw": str(resp.body)[:300]}
        return JSONResponse(
            status_code=resp.status_code,
            content={"ok": False, "error": "board_create_failed", "detail": detail},
        )

    payload = _merge_create_payload(
        resp.body,
        workspace=workspace,
        fallback_tid=epic_id,
        task_body=task_body,
    )
    tid = str(payload.get("task_id") or epic_id)
    # 只写 plan（不写 phases）— 扇出前留给 product；plan 便于人类与 Engine 读
    try:
        written = _write_seed_artifacts(workspace, tid, plan_md, None)
        payload["seeded"] = written
    except Exception as exc:
        payload["seed_warning"] = str(exc)[:200]

    flow_events.append_event(
        "epic_created",
        {
            "epic_id": tid,
            "title": title,
            "project_id": project_id,
            "workspace": workspace,
            "executor_intent": executor_intent,
        },
    )
    flow_events.remember_last_epic(project_id, tid, title)
    _hub_ensure_engine(workspace, tid)

    return {
        "ok": True,
        "epic_id": tid,
        "workspace": workspace,
        "column": "backlog",
        "project_id": project_id,
        "executor_intent": executor_intent,
        "engine_wake": payload.get("engine_wake"),
        "seeded": payload.get("seeded"),
    }


# ── Flow events / snapshot ────────────────────────────────


async def _fetch_board_dict(workspace: str) -> dict[str, list[dict]]:
    resp = await board_proxy("GET", "/api/board", params={"workspace": workspace})
    if resp.status_code != 200:
        return {}
    try:
        raw = json.loads(
            resp.body.decode()
            if isinstance(resp.body, (bytes, bytearray))
            else resp.body
        )
    except Exception:
        return {}
    if isinstance(raw, dict) and isinstance(raw.get("columns"), dict):
        return raw["columns"]
    if isinstance(raw, dict) and isinstance(raw.get("board"), dict):
        return raw["board"]
    if isinstance(raw, dict):
        # 兜底：值为 list 的键当列
        return {k: v for k, v in raw.items() if isinstance(v, list)}
    return {}


@router.get("/flow/epics")
async def flow_epics(request: Request, project_id: str = "", limit: int = 20):
    """项目最近 epic 列表（Desktop 右栏切换）。"""
    check_auth(request)
    pid = (project_id or "").strip()
    if not pid:
        raise HTTPException(status_code=400, detail="project_id required")
    lim = max(1, min(int(limit or 20), 40))
    items = flow_events.list_recent_epics(pid, limit=lim)
    return {"ok": True, "project_id": pid, "epics": items}


@router.get("/flow/snapshot")
async def flow_snapshot(
    request: Request,
    project_id: str = "",
    epic_id: str = "",
):
    check_auth(request)
    pid = (project_id or "").strip()
    if not pid:
        raise HTTPException(status_code=400, detail="project_id required")
    eid = (epic_id or "").strip()
    if not eid:
        last = flow_events.load_last_epic(pid)
        eid = str((last or {}).get("epic_id") or "") or (
            flow_events.latest_transfer_epic_id(pid) or ""
        )
    if not eid:
        return {
            "ok": True,
            "empty": True,
            "message": "定稿并转任务后显示执行流程",
            "project_id": pid,
            "epic_id": None,
            "works": [],
        }
    workspace = _project_workspace(pid)
    board = await _fetch_board_dict(workspace)
    snap = flow_events.snapshot_from_board(
        board, epic_id=eid, project_id=pid
    )
    return {"ok": True, "empty": False, **snap}


@router.get("/flow/events")
async def flow_events_sse(
    request: Request,
    project_id: str = "",
    epic_id: str = "",
):
    """SSE：fanout / work_status / ping。MVP 轮询看板合成。"""
    check_auth(request)
    pid = (project_id or "").strip()
    if not pid:
        raise HTTPException(status_code=400, detail="project_id required")

    async def gen():
        last_sig = ""
        last_beat = 0.0
        # 先推历史事件
        for rec in flow_events.read_events(project_id=pid, epic_id=epic_id or None):
            yield flow_events.format_sse(str(rec.get("event") or "message"), rec.get("data") or {})

        while True:
            if await request.is_disconnected():
                break
            eid = (epic_id or "").strip()
            if not eid:
                last = flow_events.load_last_epic(pid)
                eid = str((last or {}).get("epic_id") or "")
            now = time.time()
            if eid:
                try:
                    workspace = _project_workspace(pid)
                    board = await _fetch_board_dict(workspace)
                    snap = flow_events.snapshot_from_board(
                        board, epic_id=eid, project_id=pid
                    )
                    sig = json.dumps(snap, sort_keys=True, ensure_ascii=False)
                    if sig != last_sig:
                        last_sig = sig
                        yield flow_events.format_sse(
                            "fanout",
                            {
                                "epic_id": eid,
                                "works": snap.get("works") or [],
                            },
                        )
                        for w in snap.get("works") or []:
                            yield flow_events.format_sse(
                                "work_status",
                                {
                                    "epic_id": eid,
                                    "work_id": w.get("id"),
                                    "status": w.get("status"),
                                    "executor": w.get("executor"),
                                },
                            )
                            yield flow_events.format_sse(
                                "executor",
                                {
                                    "epic_id": eid,
                                    "work_id": w.get("id"),
                                    "executor": w.get("executor"),
                                },
                            )
                except Exception as exc:
                    yield flow_events.format_sse(
                        "error", {"message": str(exc)[:200]}
                    )
            if now - last_beat >= 15:
                last_beat = now
                yield flow_events.format_sse("ping", {"t": int(now)})
            # 短 sleep：用 asyncio
            import asyncio

            await asyncio.sleep(2.0)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/executors")
async def list_executors(request: Request):
    check_auth(request)
    import sys

    scripts = Path(__file__).resolve().parents[2]
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    from executors.registry import EXECUTOR_IDS

    return {
        "ok": True,
        "executors": sorted(e for e in EXECUTOR_IDS if e != "auto") + ["auto"],
        "default": "opencode",
    }


@router.get("/config")
async def desktop_config(request: Request):
    check_auth(request)
    return {
        "ok": True,
        "product": "CCC Desktop",
        "api_prefix": "/api/desktop",
        "threads": "unified",
        "dual_source_history": False,
        "transfer": "epic_only",
        "flow_events": "sse",
    }
