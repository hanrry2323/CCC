#!/usr/bin/env python3
"""ccc-chat-server.py — 移动端 Web 聊天界面（Chat / Execute / Board 三模式）

局域网内所有设备（iPad / iPhone / 其他）通过浏览器即可和 LLM 对话或执行指令。
- Chat 模式：proxy.mjs (:4002) 流式对话
- Execute 模式：claude -p 子进程执行
- Board 模式：代理 board-server (:7777)

用法:
    python3 scripts/ccc-chat-server.py
    浏览器打开 http://localhost:8084
"""

import asyncio
import base64
import json
import logging
import os
import re
import shutil
import time
import uuid
from pathlib import Path

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException, Request, Response
from starlette.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
HOST = "0.0.0.0"
PORT = 8084
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
    "ai-loop-router": {
        "name": "AI Loop Router",
        "path": "/Users/apple/program/ai-loop-router",
    },
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
    "backlog",
    "planned",
    "in_progress",
    "testing",
    "verified",
    "released",
    "abnormal",
]

_log = logging.getLogger("ccc-chat")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# Resolve claude CLI path (launchd has limited PATH)
CLAUDE_BIN = shutil.which("claude") or "/Users/apple/.local/bin/claude"
if not os.path.isfile(CLAUDE_BIN):
    _log.warning("claude CLI not found at %s — Execute mode will fail", CLAUDE_BIN)
CLAUDE_ENV = {**os.environ, "PATH": f"{os.environ.get('PATH', '')}:{os.path.dirname(CLAUDE_BIN)}"}

_execute_lock = asyncio.Lock()
_execute_running = False
_EXEC_QUEUE_MAX = 3
_EXECUTE_WAITERS: list[asyncio.Event] = []


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
        truncated_len = len(ctx) - 4000
        ctx = (
            ctx[:4000]
            + f"\n\n> ⚠️ 项目上下文过长，已截断 {truncated_len} 字符（仅保留前 4000 字符）"
        )
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
        raise HTTPException(
            status_code=401, headers={"WWW-Authenticate": 'Basic realm="CCC Chat"'}
        )
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
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
        stream_completed = False
        full_content = ""
        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream(
                    "POST",
                    PROXY_URL,
                    json={
                        "model": model,
                        "messages": messages,
                        "stream": True,
                        "max_tokens": 8192,
                    },
                    headers={"Accept": "text/event-stream"},
                ) as resp:
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
            stream_completed = True
            yield f"data: {json.dumps({'type': 'done', 'session_id': session_id})}\n\n"
        except (GeneratorExit, asyncio.CancelledError):
            # Client disconnected — save whatever we have
            if full_content:
                yield f"data: {json.dumps({'type': 'cancelled', 'session_id': session_id})}\n\n"
            raise
        finally:
            if full_content:
                chat_messages = [m for m in messages if m.get("role") != "system"]
                for m in chat_messages:
                    m.setdefault("mode", "chat")
                chat_messages.append(
                    {
                        "role": "assistant",
                        "content": full_content,
                        "mode": "chat",
                        "partial": not stream_completed,
                    }
                )
                _save_session(
                    session_id, chat_messages, project=project, mode="chat"
                )

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

    project_path = _project_path(project)

    # Queue check — if busy, add to wait list instead of rejecting
    if _execute_running:
        if len(_EXECUTE_WAITERS) >= _EXEC_QUEUE_MAX:
            raise HTTPException(
                status_code=429,
                detail=f"执行队列已满（{_EXEC_QUEUE_MAX}个排队上限），请稍候再试",
            )

    async def generate():
        global _execute_running
        # Queue position tracking
        waiter_event = None
        if _execute_running:
            waiter_event = asyncio.Event()
            _EXECUTE_WAITERS.append(waiter_event)
            pos = len(_EXECUTE_WAITERS)
            yield f"data: {json.dumps({'type': 'queue', 'position': pos, 'max': _EXEC_QUEUE_MAX})}\n\n"
            try:
                await asyncio.wait_for(waiter_event.wait(), timeout=180)
            except asyncio.TimeoutError:
                try:
                    _EXECUTE_WAITERS.remove(waiter_event)
                except ValueError:
                    pass  # already removed by colliding finally
                yield f"data: {json.dumps({'type': 'error', 'content': '排队超时（180s），请重新提交'})}\n\n"
                return
            except (GeneratorExit, asyncio.CancelledError):
                try:
                    _EXECUTE_WAITERS.remove(waiter_event)
                except ValueError:
                    pass
                return

        async with _execute_lock:
            _execute_running = True
            proc = None
            full_content = ""
            execution_results: list = []
            total_cost_usd = None
            total_tokens = None
            stream_completed = False
            try:
                proc = await asyncio.create_subprocess_exec(
                    CLAUDE_BIN,
                    "-p",
                    prompt,
                    "--print",
                    "--verbose",
                    "--output-format",
                    "stream-json",
                    "--model",
                    "flash",
                    cwd=project_path,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env={**CLAUDE_ENV, "CLAUDE_PROJECT_DIR": project_path},
                )

                async def _read_stderr():
                    if proc.stderr:
                        async for line in proc.stderr:
                            _log.warning(
                                "claude stderr: %s",
                                line.decode(errors="replace").rstrip(),
                            )

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
                        chunk = await asyncio.wait_for(
                            proc.stdout.read(4096), timeout=min(remaining, 5.0)
                        )
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
                                    execution_results.append(
                                        {"tool": name, "input": inp, "result": ""}
                                    )
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
                            total_tokens = (total_tokens or 0) + event.get(
                                "usage", {}
                            ).get("output_tokens", 0)
                            result_text = event.get("result", "")
                            if result_text and not full_content:
                                full_content = result_text
                                yield f"data: {json.dumps({'type': 'delta', 'content': result_text})}\n\n"

                stream_completed = True

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

            except (GeneratorExit, asyncio.CancelledError):
                # Client disconnected — save partial content
                raise
            finally:
                _execute_running = False
                # Signal next waiter (if any) — inside lock; defensively guard IndexError
                try:
                    next_waiter = _EXECUTE_WAITERS.pop(0)
                    next_waiter.set()
                except IndexError:
                    pass
                if proc and proc.returncode is None:
                    proc.kill()

                exec_messages = []
                for m in messages:
                    if m.get("role") == "system":
                        continue
                    exec_messages.append({**m, "mode": "execute"})
                if full_content:
                    exec_messages.append(
                        {
                            "role": "assistant",
                            "content": full_content,
                            "mode": "execute",
                            "partial": not stream_completed,
                        }
                    )
                _save_session(
                    session_id,
                    exec_messages,
                    project=project,
                    mode="execute",
                    execution_results=execution_results,
                    total_cost_usd=total_cost_usd,
                )

    return StreamingResponse(generate(), media_type="text/event-stream")


async def _board_proxy(
    method: str, path: str, params: dict | None = None, json_body: dict | None = None
):
    url = f"{BOARD_URL}{path}"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            if method == "GET":
                resp = await client.get(url, params=params, headers=_board_headers())
            else:
                resp = await client.post(url, json=json_body, headers=_board_headers())
            return Response(
                content=resp.content,
                status_code=resp.status_code,
                media_type="application/json",
            )
    except (httpx.ConnectError, httpx.TimeoutException):
        return Response(
            content=json.dumps(
                {"error": "看板服务离线", "detail": "Board Server 不可用"}
            ),
            status_code=503,
            media_type="application/json",
        )


@app.get("/api/board/proxy/board")
async def board_proxy_board(request: Request, workspace: str = "CCC"):
    check_auth(request)
    return await _board_proxy("GET", "/api/board", params={"workspace": workspace})


@app.get("/api/board/proxy/dashboard")
async def board_proxy_dashboard(request: Request, workspace: str = "CCC"):
    check_auth(request)
    return await _board_proxy("GET", "/api/dashboard", params={"workspace": workspace})


@app.get("/api/board/proxy/roles")
async def board_proxy_roles(request: Request):
    check_auth(request)
    return await _board_proxy("GET", "/api/roles")


@app.post("/api/board/proxy/tasks")
async def board_proxy_create_task(request: Request):
    check_auth(request)
    body = await request.json()
    return await _board_proxy("POST", "/api/tasks", json_body=body)


@app.post("/api/board/proxy/tasks/move")
async def board_proxy_move_task(request: Request):
    check_auth(request)
    body = await request.json()
    return await _board_proxy("POST", "/api/tasks/move", json_body=body)


@app.get("/api/projects")
async def list_projects(request: Request):
    check_auth(request)
    return {
        "projects": [
            {"id": pid, "name": info["name"], "path": info["path"]}
            for pid, info in PROJECTS.items()
        ]
    }


EXCLUDE_DIRS = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    ".ccc",
    ".idea",
    ".vscode",
    "dist",
    "build",
}
EXCLUDE_FILE_SUFFIXES = (".pyc", ".DS_Store", ".egg-info")
EXCLUDE_FILE_NAMES = {".DS_Store"}
BINARY_EXTS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".pdf",
    ".zip",
    ".tar",
    ".gz",
    ".pyc",
    ".so",
    ".dylib",
}
MAX_FILE_TREE_ENTRIES = 500
MAX_FILE_TREE_DEPTH = 4
MAX_FILE_READ_BYTES = 100 * 1024


