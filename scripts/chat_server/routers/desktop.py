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


@router.put("/threads/{thread_id}/messages")
async def put_thread_messages(request: Request, thread_id: str):
    """Desktop 会话镜像备份（非权威；Engine / product 扇出不读；本机 Application Support 为准）。"""
    check_auth(request)
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="JSON object required")
    pid = str(body.get("project_id") or body.get("project") or "").strip()
    if not pid:
        raise HTTPException(status_code=400, detail="project_id required")
    raw = body.get("messages")
    if not isinstance(raw, list):
        raise HTTPException(status_code=400, detail="messages array required")
    messages: list[dict] = []
    for m in raw:
        if not isinstance(m, dict):
            continue
        role = str(m.get("role") or "").strip()
        content = str(m.get("content") or "")
        if role not in ("user", "assistant", "system"):
            continue
        item: dict = {"role": role, "content": content, "mode": "chat"}
        # Desktop 工具轨透传（可选；历史消息可无）
        steps = m.get("tool_steps")
        if isinstance(steps, list) and steps:
            item["tool_steps"] = steps
        if "files_changed" in m:
            try:
                item["files_changed"] = int(m.get("files_changed") or 0)
            except (TypeError, ValueError):
                pass
        if "tools_finished" in m:
            item["tools_finished"] = bool(m.get("tools_finished"))
        messages.append(item)
    store.save_session(
        thread_id,
        messages,
        project=pid,
        mode="chat",
        status="idle",
        claude_session_id=body.get("claude_session_id"),
    )
    return {
        "ok": True,
        "thread_id": thread_id,
        "count": len(messages),
        "role": "backup",
        "note": "session mirror only; Engine does not read chat",
    }


@router.post("/agent/warm")
async def warm_agent(request: Request):
    """Hub 兼容：预热槽位（Desktop 对话走 M1 sidecar :7788，不依赖此端点）。"""
    check_auth(request)
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="JSON object required")
    pid = str(body.get("project_id") or body.get("project") or "").strip()
    if not pid:
        raise HTTPException(status_code=400, detail="project_id required")
    tid = str(body.get("thread_id") or body.get("session_id") or f"warm-{pid}").strip()
    try:
        path = get_project_path(pid)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    from ..services.claude_client import resolve_model
    from ..services.claude_session import session_manager

    model = resolve_model(body.get("model"))
    try:
        result = await session_manager.warm(path, tid, model=model)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"warm failed: {exc}") from exc
    return result


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
    return await _transfer_epic_from_body(body)


async def _transfer_epic_from_body(body: dict[str, Any]):
    """Shared by /transfer and proposals adopt。"""
    # 角色锁（架构对齐 2026-07-19）：Desktop 只能转 epic，禁止直接转 work
    body_card_kind = str(body.get("card_kind") or "").strip().lower()
    if body_card_kind and body_card_kind != "epic":
        return JSONResponse(
            status_code=400,
            content={
                "ok": False,
                "error": "role_lock_violation",
                "errors": [
                    {
                        "code": "role_lock_violation",
                        "message": f"Desktop transfer 只允许 epic，禁止 card_kind={body_card_kind}",
                    }
                ],
            },
        )

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
                "errors": [{"code": "invalid_epic_id", "message": "epic_id 非法"}],
            },
        )

    client_request_id = str(body.get("client_request_id") or "").strip()
    if client_request_id:
        remembered = flow_events.lookup_transfer_by_client_request(
            project_id, client_request_id
        )
        if remembered:
            return {
                "ok": True,
                "epic_id": remembered["epic_id"],
                "workspace": workspace,
                "column": "backlog",
                "project_id": project_id,
                "idempotent_replay": True,
                "engine_wake": {"ok": True, "mode": "idempotent", "message": "replay"},
            }

    # 写入磁盘并把 fingerprint 写进 body，让后续 remember_last_epic 落地时一并带上
    payload_fingerprint = flow_events._transfer_payload_fingerprint(body)
    if payload_fingerprint:
        body["payload_fingerprint"] = payload_fingerprint

    executor_intent = transfer_gate.resolve_executor_intent(body)
    description = transfer_gate.build_epic_description({**body, "executor_intent": executor_intent})
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
    }

    resp = await board_proxy("POST", "/api/tasks", json_body=task_body)
    if resp.status_code not in (200, 201):
        try:
            detail = json.loads(resp.body.decode() if isinstance(resp.body, (bytes, bytearray)) else resp.body)
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
    try:
        written = _write_seed_artifacts(workspace, tid, plan_md, None)
        payload["seeded"] = written
    except Exception as exc:
        payload["seed_warning"] = str(exc)[:200]

    thread_id = str(body.get("thread_id") or "").strip() or flow_events.canonical_conversation_id(
        project_id
    )
    flow_events.append_event(
        "epic_created",
        {
            "epic_id": tid,
            "title": title,
            "project_id": project_id,
            "workspace": workspace,
            "executor_intent": executor_intent,
            "thread_id": thread_id,
        },
    )
    flow_events.remember_last_epic(
        project_id, tid, title, thread_id=thread_id, client_request_id=client_request_id or None
    )
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
        "idempotent_replay": False,
    }


