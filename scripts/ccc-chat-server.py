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

# ---------- Projects: dynamic from board server, fallback to static ----------
PROJECTS: dict[str, dict] = {}
PROJECT_TO_WORKSPACE: dict[str, str] = {}

_PROJECTS_FALLBACK = {
    "ccc": {"name": "CCC", "path": str(Path(__file__).resolve().parent.parent)},
}

_log = logging.getLogger("ccc-chat")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def _reload_projects():
    """Fetch workspace list from Board Server and rebuild PROJECTS dict."""
    global PROJECTS, PROJECT_TO_WORKSPACE
    new_projects = {}
    new_mapping = {}
    try:
        import httpx
        resp = httpx.get(f"{BOARD_URL}/api/board", timeout=3.0)
        if resp.status_code == 200:
            data = resp.json()
            workspaces = data.get("workspaces", {})
            for ws_id, ws_path in workspaces.items():
                # Skip internal/system workspaces
                if ws_id.startswith("."):
                    continue
                # Build a human-readable name from the ID
                name_map = {
                    "CCC": "CCC",
                    "qxo": "QXO Observer",
                    "xianyu": "xianyu",
                    "qb": "qb Dashboard",
                    "qx": "qx",
                }
                name = name_map.get(ws_id, ws_id.capitalize())
                pid = ws_id.lower().replace(" ", "-")
                new_projects[pid] = {"name": name, "path": ws_path}
                new_mapping[pid] = ws_id
    except Exception as exc:
        _log.warning("Board server unreachable, using fallback projects: %s", exc)

    if not new_projects:
        _log.info("Using fallback project list")
        new_projects.update(_PROJECTS_FALLBACK)

    PROJECTS = new_projects
    PROJECT_TO_WORKSPACE = new_mapping


# Initial load at module import
_reload_projects()

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
    timeout = int(body.get("timeout", 180))

    user_msgs = [m for m in messages if m.get("role") == "user"]
    if not user_msgs:
        raise HTTPException(status_code=400, detail="messages required")
    prompt = user_msgs[-1].get("content", "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="prompt required")
    if check_dangerous_command(prompt):
        raise HTTPException(status_code=400, detail="危险指令已被拦截")

    project_path = _project_path(project)

    # Inject project context into the prompt
    context = _get_project_context(project)
    if context:
        prompt = (
            f"## 项目上下文\n{context}\n\n---\n\n## 用户问题\n{prompt}"
        )

    async def generate():
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
                    yield f"data: {json.dumps({'type': 'error', 'content': '响应超时（180s），请重试'})}\n\n"
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
            raise
        finally:
            if proc and proc.returncode is None:
                proc.kill()
            if full_content:
                chat_messages = [m for m in messages if m.get("role") != "system"]
                for m in chat_messages:
                    m.setdefault("mode", "chat")
                chat_messages.append(
                    {
                        "role": "assistant",
                        "content": full_content,
                        "mode": "chat",
                        "execution_results": execution_results,
                        "partial": not stream_completed,
                    }
                )
                _save_session(
                    session_id,
                    chat_messages,
                    project=project,
                    mode="chat",
                    execution_results=execution_results,
                    total_cost_usd=total_cost_usd,
                )

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.post("/api/execute")
async def execute_mode(request: Request):
    """Alias for /api/chat — merged single-channel."""
    return await chat(request)


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
  #app, #header, #sidebar, #input-area, .bubble,
  .tool-card, #input-wrap, .session-item {
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
  #chat-panel { display:flex; flex:1; flex-direction:column; overflow:hidden; }

  #messages {
    flex:1; overflow-y:auto; padding:16px; padding-bottom:8px;
    -webkit-overflow-scrolling:touch;
  }
  .msg { margin-bottom:8px; display:flex; flex-direction:column; }
  .msg.user { align-items:flex-end; }
  .msg.assistant { align-items:flex-start; }
  .msg .bubble {
    max-width:85%; padding:12px 16px; border-radius:var(--radius);
    line-height:1.5; font-size:15px; word-wrap:break-word;
    box-shadow:var(--shadow);
  }
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
    #messages { padding:10px 12px; }
    #input-area { padding:8px 12px; }
    .msg .bubble { max-width:90%; font-size:14px; }
  }
  @media(max-width:375px) {
    #header { padding:8px 10px; }
    #messages { padding:8px 10px; }
    #input-area { padding:6px 10px; }
    .msg .bubble { max-width:92%; }
    #header h1 { display:none; }
    #project-select { width:100px; }


  .file-item:hover { background:var(--code-bg); }
  .file-item.dir { font-weight:500; }
  .file-item .icon { width:16px; text-align:center; flex-shrink:0; font-family:monospace; }
  .file-item .name { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; flex:1; }
  .file-item .meta { font-size:10px; color:var(--text-secondary); flex-shrink:0; margin-left:4px; }
  .file-item .children { width:100%; }
  .file-item.collapsed > .icon::before { content:"▶"; }
  .file-item.dir:not(.collapsed) > .icon::before { content:"▼"; }

  @media(max-width:768px) {

  }

  }

  }


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

  <div id="chat-panel">
    <div id="messages"></div>
    <button id="scroll-bottom-fab-chat" class="scroll-bottom-fab" onclick="scrollFabToBottom('chat')">↓</button>
    <div id="input-area">
      <div id="input-wrap">
        <textarea id="input" rows="1" placeholder="输入消息..." onkeydown="onKey(event,'chat')"></textarea>
        <button id="send" onclick="sendChat()" disabled>↑</button>
        <button id="cancel-btn" onclick="cancelStream()">取消</button>
      </div>
    </div>
  </div>