def _walk_project_files(root: str) -> dict:
    """Walk project directory with depth + exclusion guards."""
    import threading

    result = {
        "project_id": "",
        "root": root,
        "entries": [],
        "truncated": False,
        "timed_out": False,
    }

    def _walk():
        root_path = Path(root).resolve()
        if not root_path.exists():
            result["error"] = "root not found"
            return
        try:
            for current, dirs, files in os.walk(root_path, followlinks=False):
                rel = Path(current).relative_to(root_path)
                depth = 0 if str(rel) == "." else len(rel.parts)
                dirs[:] = [
                    d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith(".")
                ]
                if depth > MAX_FILE_TREE_DEPTH:
                    dirs[:] = []
                    continue
                if str(rel) != ".":
                    if len(result["entries"]) >= MAX_FILE_TREE_ENTRIES:
                        result["truncated"] = True
                        dirs[:] = []
                        continue
                    result["entries"].append(
                        {
                            "name": Path(current).name,
                            "type": "dir",
                            "path": str(rel).replace(os.sep, "/"),
                            "depth": depth,
                        }
                    )
                for fname in files:
                    if len(result["entries"]) >= MAX_FILE_TREE_ENTRIES:
                        result["truncated"] = True
                        break
                    if fname in EXCLUDE_FILE_NAMES:
                        continue
                    if any(fname.endswith(s) for s in EXCLUDE_FILE_SUFFIXES):
                        continue
                    if fname.endswith(".egg-info") or ".egg-info" in fname:
                        continue
                    full = Path(current) / fname
                    try:
                        size = full.stat().st_size
                    except OSError:
                        size = 0
                    file_rel = (rel / fname) if str(rel) != "." else Path(fname)
                    result["entries"].append(
                        {
                            "name": fname,
                            "type": "file",
                            "path": str(file_rel).replace(os.sep, "/"),
                            "depth": depth + 1 if str(rel) != "." else 1,
                            "size": size,
                        }
                    )
        except Exception as e:
            result["error"] = f"walk failed: {e}"

    worker = threading.Thread(target=_walk, daemon=True)
    worker.start()
    worker.join(timeout=5.0)
    if worker.is_alive():
        result["timed_out"] = True
        result["truncated"] = True
    return result


@app.get("/api/projects/{project_id}/files")
async def list_project_files(request: Request, project_id: str):
    check_auth(request)
    proj = PROJECTS.get(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail=f"unknown project: {project_id}")
    root = Path(proj["path"]).resolve()
    data = _walk_project_files(str(root))
    data["project_id"] = project_id
    return data


@app.get("/api/projects/{project_id}/file")
async def read_project_file(request: Request, project_id: str, path: str):
    check_auth(request)
    proj = PROJECTS.get(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail=f"unknown project: {project_id}")
    if not path:
        raise HTTPException(status_code=400, detail="path is required")
    if ".." in path.split("/"):
        raise HTTPException(status_code=400, detail="path traversal not allowed")
    root = Path(proj["path"]).resolve()
    target = (root / path).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        raise HTTPException(status_code=400, detail="path traversal not allowed")
    parts = Path(path).parts
    if any(p in EXCLUDE_DIRS for p in parts):
        raise HTTPException(status_code=400, detail=f"access to {path} is denied")
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="file not found")
    ext = target.suffix.lower()
    if ext in BINARY_EXTS:
        raise HTTPException(status_code=415, detail="binary file not readable")
    try:
        size = target.stat().st_size
    except OSError:
        raise HTTPException(status_code=500, detail="stat failed")
    truncated = False
    if size > MAX_FILE_READ_BYTES:
        truncated = True
        content = target.read_text(errors="replace")[:MAX_FILE_READ_BYTES]
    else:
        try:
            content = target.read_text(errors="replace")
        except UnicodeDecodeError:
            raise HTTPException(status_code=415, detail="binary file not readable")
    return {
        "project_id": project_id,
        "path": path,
        "size": size,
        "truncated": truncated,
        "content": content,
    }


@app.get("/api/history")
async def list_sessions(request: Request, project: str = "ccc"):
    check_auth(request)
    chat_dir = _project_chat_dir(project)
    sessions = []
    for f in sorted(
        chat_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True
    ):
        try:
            data = json.loads(f.read_text())
            sessions.append(
                {
                    "session_id": data.get("session_id", f.stem),
                    "title": data.get("title", "Unknown")[:80],
                    "updated_at": data.get("updated_at", ""),
                    "mode": data.get("mode", "chat"),
                }
            )
        except (json.JSONDecodeError, OSError):
            pass
    return {"sessions": sessions}


@app.get("/api/history/{session_id}")
async def get_session(request: Request, session_id: str, project: str = "ccc"):
    check_auth(request)
    path = _session_path(session_id, project)
    if not path.exists():
        raise HTTPException(status_code=404)
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        raise HTTPException(status_code=500)