@router.get("/proposals")
async def list_inbox_proposals(request: Request, include_adopted: int = 0):
    check_auth(request)
    from ..services import proposals as proposals_svc

    items = proposals_svc.list_proposals(include_adopted=bool(include_adopted))
    return {"ok": True, "proposals": items}


@router.post("/proposals/{prop_id}/adopt")
async def adopt_inbox_proposal(request: Request, prop_id: str):
    """人审采纳：提案 → transfer；未采纳绝不进 backlog。"""
    check_auth(request)
    from ..services import proposals as proposals_svc

    prop = proposals_svc.get_proposal(prop_id)
    if not prop or prop.get("status") == "adopted":
        return JSONResponse(
            status_code=404,
            content={"ok": False, "error": "proposal_not_found"},
        )
    if not prop.get("project_id"):
        return JSONResponse(
            status_code=400,
            content={"ok": False, "error": "missing_project"},
        )
    crid = f"inbox-adopt-{prop['id']}-{uuid.uuid4().hex[:8]}"
    body = proposals_svc.proposal_to_transfer_body(prop, client_request_id=crid)
    result = await _transfer_epic_from_body(body)
    if isinstance(result, JSONResponse):
        return result
    if not result.get("ok"):
        return result
    proposals_svc.mark_adopted(prop["id"])
    result["proposal_id"] = prop["id"]
    result["adopted"] = True
    return result


# ── Flow events / snapshot ────────────────────────────────


async def _fetch_board_dict(workspace: str) -> dict[str, list[dict]]:
    resp = await board_proxy("GET", "/api/board", params={"workspace": workspace})
    if resp.status_code != 200:
        return {}
    try:
        raw = json.loads(resp.body.decode() if isinstance(resp.body, (bytes, bytearray)) else resp.body)
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


async def _fetch_board_with_status(workspace: str) -> tuple[dict[str, list[dict]], bool]:
    """拉取看板并返回 (columns, degraded)。degraded=True 表示看板离线/超时。"""
    resp = await board_proxy("GET", "/api/board", params={"workspace": workspace})
    if resp.status_code != 200:
        return {}, True
    try:
        raw = json.loads(resp.body.decode() if isinstance(resp.body, (bytes, bytearray)) else resp.body)
    except Exception:
        return {}, True
    cols: dict[str, list[dict]] = {}
    if isinstance(raw, dict) and isinstance(raw.get("columns"), dict):
        cols = raw["columns"]
    elif isinstance(raw, dict) and isinstance(raw.get("board"), dict):
        cols = raw["board"]
    elif isinstance(raw, dict):
        cols = {k: v for k, v in raw.items() if isinstance(v, list)}
    empty = all(not lst for lst in cols.values()) if cols else True
    if empty and resp.status_code == 200:
        # 200 但全空：可能是板真空，也可能是 Board 损坏状态；同时返回 degraded 给 UI 兜底
        return cols, False
    return cols, False


