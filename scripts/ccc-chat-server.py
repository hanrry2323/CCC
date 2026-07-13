#!/usr/bin/env python3
"""ccc-chat-server.py — 移动端 Web 聊天界面（Chat / Execute / Board 三模式）

局域网内所有设备（iPad / iPhone / 其他）通过浏览器即可和 LLM 对话或执行指令。
- Chat 模式：proxy.mjs (:4002) 流式对话
- Execute 模式：claude -p 子进程执行
- Board 模式：代理 board-server (:7777)

用法:
    python3 scripts/ccc-chat-server.py
    浏览器打开 http://localhost:8082
"""

import asyncio
import base64
import html
import json
import logging
import os
import re
import time
import uuid
from pathlib import Path

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, StreamingResponse

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
HOST = "0.0.0.0"
PORT = 8082
PROXY_URL = "http://127.0.0.1:4002/v1/chat/completions"
BOARD_URL = "http://127.0.0.1:7777"
AUTH_USER = "ccc"
AUTH_PASS = "claude2026"
CHAT_DIR = Path(__file__).resolve().parent.parent / ".ccc" / "chat"
CHAT_DIR.mkdir(parents=True, exist_ok=True)

BOARD_TOKEN = os.environ.get("QX_BOARD_TOKEN", "").strip()

PROJECTS = {
    "ccc": {"name": "CCC", "path": str(Path(__file__).resolve().parent.parent)},
    "qxo": {"name": "QXO Observer", "path": "/Users/apple/program/qx-observer"},
    "xianyu": {"name": "xianyu", "path": "/Users/apple/program/xianyu"},
    "hp": {"name": "HP KB", "path": "/Users/apple/program/hp"},
    "ai-loop-router": {"name": "AI Loop Router", "path": "/Users/apple/program/ai-loop-router"},
}

PROJECT_TO_WORKSPACE = {
    "ccc": "CCC",
    "qxo": "qxo",
    "xianyu": "xianyu",
    "hp": "hp",
    "ai-loop-router": "ai-loop-router",
}

DANGEROUS_PATTERNS = re.compile(
    r"(?i)\b(rm\s+-rf|rm\s+/|sudo\b|dd\s+if=|format\b|mkfs\b|>\s*/dev/)",
)

BOARD_COLUMNS = [
    "backlog", "planned", "in_progress", "testing",
    "verified", "released", "abnormal",
]

_log = logging.getLogger("ccc-chat")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

_execute_lock = asyncio.Lock()
_execute_running = False


def _get_project_context(project_id: str) -> str:
    proj = PROJECTS.get(project_id)
    if not proj:
        return ""
    claude_path = Path(proj["path"]) / "CLAUDE.md"
    home_claude = Path.home() / ".claude" / "CLAUDE.md"
    parts = []
    if claude_path.exists():
        parts.append(f"## Project {proj['name']}")
        parts.append(claude_path.read_text().strip())
    if home_claude.exists():
        parts.append("## Global Config")
        parts.append(home_claude.read_text().strip())
    ctx = "\n\n".join(parts)
    if len(ctx) > 4000:
        ctx = ctx[:4000] + "\n...(truncated)"
    return ctx


def _project_path(project_id: str) -> str:
    proj = PROJECTS.get(project_id)
    if not proj:
        raise HTTPException(status_code=400, detail=f"unknown project: {project_id}")
    return proj["path"]


def _project_chat_dir(project_id: str) -> Path:
    d = CHAT_DIR / project_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _session_path(session_id: str, project_id: str = "ccc") -> Path:
    return _project_chat_dir(project_id) / f"{session_id}.json"


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S+08:00")


def check_dangerous_command(text: str) -> bool:
    return bool(DANGEROUS_PATTERNS.search(text))


def check_auth(request: Request):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Basic "):
        raise HTTPException(status_code=401, headers={"WWW-Authenticate": 'Basic realm="CCC Chat"'})
    try:
        decoded = base64.b64decode(auth[6:]).decode()
        user, passwd = decoded.split(":", 1)
    except Exception:
        raise HTTPException(status_code=401)
    if user != AUTH_USER or passwd != AUTH_PASS:
        raise HTTPException(status_code=401)
    return True


def _board_headers() -> dict:
    headers = {"Content-Type": "application/json"}
    if BOARD_TOKEN:
        headers["Authorization"] = f"Bearer {BOARD_TOKEN}"
    return headers


def _save_session(
    session_id: str,
    messages: list,
    reply: str = "",
    project: str = "ccc",
    mode: str = "chat",
    execution_results: list | None = None,
    total_cost_usd: float | None = None,
):
    path = _session_path(session_id, project)
    title_src = ""
    for m in messages:
        if m.get("role") == "user" and m.get("content"):
            title_src = m["content"]
            break
    data: dict = {
        "session_id": session_id,
        "title": (title_src[:60] if title_src else "New Chat"),
        "project": project,
        "messages": messages,
        "mode": mode,
        "updated_at": _now_iso(),
    }
    if path.exists():
        try:
            existing = json.loads(path.read_text())
            data["created_at"] = existing.get("created_at", _now_iso())
        except (json.JSONDecodeError, OSError):
            data["created_at"] = _now_iso()
    else:
        data["created_at"] = _now_iso()
    if reply:
        data["reply"] = reply
    if execution_results is not None:
        data["execution_results"] = execution_results
    if total_cost_usd is not None:
        data["total_cost_usd"] = total_cost_usd
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2))


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(title="CCC Chat", docs_url=None, redoc_url=None)