@app.delete("/api/history/{session_id}")
async def delete_session(request: Request, session_id: str, project: str = "ccc"):
    check_auth(request)
    path = _session_path(session_id, project)
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
<meta name="color-scheme" content="light dark">
<title>CCC Chat</title>
<style>
  html { transition: background 0.3s ease; }
  body { transition: var(--transition-theme); }
  #app, #header, #sidebar, #input-area, #tabbar, .bubble,
  .board-col, #task-modal, #modal-overlay, .file-tree-panel,
  .board-card, .tool-card, #input-wrap, .session-item {
    transition: var(--transition-theme);
  }
  :root {
    --bg: #f8f8fa;
    --surface: #ffffff;
    --text: #1d1d1f;
    --text-secondary: #86868b;
    --border: #e5e5ea;
    --accent: #007aff;
    --accent-hover: #0056b3;
    --user-bg: #007aff;
    --user-text: #ffffff;
    --assistant-bg: #ffffff;
    --code-bg: #f0f0f5;
    --shadow: 0 1px 3px rgba(0,0,0,0.06);
    --shadow-sm: 0 1px 2px rgba(0,0,0,0.05);
    --shadow-lg: 0 4px 12px rgba(0,0,0,0.12);
    --danger: #ff3b30;
    --success: #34c759;
    --radius: 18px;
    --radius-sm: 8px;
    --radius-lg: 22px;
    --max-w: 720px;
    --space-xs: 4px;
    --space-sm: 8px;
    --space-md: 12px;
    --space-lg: 16px;
    --space-xl: 24px;
    --terminal-bg: #1a1b26;
    --terminal-text: #a9b1d6;
    --terminal-prompt: #73daca;
    --terminal-header: #7aa2f7;
    --terminal-sep: #2f3346;
    --terminal-info: #565f89;
    --terminal-body: #1f2233;
    --terminal-comment: #565f89;
    --transition-theme: background 0.3s ease, color 0.3s ease, border-color 0.3s ease, box-shadow 0.3s ease;
  }
  [data-theme="dark"] {
    --bg: #1c1c1e;
    --surface: #2c2c2e;
    --text: #f5f5f7;
    --text-secondary: #98989d;
    --border: #38383a;
    --accent: #0a84ff;
    --accent-hover: #409cff;
    --user-bg: #0a84ff;
    --user-text: #ffffff;
    --assistant-bg: #2c2c2e;
    --code-bg: #3a3a3c;
    --shadow: 0 1px 3px rgba(0,0,0,0.3);
    --shadow-sm: 0 1px 2px rgba(0,0,0,0.2);
    --shadow-lg: 0 4px 12px rgba(0,0,0,0.4);
    --danger: #ff453a;
    --success: #30d158;
    --terminal-bg: #0d0e15;
    --terminal-text: #a9b1d6;
    --terminal-prompt: #73daca;
    --terminal-header: #7aa2f7;
    --terminal-sep: #1a1b2e;
    --terminal-info: #565f89;
    --terminal-body: #13141f;
    --terminal-comment: #3b3d55;
  }
  * { margin:0; padding:0; box-sizing:border-box; }
    --shadow-lg: 0 4px 12px rgba(0,0,0,0.12);
    --danger: #ff3b30;
    --accent-hover: #0056b3;
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
    padding:var(--space-md) var(--space-lg); padding-top:calc(var(--space-md) + env(safe-area-inset-top,0px));
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
  .msg { margin-bottom:8px; display:flex; flex-direction:column; }
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
    border-bottom-right-radius:4px; box-shadow:none;
  }
  .msg.assistant .bubble {
    background:var(--assistant-bg); border:1px solid var(--border);
    border-bottom-left-radius:4px; color:var(--text);
  }
  .msg.user + .msg.user, .msg.assistant + .msg.assistant { margin-top:-8px; }
  .msg .ts { font-size:11px; color:var(--text-secondary); margin-top:4px; padding-left:4px; }
  .msg.user .ts { padding-right:4px; text-align:right; }
  .code-block-wrap { position:relative; margin:8px 0; }
  .code-block-wrap pre { margin:0; border-radius:8px 8px 0 0; }
  .copy-btn {
    display:block; width:100%; padding:4px 12px; font-size:11px; color:var(--text-secondary);
    background:var(--code-bg); border:1px solid var(--border); border-top:none;
    border-radius:0 0 8px 8px; cursor:pointer; transition:background 0.2s;
    text-align:right;
  }
  .copy-btn:hover { background:var(--border); }
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
  @keyframes msg-fade-in { from { opacity:0; transform:translateY(4px); } to { opacity:1; transform:translateY(0); } }
  .msg { animation: msg-fade-in 0.2s ease-out; }
  .tool-card { transition: border-color 0.2s, box-shadow 0.2s; }
  .tool-card:hover { border-color:var(--accent); box-shadow:0 1px 6px rgba(0,122,255,0.1); }
  /* Terminal mode Execute */
  .terminal-output {
    background:var(--terminal-bg); color:var(--terminal-text);
    font-family:'SF Mono','Menlo','Consolas',monospace;
    font-size:13px; line-height:1.7;
    padding:14px; overflow-y:auto; flex:1;
    -webkit-overflow-scrolling:touch;
    transition: var(--transition-theme);
  }
  .terminal-line { padding:1px 0; white-space:pre-wrap; word-break:break-word; }
  .terminal-line + .terminal-line { margin-top:2px; }
  .terminal-prompt { color:var(--terminal-prompt); font-weight:600; }
  .terminal-command { color:var(--terminal-text); font-weight:500; }
  .terminal-output-text { color:var(--terminal-text); }
  .terminal-timestamp { color:var(--terminal-comment); font-size:11px; margin-right:8px; }
  .terminal-cursor { display:inline-block; }
  .terminal-cursor::after { content:'▊'; animation:term-blink 1s step-end infinite; color:var(--terminal-prompt); }
  @keyframes term-blink { 50% { opacity:0; } }
  .terminal-tool-header {
    color:var(--terminal-header); font-weight:600; margin:8px 0 4px;
    display:flex; align-items:center; gap:6px; font-size:12px;
  }
  .terminal-tool-header .tool-icon { font-size:14px; }
  .terminal-tool-header .tool-status { font-size:11px; color:var(--success); }
  .terminal-tool-header .tool-status.running { color:#e0af68; animation:term-blink 1s step-end infinite; }
  .terminal-tool-body {
    background:var(--terminal-body); border-left:3px solid var(--terminal-header); border-radius:4px;
    padding:8px 12px; margin:4px 0 10px; font-size:12px; overflow-x:auto;
  }
  .terminal-tool-body pre { margin:0; font-size:12px; color:var(--terminal-text); white-space:pre-wrap; word-break:break-word; }
  .terminal-separator { border:none; border-top:1px solid var(--terminal-sep); margin:6px 0; }
  .terminal-info { color:var(--terminal-comment); font-size:11px; padding:4px 0; }
  /* Diff visualization */
  .diff-file { margin:12px 0; background:var(--terminal-body); border-radius:6px; overflow:hidden; border:1px solid var(--terminal-sep); }
  .diff-file-header {
    padding:6px 12px; font-size:12px; color:var(--terminal-header);
    background:var(--terminal-info); font-weight:500;
    display:flex; justify-content:space-between; align-items:center;
  }
  .diff-summary { color:var(--success); font-size:11px; }
  .diff-hunk-header {
    padding:4px 12px; font-size:11px; color:var(--terminal-comment);
    background:var(--terminal-body); font-family:monospace; border-bottom:1px solid var(--terminal-sep);
  }
  .diff-line {
    padding:1px 12px; font-size:12px; line-height:1.6;
    font-family:'SF Mono','Menlo',monospace; white-space:pre-wrap;
    display:flex; word-break:break-word;
  }
  .diff-prefix { width:14px; flex-shrink:0; text-align:center; user-select:none; }
  .diff-add { background:rgba(65,179,100,0.12); color:var(--success); }
  .diff-del { background:rgba(245,85,85,0.12); color:var(--danger); }
  .diff-ctx { color:#a9b1d6; }
  .diff-global-summary {
    padding:6px 12px; font-size:12px; color:var(--terminal-text);
    background:var(--terminal-body); border-radius:6px; margin-bottom:8px; text-align:center;
    border:1px solid var(--terminal-sep);
  }
  /* Exec layout */
  .exec-layout { display:flex; flex:1; overflow:hidden; min-height:0; }
  .exec-meta-bar {
    padding:4px 12px; background:var(--terminal-body); color:var(--terminal-comment);
    font-size:11px; border-bottom:1px solid var(--terminal-sep);
    text-align:right; font-family:'SF Mono','Menlo',monospace;
  }
  #input-area {
    padding:12px 16px;
    background:var(--surface); border-top:0.5px solid var(--border);
  }
  #input-wrap {
    display:flex; gap:8px; align-items:flex-end;
    background:var(--surface); border-radius:20px; padding:2px 4px 2px 12px;
    border:1px solid var(--border);
  }
  #input-wrap:focus-within { border-color:var(--accent); box-shadow:0 0 0 2px rgba(0,122,255,0.15), 0 2px 8px rgba(0,0,0,0.08); }
  #mode-switch {
    width:44px; height:44px; border-radius:50%; border:none; background:transparent;
    color:var(--text); font-size:16px; cursor:pointer; flex-shrink:0; padding:0;
    display:flex; align-items:center; justify-content:center; transition:background 0.2s;
  }
  #mode-switch:hover { background:var(--code-bg); }
  .mode-switch-exec {
    width:44px; height:44px; border-radius:50%; border:none;
    background:var(--bg); color:var(--text); font-size:14px;
    cursor:pointer; flex-shrink:0; display:flex;
    align-items:center; justify-content:center; padding:0;
  }
  .cancel-exec {
    background:var(--danger); color:#fff; font-size:12px;
    width:auto; padding:0 12px; border-radius:18px; border:none;
    height:36px; min-height:44px; display:none;
  }
  #input, #exec-input {
    flex:1; border:none; outline:none; background:transparent;
    font-size:16px; color:var(--text); resize:none;
    max-height:120px; line-height:1.4; padding:8px 0; font-family:inherit;
  }
  #input::placeholder, #exec-input::placeholder { color:var(--text-secondary); }
  #send, #exec-send, #cancel-btn {
    width:44px; height:44px; border-radius:50%; border:none;
    background:var(--accent); color:#fff; font-size:18px;
    cursor:pointer; display:flex; align-items:center; justify-content:center;
    flex-shrink:0; transition:opacity 0.15s;
  }
  #cancel-btn { background:var(--danger); font-size:12px; width:auto; padding:0 12px; border-radius:18px; display:none; }
  .scroll-bottom-fab {
    position:absolute; bottom:60px; right:16px;
    width:40px; height:40px; border-radius:50%;
    background:var(--surface); border:1px solid var(--border);
    color:var(--accent); font-size:18px; box-shadow:var(--shadow);
    cursor:pointer; z-index:8; display:none;
    align-items:center; justify-content:center;
    transition:opacity 0.2s, transform 0.2s;
  }
  .scroll-bottom-fab.show { display:flex; }
  #send:disabled, #exec-send:disabled { opacity:0.3; cursor:default; transition:opacity 0.2s; }
  #send.loading, #exec-send.loading { animation:spin 1s linear infinite; }
  @keyframes spin { from { transform:rotate(0deg); } to { transform:rotate(360deg); } }
  #tabbar {
    display:flex; background:var(--surface);
    border-top:0.5px solid var(--border);
    padding-bottom:env(safe-area-inset-bottom,0px);
    padding-top:4px;
  }
  .tab-btn {
    flex:1; display:flex; flex-direction:column; align-items:center;
    padding:8px 0 6px; border:none; background:none; cursor:pointer;
    color:var(--text-secondary); font-size:10px; gap:2px;
    position:relative; min-height:48px; transition:color 0.2s;
  }
  .tab-btn.active { color:var(--accent); }
  .tab-btn.active::after {
    content:''; position:absolute; bottom:0; left:20%; right:20%;
    height:3px; background:var(--accent); border-radius:1.5px 1.5px 0 0;
    transition:all 0.2s;
  }
  .tab-btn .tab-icon { font-size:22px; }
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
  .sidebar-handle {
    width:36px; height:4px; border-radius:2px;
    background:var(--border); margin:0 auto 12px;
    position:sticky; top:0;
  }
  #sidebar h2 { font-size:16px; margin-bottom:12px; }
  .session-item {
    padding:12px; border-radius:10px; margin-bottom:4px;
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
    border-bottom:0.5px solid var(--border); color:var(--text-secondary); text-decoration:none; transition:color .2s;
  }
  .board-col-cards { overflow-y:auto; padding:8px; flex:1; }
  .board-card {
    background:var(--bg); border-radius:10px; padding:12px;
    margin-bottom:8px; border:1px solid var(--border); cursor:pointer;
  }
  .board-card .title { font-size:14px; font-weight:500; margin-bottom:4px; }
  .board-card .time { font-size:11px; color:var(--text-secondary); }
  .board-scroll-indicator { display:none; }
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
    #sidebar {
      position:fixed; top:auto; bottom:0; left:0; width:100%;
      height:auto; max-height:80vh;
      background:var(--surface); border-right:none;
      border-radius:16px 16px 0 0;
      transform:translateY(100%);
      transition:transform 0.35s cubic-bezier(0.32, 0.72, 0, 1);
      padding:20px 16px; z-index:20;
      padding-bottom:calc(20px + env(safe-area-inset-bottom,0px));
    }
    #sidebar.open { left:0; transform:translateY(0); }
    #header { padding:10px 12px; }
    #messages, #exec-messages { padding:10px 12px; }
    #input-area { padding:8px 12px; }
    .msg .bubble { max-width:90%; font-size:14px; }
  }
  @media(max-width:375px) {
    #header { padding:8px 10px; }
    #messages, #exec-messages { padding:8px 10px; }
    #input-area { padding:6px 10px; }
    .msg .bubble { max-width:92%; }
    #header h1 { display:none; }
    #project-select { width:100px; }
  }
  .file-tree-panel { width:260px; flex-shrink:0; border-right:1px solid var(--border); overflow-y:auto; background:var(--surface); display:flex; flex-direction:column; padding:12px; }
  .exec-main { flex:1; display:flex; flex-direction:column; overflow:hidden; min-width:0; }
  .file-tree-panel .header { padding:8px 12px; font-size:12px; font-weight:600; color:var(--text-secondary); border-bottom:1px solid var(--border); display:flex; align-items:center; justify-content:space-between; }
  .file-tree-panel .header button { background:transparent; border:none; color:var(--accent); cursor:pointer; font-size:11px; padding:2px 4px; }
  #file-tree { padding:4px 0; font-size:12px; flex:1; overflow-y:auto; }
  .file-item { padding:6px 12px; font-size:12px; cursor:pointer; display:flex; align-items:center; gap:6px; color:var(--text); user-select:none; }
  .file-item:hover { background:var(--code-bg); }
  .file-item.dir { font-weight:500; }
  .file-item .icon { width:16px; text-align:center; flex-shrink:0; font-family:monospace; }
  .file-item .name { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; flex:1; }
  .file-item .meta { font-size:10px; color:var(--text-secondary); flex-shrink:0; margin-left:4px; }
  .file-item .children { width:100%; }
  .file-item.collapsed > .icon::before { content:"▶"; }
  .file-item.dir:not(.collapsed) > .icon::before { content:"▼"; }
  .file-item:not(.dir) > .icon::before { content:"·"; color:var(--text-secondary); }
  .file-tree-offline { padding:12px; font-size:11px; color:var(--text-secondary); }
  .file-tree-meta { padding:8px 12px; font-size:10px; color:var(--text-secondary); border-top:1px solid var(--border); }
  .file-content-preview { max-height:400px; overflow-y:auto; background:var(--code-bg); border-radius:8px; padding:12px; margin:8px 0; font-size:12px; white-space:pre-wrap; word-break:break-all; font-family:'SF Mono',Monaco,monospace; line-height:1.5; }
  .file-content-preview .meta-bar { display:flex; gap:8px; align-items:center; justify-content:space-between; margin-bottom:8px; font-family:inherit; font-size:11px; color:var(--text-secondary); }
  .file-content-preview .meta-bar button { background:transparent; border:1px solid var(--border); border-radius:6px; padding:2px 8px; cursor:pointer; font-family:inherit; }
  @media(max-width:768px) {
    .exec-layout { flex-direction:column; }
    .file-tree-panel { width:100%; max-height:180px; border-right:none; border-bottom:1px solid var(--border); }
    #board-scroll {
      scroll-snap-type: x mandatory;
      -webkit-overflow-scrolling:touch;
      gap:8px;
    }
    .board-col {
      scroll-snap-align: start;
      min-width:85vw;
    }
    .board-scroll-indicator {
      display:flex; justify-content:center; gap:6px; padding:6px 0;
    }
  }
  @media(max-width:480px) {
    .file-tree-panel { max-height:140px; }
  }
  @media(orientation:landscape) and (max-width:768px) {
    .file-tree-panel { width:200px; max-height:none; border-right:1px solid var(--border); border-bottom:none; }
    .exec-layout { flex-direction:row; }
  }
  @media(orientation:landscape) and (max-height:414px) {
    .tab-btn .tab-icon { font-size:16px; }
    .tab-btn { padding:4px 0 2px; }
    #tabbar { height:36px; }
  }
  /* Skeleton loading */
  @keyframes skeleton-pulse { 0%,100%{opacity:.4} 50%{opacity:.8} }
  .skeleton { background:var(--code-bg); border-radius:8px; animation:skeleton-pulse 1.5s ease-in-out infinite; }
  .skeleton-line { height:14px; margin-bottom:8px; width:100%; }
  .skeleton-line:nth-child(2) { width:85%; }
  .skeleton-line:nth-child(3) { width:60%; }
  .skeleton-card { height:60px; margin-bottom:8px; border-radius:10px; }
  /* Message editing */
  .msg.user .bubble .edit-textarea {
    width:100%; padding:8px; border-radius:8px; border:1px solid rgba(255,255,255,0.3);
    background:rgba(255,255,255,0.15); color:#fff; font-size:14px; font-family:inherit;
    resize:vertical; min-height:60px; outline:none;
  }
  .msg.user .bubble .edit-actions { display:flex; gap:6px; margin-top:6px; justify-content:flex-end; }
  .msg.user .bubble .edit-actions button {
    padding:4px 12px; border-radius:12px; border:none; font-size:12px; cursor:pointer;
  }
  .msg.user .bubble .edit-actions .edit-save { background:rgba(255,255,255,0.9); color:#007aff; }
  .msg.user .bubble .edit-actions .edit-cancel { background:rgba(255,255,255,0.2); color:rgba(255,255,255,0.8); }
  [data-theme="dark"] .msg.user .bubble .edit-textarea {
    background:rgba(255,255,255,0.1);
  }
</style>
</head>
<body>
<div id="app">
  <div id="header">
    <button id="menuBtn" onclick="toggleSidebar()" aria-label="Menu">☰</button>
    <h1 id="header-title">CCC Chat</h1>
    <button id="themeBtn" onclick="toggleTheme()" aria-label="切换主题" style="font-size:18px;background:none;border:none;cursor:pointer;padding:4px 2px;line-height:1;">🌙</button>
    <select id="project-select" onchange="onProjectChange()"></select>
    <button id="newBtn" onclick="newChat()">新对话</button>
  </div>

  <div id="chat-panel" class="tab-panel active">
    <div id="messages"></div>
    <button id="scroll-bottom-fab-chat" class="scroll-bottom-fab" onclick="scrollFabToBottom('chat')">↓</button>
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
    <div class="exec-layout">
      <div class="file-tree-panel">
        <div class="header"><span>文件</span><button onclick="loadFileTree()" title="刷新">↻</button></div>
        <div id="file-tree"><div class="file-tree-offline">切换到 Execute 时加载…</div></div>
        <div id="file-tree-meta" class="file-tree-meta"></div>
      </div>
      <div class="exec-main">
        <div class="exec-meta-bar" id="exec-meta-bar">~ project · execute terminal</div>
        <div id="exec-terminal" class="terminal-output">
          <div class="terminal-line"><span class="terminal-info"> CCC Execute Terminal</span></div>
          <div class="terminal-line"><span class="terminal-info"> 输入指令开始执行...</span></div>
        </div>
        <button id="scroll-bottom-fab-exec" class="scroll-bottom-fab" onclick="scrollFabToBottom('exec')">↓</button>
      </div>
    </div>
    <div id="input-area">
      <div id="input-wrap">
        <button class="mode-switch-exec" onclick="switchTab('chat')" title="切换到 Chat">💬</button>
        <textarea id="exec-input" rows="1" placeholder="输入执行指令..." onkeydown="onKey(event,'execute')"></textarea>
        <button id="exec-send" onclick="sendExecute()" disabled>⚡</button>
        <button id="exec-cancel-btn" class="cancel-exec" onclick="cancelStream()">取消</button>
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
    <div id="board-scroll-indicator" class="board-scroll-indicator"></div>
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
  <div class="sidebar-handle"></div>
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
let chatAutoScroll = true;
let execAutoScroll = true;
let currentProject = 'ccc';
let currentTab = 'chat';
let abortController = null;

const input = document.getElementById('input');
const execInput = document.getElementById('exec-input');
const sendBtn = document.getElementById('send');
const execSendBtn = document.getElementById('exec-send');
const messagesEl = document.getElementById('messages');
const execMessagesEl = document.getElementById('exec-messages') || document.getElementById('exec-terminal');

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
  chatAutoScroll = messagesEl.scrollTop + messagesEl.clientHeight >= messagesEl.scrollHeight - 80;
});
if (execMessagesEl && execMessagesEl.id === 'exec-messages') {
  execMessagesEl.addEventListener('scroll', () => {
    execAutoScroll = execMessagesEl.scrollTop + execMessagesEl.clientHeight >= execMessagesEl.scrollHeight - 80;
  });
}
const execTerminalEl = document.getElementById('exec-terminal');
if (execTerminalEl) {
  execTerminalEl.addEventListener('scroll', () => {
    execAutoScroll = execTerminalEl.scrollTop + execTerminalEl.clientHeight >= execTerminalEl.scrollHeight - 80;
  });
}