@router.get("/flow/epics")
async def flow_epics(
    request: Request,
    project_id: str = "",
    thread_id: str = "",
    limit: int = 20,
):
    """epic 列表。`::main` = 项目会话视图（不过滤）；其它 thread_id 精确匹配。"""
    check_auth(request)
    pid = (project_id or "").strip()
    if not pid:
        raise HTTPException(status_code=400, detail="project_id required")
    lim = max(1, min(int(limit or 20), 40))
    tid = (thread_id or "").strip() or None
    items = flow_events.list_recent_epics(pid, thread_id=tid, limit=lim)
    conv_view = "project_single" if (not tid or flow_events.is_project_conversation_id(tid)) else "thread_exact"
    hint = flow_events.bound_hint_for_epics(items, thread_id=tid)
    return {
        "ok": True,
        "project_id": pid,
        "thread_id": tid,
        "conversation_view": conv_view,
        "bound_hint": hint,
        "epics": items,
    }


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
        eid = str((last or {}).get("epic_id") or "") or (flow_events.latest_transfer_epic_id(pid) or "")
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
    board, board_degraded = await _fetch_board_with_status(workspace)
    snap = flow_events.snapshot_from_board(board, epic_id=eid, project_id=pid)
    payload = {"ok": True, "empty": False, **snap}
    if board_degraded:
        payload["board_status"] = "degraded"
        payload["board_message"] = "看板暂不可达，已返回最后一次缓存"
    else:
        payload["board_status"] = "ok"
    return payload


