import asyncio
import base64
import json
import re
import uuid
from pathlib import Path

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse

from ..auth import check_auth
from .. import config
from ..services import session_store as store
from ..services.claude_client import stream_chat, _get_project_context, resolve_model
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
    check_auth(request)
    body = await request.json()
    messages = body.get("messages", [])
    session_id = body.get("session_id", str(uuid.uuid4()))
    model = resolve_model(body.get("model", "flash"))
    project = body.get("project", "ccc")
    timeout = int(body.get("timeout", 180))
    attachments = body.get("attachments") or []

    user_msgs = [m for m in messages if m.get("role") == "user"]
    if not user_msgs:
        raise HTTPException(status_code=400, detail="messages required")
    prompt = user_msgs[-1].get("content", "").strip()
    if not prompt and not attachments:
        raise HTTPException(status_code=400, detail="prompt required")
    if check_dangerous(prompt):
        raise HTTPException(status_code=400, detail="危险指令已被拦截")

    project_path = get_project_path(project)
    # F-SEC-03: cwd jail — 拒绝跳出项目根
    if not _is_path_inside(project_path, project_path):
        raise HTTPException(status_code=400, detail="invalid project path")

    attachment_notes = _materialize_attachments(
        attachments, project_path=project_path, session_id=session_id.replace(":", "_")
    )
    if attachment_notes:
        prompt = (prompt + "\n\n" if prompt else "") + attachment_notes

    resume_id = parse_claude_session_id(session_id)
    # 续聊 Claude 会话时不再注入整份项目上下文（避免污染已有 transcript）
    if not resume_id:
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
                model=model,
                resume_session_id=resume_id,
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
            # Hub 自建会话才写本地 JSON；Claude 续聊以 ~/.claude transcript 为准
            if not resume_id:
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