@app.post("/api/chat")
async def chat(request: Request):
    check_auth(request)
    body = await request.json()
    messages = body.get("messages", [])
    session_id = body.get("session_id", str(uuid.uuid4()))
    model = body.get("model", "flash")
    project = body.get("project", "ccc")

    context = _get_project_context(project)
    if context:
        system_msg = {"role": "system", "content": f"当前项目上下文:\n{context}"}
        messages = [system_msg] + messages

    if not messages:
        raise HTTPException(status_code=400, detail="messages required")

    async def generate():
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream(
                "POST",
                PROXY_URL,
                json={"model": model, "messages": messages, "stream": True, "max_tokens": 8192},
                headers={"Accept": "text/event-stream"},
            ) as resp:
                full_content = ""
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                            choices = chunk.get("choices", [])
                            if not choices:
                                continue
                            delta = choices[0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                full_content += content
                                yield f"data: {json.dumps({'type': 'delta', 'content': content})}\n\n"
                        except json.JSONDecodeError:
                            pass
                yield f"data: {json.dumps({'type': 'done', 'session_id': session_id})}\n\n"
                if full_content:
                    chat_messages = [m for m in messages if m.get("role") != "system"]
                    for m in chat_messages:
                        m.setdefault("mode", "chat")
                    chat_messages.append({"role": "assistant", "content": full_content, "mode": "chat"})
                    _save_session(session_id, chat_messages, project=project, mode="chat")

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.post("/api/execute")
async def execute_mode(request: Request):
    check_auth(request)
    global _execute_running

    body = await request.json()
    messages = body.get("messages", [])
    session_id = body.get("session_id", str(uuid.uuid4()))
    project = body.get("project", "ccc")
    timeout = int(body.get("timeout", 120))

    user_msgs = [m for m in messages if m.get("role") == "user"]
    if not user_msgs:
        raise HTTPException(status_code=400, detail="messages required")
    prompt = user_msgs[-1].get("content", "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="prompt required")
    if check_dangerous_command(prompt):
        raise HTTPException(status_code=400, detail="危险指令已被拦截")

    if _execute_running:
        raise HTTPException(status_code=429, detail="前一个执行中，请稍候")

    project_path = _project_path(project)

    async def generate():
        global _execute_running
        async with _execute_lock:
            _execute_running = True
            proc = None
            full_content = ""
            execution_results: list = []
            total_cost_usd = None
            total_tokens = None
            try:
                proc = await asyncio.create_subprocess_exec(
                    "claude", "-p", prompt, "--print",
                    "--output-format", "stream-json",
                    "--model", "flash",
                    cwd=project_path,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env={**os.environ, "CLAUDE_PROJECT_DIR": project_path},
                )

                async def _read_stderr():
                    if proc.stderr:
                        async for line in proc.stderr:
                            _log.warning("claude stderr: %s", line.decode(errors="replace").rstrip())

                stderr_task = asyncio.create_task(_read_stderr())

                deadline = asyncio.get_event_loop().time() + timeout
                buffer = b""
                while True:
                    if await request.is_disconnected():
                        proc.kill()
                        break
                    remaining = deadline - asyncio.get_event_loop().time()
                    if remaining <= 0:
                        proc.kill()
                        yield f"data: {json.dumps({'type': 'error', 'content': '执行超时（120s）'})}\n\n"
                        break
                    try:
                        chunk = await asyncio.wait_for(proc.stdout.read(4096), timeout=min(remaining, 5.0))
                    except asyncio.TimeoutError:
                        if proc.returncode is not None:
                            break
                        continue
                    if not chunk:
                        break
                    buffer += chunk
                    while b"\n" in buffer:
                        line, buffer = buffer.split(b"\n", 1)
                        line_str = line.decode(errors="replace").strip()
                        if not line_str:
                            continue
                        try:
                            event = json.loads(line_str)
                        except json.JSONDecodeError:
                            continue
                        evt_type = event.get("type")
                        if evt_type == "assistant":
                            msg = event.get("message", {})
                            for block in msg.get("content", []):
                                btype = block.get("type")
                                if btype == "text":
                                    text = block.get("text", "")
                                    if text:
                                        full_content += text
                                        yield f"data: {json.dumps({'type': 'delta', 'content': text})}\n\n"
                                elif btype == "tool_use":
                                    name = block.get("name", "tool")
                                    inp = block.get("input", {})
                                    execution_results.append({"tool": name, "input": inp, "result": ""})
                                    yield f"data: {json.dumps({'type': 'tool_use', 'name': name, 'input': inp})}\n\n"
                        elif evt_type == "user":
                            msg = event.get("message", {})
                            for block in msg.get("content", []):
                                if block.get("type") == "tool_result":
                                    result = block.get("content", "")
                                    if execution_results:
                                        execution_results[-1]["result"] = result
                                    yield f"data: {json.dumps({'type': 'tool_result', 'content': result})}\n\n"
                        elif evt_type == "result":
                            total_cost_usd = event.get("total_cost_usd")
                            total_tokens = event.get("usage", {}).get("input_tokens", 0)
                            total_tokens = (total_tokens or 0) + event.get("usage", {}).get("output_tokens", 0)
                            result_text = event.get("result", "")
                            if result_text and not full_content:
                                full_content = result_text
                                yield f"data: {json.dumps({'type': 'delta', 'content': result_text})}\n\n"

                try:
                    await asyncio.wait_for(proc.wait(), timeout=5)
                except asyncio.TimeoutError:
                    proc.kill()
                    await proc.wait()

                stderr_task.cancel()
                try:
                    await stderr_task
                except asyncio.CancelledError:
                    pass

                if total_cost_usd is not None or total_tokens:
                    yield f"data: {json.dumps({'type': 'cost', 'tokens': total_tokens or 0, 'usd': total_cost_usd or 0})}\n\n"

                yield f"data: {json.dumps({'type': 'done', 'session_id': session_id})}\n\n"

                exec_messages = []
                for m in messages:
                    if m.get("role") == "system":
                        continue
                    exec_messages.append({**m, "mode": "execute"})
                if full_content:
                    exec_messages.append({"role": "assistant", "content": full_content, "mode": "execute"})
                _save_session(
                    session_id, exec_messages, project=project, mode="execute",
                    execution_results=execution_results,
                    total_cost_usd=total_cost_usd,
                )
            finally:
                _execute_running = False
                if proc and proc.returncode is None:
                    proc.kill()

    return StreamingResponse(generate(), media_type="text/event-stream")

@app.get("/api/projects")
async def list_projects(request: Request):
    check_auth(request)
    return {
        "projects": [
            {"id": pid, "name": info["name"], "path": info["path"]}
            for pid, info in PROJECTS.items()
        ]
    }


@app.get("/api/history")
async def list_sessions(request: Request):
    check_auth(request)
    sessions = []
    for f in sorted(CHAT_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            data = json.loads(f.read_text())
            sessions.append({
                "session_id": data.get("session_id", f.stem),
                "title": data.get("title", "Unknown")[:80],
                "updated_at": data.get("updated_at", ""),
            })
        except (json.JSONDecodeError, OSError):
            pass
    return {"sessions": sessions}


@app.get("/api/history/{session_id}")
async def get_session(request: Request, session_id: str):
    check_auth(request)
    path = _session_path(session_id)
    if not path.exists():
        raise HTTPException(status_code=404)
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        raise HTTPException(status_code=500)


@app.delete("/api/history/{session_id}")
async def delete_session(request: Request, session_id: str):
    check_auth(request)
    path = _session_path(session_id)
    if path.exists():
        path.unlink()
    return {"ok": True}


# ---------------------------------------------------------------------------
# Frontend
# ---------------------------------------------------------------------------
HTML_UI = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="color-scheme" content="light">
<title>CCC Chat</title>
<style>
  :root {
    --bg: #f8f8fa;
    --surface: #ffffff;
    --text: #1d1d1f;
    --text-secondary: #86868b;
    --border: #e5e5ea;
    --accent: #007aff;
    --user-bg: #007aff;
    --user-text: #ffffff;
    --assistant-bg: #ffffff;
    --code-bg: #f0f0f5;
    --shadow: 0 1px 3px rgba(0,0,0,0.06);
    --radius: 18px;
    --max-w: 720px;
  }
  * { margin:0; padding:0; box-sizing:border-box; }
  html,body { height:100%; overflow:hidden; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", sans-serif;
    background: var(--bg);
    color: var(--text);
    -webkit-font-smoothing: antialiased;
  }
  #app { display:flex; flex-direction:column; height:100%; max-width:var(--max-w); margin:0 auto; }
  #header {
    display:flex; align-items:center; gap:10px;
    padding:12px 16px; padding-top:calc(12px + env(safe-area-inset-top,0px));
    background:var(--surface); border-bottom:0.5px solid var(--border);
    position:sticky; top:0; z-index:10;
  }
  #header h1 { font-size:17px; font-weight:600; flex:1; }
  #project-select {
    font-size:13px; padding:6px 10px; border-radius:10px;
    border:1px solid var(--border); background:var(--surface); color:var(--text);
    outline:none; max-width:130px;
  }
  #header button, .icon-btn {
    background:none; border:none; color:var(--accent);
    font-size:15px; font-weight:500; cursor:pointer; padding:6px 4px;
  }
  .tab-panel { display:none; flex:1; flex-direction:column; overflow:hidden; }
  .tab-panel.active { display:flex; }
  #messages, #exec-messages {
    flex:1; overflow-y:auto; padding:16px; padding-bottom:8px;
    -webkit-overflow-scrolling:touch;
  }
  .msg { margin-bottom:16px; display:flex; flex-direction:column; }
  .msg.user { align-items:flex-end; }
  .msg.assistant { align-items:flex-start; }
  .msg.execute .bubble-wrap { display:flex; align-items:flex-start; gap:6px; max-width:90%; }
  .msg.execute .exec-icon { font-size:16px; flex-shrink:0; margin-top:12px; }
  .msg .bubble {
    max-width:85%; padding:12px 16px; border-radius:var(--radius);
    line-height:1.5; font-size:15px; word-wrap:break-word;
    box-shadow:var(--shadow);
  }
  .msg.execute .bubble { max-width:100%; flex:1; }
  .msg.user .bubble {
    background:var(--user-bg); color:var(--user-text);
    border-bottom-right-radius:4px;
  }
  .msg.assistant .bubble {
    background:var(--assistant-bg); border:1px solid var(--border);
    border-bottom-left-radius:4px; color:var(--text);
  }
  .msg .cost-info { font-size:11px; color:var(--text-secondary); margin-top:6px; padding-left:4px; }
  .tool-card {
    background:var(--code-bg); border-radius:10px; margin:8px 0; overflow:hidden;
    border:1px solid var(--border);
  }
  .tool-card summary {
    padding:8px 12px; cursor:pointer; font-size:13px; font-weight:500;
    color:var(--accent); list-style:none;
  }
  .tool-card summary::-webkit-details-marker { display:none; }
  .tool-card pre {
    padding:8px 12px; font-size:12px; overflow-x:auto;
    border-top:1px solid var(--border); white-space:pre-wrap;
  }
  .msg .bubble p { margin-bottom:8px; }
  .msg .bubble p:last-child { margin-bottom:0; }
  .msg .bubble pre {
    background:var(--code-bg); border-radius:8px; padding:12px;
    overflow-x:auto; margin:8px 0; font-size:13px;
  }
  .msg .bubble code {
    background:var(--code-bg); padding:2px 6px; border-radius:4px; font-size:13px;
  }
  .msg .bubble pre code { background:none; padding:0; }
  .msg .bubble ul, .msg .bubble ol { margin:8px 0; padding-left:20px; }
  .msg .bubble li { margin-bottom:4px; }
  .msg .bubble h1,.msg .bubble h2,.msg .bubble h3 { margin:12px 0 6px; }
  .typing .bubble { min-height:24px; display:flex; align-items:center; gap:4px; }
  .typing .dot { width:6px; height:6px; border-radius:50%; background:var(--text-secondary); animation:typing 1.4s infinite; }
  .typing .dot:nth-child(2) { animation-delay:0.2s; }
  .typing .dot:nth-child(3) { animation-delay:0.4s; }
  @keyframes typing { 0%,60%,100% { opacity:0.3; } 30% { opacity:1; } }
  #input-area {
    padding:12px 16px;
    background:var(--surface); border-top:0.5px solid var(--border);
  }
  #input-wrap {
    display:flex; gap:8px; align-items:flex-end;
    background:var(--surface); border-radius:20px; padding:4px 4px 4px 8px;
    border:1px solid var(--border);
  }
  #input-wrap:focus-within { border-color:var(--accent); }
  #mode-switch {
    width:32px; height:32px; border-radius:50%; border:1px solid var(--border);
    background:var(--bg); font-size:14px; cursor:pointer; flex-shrink:0;
    display:flex; align-items:center; justify-content:center;
  }
  #input, #exec-input {
    flex:1; border:none; outline:none; background:transparent;
    font-size:16px; color:var(--text); resize:none;
    max-height:120px; line-height:1.4; padding:8px 0; font-family:inherit;
  }
  #send, #exec-send, #cancel-btn {
    width:36px; height:36px; border-radius:50%; border:none;
    background:var(--accent); color:#fff; font-size:18px;
    cursor:pointer; display:flex; align-items:center; justify-content:center;
    flex-shrink:0; transition:opacity 0.15s;
  }
  #cancel-btn { background:#ff3b30; font-size:12px; width:auto; padding:0 12px; border-radius:18px; display:none; }
  #send:disabled, #exec-send:disabled { opacity:0.4; cursor:default; }
  #send.loading, #exec-send.loading { animation:spin 1s linear infinite; }
  @keyframes spin { from { transform:rotate(0deg); } to { transform:rotate(360deg); } }
  #tabbar {
    display:flex; background:var(--surface);
    border-top:0.5px solid var(--border);
    padding-bottom:env(safe-area-inset-bottom,0px);
  }
  .tab-btn {
    flex:1; display:flex; flex-direction:column; align-items:center;
    padding:8px 0 6px; border:none; background:none; cursor:pointer;
    color:var(--text-secondary); font-size:10px; gap:2px;
  }
  .tab-btn.active { color:var(--accent); }
  .tab-btn .tab-icon { font-size:20px; }
  #sidebar {
    position:fixed; top:0; left:-280px; width:280px; height:100%;
    background:var(--surface); border-right:1px solid var(--border);
    transition:left 0.3s; z-index:20; padding:16px;
    padding-top:calc(16px + env(safe-area-inset-top,0px)); overflow-y:auto;
  }
  #sidebar.open { left:0; }
  #overlay {
    position:fixed; top:0; left:0; width:100%; height:100%;
    background:rgba(0,0,0,0.3); z-index:19; display:none;
  }
  #overlay.show { display:block; }
  #sidebar h2 { font-size:16px; margin-bottom:12px; }
  .session-item {
    padding:10px 12px; border-radius:10px; margin-bottom:4px;
    font-size:14px; cursor:pointer; white-space:nowrap; overflow:hidden;
    text-overflow:ellipsis; color:var(--text);
  }
  .session-item:hover { background:var(--code-bg); }
  .session-item .date { font-size:11px; color:var(--text-secondary); margin-top:2px; }
  .session-item .mode-tag { font-size:10px; color:var(--accent); }
  /* Board tab */
  #board-panel { position:relative; }
  #board-header-bar {
    display:flex; align-items:center; justify-content:space-between;
    padding:8px 16px; background:var(--surface);
    border-bottom:0.5px solid var(--border);
  }
  #board-scroll {
    flex:1; overflow-x:auto; overflow-y:hidden;
    display:flex; gap:12px; padding:12px 16px;
    -webkit-overflow-scrolling:touch;
  }
  .board-col {
    min-width:220px; max-width:220px; flex-shrink:0;
    background:var(--surface); border-radius:14px;
    border:1px solid var(--border); display:flex; flex-direction:column;
    max-height:100%;
  }
  .board-col-title {
    padding:10px 12px; font-size:13px; font-weight:600;
    border-bottom:0.5px solid var(--border); color:var(--text-secondary);
  }
  .board-col-cards { overflow-y:auto; padding:8px; flex:1; }
  .board-card {
    background:var(--bg); border-radius:10px; padding:10px;
    margin-bottom:8px; border:1px solid var(--border); cursor:pointer;
  }
  .board-card .title { font-size:14px; font-weight:500; margin-bottom:4px; }
  .board-card .time { font-size:11px; color:var(--text-secondary); }
  #board-offline {
    display:none; text-align:center; padding:40px 20px;
    color:var(--text-secondary); font-size:15px;
  }
  #fab-new-task {
    position:absolute; bottom:calc(16px + env(safe-area-inset-bottom,0px));
    right:16px; width:56px; height:56px; border-radius:50%;
    background:var(--accent); color:#fff; border:none; font-size:28px;
    box-shadow:0 4px 12px rgba(0,122,255,0.3); cursor:pointer; z-index:5;
  }
  #modal-overlay {
    position:fixed; top:0; left:0; width:100%; height:100%;
    background:rgba(0,0,0,0.4); z-index:30; display:none;
    align-items:flex-end; justify-content:center;
  }
  #modal-overlay.show { display:flex; }
  #task-modal {
    background:var(--surface); border-radius:14px 14px 0 0;
    width:100%; max-width:var(--max-w); padding:20px;
    padding-bottom:calc(20px + env(safe-area-inset-bottom,0px));
  }
  #task-modal h3 { margin-bottom:16px; font-size:17px; }
  #task-modal input, #task-modal textarea {
    width:100%; padding:12px; border:1px solid var(--border);
    border-radius:10px; font-size:15px; margin-bottom:12px;
    font-family:inherit; background:var(--surface); color:var(--text);
  }
  #task-modal .modal-actions { display:flex; gap:12px; justify-content:flex-end; }
  #task-modal .modal-actions button {
    padding:10px 20px; border-radius:10px; border:none;
    font-size:15px; cursor:pointer;
  }
  #task-modal .btn-cancel { background:var(--bg); color:var(--text); }
  #task-modal .btn-submit { background:var(--accent); color:#fff; }
  @media(max-width:480px) {
    #header { padding:10px 12px; }
    #messages, #exec-messages { padding:10px 12px; }
    #input-area { padding:8px 12px; }
    .msg .bubble { max-width:90%; font-size:14px; }
  }