@router.get("/flow/events")
async def flow_events_sse(
    request: Request,
    project_id: str = "",
    epic_id: str = "",
):
    """SSE：优先 JSONL 推送 fanout/work_status；看板轮询仅作断线兜底。"""
    check_auth(request)
    pid = (project_id or "").strip()
    if not pid:
        raise HTTPException(status_code=400, detail="project_id required")

    async def gen():
        import asyncio

        last_ts = ""
        last_sig = ""
        last_beat = 0.0
        last_board_poll = 0.0
        board_interval = 8.0  # 95+：缩小看板轮询
        # Phase 2.4: offset 增量读，避免每 0.5s 整文件 splitlines
        last_offset = 0
        last_inode = 0
        jsonl_updated = False
        # Phase14：本 epic 上次观察到的 stage；进入终态时主动推 epic_done（不等下次 fanout）
        last_terminal_stage: dict[str, str] = {}

        # 先推历史事件（用 offset 读，初始化 last_offset/inode）
        recs, last_offset, last_inode = flow_events.read_events_from_offset(
            0, project_id=pid, epic_id=epic_id or None, limit=80
        )
        jsonl_updated = bool(recs)
        for rec in recs:
            yield flow_events.format_sse(str(rec.get("event") or "message"), rec.get("data") or {})
            ts = str(rec.get("ts") or "")
            if ts > last_ts:
                last_ts = ts

        while True:
            if await request.is_disconnected():
                break
            eid_filter = (epic_id or "").strip() or None
            # 1) JSONL 推送优先（offset 增量读）
            recs, new_offset, new_inode = flow_events.read_events_from_offset(
                last_offset,
                project_id=pid,
                epic_id=eid_filter,
                after_ts=last_ts or None,
                limit=100,
            )
            if new_inode != last_inode:
                # 日志被轮转 → 重置（recs 已是新文件从头读的结果）
                last_inode = new_inode
            last_offset = new_offset
            jsonl_updated = bool(recs)
            for rec in recs:
                if await request.is_disconnected():
                    return
                yield flow_events.format_sse(str(rec.get("event") or "message"), rec.get("data") or {})
                ts = str(rec.get("ts") or "")
                if ts > last_ts:
                    last_ts = ts
            # 让出事件循环，减轻慢客户端时的缓冲堆积
            await asyncio.sleep(0)

            now = time.time()
            # 2) 兜底：低频看板合成（仅当 JSONL 无更新时触发，避免双推送）
            if not jsonl_updated and now - last_board_poll >= board_interval:
                if await request.is_disconnected():
                    return
                last_board_poll = now
                eid = eid_filter or ""
                if not eid:
                    last = flow_events.load_last_epic(pid)
                    eid = str((last or {}).get("epic_id") or "")
                if eid:
                    try:
                        workspace = _project_workspace(pid)
                        board = await _fetch_board_dict(workspace)
                        snap = flow_events.snapshot_from_board(board, epic_id=eid, project_id=pid)
                        sig = json.dumps(snap, sort_keys=True, ensure_ascii=False)
                        if sig != last_sig:
                            last_sig = sig
                            yield flow_events.format_sse(
                                "fanout",
                                {
                                    "project_id": pid,
                                    "epic_id": eid,
                                    "works": snap.get("works") or [],
                                },
                            )
                            for w in snap.get("works") or []:
                                yield flow_events.format_sse(
                                    "work_status",
                                    {
                                        "project_id": pid,
                                        "epic_id": eid,
                                        "work_id": w.get("id"),
                                        "status": w.get("status"),
                                        "executor": w.get("executor"),
                                    },
                                )
                        # Phase14：本 epic 进入 done 时主动推 epic_done；不等下一次 fanout。
                        # failed 留给 snapshot 的 stopLoss 路径，避免重复推送。
                        stage = str(snap.get("user_stage") or "").strip().lower()
                        prev = last_terminal_stage.get(eid)
                        if stage == "done" and prev != "done":
                            yield flow_events.format_sse(
                                "epic_done",
                                {
                                    "project_id": pid,
                                    "epic_id": eid,
                                    "split_status": "done",
                                },
                            )
                            flow_events.append_event(
                                "epic_done",
                                {
                                    "project_id": pid,
                                    "epic_id": eid,
                                    "split_status": "done",
                                },
                            )
                        last_terminal_stage[eid] = stage
                    except Exception as exc:
                        yield flow_events.format_sse("error", {"message": str(exc)[:200]})
            if now - last_beat >= 15:
                last_beat = now
                yield flow_events.format_sse("ping", {"t": int(now)})
            await asyncio.sleep(0.5)

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
    try:
        from executors.registry import EXECUTOR_IDS
    except ImportError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"executors registry unavailable: {exc}",
        ) from exc

    return {
        "ok": True,
        "executors": sorted(e for e in EXECUTOR_IDS if e != "auto") + ["auto"],
        "default": "opencode",
    }


@router.get("/tasks/{task_id}/artifacts")
async def task_artifacts(task_id: str, request: Request, workspace: str = "CCC"):
    """Phase 2.4: 返回 task 的 plan/report/review/verdict 产物"""
    check_auth(request)
    import os

    w = _resolve_workspace(workspace)
    root = _workspace_root(w)
    artifacts = {}
    for key, fname in [
        ("planMd", f"plans/{task_id}.plan.md"),
        ("phasesJsonl", f"phases/{task_id}.phases.json"),
        ("reportMd", f"reports/{task_id}.report.md"),
        ("reviewMd", f"reports/{task_id}.review.md"),
        ("verdictMd", f"verdicts/{task_id}.verdict.md"),
    ]:
        p = root / ".ccc" / fname
        if p.exists():
            artifacts[key] = p.read_text(encoding="utf-8", errors="replace")
        else:
            artifacts[key] = ""
    return JSONResponse(artifacts)