</div>

<div id="overlay" onclick="toggleSidebar()"></div>
<div id="sidebar">
  <div class="sidebar-handle"></div>
  <h2>对话历史</h2>
  <div id="sessionList"></div>
</div>


<script>
const AUTH = 'Basic ' + btoa('ccc:claude2026');

let sessionId = crypto.randomUUID?.() ?? Date.now().toString(36)+Math.random().toString(36).slice(2);
let currentMessages = [];
let streaming = false;
let chatAutoScroll = true;
let currentProject = 'ccc';
let abortController = null;

const input = document.getElementById('input');
const sendBtn = document.getElementById('send');
const messagesEl = document.getElementById('messages');

function setupInput(el, btn) {
  el.addEventListener('input', () => {
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 120) + 'px';
    btn.disabled = !el.value.trim();
  });
}
setupInput(input, sendBtn);

messagesEl.addEventListener('scroll', () => {
  chatAutoScroll = messagesEl.scrollTop + messagesEl.clientHeight >= messagesEl.scrollHeight - 80;
});

const scrollFabChat = document.getElementById('scroll-bottom-fab-chat');
function updateFab(container, fab) {
  if (!container || !fab) return;
  const threshold = 200;
  const atBottom = container.scrollTop + container.clientHeight >= container.scrollHeight - threshold;
  const isMobile = window.innerWidth <= 768;
  fab.classList.toggle('show', !atBottom && isMobile);
}
function scrollFabToBottom() {
  if (messagesEl) { messagesEl.scrollTop = messagesEl.scrollHeight; }
  if (scrollFabChat) scrollFabChat.classList.remove('show');
}
messagesEl.addEventListener('scroll', () => updateFab(messagesEl, scrollFabChat));
window.addEventListener('resize', () => { updateFab(messagesEl, scrollFabChat); });

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
        if (messagesEl) messagesEl.scrollTop = messagesEl.scrollHeight;
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
  loadHistory();
}






function showCancel(show) {
  document.getElementById('cancel-btn').style.display = show ? 'flex' : 'none';
  sendBtn.style.display = show ? 'none' : 'flex';
}

function cancelStream() {
  if (abortController) abortController.abort();
  streaming = false;
  showCancel(false);
  sendBtn.classList.remove('loading');
}

async function sendChat() {
  const text = input.value.trim();
  if (!text || streaming) return;
  input.value = '';
  input.style.height = 'auto';
  sendBtn.disabled = true;
  currentMessages.push({ role: 'user', content: text, mode: 'chat' });
  renderMessage(messagesEl, 'user', text);
  await streamRequest('/api/chat', currentMessages, sessionId, messagesEl);
  loadHistory();
}