const scrollFabChat = document.getElementById('scroll-bottom-fab-chat');
const scrollFabExec = document.getElementById('scroll-bottom-fab-exec');
function updateFab(container, fab) {
  if (!container || !fab) return;
  const threshold = 200;
  const atBottom = container.scrollTop + container.clientHeight >= container.scrollHeight - threshold;
  const isMobile = window.innerWidth <= 768;
  fab.classList.toggle('show', !atBottom && isMobile);
}
function scrollFabToBottom(mode) {
  const el = mode === 'chat' ? messagesEl : (execMessagesEl.id === 'exec-messages' ? execMessagesEl : execTerminalEl);
  if (el) { el.scrollTop = el.scrollHeight; }
  const fab = mode === 'chat' ? scrollFabChat : scrollFabExec;
  if (fab) fab.classList.remove('show');
}
messagesEl.addEventListener('scroll', () => updateFab(messagesEl, scrollFabChat));
if (execTerminalEl) execTerminalEl.addEventListener('scroll', () => updateFab(execTerminalEl, scrollFabExec));
window.addEventListener('resize', () => { updateFab(messagesEl, scrollFabChat); updateFab(execTerminalEl, scrollFabExec); });

(function setupKeyboardHandler() {
  if (!window.visualViewport) return;
  let keyboardActive = false;
  window.visualViewport.addEventListener('resize', () => {
    const vp = window.visualViewport;
    const keyboardHeight = window.innerHeight - vp.height;
    const inputArea = document.getElementById('input-area');
    const header = document.getElementById('header');
    if (!inputArea || !header) return;
    if (keyboardHeight > 100) {
      keyboardActive = true;
      inputArea.style.transform = 'translateY(-' + keyboardHeight + 'px)';
      header.style.position = 'relative';
      setTimeout(() => {
        const el = currentTab === 'chat' ? messagesEl : (execMessagesEl.id === 'exec-messages' ? execMessagesEl : execTerminalEl);
        if (el) el.scrollTop = el.scrollHeight;
      }, 50);
    } else if (keyboardActive) {
      keyboardActive = false;
      inputArea.style.transform = '';
      header.style.position = '';
    }
  });
})();