</style>
</head>
<body>
<div id="app">
  <div id="header">
    <button id="menuBtn" onclick="toggleSidebar()" aria-label="Menu">☰</button>
    <h1 id="header-title">CCC Chat</h1>
    <select id="project-select" onchange="onProjectChange()"></select>
    <button id="newBtn" onclick="newChat()">新对话</button>
  </div>

  <div id="chat-panel" class="tab-panel active">
    <div id="messages"></div>
    <div id="input-area">
      <div id="input-wrap">
        <button id="mode-switch" onclick="toggleInputMode()" title="切换 Chat/Execute">💬</button>
        <textarea id="input" rows="1" placeholder="输入消息..." onkeydown="onKey(event,'chat')"></textarea>
        <button id="send" onclick="sendChat()" disabled>↑</button>
        <button id="cancel-btn" onclick="cancelStream()">取消</button>
      </div>
    </div>
  </div>

  <div id="exec-panel" class="tab-panel">
    <div id="exec-messages"></div>
    <div id="input-area">
      <div id="input-wrap">
        <button class="mode-switch-exec" onclick="switchTab('chat')" title="切换到 Chat">💬</button>
        <textarea id="exec-input" rows="1" placeholder="输入执行指令..." onkeydown="onKey(event,'execute')"></textarea>
        <button id="exec-send" onclick="sendExecute()" disabled>⚡</button>
        <button id="exec-cancel-btn" class="cancel-exec" onclick="cancelStream()" style="display:none;background:#ff3b30;color:#fff;font-size:12px;width:auto;padding:0 12px;border-radius:18px;border:none;height:36px;">取消</button>
      </div>
    </div>
  </div>

  <div id="board-panel" class="tab-panel">
    <div id="board-header-bar">
      <span style="font-size:15px;font-weight:600;">看板</span>
      <button class="icon-btn" onclick="loadBoard()">↻ 刷新</button>
    </div>
    <div id="board-offline">看板服务离线</div>
    <div id="board-scroll"></div>
    <button id="fab-new-task" onclick="openTaskModal()">+</button>
  </div>

  <div id="tabbar">
    <button class="tab-btn active" data-tab="chat" onclick="switchTab('chat')">
      <span class="tab-icon">💬</span><span>Chat</span>
    </button>
    <button class="tab-btn" data-tab="execute" onclick="switchTab('execute')">
      <span class="tab-icon">⚡</span><span>Execute</span>
    </button>
    <button class="tab-btn" data-tab="board" onclick="switchTab('board')">
      <span class="tab-icon">▦</span><span>Board</span>
    </button>
  </div>
