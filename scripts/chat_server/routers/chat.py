import asyncio
import base64
import json
import logging
import re
import uuid
from pathlib import Path

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse

logger = logging.getLogger("ccc.chat")

from ..auth import check_auth
from .. import config
from ..services import session_store as store
from ..services.claude_client import (
    stream_chat,
    _get_project_context,
    resolve_model,
    resolve_chat_timeouts,
)
from ..services.claude_history import parse_claude_session_id
from .projects import PROJECTS, get_project_path

router = APIRouter()

UPLOAD_MAX_BYTES = 8 * 1024 * 1024  # 8MB per file
ALLOWED_ATTACHMENT_EXTS = frozenset({
    ".png", ".jpg", ".jpeg", ".gif", ".webp",
    ".txt", ".md", ".csv", ".json", ".py", ".js", ".ts", ".html", ".css",
})
_SAFE_NAME = re.compile(r"[^a-zA-Z0-9._\-]+")


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


def _safe_filename(name: str) -> str:
    base = Path(name or "file").name
    cleaned = _SAFE_NAME.sub("_", base).strip("._") or "file"
    return cleaned[:120]


def _materialize_attachments(
    attachments: list,
    *,
    project_path: str,
    session_id: str,
) -> str:
    """Save chat attachments under project .ccc/chat-uploads and return prompt notes."""
    if not attachments:
        return ""
    if len(attachments) > 8:
        raise HTTPException(status_code=400, detail="最多 8 个附件")

    upload_root = Path(project_path) / ".ccc" / "chat-uploads" / session_id
    upload_root.mkdir(parents=True, exist_ok=True)
    if not _is_path_inside(project_path, str(upload_root)):
        raise HTTPException(status_code=400, detail="invalid upload path")

    notes: list[str] = ["## 用户附件（已保存到项目内，可用 Read 工具打开）"]
    for idx, att in enumerate(attachments):
        if not isinstance(att, dict):
            continue
        name = _safe_filename(str(att.get("name") or f"attachment-{idx}"))
        ext = Path(name).suffix.lower()
        if ext and ext not in ALLOWED_ATTACHMENT_EXTS:
            raise HTTPException(status_code=400, detail=f"不支持的附件类型: {ext}")
        raw_b64 = att.get("content_base64") or att.get("data") or ""
        if not isinstance(raw_b64, str) or not raw_b64.strip():
            raise HTTPException(status_code=400, detail=f"附件缺少内容: {name}")
        if "," in raw_b64 and raw_b64.strip().startswith("data:"):
            raw_b64 = raw_b64.split(",", 1)[1]
        try:
            data = base64.b64decode(raw_b64, validate=False)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"附件解码失败: {name}") from exc
        if len(data) > UPLOAD_MAX_BYTES:
            raise HTTPException(status_code=400, detail=f"附件过大（>8MB）: {name}")
        dest = upload_root / f"{idx:02d}-{name}"
        dest.write_bytes(data)
        notes.append(f"- `{dest}` ({len(data)} bytes)")
    return "\n".join(notes) if len(notes) > 1 else ""