// Theme initialization
(function initTheme() {
  const saved = localStorage.getItem('ccc-chat-theme');
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  const isDark = saved ? saved === 'dark' : prefersDark;
  document.documentElement.setAttribute('data-theme', isDark ? 'dark' : 'light');
  const btn = document.getElementById('themeBtn');
  if (btn) btn.textContent = isDark ? '☀️' : '🌙';
})();
window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
  if (!localStorage.getItem('ccc-chat-theme')) {
    const isDark = e.matches;
    document.documentElement.setAttribute('data-theme', isDark ? 'dark' : 'light');
    const btn = document.getElementById('themeBtn');
    if (btn) btn.textContent = isDark ? '☀️' : '🌙';
  }
});
function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme') || 'light';
  const next = current === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  localStorage.setItem('ccc-chat-theme', next);
  const btn = document.getElementById('themeBtn');
  if (btn) btn.textContent = next === 'dark' ? '☀️' : '🌙';
}

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
  if (tab === 'execute') loadFileTree();
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
  updateExecMetaBar();
  loadHistory();
  if (currentTab === 'board') loadBoard();
  if (currentTab === 'execute') loadFileTree();
}

function updateExecMetaBar() {
  const bar = document.getElementById('exec-meta-bar');
  if (bar) bar.textContent = '~ ' + currentProject + ' · execute terminal';
}

const FILE_TREE_RENDER_LIMIT = 300;
let _fileTreeExpanded = new Set();

async function loadFileTree() {
  const container = document.getElementById('file-tree');
  const metaEl = document.getElementById('file-tree-meta');
  if (!container) return;
  if (!currentProject) {
    container.innerHTML = '<div class="file-tree-offline">请先选择项目</div>';
    if (metaEl) metaEl.textContent = '';
    return;
  }
  container.innerHTML = '<div class="file-tree-offline">加载中…</div>';
  try {
    const resp = await fetch('/api/projects/' + encodeURIComponent(currentProject) + '/files', {
      headers: { Authorization: AUTH },
    });
    if (!resp.ok) throw new Error('HTTP ' + resp.status);
    const data = await resp.json();
    renderFileTree(data.entries || [], container);
    let meta = (data.entries || []).length + ' 项';
    if (data.truncated) meta += ' · 已截断';
    if (data.timed_out) meta += ' · 超时';
    if (metaEl) metaEl.textContent = meta;
  } catch (e) {
    container.innerHTML = '<div class="file-tree-offline">加载失败: ' + (e.message || e) + '</div>';
    if (metaEl) metaEl.textContent = '';
  }
}

function renderFileTree(entries, container) {
  container.innerHTML = '';
  if (!entries.length) {
    container.innerHTML = '<div class="file-tree-offline">（空目录）</div>';
    return;
  }
  const nodes = new Map();
  const root = { name: '', type: 'dir', path: '', depth: 0, children: [] };
  const sorted = entries.slice(0, FILE_TREE_RENDER_LIMIT);
  for (const e of sorted) {
    const parts = e.path.split('/').filter(Boolean);
    let cur = root;
    let acc = [];
    for (let i = 0; i < parts.length; i++) {
      acc.push(parts[i]);
      const key = acc.join('/');
      let node = nodes.get(key);
      if (!node) {
        const isLeaf = (i === parts.length - 1) && e.type === 'file';
        node = {
          name: parts[i],
          type: isLeaf ? 'file' : 'dir',
          path: key,
          depth: i + 1,
          size: isLeaf ? (e.size || 0) : undefined,
          children: [],
        };
        cur.children.push(node);
        nodes.set(key, node);
      }
      cur = node;
    }
  }
  const frag = document.createDocumentFragment();
  for (const child of root.children) {
    frag.appendChild(_buildFileItem(child));
  }
  container.appendChild(frag);
}

function _buildFileItem(node) {
  const wrap = document.createElement('div');
  wrap.className = 'file-item ' + node.type;
  wrap.dataset.path = node.path;
  wrap.dataset.type = node.type;
  const icon = document.createElement('span');
  icon.className = 'icon';
  wrap.appendChild(icon);
  const name = document.createElement('span');
  name.className = 'name';
  name.textContent = node.name;
  wrap.appendChild(name);
  if (node.type === 'file' && typeof node.size === 'number') {
    const meta = document.createElement('span');
    meta.className = 'meta';
    meta.textContent = node.size > 1024 ? Math.round(node.size / 1024) + 'KB' : node.size + 'B';
    wrap.appendChild(meta);
  }
  if (node.children && node.children.length) {
    const childWrap = document.createElement('div');
    childWrap.className = 'children';
    for (const c of node.children) {
      childWrap.appendChild(_buildFileItem(c));
    }
    wrap.appendChild(childWrap);
    if (!_fileTreeExpanded.has(node.path)) wrap.classList.add('collapsed');
    wrap.addEventListener('click', (ev) => {
      ev.stopPropagation();
      if (wrap.classList.toggle('collapsed')) {
        _fileTreeExpanded.delete(node.path);
      } else {
        _fileTreeExpanded.add(node.path);
      }
    });
  } else if (node.type === 'file') {
    wrap.addEventListener('click', (ev) => {
      ev.stopPropagation();
      readFile(node.path);
    });
  }
  return wrap;
}

async function readFile(path) {
  if (!path) return;
  try {
    const resp = await fetch('/api/projects/' + encodeURIComponent(currentProject) + '/file?path=' + encodeURIComponent(path), {
      headers: { Authorization: AUTH },
    });
    if (!resp.ok) {
      const detail = await resp.json().catch(() => ({}));
      alert('无法读取文件: ' + (detail.detail || ('HTTP ' + resp.status)));
      return;
    }
    const data = await resp.json();
    showFilePreview(path, data);
  } catch (e) {
    alert('读取失败: ' + (e.message || e));
  }
}