</div>

<div id="overlay" onclick="toggleSidebar()"></div>
<div id="sidebar">
  <h2>对话历史</h2>
  <div id="sessionList"></div>
</div>

<div id="modal-overlay" onclick="closeTaskModal(event)">
  <div id="task-modal" onclick="event.stopPropagation()">
    <h3>新建任务</h3>
    <input id="task-title" placeholder="任务标题" />
    <textarea id="task-desc" rows="3" placeholder="任务描述（可选）"></textarea>
    <div class="modal-actions">
      <button class="btn-cancel" onclick="closeTaskModal()">取消</button>
      <button class="btn-submit" onclick="createTask()">创建</button>
    </div>
  </div>
</div>

<script>
const AUTH = 'Basic ' + btoa('ccc:claude2026');
const DANGEROUS = /\b(rm\s+-rf|rm\s+\/|sudo\b|dd\s+if=|format\b|mkfs\b|>\s*\/dev\/)/i;
const COLUMN_LABELS = {
  backlog:'Backlog', planned:'Planned', in_progress:'In Progress',
  testing:'Testing', verified:'Verified', released:'Released', abnormal:'Abnormal'
};
const PROJECT_WORKSPACE = {ccc:'CCC', qxo:'qxo', xianyu:'xianyu', hp:'hp', 'ai-loop-router':'ai-loop-router'};

