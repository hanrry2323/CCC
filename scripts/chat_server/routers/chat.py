import asyncio
import json
import re
import uuid
from pathlib import Path

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse

from ..auth import check_auth
from .. import config
from ..services import session_store as store
from ..services.claude_client import stream_chat, _get_project_context
from .projects import PROJECTS, get_project_path

router = APIRouter()


def check_dangerous(text: str) -> bool:
    """F-SEC-03: 辅助拦截；主防线在工具 allowlist + cwd jail。"""
    return bool(config.DANGEROUS_PATTERN.search(text))


def _is_path_inside(root: str, candidate: str) -> bool:
    try:
        root_p = Path(root).resolve()
        cand = Path(candidate).resolve()
        cand.relative_to(root_p)
        return True
    except (ValueError, OSError):
        return False


@router.post("/api/chat")
async def chat(request: Request):
    check_auth(request)
    body = await request.json()
    messages = body.get("messages", [])
    session_id = body.get("session_id", str(uuid.uuid4()))
    model = body.get("model", "flash")
    project = body.get("project", "ccc")
    timeout = int(body.get("timeout", 180))

    user_msgs = [m for m in messages if m.get("role") == "user"]
    if not user_msgs:
        raise HTTPException(status_code=400, detail="messages required")
    prompt = user_msgs[-1].get("content", "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="prompt required")
    if check_dangerous(prompt):
        raise HTTPException(status_code=400, detail="危险指令已被拦截")

    project_path = get_project_path(project)
    # F-SEC-03: cwd jail — 拒绝跳出项目根
    if not _is_path_inside(project_path, project_path):
        raise HTTPException(status_code=400, detail="invalid project path")

    store.save_session(
        session_id, messages,
        project=project, mode="chat",
        execution_results=[], status="pending",
    )

    context = _get_project_context(project, PROJECTS)
    if context:
        prompt = f"## 项目上下文\n{context}\n\n---\n\n## 用户问题\n{prompt}"

    async def generate():
        full_content = ""
        execution_results: list = []
        total_cost_usd = None
        stream_completed = False

        try:
            async for event in stream_chat(
                prompt, project_path,
                lambda: request.scope.get("disconnect_received", False),
                timeout,
            ):
                evt_type = event.get("type")

                if evt_type == "delta":
                    text = event.get("content", "")
                    if text:
                        full_content += text
                        yield f"data: {json.dumps(event)}\n\n"

                elif evt_type == "tool_use":
                    execution_results.append({
                        "tool": event.get("name", "tool"),
                        "input": event.get("input", {}),
                        "result": "",
                    })
                    yield f"data: {json.dumps(event)}\n\n"

                elif evt_type == "tool_result":
                    if execution_results:
                        execution_results[-1]["result"] = event.get("content", "")
                    yield f"data: {json.dumps(event)}\n\n"

                elif evt_type == "cost":
                    total_cost_usd = event.get("usd")
                    yield f"data: {json.dumps(event)}\n\n"

                elif evt_type == "error":
                    yield f"data: {json.dumps(event)}\n\n"

                elif evt_type == "done":
                    stream_completed = True
                    yield f"data: {json.dumps({'type': 'done', 'session_id': session_id})}\n\n"

        except (GeneratorExit, asyncio.CancelledError):
            raise
        finally:
            chat_messages = [m for m in messages if m.get("role") != "system"]
            for m in chat_messages:
                m.setdefault("mode", "chat")
            if full_content:
                chat_messages.append({
                    "role": "assistant",
                    "content": full_content,
                    "mode": "chat",
                    "execution_results": execution_results,
                    "partial": not stream_completed,
                })
            store.save_session(
                session_id, chat_messages,
                project=project, mode="chat",
                execution_results=execution_results,
                total_cost_usd=total_cost_usd,
                status="completed" if stream_completed else "partial",
            )

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.post("/api/execute")
async def execute_mode(request: Request):
    return await chat(request)