@router.post("/api/chat")
async def chat(request: Request):
    """Hub /api/chat — legacy（网页运维可留）；Desktop 对话面禁止调用，只走本机 sidecar。"""
    check_auth(request)
    body = await request.json()
    messages = body.get("messages", [])
    session_id = body.get("session_id", str(uuid.uuid4()))
    model = resolve_model(body.get("model", "flash"))
    project = body.get("project", "ccc")
    raw_timeout = body.get("timeout")
    try:
        requested_timeout = int(raw_timeout) if raw_timeout is not None else None
    except (TypeError, ValueError):
        requested_timeout = None
    idle_s, max_s = resolve_chat_timeouts(requested_timeout)
    attachments = body.get("attachments") or []

    user_msgs = [m for m in messages if m.get("role") == "user"]
    if not user_msgs:
        raise HTTPException(status_code=400, detail="messages required")
    prompt = user_msgs[-1].get("content", "").strip()
    if not prompt and not attachments:
        raise HTTPException(status_code=400, detail="prompt required")
    if check_dangerous(prompt):
        raise HTTPException(status_code=400, detail="危险指令已被拦截")

    logger.info(
        "hub_chat_legacy project=%s session=%s (Desktop must use sidecar :7788)",
        project,
        session_id[:24] if isinstance(session_id, str) else session_id,
    )

    project_path = get_project_path(project)
    # F-SEC-03: cwd jail — 拒绝跳出项目根
    if not _is_path_inside(project_path, project_path):
        raise HTTPException(status_code=400, detail="invalid project path")

    attachment_notes = _materialize_attachments(
        attachments, project_path=project_path, session_id=session_id.replace(":", "_")
    )
    if attachment_notes:
        prompt = (prompt + "\n\n" if prompt else "") + attachment_notes

    # Resume sources: explicit claude:… id, or Hub-stored binding
    resume_id = parse_claude_session_id(session_id)
    existing = None if resume_id else store.get_session(session_id, project)
    if not resume_id and existing:
        stored = str(existing.get("claude_session_id") or "").strip()
        if stored:
            resume_id = stored

    # 续聊（已有 Claude session）不再注入整份项目上下文
    is_hub_owned = not session_id.startswith("claude:")
    if is_hub_owned:
        store.save_session(
            session_id, messages,
            project=project, mode="chat",
            execution_results=[], status="pending",
            claude_session_id=resume_id,
        )
    if not resume_id:
        context = _get_project_context(project, PROJECTS)
        if context:
            prompt = f"## 项目上下文\n{context}\n\n---\n\n## 用户问题\n{prompt}"

    # 每轮强制老板对话人格（含续聊；短问可 light）
    from ..hub_voice import wrap_hub_prompt

    prompt_mode = str(body.get("prompt_mode") or body.get("promptMode") or "").strip()
    prompt = wrap_hub_prompt(prompt, mode=prompt_mode or None)

    async def generate():
        full_content = ""
        execution_results: list = []
        total_cost_usd = None
        stream_completed = False
        claude_session_id = resume_id or ""
        # Starlette 不会自动写 disconnect_received；必须轮询 is_disconnected
        client_gone = {"v": False}

        async def _watch_disconnect() -> None:
            try:
                while not client_gone["v"]:
                    if await request.is_disconnected():
                        client_gone["v"] = True
                        return
                    await asyncio.sleep(0.35)
            except asyncio.CancelledError:
                return

        watch = asyncio.create_task(
            _watch_disconnect(), name=f"ccc-chat-disconnect-{session_id[:12]}"
        )
        try:
            async for event in stream_chat(
                prompt,
                project_path,
                lambda: client_gone["v"],
                timeout=requested_timeout,
                model=model,
                resume_session_id=resume_id,
                idle_timeout=idle_s,
                max_timeout=max_s,
                hub_session_id=session_id,
            ):
                evt_type = event.get("type")

                if evt_type == "ping":
                    # SSE 注释心跳：兼容不识别 ping 的客户端，同时冲刷缓冲
                    yield f": ping {event.get('ts', '')}\n\n"
                    yield f"data: {json.dumps(event)}\n\n"
                    continue

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
                    partial = bool(event.get("partial")) or client_gone["v"]
                    stream_completed = not partial
                    claude_session_id = (
                        str(event.get("claude_session_id") or "").strip()
                        or claude_session_id
                    )
                    done_payload = {
                        "type": "done",
                        "session_id": session_id,
                        "claude_session_id": claude_session_id,
                        "partial": partial,
                    }
                    yield f"data: {json.dumps(done_payload)}\n\n"

        except (GeneratorExit, asyncio.CancelledError):
            client_gone["v"] = True
            stream_completed = False
            raise
        finally:
            watch.cancel()
            try:
                await watch
            except (asyncio.CancelledError, Exception):
                pass
            # Hub 自建会话写本地 JSON；Claude 侧栏续聊以 ~/.claude transcript 为准
            if is_hub_owned:
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
                    claude_session_id=claude_session_id or None,
                )

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "X-CCC-Chat-Role": "legacy",
        },
    )


@router.post("/api/execute")
async def execute_mode(request: Request):
    return await chat(request)