let sessionId = crypto.randomUUID?.() ?? Date.now().toString(36)+Math.random().toString(36).slice(2);
let execSessionId = crypto.randomUUID?.() ?? Date.now().toString(36)+Math.random().toString(36).slice(2);
let currentMessages = [];
let execMessages = [];
let streaming = false;
let autoScroll = true;
let currentProject = 'ccc';
let currentTab = 'chat';
let abortController = null;

const input = document.getElementById('input');
const execInput = document.getElementById('exec-input');
const sendBtn = document.getElementById('send');
const execSendBtn = document.getElementById('exec-send');
const messagesEl = document.getElementById('messages');
const execMessagesEl = document.getElementById('exec-messages');

function setupInput(el, btn) {
  el.addEventListener('input', () => {
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 120) + 'px';
    btn.disabled = !el.value.trim();
  });
}
setupInput(input, sendBtn);
setupInput(execInput, execSendBtn);

messagesEl.addEventListener('scroll', () => {
  autoScroll = messagesEl.scrollTop + messagesEl.clientHeight >= messagesEl.scrollHeight - 80;
});
execMessagesEl.addEventListener('scroll', () => {
  autoScroll = execMessagesEl.scrollTop + execMessagesEl.clientHeight >= execMessagesEl.scrollHeight - 80;
});