@router.post("/flow/works/{work_id}/retry")
async def retry_failed_work(work_id: str, request: Request, body: dict | None = None):
    """Phase 3.2: 重试失败 work"""
    check_auth(request)
    ws = (body or {}).get("workspace", "CCC")
    w = _resolve_workspace(ws)
    root = _workspace_root(w)
    # 重试 = 从异常状态重置到 in_progress
    tasks_dir = root / ".ccc" / "board"
    for col in ["abnormal", "testing", "in_progress", "planned"]:
        col_dir = tasks_dir / col
        if not col_dir.exists():
            continue
        for f in col_dir.iterdir():
            if not f.name.endswith(".json"):
                continue
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                if data.get("id") == work_id or data.get("workId") == work_id:
                    data["status"] = "in_progress"
                    data["retry_count"] = data.get("retry_count", 0) + 1
                    # 移回 in_progress 目录
                    dst = tasks_dir / "in_progress" / f.name
                    f.rename(dst)
                    dst.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                    return {"ok": True, "work_id": work_id, "new_status": "in_progress"}
            except Exception:
                continue
    raise HTTPException(status_code=404, detail=f"Work {work_id} not found")


@router.get("/flow/works/{work_id}/failures")
async def work_failures(work_id: str, request: Request, workspace: str = "CCC"):
    """Phase 3.3: 返回 work 的失败记录"""
    check_auth(request)
    w = _resolve_workspace(workspace)
    root = _workspace_root(w)
    failures_path = root / ".ccc" / "stats" / "failures.jsonl"
    if not failures_path.exists():
        return JSONResponse([])
    records = []
    for line in failures_path.read_text(encoding="utf-8").strip().split("\n"):
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
            if rec.get("task_id") == work_id or rec.get("work_id") == work_id:
                records.append(rec)
        except Exception:
            continue
    return JSONResponse(records)


@router.get("/config")
async def desktop_config(request: Request):
    check_auth(request)
    # 只读探测：验收脚本断言方案 Agent = loop-code（不改产品行为）
    agent_cli = ""
    agent_runtime = "unknown"
    try:
        import sys

        scripts = Path(__file__).resolve().parents[2]
        if str(scripts) not in sys.path:
            sys.path.insert(0, str(scripts))
        from _claude_cli import resolve_claude_cli

        agent_cli = resolve_claude_cli(require=False) or ""
        if agent_cli and "vendor/loop-code/cli" in agent_cli.replace("\\", "/"):
            agent_runtime = "loop-code"
        elif agent_cli:
            agent_runtime = "claude"
    except Exception:
        pass
    return {
        "ok": True,
        "product": "CCC Desktop",
        "api_prefix": "/api/desktop",
        "threads": "unified",
        "conversation_model": "project_single",
        "dual_source_history": False,
        "transfer": "epic_only",
        "flow_events": "sse",
        "agent_runtime": agent_runtime,
        "agent_cli": agent_cli,
    }


def _repo_root() -> Path:
    # scripts/chat_server/routers/desktop.py → repo root
    return Path(__file__).resolve().parents[3]


def _read_hub_version_payload() -> dict[str, Any]:
    """只读：VERSION + git HEAD + hub_api_version（F2-2 双机对齐）。"""
    import subprocess

    root = _repo_root()
    version = ""
    ver_path = root / "VERSION"
    if ver_path.is_file():
        try:
            version = ver_path.read_text(encoding="utf-8").strip()
        except OSError:
            version = ""
    commit = ""
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if proc.returncode == 0:
            commit = (proc.stdout or "").strip()
    except (OSError, subprocess.TimeoutExpired):
        commit = ""
    return {
        "ok": True,
        "version": version,
        "commit": commit,
        "hub_api_version": "v1",
    }


@router.get("/version")
async def desktop_version(request: Request):
    """F2-2：双机版本对齐只读端点。无写副作用。"""
    check_auth(request)
    return _read_hub_version_payload()