function showFilePreview(path, data) {
  const wrap = document.createElement('div');
  wrap.className = 'msg';
  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  bubble.style.maxWidth = '92%';
  const meta = document.createElement('div');
  meta.className = 'file-content-preview';
  const bar = document.createElement('div');
  bar.className = 'meta-bar';
  const title = document.createElement('span');
  title.textContent = path + (data.truncated ? ' · 已截断(' + data.size + 'B)' : ' · ' + data.size + 'B');
  bar.appendChild(title);
  const close = document.createElement('button');
  close.textContent = '关闭';
  close.onclick = () => wrap.remove();
  bar.appendChild(close);
  meta.appendChild(bar);
  const code = document.createElement('div');
  code.textContent = data.content || '';
  meta.appendChild(code);
  bubble.appendChild(meta);
  wrap.appendChild(bubble);
  const terminal = document.getElementById('exec-terminal');
  if (terminal) {
    wrap.classList.add('terminal-line');
    terminal.appendChild(wrap);
    terminal.scrollTop = terminal.scrollHeight;
  }
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
  const terminal = getTerminal();
  if (currentTab === 'execute' && terminal) {
    terminal.querySelector('.terminal-cursor')?.remove();
    const runningTool = terminal.querySelector('.terminal-tool-header .tool-status.running');
    if (runningTool) {
      runningTool.classList.remove('running');
      runningTool.textContent = ' cancelled';
    }
    appendTerminalInfo(' 用户终止');
  }
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

const TOOL_ICONS = {
  Bash:'⚡', Edit:'✎', Read:'📖', Write:'📝', Glob:'🔍', Grep:'🔍',
  WebFetch:'🌐', WebSearch:'🔎', TodoWrite:'☑', Think:'💭'
};
function toolIcon(name) { return TOOL_ICONS[name] || '🔧'; }
function terminalNow() {
  const d = new Date();
  const pad = n => String(n).padStart(2, '0');
  return pad(d.getHours()) + ':' + pad(d.getMinutes()) + ':' + pad(d.getSeconds());
}

function getTerminal() {
  return document.getElementById('exec-terminal');
}
function terminalScrollToBottom() {
  const t = getTerminal();
  if (t && execAutoScroll) t.scrollTop = t.scrollHeight;
}

function renderTerminalCommand(text) {
  const t = getTerminal();
  if (!t) return;
  const line = document.createElement('div');
  line.className = 'terminal-line';
  const prompt = document.createElement('span');
  prompt.className = 'terminal-prompt';
  prompt.textContent = '$ ';
  const cmd = document.createElement('span');
  cmd.className = 'terminal-command';
  cmd.textContent = text;
  line.appendChild(prompt);
  line.appendChild(cmd);
  t.appendChild(line);
  terminalScrollToBottom();
}

function appendTerminalInfo(text) {
  const t = getTerminal();
  if (!t) return;
  const line = document.createElement('div');
  line.className = 'terminal-line';
  const info = document.createElement('span');
  info.className = 'terminal-info';
  info.textContent = text;
  line.appendChild(info);
  t.appendChild(line);
  terminalScrollToBottom();
}

function appendTerminalSeparator() {
  const t = getTerminal();
  if (!t) return;
  const hr = document.createElement('hr');
  hr.className = 'terminal-separator';
  t.appendChild(hr);
}

function parseDiff(text) {
  const files = [];
  let currentFile = null;
  if (!text || typeof text !== 'string') return files;
  const lines = text.split('\n');
  for (const line of lines) {
    const fileMatch = line.match(/^diff --git a\/(.+) b\/(.+)$/);
    if (fileMatch) {
      currentFile = { path: fileMatch[2], hunks: [], additions: 0, deletions: 0 };
      files.push(currentFile);
      continue;
    }
    const hunkMatch = line.match(/^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)?$/);
    if (hunkMatch && currentFile) {
      const hunk = {
        oldStart: +hunkMatch[1],
        oldLines: +(hunkMatch[2] || 1),
        newStart: +hunkMatch[3],
        newLines: +(hunkMatch[4] || 1),
        header: (hunkMatch[5] || '').trim(),
        lines: []
      };
      currentFile.hunks.push(hunk);
      continue;
    }
    if (currentFile && currentFile.hunks.length > 0) {
      const hunk = currentFile.hunks[currentFile.hunks.length - 1];
      if (line.startsWith('+++ ') || line.startsWith('--- ')) continue;
      if (line.startsWith('\\ No newline')) continue;
      if (line.startsWith('+')) { hunk.lines.push({ type: 'add', text: line.slice(1) }); currentFile.additions++; }
      else if (line.startsWith('-')) { hunk.lines.push({ type: 'del', text: line.slice(1) }); currentFile.deletions++; }
      else if (line.startsWith(' ')) { hunk.lines.push({ type: 'ctx', text: line.slice(1) }); }
    }
  }
  return files;
}

function renderDiff(files) {
  if (!files || files.length === 0) return '';
  let html = '';
  for (const f of files) {
    html += '<div class="diff-file">';
    html += '<div class="diff-file-header"><span>📝 ' + escapeHtml(f.path) + '</span><span class="diff-summary">+' + f.additions + ' -' + f.deletions + '</span></div>';
    for (const hunk of f.hunks) {
      html += '<div class="diff-hunk-header">@@ -' + hunk.oldStart + ',' + hunk.oldLines + ' +' + hunk.newStart + ',' + hunk.newLines + ' @@' + (hunk.header ? ' ' + escapeHtml(hunk.header) : '') + '</div>';
      for (const line of hunk.lines) {
        const cls = line.type === 'add' ? 'diff-add' : (line.type === 'del' ? 'diff-del' : 'diff-ctx');
        const prefix = line.type === 'add' ? '+' : (line.type === 'del' ? '-' : ' ');
        html += '<div class="diff-line ' + cls + '"><span class="diff-prefix">' + prefix + '</span>' + escapeHtml(line.text) + '</div>';
      }
    }
    html += '</div>';
  }
  if (files.length > 1) {
    const totalAdd = files.reduce((s, f) => s + f.additions, 0);
    const totalDel = files.reduce((s, f) => s + f.deletions, 0);
    html = '<div class="diff-global-summary">' + files.length + ' 个文件变更，+' + totalAdd + ' -' + totalDel + '</div>' + html;
  }
  return html;
}

async function terminalStream(url, msgs, sid, isExecute) {
  const terminal = getTerminal();
  streaming = true;
  showCancel(true);
  if (isExecute) execSendBtn.classList.add('loading');
  else sendBtn.classList.add('loading');
  abortController = new AbortController();

  let fullContent = '';
  let costInfo = null;
  const toolEntries = [];
  let outputLine = null;

  function ensureOutputLine() {
    if (outputLine && outputLine.isConnected) return outputLine;
    const line = document.createElement('div');
    line.className = 'terminal-line terminal-output-text';
    line.innerHTML = '<span class="terminal-cursor"></span>';
    terminal.appendChild(line);
    outputLine = line;
    return line;
  }

  function appendOutput(text) {
    const line = ensureOutputLine();
    const cursor = line.querySelector('.terminal-cursor');
    const textNode = document.createTextNode(text);
    line.insertBefore(textNode, cursor);
    fullContent += text;
    terminalScrollToBottom();
  }

  function removeCursor() {
    if (outputLine && outputLine.isConnected) {
      const c = outputLine.querySelector('.terminal-cursor');
      if (c) c.remove();
    }
  }

  function appendToolHeader(name, inputObj) {
    removeCursor();
    const header = document.createElement('div');
    header.className = 'terminal-tool-header';
    header.dataset.toolName = name;
    header.innerHTML = '<span class="terminal-timestamp">' + terminalNow() + '</span><span class="tool-icon">' + toolIcon(name) + '</span><span class="tool-name">' + escapeHtml(name) + '</span><span class="tool-status running">running...</span>';
    const body = document.createElement('div');
    body.className = 'terminal-tool-body';
    const pre = document.createElement('pre');
    pre.textContent = JSON.stringify(inputObj, null, 2);
    body.appendChild(pre);
    terminal.appendChild(header);
    terminal.appendChild(body);
    toolEntries.push({ name: name, header: header, body: body });
    terminalScrollToBottom();
  }

  function appendToolResult(content) {
    removeCursor();
    if (!toolEntries.length) return;
    const entry = toolEntries[toolEntries.length - 1];
    const status = entry.header.querySelector('.tool-status');
    if (status) { status.classList.remove('running'); status.textContent = '✓ done'; }
    const text = typeof content === 'string' ? content : JSON.stringify(content, null, 2);
    const files = parseDiff(text);
    if (files.length > 0) {
      const wrapper = document.createElement('div');
      wrapper.innerHTML = renderDiff(files);
      entry.body.appendChild(wrapper);
    } else {
      const pre = document.createElement('pre');
      pre.textContent = text;
      entry.body.appendChild(pre);
    }
    terminalScrollToBottom();
  }

  try {
    const resp = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: AUTH },
      body: JSON.stringify({ messages: msgs, session_id: sid, model: 'flash', project: currentProject, timeout: 120 }),
      signal: abortController.signal,
    });
    if (!resp.ok) {
      const errText = resp.status === 429 ? '前一个执行中，请稍候' : resp.status === 400 ? '危险指令已被拦截' : '请求失败: HTTP ' + resp.status;
      appendTerminalInfo('✗ ' + errText);
      execMessages.push({ role: 'assistant', content: errText, mode: 'execute' });
      return;
    }

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
            appendOutput(data.content);
          } else if (data.type === 'tool_use') {
            appendToolHeader(data.name || 'tool', data.input || {});
          } else if (data.type === 'tool_result') {
            appendToolResult(data.content);
          } else if (data.type === 'cost') {
            costInfo = data;
          } else if (data.type === 'done') {
             if (data.session_id) execSessionId = data.session_id;
           } else if (data.type === 'error') {
             removeCursor();
             appendTerminalInfo('✗ ' + data.content);
              fullContent += (fullContent ? '\n' : '') + data.content;
            }
          } catch(e) {}
        }
      }
    } catch(e) {
     if (costInfo) {
      appendTerminalSeparator();
      const info = document.createElement('div');
      info.className = 'terminal-line';
      const span = document.createElement('span');
      span.className = 'terminal-info';
      span.textContent = 'ⓘ Tokens: ' + (costInfo.tokens || 0) + ' · $' + (costInfo.usd || 0).toFixed(4);
      info.appendChild(span);
      terminal.appendChild(info);
    }

    if (fullContent) {
      execMessages.push({ role: 'assistant', content: fullContent, mode: 'execute' });
    }
  } catch(e) {
    if (e.name !== 'AbortError') {
      removeCursor();
      appendTerminalInfo('✗ 网络错误: ' + e.message);
    }
  }
  streaming = false;
  showCancel(false);
  sendBtn.classList.remove('loading');
  execSendBtn.classList.remove('loading');
  abortController = null;
  terminalScrollToBottom();
}

function resetTerminal() {
  const t = getTerminal();
  if (!t) return;
  t.innerHTML = '';
  const line1 = document.createElement('div');
  line1.className = 'terminal-line';
  const info1 = document.createElement('span');
  info1.className = 'terminal-info';
  info1.textContent = ' CCC Execute Terminal';
  line1.appendChild(info1);
  t.appendChild(line1);
  const line2 = document.createElement('div');
  line2.className = 'terminal-line';
  const info2 = document.createElement('span');
  info2.className = 'terminal-info';
  info2.textContent = ' 输入指令开始执行...';
  line2.appendChild(info2);
  t.appendChild(line2);
}