loadProjects();
loadHistory();

function switchTab(tab) {
  currentTab = tab;
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.getElementById(tab + '-panel').classList.add('active');
  document.querySelector('.tab-btn[data-tab="'+tab+'"]').classList.add('active');
  const titles = {chat:'CCC Chat', execute:'CCC Execute', board:'CCC Board'};
  document.getElementById('header-title').textContent = titles[tab] || 'CCC';
  document.getElementById('newBtn').style.display = tab === 'board' ? 'none' : '';
  if (tab === 'board') loadBoard();
}

function toggleInputMode() {
  if (currentTab === 'chat') switchTab('execute');
  else switchTab('chat');
}

async function loadProjects() {
  try {
    const resp = await fetch('/api/projects', { headers: { Authorization: AUTH } });
    const data = await resp.json();
    const sel = document.getElementById('project-select');
    sel.innerHTML = '';
    for (const p of data.projects) {
      const opt = document.createElement('option');
      opt.value = p.id;
      opt.textContent = p.name;
      if (p.id === currentProject) opt.selected = true;
      sel.appendChild(opt);
    }
  } catch(e) {}
}

function onProjectChange() {
  currentProject = document.getElementById('project-select').value;
  newChat();
  newExecChat();
  loadHistory();
  if (currentTab === 'board') loadBoard();
}

function checkDangerous(text) {
  if (DANGEROUS.test(text)) {
    alert('检测到危险指令（rm/sudo/dd/format/mkfs/>/dev/），已拦截。');
    return true;
  }
  return false;
}

function showCancel(show) {
  document.getElementById('cancel-btn').style.display = show ? 'flex' : 'none';
  document.getElementById('exec-cancel-btn').style.display = show ? 'inline-flex' : 'none';
  sendBtn.style.display = show ? 'none' : 'flex';
  execSendBtn.style.display = show ? 'none' : 'flex';
}

function cancelStream() {
  if (abortController) abortController.abort();
  streaming = false;
  showCancel(false);
  sendBtn.classList.remove('loading');
  execSendBtn.classList.remove('loading');
}

async function sendChat() {
  const text = input.value.trim();
  if (!text || streaming) return;
  input.value = '';
  input.style.height = 'auto';
  sendBtn.disabled = true;
  currentMessages.push({ role: 'user', content: text, mode: 'chat' });
  renderMessage(messagesEl, 'user', text);
  await streamRequest('/api/chat', currentMessages, sessionId, messagesEl, false);
  loadHistory();
}

async function sendExecute() {
  const text = execInput.value.trim();
  if (!text || streaming) return;
  if (checkDangerous(text)) return;
  execInput.value = '';
  execInput.style.height = 'auto';
  execSendBtn.disabled = true;
  execMessages.push({ role: 'user', content: text, mode: 'execute' });
  renderMessage(execMessagesEl, 'user', text, true);
  await streamRequest('/api/execute', execMessages, execSessionId, execMessagesEl, true);
  loadHistory();
}