async function streamRequest(url, msgs, sid, container) {
  const typingId = 'typing-' + Date.now();
  const typingEl = document.createElement('div');
  typingEl.className = 'msg assistant typing';
  typingEl.id = typingId;
  typingEl.innerHTML = '<div class="bubble"><span class="dot"></span><span class="dot"></span><span class="dot"></span></div>';
  container.appendChild(typingEl);
  scrollToBottom(container);

  streaming = true;
  showCancel(true);
  sendBtn.classList.add('loading');
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
      renderMessage(container, 'assistant', errText);
      currentMessages.push({ role: 'assistant', content: errText, mode: 'chat' });
      return;
    }
    removeTyping(typingId);

    const now = ts();
    const msgDiv = document.createElement('div');
    msgDiv.className = 'msg assistant';
    msgDiv.innerHTML = '<div class="bubble"></div>';
    const bubble = msgDiv.querySelector('.bubble');
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
            if (data.session_id) sessionId = data.session_id;
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
      costEl.textContent = 'Tokens: ' + (costInfo.tokens||0) + ' \u00b7 $' + (costInfo.usd||0).toFixed(4);
      msgDiv.appendChild(costEl);
    }

    currentMessages.push({ role: 'assistant', content: fullContent, mode: 'chat' });
  } catch(e) {
    if (e.name !== 'AbortError') {
      removeTyping(typingId);
      renderMessage(container, 'assistant', '\u7f51\u7edc\u9519\u8bef: ' + e.message);
    }
  }
  streaming = false;
  showCancel(false);
  sendBtn.classList.remove('loading');
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
    sendChat();
  }
}

function ts() {
  const d = new Date();
  return String(d.getHours()).padStart(2,'0') + ':' + String(d.getMinutes()).padStart(2,'0');
}
function renderMessage(container, role, content) {
  const div = document.createElement('div');
  div.className = 'msg ' + role;
  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  bubble.innerHTML = renderMarkdown(content);
  div.appendChild(bubble);
  const tsEl = document.createElement('div');
  tsEl.className = 'ts';
  tsEl.textContent = ts();
  div.appendChild(tsEl);
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
  const container = document.getElementById('messages');
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
  // --- Step 0: guard tool_call XML blocks (before HTML escaping) ---
  const toolCalls = [];
  text = text.replace(/<tool_call>[\s\S]*?<\/tool_call>/g, (match) => {
    const idx = toolCalls.length;
    toolCalls.push(match);
    return '\x00TOOLCALL' + idx + '\x00';
  });
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
  // Tool calls — render as collapsible cards
  h = h.replace(/\x00TOOLCALL(\d+)\x00/g, (_, i) => {
    const raw = toolCalls[parseInt(i)] || '';
    // Extract tool name and arguments
    const nameMatch = raw.match(/<tool_call>[\s\S]*?"name"\s*:\s*"([^"]+)"/);
    const argMatch = raw.match(/<tool_call>[\s\S]*?"arguments"\s*:\s*\{([^}]+)\}/);
    const name = nameMatch ? nameMatch[1] : 'tool';
    const args = argMatch ? '{' + argMatch[1] + '}' : raw.replace(/<\/?tool_call>/g, '').trim();
    return '<details class="tool-card" style="margin:8px 0"><summary style="padding:8px 12px;font-size:13px;font-weight:500;cursor:pointer;color:var(--accent);list-style:none;display:flex;align-items:center;gap:6px"><span>🛠</span> ' + escapeHtml(name) + '</summary><pre style="padding:8px 12px;font-size:12px;overflow-x:auto;border-top:1px solid var(--border);margin:0;white-space:pre-wrap">' + escapeHtml(args) + '</pre></details>';
  });
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
      item.onclick = () => loadSession(s.session_id);
      list.appendChild(item);
    }
  } catch(e) {}
}

async function loadSession(id, mode) {
  try {
    const resp = await fetch('/api/history/' + id + '?project=' + encodeURIComponent(currentProject), { headers: { Authorization: AUTH } });
    const data = await resp.json();
    sessionId = data.session_id;
    currentMessages = data.messages || [];
    messagesEl.innerHTML = '';
    for (const msg of currentMessages) renderMessage(messagesEl, msg.role, msg.content);
    if (data.reply && !currentMessages.some(m => m.role === 'assistant')) {
      renderMessage(messagesEl, 'assistant', data.reply);
      currentMessages.push({role:'assistant', content: data.reply, mode:'chat'});
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
