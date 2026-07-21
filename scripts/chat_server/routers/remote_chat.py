"""Hub 远程管理对话 — 会话分区（hub:: thread），非 Desktop 本机会话权威。

契约：docs/product/hub-remote-management.md · hub-api-v1 附录 A
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from .. import config
from ..auth import check_auth
from ..services import session_store as store
from ..services.claude_client import (
    _get_project_context,
    resolve_model,
    stream_chat,
)
from ..services.claude_session import session_manager
from .projects import PROJECTS, get_project_path, reload_projects

router = APIRouter(prefix="/api/remote-chat", tags=["remote-chat"])
_log = logging.getLogger("ccc-hub.remote-chat")

HUB_THREAD_PREFIX = "hub::"


def normalize_hub_thread_id(project_id: str, thread_id: str | None) -> str:
    """强制 hub:: 前缀；缺省 hub::{project}::main。"""
    pid = (project_id or "").strip() or "ccc"
    tid = (thread_id or "").strip()
    if not tid:
        return f"{HUB_THREAD_PREFIX}{pid}::main"
    if not tid.startswith(HUB_THREAD_PREFIX):
        raise ValueError(
            "thread_id must start with 'hub::' "
            "(Hub remote sessions are partitioned from Desktop)"
        )
    store._safe_session_id(tid)  # noqa: SLF001 — 校验入口
    return tid


def _project_id_from_body(body: dict[str, Any]) -> str:
    return (body.get("project_id") or body.get("project") or "").strip() or "ccc"


def _thread_from_body(body: dict[str, Any], project: str) -> str:
    """Accept thread_id or legacy session_id; enforce hub::."""
    raw = body.get("thread_id") or body.get("session_id")
    return normalize_hub_thread_id(project, raw if raw else None)


def _load_messages(thread_id: str, project: str) -> tuple[list[dict], str]:
    try:
        path = store._session_path(thread_id, project)  # noqa: SLF001
        if not path.exists():
            return [], ""
        data = json.loads(path.read_text(encoding="utf-8"))
        return list(data.get("messages") or []), str(
            data.get("claude_session_id") or ""
        )
    except Exception:
        return [], ""


@router.post("/stream")
async def remote_chat_stream(request: Request):
    check_auth(request)
    body = await request.json()
    project = _project_id_from_body(body)
    message = (body.get("message") or body.get("prompt") or "").strip()
    if not message:
        msgs = body.get("messages") or []
        user_msgs = [m for m in msgs if m.get("role") == "user"]
        if user_msgs:
            message = (user_msgs[-1].get("content") or "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="message required")
    if config.DANGEROUS_PATTERN.search(message):
        raise HTTPException(status_code=400, detail="危险指令已被拦截")

    try:
        thread_id = _thread_from_body(body, project)
    except ValueError as exc:
        return JSONResponse(
            status_code=400,
            content={
                "ok": False,
                "error": "invalid_thread_id",
                "message": str(exc),
            },
        )

    tool_mode = config.resolve_tool_mode(
        body.get("tool_mode"), user_text=message
    )
    model = resolve_model(body.get("model"))
    resume = (body.get("claude_session_id") or "").strip() or None

    if not PROJECTS:
        reload_projects()
    project_path = get_project_path(project)

    prior_messages, stored_sid = _load_messages(thread_id, project)
    if not resume and stored_sid:
        resume = stored_sid

    prior_messages.append({"role": "user", "content": message, "mode": "chat"})
    store.save_session(
        thread_id,
        prior_messages,
        project=project,
        mode="chat",
        status="pending",
        claude_session_id=resume,
    )

    context = _get_project_context(project, PROJECTS)
    prompt = message
    if context:
        prompt = (
            f"## 项目上下文\n{context}\n\n---\n\n## 用户问题\n{message}"
        )
    prompt = (
        "【Hub 远程管理口】你在 Mac2017 Hub 网页远程会话中。"
        "本会话与用户本机 Desktop 对话相互独立。"
        "可协助对齐基线、定稿方案；下达任务走 transfer 门禁。"
        f"当前工具模式：{tool_mode}。\n\n{prompt}"
    )

    disconnected = {"flag": False}

    async def _watch_disconnect() -> None:
        try:
            while True:
                if await request.is_disconnected():
                    disconnected["flag"] = True
                    return
                await asyncio.sleep(0.5)
        except Exception:
            disconnected["flag"] = True

    async def generate():
        full_content = ""
        execution_results: list = []
        claude_sid = resume or ""
        stream_completed = False
        watcher = asyncio.create_task(_watch_disconnect())
        try:
            async for event in stream_chat(
                prompt,
                project_path,
                lambda: disconnected["flag"],
                model=model,
                resume_session_id=resume,
                hub_session_id=thread_id,
                tool_mode=tool_mode,
                user_text_for_tools=message,
            ):
                evt_type = event.get("type")
                if evt_type == "delta":
                    text = event.get("content", "")
                    if text:
                        full_content += text
                        yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                elif evt_type in (
                    "tool_use",
                    "tool_result",
                    "cost",
                    "error",
                    "ping",
                ):
                    if evt_type == "tool_use":
                        execution_results.append(
                            {
                                "tool": event.get("name", "tool"),
                                "input": event.get("input", {}),
                                "result": "",
                            }
                        )
                    elif evt_type == "tool_result" and execution_results:
                        execution_results[-1]["result"] = event.get(
                            "content", ""
                        )
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                elif evt_type == "done":
                    stream_completed = not event.get("partial")
                    claude_sid = event.get("claude_session_id") or claude_sid
                    out = {
                        "type": "done",
                        "session_id": thread_id,
                        "thread_id": thread_id,
                        "claude_session_id": claude_sid,
                        "partial": event.get("partial", False),
                    }
                    yield f"data: {json.dumps(out, ensure_ascii=False)}\n\n"
        except (GeneratorExit, asyncio.CancelledError):
            raise
        except Exception as exc:
            _log.exception("remote-chat stream failed: %s", exc)
            err = {"type": "error", "content": str(exc)}
            yield f"data: {json.dumps(err, ensure_ascii=False)}\n\n"
            done = {
                "type": "done",
                "session_id": thread_id,
                "thread_id": thread_id,
                "partial": True,
            }
            yield f"data: {json.dumps(done, ensure_ascii=False)}\n\n"
        finally:
            watcher.cancel()
            try:
                await watcher
            except asyncio.CancelledError:
                pass
            msgs = list(prior_messages)
            if full_content:
                msgs.append(
                    {
                        "role": "assistant",
                        "content": full_content,
                        "mode": "chat",
                        "execution_results": execution_results,
                        "partial": not stream_completed,
                    }
                )
            store.save_session(
                thread_id,
                msgs,
                project=project,
                mode="chat",
                execution_results=execution_results,
                status="completed" if stream_completed else "partial",
                claude_session_id=claude_sid or None,
            )

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.post("/stop")
async def remote_chat_stop(request: Request):
    check_auth(request)
    body = await request.json()
    project = _project_id_from_body(body)
    try:
        thread_id = _thread_from_body(body, project)
    except ValueError as exc:
        return JSONResponse(
            status_code=400,
            content={
                "ok": False,
                "error": "invalid_thread_id",
                "message": str(exc),
            },
        )
    if not PROJECTS:
        reload_projects()
    project_path = get_project_path(project)
    dropped = await session_manager.cancel_session(project_path, thread_id)
    return {"ok": True, "dropped": dropped, "thread_id": thread_id}


@router.get("/history")
async def remote_chat_history(
    request: Request,
    project: str = "ccc",
    thread_id: str | None = None,
):
    check_auth(request)
    try:
        tid = normalize_hub_thread_id(project, thread_id)
    except ValueError as exc:
        return JSONResponse(
            status_code=400,
            content={
                "ok": False,
                "error": "invalid_thread_id",
                "message": str(exc),
            },
        )
    messages, claude_sid = _load_messages(tid, project)
    return {
        "ok": True,
        "thread_id": tid,
        "project": project,
        "messages": messages,
        "title": "Hub 远程会话",
        "claude_session_id": claude_sid,
    }


@router.get("/threads")
async def remote_chat_threads(request: Request, project: str = "ccc"):
    """列出该项目下 hub:: 远程会话（分区过滤）。"""
    check_auth(request)
    sessions = store.list_sessions(project, include_tests=False)
    remote = [
        s
        for s in sessions
        if str(s.get("session_id") or "").startswith(HUB_THREAD_PREFIX)
    ]
    return {"ok": True, "project": project, "sessions": remote}