async function streamRequest(url, msgs, sid, container, isExecute) {
  const typingId = 'typing-' + Date.now();
  const typingEl = document.createElement('div');
  typingEl.className = 'msg assistant typing' + (isExecute ? ' execute' : '');
  typingEl.id = typingId;
  typingEl.innerHTML = isExecute
    ? '<div class="bubble-wrap"><span class="exec-icon">⚡</span><div class="bubble"><span class="dot"></span><span class="dot"></span><span class="dot"></span></div></div>'
    : '<div class="bubble"><span class="dot"></span><span class="dot"></span><span class="dot"></span></div>';
  container.appendChild(typingEl);
  scrollToBottom(container);

  streaming = true;
  showCancel(true);
  if (isExecute) execSendBtn.classList.add('loading');
  else sendBtn.classList.add('loading');
  abortController = new AbortController();

  let fullContent = '';
  let costInfo = null;
  const toolCards = [];

  try {
    const resp = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: AUTH },
      body: JSON.stringify({ messages: msgs, session_id: sid, model: 'flash', project: currentProject, timeout: 120 }),
      signal: abortController.signal,
    });
    if (!resp.ok) {
      removeTyping(typingId);
      const errText = resp.status === 429 ? '前一个执行中，请稍候' : resp.status === 400 ? '危险指令已被拦截' : '请求失败: HTTP ' + resp.status;
      renderMessage(container, 'assistant', errText, isExecute);
      if (isExecute) execMessages.push({ role: 'assistant', content: errText, mode: 'execute' });
      else currentMessages.push({ role: 'assistant', content: errText, mode: 'chat' });
      return;
    }
    removeTyping(typingId);

    const msgDiv = document.createElement('div');
    msgDiv.className = 'msg assistant' + (isExecute ? ' execute' : '');
    if (isExecute) {
      msgDiv.innerHTML = '<div class="bubble-wrap"><span class="exec-icon">⚡</span><div class="bubble"></div></div>';
    } else {
      msgDiv.innerHTML = '<div class="bubble"></div>';
    }
    const bubble = isExecute ? msgDiv.querySelector('.bubble') : msgDiv.querySelector('.bubble');
    container.appendChild(msgDiv);

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        try {
          const data = JSON.parse(line.slice(6));
          if (data.type === 'delta') {
            fullContent += data.content;
            bubble.innerHTML = renderMarkdown(fullContent);
            for (const tc of toolCards) bubble.appendChild(tc);
            if (autoScroll) scrollToBottom(container);
          } else if (data.type === 'tool_use') {
            const card = document.createElement('details');
            card.className = 'tool-card';
            card.open = false;
            card.innerHTML = '<summary>🛠 ' + escapeHtml(data.name || 'tool') + '</summary><pre>' + escapeHtml(JSON.stringify(data.input, null, 2)) + '</pre>';
            toolCards.push(card);
            bubble.appendChild(card);
          } else if (data.type === 'tool_result') {
            if (toolCards.length) {
              const last = toolCards[toolCards.length - 1];
              const pre = document.createElement('pre');
              pre.textContent = typeof data.content === 'string' ? data.content : JSON.stringify(data.content, null, 2);
              last.appendChild(pre);
            }
          } else if (data.type === 'cost') {
            costInfo = data;
          } else if (data.type === 'done') {
            if (data.session_id) {
              if (isExecute) execSessionId = data.session_id;
              else sessionId = data.session_id;
            }
          } else if (data.type === 'error') {
            fullContent += (fullContent ? '\n' : '') + data.content;
            bubble.innerHTML = renderMarkdown(fullContent);
          }
        } catch(e) {}
      }
    }

    if (costInfo) {
      const costEl = document.createElement('div');
      costEl.className = 'cost-info';
      costEl.textContent = 'Tokens: ' + (costInfo.tokens||0) + ' · $' + (costInfo.usd||0).toFixed(4);
      msgDiv.appendChild(costEl);
    }

    const assistantMsg = { role: 'assistant', content: fullContent, mode: isExecute ? 'execute' : 'chat' };
    if (isExecute) execMessages.push(assistantMsg);
    else currentMessages.push(assistantMsg);
  } catch(e) {
    if (e.name !== 'AbortError') {
      removeTyping(typingId);
      renderMessage(container, 'assistant', '网络错误: ' + e.message, isExecute);
    }
  }
  streaming = false;
  showCancel(false);
  sendBtn.classList.remove('loading');
  execSendBtn.classList.remove('loading');
  abortController = null;
  scrollToBottom(container);
}

function removeTyping(id) {
  const el = document.getElementById(id);
  if (el) el.remove();
}

function onKey(e, mode) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    if (mode === 'execute') sendExecute();
    else sendChat();
  }
}

function renderMessage(container, role, content, isExecute) {
  const div = document.createElement('div');
  div.className = 'msg ' + role + (isExecute && role === 'assistant' ? ' execute' : '');
  if (isExecute && role === 'assistant') {
    div.innerHTML = '<div class="bubble-wrap"><span class="exec-icon">⚡</span><div class="bubble">' + renderMarkdown(content) + '</div></div>';
  } else {
    const bubble = document.createElement('div');
    bubble.className = 'bubble';
    bubble.innerHTML = renderMarkdown(content);
    div.appendChild(bubble);
  }
  container.appendChild(div);
  scrollToBottom(container);
}