function renderTerminalHistory(messages) {
  const t = getTerminal();
  if (!t) return;
  resetTerminal();
  for (const msg of messages) {
    if (msg.role === 'user') {
      renderTerminalCommand(msg.content || '');
    } else if (msg.role === 'assistant') {
      const text = msg.content || '';
      const results = msg.execution_results || [];
      const partial = msg.partial || false;

      if (results && results.length > 0) {
        // Restore tool headers and results
        appendTerminalSeparator();
        for (const r of results) {
          appendTerminalInfo('⚡ ' + (r.tool || 'tool'));
          const body = document.createElement('div');
          body.className = 'terminal-tool-body';
          const pre = document.createElement('pre');
          pre.textContent = JSON.stringify(r.input || {}, null, 2);
          body.appendChild(pre);
          if (r.result) {
            const files = parseDiff(r.result);
            if (files.length > 0) {
              const wrapper = document.createElement('div');
              wrapper.innerHTML = renderDiff(files);
              body.appendChild(wrapper);
            } else {
              const resultPre = document.createElement('pre');
              resultPre.textContent = r.result;
              body.appendChild(resultPre);
            }
          }
          t.appendChild(body);
          appendTerminalSeparator();
        }
      }

      if (text) {
        const files = parseDiff(text);
        if (files.length > 0) {
          const wrapper = document.createElement('div');
          wrapper.innerHTML = renderDiff(files);
          t.appendChild(wrapper);
        } else {
          const line = document.createElement('div');
          line.className = 'terminal-line terminal-output-text';
          if (partial) {
            const partialTag = document.createElement('span');
            partialTag.className = 'terminal-info';
            partialTag.textContent = ' [部分结果 — 用户中断] ';
            line.appendChild(partialTag);
          }
          const textSpan = document.createElement('span');
          textSpan.textContent = text;
          line.appendChild(textSpan);
          t.appendChild(line);
        }
      }
    }
  }
  terminalScrollToBottom();
}