function renderMarkdown(text) {
  if (!text) return '';
  let h = escapeHtml(text);
  h = h.replace(/```(\w*)\n?([\s\S]*?)```/g, '<pre><code class="lang-$1">$2</code></pre>');
  h = h.replace(/`([^`]+)`/g, '<code>$1</code>');
  h = h.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  h = h.replace(/^- (.+)$/gm, '<li>$1</li>');
  h = h.replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>');
  h = h.replace(/^### (.+)$/gm, '<h3>$1</h3>');
  h = h.replace(/\n\n+/g, '</p><p>');
  h = '<p>' + h + '</p>';
  h = h.replace(/<p><\/p>/g, '');
  return h;
}

function escapeHtml(text) {
  const map = {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'};
  return String(text).replace(/[&<>"]/g, c => map[c]);
}

function scrollToBottom(el) { el.scrollTop = el.scrollHeight; }

function toggleSidebar() {
  document.getElementById('sidebar').classList.toggle('open');
  document.getElementById('overlay').classList.toggle('show');
}

async function loadHistory() {
  try {
    const resp = await fetch('/api/history', { headers: { Authorization: AUTH } });
    const data = await resp.json();
    const list = document.getElementById('sessionList');
    list.innerHTML = '';
    for (const s of data.sessions) {
      const item = document.createElement('div');
      item.className = 'session-item';
      const modeTag = s.mode === 'execute' ? '<span class="mode-tag">⚡ Execute</span> ' : '';
      item.innerHTML = modeTag + '<div>' + escapeHtml(s.title) + '</div><div class="date">' + (s.updated_at||'') + '</div>';
      item.onclick = () => loadSession(s.session_id, s.mode);
      list.appendChild(item);
    }
  } catch(e) {}
}

async function loadSession(id, mode) {
  try {
    const resp = await fetch('/api/history/' + id, { headers: { Authorization: AUTH } });
    const data = await resp.json();
    const isExec = mode === 'execute' || data.mode === 'execute';
    if (isExec) {
      switchTab('execute');
      execSessionId = data.session_id;
      execMessages = data.messages || [];
      execMessagesEl.innerHTML = '';
      for (const msg of execMessages) renderMessage(execMessagesEl, msg.role, msg.content, msg.role === 'assistant');
    } else {
      switchTab('chat');
      sessionId = data.session_id;
      currentMessages = data.messages || [];
      messagesEl.innerHTML = '';
      for (const msg of currentMessages) renderMessage(messagesEl, msg.role, msg.content, false);
      if (data.reply && !currentMessages.some(m => m.role === 'assistant')) {
        renderMessage(messagesEl, 'assistant', data.reply, false);
        currentMessages.push({role:'assistant', content: data.reply, mode:'chat'});
      }
    }
    toggleSidebar();
  } catch(e) {}
}

function newChat() {
  sessionId = crypto.randomUUID?.() ?? Date.now().toString(36)+Math.random().toString(36).slice(2);
  currentMessages = [];
  messagesEl.innerHTML = '';
  input.value = '';
  sendBtn.disabled = true;
}

function newExecChat() {
  execSessionId = crypto.randomUUID?.() ?? Date.now().toString(36)+Math.random().toString(36).slice(2);
  execMessages = [];
  execMessagesEl.innerHTML = '';
  execInput.value = '';
  execSendBtn.disabled = true;
}

async function loadBoard() {
  document.getElementById('board-scroll').innerHTML = '<div style="padding:40px;text-align:center;color:var(--text-secondary)">看板视图占位 — 稍后实现</div>';
}

function openTaskModal() {
  document.getElementById('modal-overlay').classList.add('show');
  document.getElementById('task-title').value = '';
  document.getElementById('task-desc').value = '';
}

function closeTaskModal(e) {
  if (e && e.target !== document.getElementById('modal-overlay')) return;
  document.getElementById('modal-overlay').classList.remove('show');
}

async function createTask() {
  const title = document.getElementById('task-title').value.trim();
  if (!title) { alert('请输入标题'); return; }
  const desc = document.getElementById('task-desc').value.trim();
  const ws = PROJECT_WORKSPACE[currentProject] || currentProject;
  const id = 'chat-' + Date.now();
  try {
    const resp = await fetch('/api/board/proxy/tasks', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: AUTH },
      body: JSON.stringify({ id, title, description: desc, workspace: ws }),
    });
    if (resp.status === 503) { alert('看板服务离线'); return; }
    if (!resp.ok) { alert('创建失败: HTTP ' + resp.status); return; }
    closeTaskModal();
    loadBoard();
  } catch(e) { alert('网络错误'); }
}
</script>
</body>
</html>"""


@app.get("/")
async def serve_ui(request: Request):
    return HTMLResponse(HTML_UI)


def main():
    print("  CCC Chat Server v0.29.0")
    print("  ─────────────────────")
    print(f"  地址: http://0.0.0.0:{PORT}")
    print(f"  本地: http://localhost:{PORT}")
    print(f"  账号: {AUTH_USER} / {AUTH_PASS}")
    print(f"  历史: {CHAT_DIR}/{{project}}/")
    print()
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")


if __name__ == "__main__":
    main()