async function sendExecute() {
  const text = execInput.value.trim();
  if (!text || streaming) return;
  if (checkDangerous(text)) return;
  execInput.value = '';
  execInput.style.height = 'auto';
  execSendBtn.disabled = true;
  execMessages.push({ role: 'user', content: text, mode: 'execute' });
  renderTerminalCommand(text);
  await terminalStream('/api/execute', execMessages, execSessionId, true);
  setTimeout(() => loadHistory(), 300);
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

    const now = ts();
    const msgDiv = document.createElement('div');
    msgDiv.className = 'msg assistant' + (isExecute ? ' execute' : '');
    if (isExecute) {
      msgDiv.innerHTML = '<div class="bubble-wrap"><span class="exec-icon">⚡</span><div class="bubble"></div></div>';
    } else {
      msgDiv.innerHTML = '<div class="bubble"></div>';
    }
    const bubble = isExecute ? msgDiv.querySelector('.bubble') : msgDiv.querySelector('.bubble');
    const tsEl = document.createElement('div');
    tsEl.className = 'ts';
    tsEl.textContent = now;
    msgDiv.appendChild(tsEl);
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
            if (chatAutoScroll) scrollToBottom(container);
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

function ts() {
  const d = new Date();
  return String(d.getHours()).padStart(2,'0') + ':' + String(d.getMinutes()).padStart(2,'0');
}
function renderMessage(container, role, content, isExecute) {
  const div = document.createElement('div');
  div.className = 'msg ' + role + (isExecute && role === 'assistant' ? ' execute' : '');
  if (isExecute && role === 'assistant') {
    div.innerHTML = '<div class="bubble-wrap"><span class="exec-icon">⚡</span><div class="bubble">' + renderMarkdown(content) + '</div></div><div class="ts">' + ts() + '</div>';
  } else {
    const bubble = document.createElement('div');
    bubble.className = 'bubble';
    bubble.innerHTML = renderMarkdown(content);
    div.appendChild(bubble);
    const tsEl = document.createElement('div');
    tsEl.className = 'ts';
    tsEl.textContent = ts();
    div.appendChild(tsEl);
  }
  // Double-click on user message to edit
  if (role === 'user') {
    div.style.cursor = 'pointer';
    div.title = '双击编辑';
    div.addEventListener('dblclick', function(ev) {
      if (ev.target.closest('.edit-textarea, .edit-actions, button')) return;
      editMessage(this, container);
    });
  }
  container.appendChild(div);
  scrollToBottom(container);
}

function editMessage(msgEl, container) {
  const bubble = msgEl.querySelector('.bubble');
  if (!bubble) return;
  const currentText = bubble.textContent || '';
  // Replace bubble content with edit area
  const safeText = escapeHtml(currentText).replace(/'/g, "\\'");
  bubble.innerHTML = '<div class="edit-area"><textarea class="edit-textarea">' + safeText + '</textarea><div class="edit-actions"><button class="edit-save" onclick="saveEdit(this)">保存</button><button class="edit-cancel" onclick="cancelEdit(this)">取消</button></div></div>';
  const textarea = bubble.querySelector('.edit-textarea');
  textarea.dataset.original = currentText;
  textarea.focus();
  textarea.setSelectionRange(textarea.value.length, textarea.value.length);
}

function saveEdit(btn) {
  const editArea = btn.closest('.edit-area');
  const textarea = editArea.querySelector('.edit-textarea');
  const newText = textarea.value.trim();
  const originalText = textarea.dataset.original || '';
  if (!newText || newText === originalText) {
    cancelEditInternal(editArea, originalText);
    return;
  }
  // Find the message element and all following messages
  const msgEl = btn.closest('.msg');
  if (!msgEl) return;
  // Find which messages container this belongs to
  const container = msgEl.closest('#messages, #exec-messages, #exec-terminal') || document.getElementById('messages');
  const siblings = [];
  let next = msgEl.nextElementSibling;
  while (next) {
    if (next.classList.contains('msg') && !next.classList.contains('typing')) {
      siblings.push(next);
    }
    next = next.nextElementSibling;
  }
  // Remove all following messages (the old response chain)
  siblings.forEach(s => s.remove());
  // Restore bubble content
  const bubble = msgEl.querySelector('.bubble');
  if (bubble) bubble.innerHTML = renderMarkdown(newText);
  // Update messages array
  const idx = currentMessages.findIndex(m => m.role === 'user');
  if (idx !== -1) {
    currentMessages = currentMessages.slice(0, idx + 1);
    currentMessages[idx].content = newText;
  }
  // Re-send
  input.value = newText;
  sendChat();
}

function cancelEdit(btn) {
  const editArea = btn.closest('.edit-area');
  const textarea = editArea ? editArea.querySelector('.edit-textarea') : null;
  const originalText = textarea ? (textarea.dataset.original || '') : '';
  cancelEditInternal(editArea, originalText);
}

function cancelEditInternal(editArea, originalText) {
  if (!editArea) return;
  const bubble = editArea.closest('.bubble');
  if (bubble) bubble.innerHTML = renderMarkdown(originalText || '');
}

function renderMarkdown(text) {
  if (!text) return '';
  // --- Step 1: guard code blocks ---
  const codeBlocks = [];
  let h = escapeHtml(text);
  h = h.replace(/```(\w*)\n?([\s\S]*?)```/g, (_, lang, code) => {
    const idx = codeBlocks.length;
    codeBlocks.push('<div class="code-block-wrap"><pre><code class="lang-' + lang + '">' + code + '</code></pre><button class="copy-btn" onclick="copyCode(this)">复制</button></div>');
    return '\x00CODE' + idx + '\x00';
  });
  // Guard inline code (must be after code blocks to avoid double-escape)
  const inlineCodes = [];
  h = h.replace(/`([^`]+)`/g, (_, c) => {
    const idx = inlineCodes.length;
    inlineCodes.push('<code>' + c + '</code>');
    return '\x00ICODE' + idx + '\x00';
  });

  // --- Step 2: block-level transforms ---
  const lines = h.split('\n');
  const out = [];
  let inTable = false;
  let inList = false;
  let listType = null;

  function closeList() {
    if (inList) { out.push(listType === 'ol' ? '</ol>' : '</ul>'); inList = false; listType = null; }
  }

  for (let i = 0; i < lines.length; i++) {
    const raw = lines[i];
    const line = raw.trimEnd();

    // Horizontal rule
    if (/^[-*_]{3,}\s*$/.test(line.trim())) { closeList(); inTable = false; out.push('<hr>'); continue; }

    // Headers
    const h1Match = line.match(/^# (.+)$/);
    if (h1Match) { closeList(); inTable = false; out.push('<h1>' + h1Match[1] + '</h1>'); continue; }
    const h2Match = line.match(/^## (.+)$/);
    if (h2Match) { closeList(); inTable = false; out.push('<h2>' + h2Match[1] + '</h2>'); continue; }
    const h3Match = line.match(/^### (.+)$/);
    if (h3Match) { closeList(); inTable = false; out.push('<h3>' + h3Match[1] + '</h3>'); continue; }
    const h4Match = line.match(/^#### (.+)$/);
    if (h4Match) { closeList(); inTable = false; out.push('<h4>' + h4Match[1] + '</h4>'); continue; }

    // Blockquote
    const bqMatch = line.match(/^> ?(.+)$/);
    if (bqMatch) { closeList(); inTable = false; out.push('<blockquote>' + bqMatch[1] + '</blockquote>'); continue; }

    // Unordered list
    const ulMatch = line.match(/^[-*+] (.+)$/);
    if (ulMatch) {
      if (!inList || listType !== 'ul') { closeList(); out.push('<ul>'); inList = true; listType = 'ul'; }
      out.push('<li>' + ulMatch[1] + '</li>');
      continue;
    }

    // Ordered list
    const olMatch = line.match(/^\d+\.\s+(.+)$/);
    if (olMatch) {
      if (!inList || listType !== 'ol') { closeList(); out.push('<ol>'); inList = true; listType = 'ol'; }
      out.push('<li>' + olMatch[1] + '</li>');
      continue;
    }

    // Table — detect header row
    if (line.includes('|')) {
      const cells = line.split('|').filter(Boolean);
      if (!inTable && i + 1 < lines.length && /^[\s|:-]+$/.test(lines[i+1].trim())) {
        // This is a table header
        closeList();
        out.push('<table><thead><tr>' + cells.map(c => '<th>' + c.trim() + '</th>').join('') + '</tr></thead><tbody>');
        inTable = true;
        i++; // skip separator row
        continue;
      } else if (inTable && cells.length > 1) {
        out.push('<tr>' + cells.map(c => '<td>' + c.trim() + '</td>').join('') + '</tr>');
        continue;
      }
    } else if (inTable) {
      out.push('</tbody></table>');
      inTable = false;
    }

    closeList();

    // Empty line = paragraph break
    if (line.trim() === '') { out.push('</p><p>'); continue; }

    // Regular paragraph line
    out.push(line);
  }
  closeList();
  if (inTable) out.push('</tbody></table>');

  h = out.join('\n');

  // Wrap consecutive non-tag lines in <p>
  h = h.replace(/^(?!<[a-z/]|$)(.+)$/gm, '<p>$1</p>');
  // Fix double paragraph from empty lines
  h = h.replace(/<\/p>\s*<p><\/p>/g, '</p><p>');

  // --- Step 3: inline transforms ---
  // Links (must come before other inline transforms to avoid escaping URL)
  h = h.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
  // Images
  h = h.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img src="$2" alt="$1" style="max-width:100%;border-radius:8px;margin:8px 0;">');
  // Bold
  h = h.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  // Italic
  h = h.replace(/(?<!\*)\*([^*]+)\*(?!\*)/g, '<em>$1</em>');
  // Inline code
  h = h.replace(/\x00ICODE(\d+)\x00/g, (_, i) => inlineCodes[parseInt(i)] || '');
  // Code blocks (last, to protect content)
  h = h.replace(/\x00CODE(\d+)\x00/g, (_, i) => codeBlocks[parseInt(i)] || '');

  // Clean up empty paragraphs
  h = h.replace(/<p><\/p>/g, '');
  h = h.replace(/<p>\s*<\/p>/g, '');

  return h;
}

function copyCode(btn) {
  const pre = btn.closest('.code-block-wrap').querySelector('pre');
  const code = pre ? (pre.textContent || pre.innerText) : '';
  navigator.clipboard.writeText(code).then(() => {
    const orig = btn.textContent;
    btn.textContent = '已复制';
    setTimeout(() => btn.textContent = orig, 1500);
  }).catch(() => {
    btn.textContent = '复制失败';
  });
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

(function setupSidebarSwipe() {
  const sidebar = document.getElementById('sidebar');
  let startY = 0;
  sidebar.addEventListener('touchstart', (e) => {
    if (e.touches.length === 1) startY = e.touches[0].clientY;
  }, {passive:true});
  sidebar.addEventListener('touchmove', (e) => {
    if (e.touches.length !== 1 || !startY) return;
    const dy = e.touches[0].clientY - startY;
    if (dy > 80) {
      startY = 0;
      if (sidebar.classList.contains('open')) toggleSidebar();
    }
  }, {passive:true});
})();

async function loadHistory() {
  const list = document.getElementById('sessionList');
  if (list) {
    list.innerHTML = '<div class="skeleton skeleton-card"></div><div class="skeleton skeleton-card"></div><div class="skeleton skeleton-card"></div>';
  }
  try {
    const resp = await fetch('/api/history?project=' + encodeURIComponent(currentProject), { headers: { Authorization: AUTH } });
    const data = await resp.json();
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
    const resp = await fetch('/api/history/' + id + '?project=' + encodeURIComponent(currentProject), { headers: { Authorization: AUTH } });
    const data = await resp.json();
    const isExec = mode === 'execute' || data.mode === 'execute';
    if (isExec) {
      switchTab('execute');
      execSessionId = data.session_id;
      execMessages = data.messages || [];
      // Attach execution_results to the last assistant message for rich replay
      if (data.execution_results && execMessages.length > 0) {
        const last = execMessages[execMessages.length - 1];
        if (last.role === 'assistant') {
          last.execution_results = data.execution_results;
        }
      }
      execMessagesEl.innerHTML = '';
      renderTerminalHistory(execMessages);
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
  resetTerminal();
  execInput.value = '';
  execSendBtn.disabled = true;
}

async function loadBoard() {
  const scroll = document.getElementById('board-scroll');
  const offline = document.getElementById('board-offline');
  scroll.innerHTML = '';
  offline.style.display = 'none';
  const ws = PROJECT_WORKSPACE[currentProject] || currentProject;
  try {
    const resp = await fetch('/api/board/proxy/board?workspace=' + encodeURIComponent(ws), { headers: { Authorization: AUTH } });
    if (resp.status === 503) {
      offline.style.display = 'block';
      return;
    }
    const data = await resp.json();
    const columns = data.columns || {};
    for (const col of ['backlog','planned','in_progress','testing','verified','released','abnormal']) {
      const colEl = document.createElement('div');
      colEl.className = 'board-col';
      const tasks = columns[col] || [];
      colEl.innerHTML = '<div class="board-col-title">' + (COLUMN_LABELS[col]||col) + ' (' + tasks.length + ')</div><div class="board-col-cards"></div>';
      const cards = colEl.querySelector('.board-col-cards');
      for (const t of tasks) {
        const card = document.createElement('div');
        card.className = 'board-card';
        card.innerHTML = '<div class="title">' + escapeHtml(t.title || t.id) + '</div><div class="time">' + escapeHtml(t.updated_at || t.created_at || '') + '</div>';
        cards.appendChild(card);
      }
      scroll.appendChild(colEl);
    }
    const indicator = document.getElementById('board-scroll-indicator');
    if (indicator) {
      const colCount = ['backlog','planned','in_progress','testing','verified','released','abnormal'].length;
      indicator.innerHTML = '';
      if (window.innerWidth <= 768) {
        for (let i = 0; i < colCount; i++) {
          const dot = document.createElement('span');
          dot.style.cssText = 'width:6px;height:6px;border-radius:50%;background:var(--border);display:inline-block;transition:background 0.2s;';
          if (i === 0) dot.style.background = 'var(--accent)';
          indicator.appendChild(dot);
        }
        let ticking = false;
        scroll.addEventListener('scroll', () => {
          if (!ticking) {
            requestAnimationFrame(() => {
              const scrollLeft = scroll.scrollLeft;
              const colW = scroll.clientWidth;
              const idx = Math.round(scrollLeft / colW);
              const dots = indicator.querySelectorAll('span');
              dots.forEach((d, i) => { d.style.background = i === idx ? 'var(--accent)' : 'var(--border)'; });
              ticking = false;
            });
            ticking = true;
          }
        });
      }
    }
  } catch(e) {
    offline.style.display = 'block';
  }
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
    global PORT
    import argparse

    parser = argparse.ArgumentParser(description="CCC Chat Server")
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("CCC_CHAT_PORT", PORT)),
        help=f"绑定端口 (默认 {PORT}, 也可由 CCC_CHAT_PORT 环境变量覆盖)",
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("CCC_CHAT_HOST", HOST),
        help=f"绑定地址 (默认 {HOST})",
    )
    parser.add_argument(
        "--no-open",
        action="store_true",
        default=os.environ.get("CCC_CHAT_NO_OPEN", "0") == "1",
        help="启动后不自动打开浏览器 (sidecar 模式)",
    )
    args = parser.parse_args()
    PORT = args.port
    bind_host = args.host

    print("  CCC Chat Server v0.29.0")
    print("  ─────────────────────")
    print(f"  地址: http://{bind_host}:{PORT}")
    print(f"  本地: http://localhost:{PORT}")
    print(f"  账号: {AUTH_USER} / {AUTH_PASS}")
    print(f"  历史: {CHAT_DIR}/{{project}}/")
    if args.no_open:
        print("  浏览器: 关闭 (--no-open)")
    print()

    if not args.no_open and bind_host in ("0.0.0.0", "127.0.0.1", "localhost"):
        import threading
        import webbrowser

        def _open():
            try:
                webbrowser.open(f"http://localhost:{PORT}")
            except Exception as exc:
                print(f"  WARN: 自动打开浏览器失败: {exc}")

        threading.Timer(1.2, _open).start()

    uvicorn.run(app, host=bind_host, port=PORT, log_level="info")


if __name__ == "__main__":
    main()
