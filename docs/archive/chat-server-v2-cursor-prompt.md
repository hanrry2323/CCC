# CCC Chat Server v2 — Cursor 执行指令

> 一次性执行。每个 `FILE:` 块是完整文件内容，直接写入对应路径。
> 严格按顺序执行，不要跳过，不要省略。

---

## Step 0: 创建目录

```bash
cd /Users/apple/program/CCC
mkdir -p scripts/chat-server/routers
mkdir -p scripts/chat-server/services
mkdir -p scripts/chat-server/frontend/css
mkdir -p scripts/chat-server/frontend/js/components
```

---

## Step 1: 后端 — 基础模块

这些是 Python 文件，放在 `scripts/chat-server/` 下。

### FILE: scripts/chat-server/__init__.py

（空文件）

### FILE: scripts/chat-server/config.py

```python
import os
import re
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CHAT_DIR = PROJECT_ROOT / ".ccc" / "chat"
CHAT_DIR.mkdir(parents=True, exist_ok=True)

HOST = os.environ.get("CCC_CHAT_HOST", "0.0.0.0")
PORT = int(os.environ.get("CCC_CHAT_PORT", "8084"))
AUTH_USER = os.environ.get("CCC_CHAT_USER", "ccc")
AUTH_PASS = os.environ.get("CCC_CHAT_PASS", "claude2026")
BOARD_URL = os.environ.get("CCC_BOARD_URL", "http://127.0.0.1:7777")
BOARD_TOKEN = os.environ.get("QX_BOARD_TOKEN", "").strip()
PROXY_URL = os.environ.get("CCC_PROXY_URL", "http://127.0.0.1:4002/v1/chat/completions")

DANGEROUS_PATTERN = re.compile(
    r"(?i)\b(rm\s+-rf|rm\s+/|sudo\b|dd\s+if=|format\b|mkfs\b|>\s*/dev/)"
)

BOARD_COLUMNS = [
    "backlog", "planned", "in_progress",
    "testing", "verified", "released", "abnormal",
]

CLAUDE_BIN = shutil.which("claude") or "/Users/apple/.local/bin/claude"
CLAUDE_ENV = {
    **os.environ,
    "PATH": f"{os.environ.get('PATH', '')}:{os.path.dirname(CLAUDE_BIN)}"
}

_PROJECTS_FALLBACK = {
    "ccc": {"name": "CCC", "path": str(PROJECT_ROOT)},
}
```

### FILE: scripts/chat-server/models.py

```python
from pydantic import BaseModel
from typing import Any


class ChatRequest(BaseModel):
    messages: list[dict[str, Any]] = []
    session_id: str = ""
    model: str = "flash"
    project: str = "ccc"
    timeout: int = 180


class SessionData(BaseModel):
    session_id: str
    title: str = "New Chat"
    project: str = "ccc"
    messages: list[dict[str, Any]] = []
    mode: str = "chat"
    created_at: str = ""
    updated_at: str = ""
    status: str = ""
    reply: str = ""
    execution_results: list[dict[str, Any]] = []
    total_cost_usd: float | None = None
```

### FILE: scripts/chat-server/auth.py

```python
import base64
from fastapi import Request, HTTPException
from . import config


def check_auth(request: Request):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Basic "):
        raise HTTPException(
            status_code=401,
            headers={"WWW-Authenticate": 'Basic realm="CCC Chat"'},
        )
    try:
        decoded = base64.b64decode(auth[6:]).decode()
        user, passwd = decoded.split(":", 1)
    except Exception:
        raise HTTPException(status_code=401)
    if user != config.AUTH_USER or passwd != config.AUTH_PASS:
        raise HTTPException(status_code=401)
    return True


def board_headers() -> dict:
    headers = {"Content-Type": "application/json"}
    if config.BOARD_TOKEN:
        headers["Authorization"] = f"Bearer {config.BOARD_TOKEN}"
    return headers
```

---

## Step 2: 后端 — Services

### FILE: scripts/chat-server/services/__init__.py

（空文件）

### FILE: scripts/chat-server/services/session_store.py

```python
import json
import time
from pathlib import Path

from .. import config


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S+08:00")


def _project_chat_dir(project_id: str) -> Path:
    d = config.CHAT_DIR / project_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _session_path(session_id: str, project_id: str = "ccc") -> Path:
    return _project_chat_dir(project_id) / f"{session_id}.json"


def save_session(
    session_id: str,
    messages: list,
    reply: str = "",
    project: str = "ccc",
    mode: str = "chat",
    execution_results: list | None = None,
    total_cost_usd: float | None = None,
    status: str | None = None,
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
        "updated_at": now_iso(),
    }
    if status:
        data["status"] = status
    if path.exists():
        try:
            existing = json.loads(path.read_text())
            data["created_at"] = existing.get("created_at", now_iso())
        except (json.JSONDecodeError, OSError):
            data["created_at"] = now_iso()
    else:
        data["created_at"] = now_iso()
    if reply:
        data["reply"] = reply
    if execution_results is not None:
        data["execution_results"] = execution_results
    if total_cost_usd is not None:
        data["total_cost_usd"] = total_cost_usd
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def list_sessions(project: str = "ccc") -> list[dict]:
    chat_dir = _project_chat_dir(project)
    sessions = []
    for f in sorted(
        chat_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True
    ):
        try:
            data = json.loads(f.read_text())
            sessions.append({
                "session_id": data.get("session_id", f.stem),
                "title": str(data.get("title", "Unknown"))[:80],
                "updated_at": data.get("updated_at", ""),
                "mode": data.get("mode", "chat"),
            })
        except (json.JSONDecodeError, OSError):
            pass
    return sessions


def get_session(session_id: str, project: str = "ccc") -> dict | None:
    path = _session_path(session_id, project)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def delete_session(session_id: str, project: str = "ccc") -> bool:
    path = _session_path(session_id, project)
    if path.exists():
        path.unlink()
        return True
    return False
```

### FILE: scripts/chat-server/services/claude_client.py

```python
import asyncio
import json
import logging
from pathlib import Path

from .. import config

_log = logging.getLogger("ccc-chat")


def _get_project_context(project_id: str, projects: dict) -> str:
    proj = projects.get(project_id)
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


async def stream_chat(
    prompt: str,
    project_path: str,
    request_disconnected,
    timeout: int = 180,
):
    """Generator that yields SSE event dicts from Claude subprocess."""
    proc = None
    try:
        proc = await asyncio.create_subprocess_exec(
            config.CLAUDE_BIN,
            "-p",
            "--print",
            "--verbose",
            "--output-format",
            "stream-json",
            "--model",
            "flash",
            cwd=project_path,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**config.CLAUDE_ENV, "CLAUDE_PROJECT_DIR": project_path},
        )
        assert proc.stdin is not None
        proc.stdin.write(prompt.encode())
        await proc.stdin.drain()
        proc.stdin.close()

        async def _read_stderr():
            if proc.stderr:
                async for line in proc.stderr:
                    _log.warning("claude stderr: %s", line.decode(errors="replace").rstrip())

        stderr_task = asyncio.create_task(_read_stderr())

        deadline = asyncio.get_event_loop().time() + timeout
        buffer = b""

        while True:
            if request_disconnected():
                proc.kill()
                break
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                proc.kill()
                yield {"type": "error", "content": "响应超时（180s），请重试"}
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
                                yield {"type": "delta", "content": text}
                        elif btype == "tool_use":
                            yield {
                                "type": "tool_use",
                                "name": block.get("name", "tool"),
                                "input": block.get("input", {}),
                            }
                elif evt_type == "user":
                    msg = event.get("message", {})
                    for block in msg.get("content", []):
                        if block.get("type") == "tool_result":
                            yield {
                                "type": "tool_result",
                                "content": block.get("content", ""),
                            }
                elif evt_type == "result":
                    yield {
                        "type": "cost",
                        "tokens": (
                            (event.get("usage", {}).get("input_tokens", 0) or 0)
                            + (event.get("usage", {}).get("output_tokens", 0) or 0)
                        ),
                        "usd": event.get("total_cost_usd", 0) or 0,
                    }
                    result_text = event.get("result", "")
                    if result_text:
                        yield {"type": "delta", "content": result_text}

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

        yield {"type": "done", "session_id": ""}

    except (GeneratorExit, asyncio.CancelledError):
        raise
    finally:
        if proc and proc.returncode is None:
            proc.kill()
```

### FILE: scripts/chat-server/services/board_client.py

```python
import json

import httpx
from fastapi.responses import Response

from .. import config
from ..auth import board_headers


async def board_proxy(method: str, path: str, params: dict | None = None, json_body: dict | None = None):
    url = f"{config.BOARD_URL}{path}"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            if method == "GET":
                resp = await client.get(url, params=params, headers=board_headers())
            else:
                resp = await client.post(url, json=json_body, headers=board_headers())
            return Response(
                content=resp.content,
                status_code=resp.status_code,
                media_type="application/json",
            )
    except (httpx.ConnectError, httpx.TimeoutException):
        return Response(
            content=json.dumps({"error": "看板服务离线", "detail": "Board Server 不可用"}),
            status_code=503,
            media_type="application/json",
        )
```

---

## Step 3: 后端 — Routers

### FILE: scripts/chat-server/routers/__init__.py

（空文件）

### FILE: scripts/chat-server/routers/projects.py

```python
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ..auth import check_auth
from .. import config

router = APIRouter()

PROJECTS: dict[str, dict] = {}
PROJECT_TO_WORKSPACE: dict[str, str] = {}


def reload_projects():
    global PROJECTS, PROJECT_TO_WORKSPACE
    new_projects = {}
    new_mapping = {}
    try:
        import httpx
        resp = httpx.get(f"{config.BOARD_URL}/api/board", timeout=3.0)
        if resp.status_code == 200:
            data = resp.json()
            workspaces = data.get("workspaces", {})
            name_map = {
                "CCC": "CCC", "qxo": "QXO Observer",
                "xianyu": "xianyu", "qb": "qb Dashboard", "qx": "qx",
            }
            for ws_id, ws_path in workspaces.items():
                if ws_id.startswith("."):
                    continue
                name = name_map.get(ws_id, ws_id.capitalize())
                pid = ws_id.lower().replace(" ", "-")
                new_projects[pid] = {"name": name, "path": ws_path}
                new_mapping[pid] = ws_id
    except Exception as exc:
        import logging
        logging.getLogger("ccc-chat").warning("Board unreachable: %s", exc)

    if not new_projects:
        new_projects.update(config._PROJECTS_FALLBACK)

    PROJECTS.clear()
    PROJECTS.update(new_projects)
    PROJECT_TO_WORKSPACE.clear()
    PROJECT_TO_WORKSPACE.update(new_mapping)


reload_projects()


def get_project_path(project_id: str) -> str:
    proj = PROJECTS.get(project_id)
    if not proj:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"unknown project: {project_id}")
    return proj["path"]


@router.get("/api/projects")
async def list_projects(request: Request):
    check_auth(request)
    return {
        "projects": [
            {"id": pid, "name": info["name"], "path": info["path"]}
            for pid, info in PROJECTS.items()
        ]
    }
```

### FILE: scripts/chat-server/routers/sessions.py

```python
import uuid
from fastapi import APIRouter, Request, HTTPException

from ..auth import check_auth
from ..services import session_store as store

router = APIRouter()


@router.get("/api/history")
async def list_sessions(request: Request, project: str = "ccc"):
    check_auth(request)
    return {"sessions": store.list_sessions(project)}


@router.get("/api/history/{session_id}")
async def get_session(request: Request, session_id: str, project: str = "ccc"):
    check_auth(request)
    data = store.get_session(session_id, project)
    if data is None:
        raise HTTPException(status_code=404)
    return data


@router.delete("/api/history/{session_id}")
async def delete_session(request: Request, session_id: str, project: str = "ccc"):
    check_auth(request)
    store.delete_session(session_id, project)
    return {"ok": True}
```

### FILE: scripts/chat-server/routers/files.py

```python
import os
import threading
from pathlib import Path
from fastapi import APIRouter, Request, HTTPException

from ..auth import check_auth
from .projects import PROJECTS

router = APIRouter()

EXCLUDE_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", ".ccc",
    ".idea", ".vscode", "dist", "build",
}
EXCLUDE_FILE_NAMES = {".DS_Store"}
EXCLUDE_FILE_SUFFIXES = (".pyc", ".egg-info")
BINARY_EXTS = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico",
    ".pdf", ".zip", ".tar", ".gz", ".pyc",
    ".so", ".dylib",
}
MAX_FILE_TREE_ENTRIES = 500
MAX_FILE_TREE_DEPTH = 4
MAX_FILE_READ_BYTES = 100 * 1024


def _walk_project_files(root: str) -> dict:
    result = {
        "project_id": "", "root": root,
        "entries": [], "truncated": False, "timed_out": False,
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
                dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith(".")]
                if depth > MAX_FILE_TREE_DEPTH:
                    dirs[:] = []
                    continue
                if str(rel) != ".":
                    if len(result["entries"]) >= MAX_FILE_TREE_ENTRIES:
                        result["truncated"] = True
                        dirs[:] = []
                        continue
                    result["entries"].append({
                        "name": Path(current).name, "type": "dir",
                        "path": str(rel).replace(os.sep, "/"), "depth": depth,
                    })
                for fname in files:
                    if len(result["entries"]) >= MAX_FILE_TREE_ENTRIES:
                        result["truncated"] = True
                        break
                    if fname in EXCLUDE_FILE_NAMES:
                        continue
                    if any(fname.endswith(s) for s in EXCLUDE_FILE_SUFFIXES):
                        continue
                    full = Path(current) / fname
                    try:
                        size = full.stat().st_size
                    except OSError:
                        size = 0
                    file_rel = (rel / fname) if str(rel) != "." else Path(fname)
                    result["entries"].append({
                        "name": fname, "type": "file",
                        "path": str(file_rel).replace(os.sep, "/"),
                        "depth": depth + 1 if str(rel) != "." else 1,
                        "size": size,
                    })
        except Exception as e:
            result["error"] = f"walk failed: {e}"

    worker = threading.Thread(target=_walk, daemon=True)
    worker.start()
    worker.join(timeout=5.0)
    if worker.is_alive():
        result["timed_out"] = True
        result["truncated"] = True
    return result


@router.get("/api/projects/{project_id}/files")
async def list_project_files(request: Request, project_id: str):
    check_auth(request)
    proj = PROJECTS.get(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail=f"unknown project: {project_id}")
    root = Path(proj["path"]).resolve()
    data = _walk_project_files(str(root))
    data["project_id"] = project_id
    return data


@router.get("/api/projects/{project_id}/file")
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
        "project_id": project_id, "path": path,
        "size": size, "truncated": truncated, "content": content,
    }
```

### FILE: scripts/chat-server/routers/board.py

```python
from fastapi import APIRouter, Request

from ..auth import check_auth
from ..services.board_client import board_proxy

router = APIRouter()


@router.get("/api/board/proxy/board")
async def board_proxy_board(request: Request, workspace: str = "CCC"):
    check_auth(request)
    return await board_proxy("GET", "/api/board", params={"workspace": workspace})


@router.get("/api/board/proxy/dashboard")
async def board_proxy_dashboard(request: Request, workspace: str = "CCC"):
    check_auth(request)
    return await board_proxy("GET", "/api/dashboard", params={"workspace": workspace})


@router.get("/api/board/proxy/roles")
async def board_proxy_roles(request: Request):
    check_auth(request)
    return await board_proxy("GET", "/api/roles")


@router.post("/api/board/proxy/tasks")
async def board_proxy_create_task(request: Request):
    check_auth(request)
    body = await request.json()
    return await board_proxy("POST", "/api/tasks", json_body=body)


@router.post("/api/board/proxy/tasks/move")
async def board_proxy_move_task(request: Request):
    check_auth(request)
    body = await request.json()
    return await board_proxy("POST", "/api/tasks/move", json_body=body)
```

### FILE: scripts/chat-server/routers/chat.py

```python
import asyncio
import json
import re
import uuid

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse

from ..auth import check_auth
from .. import config
from ..services import session_store as store
from ..services.claude_client import stream_chat, _get_project_context
from .projects import PROJECTS, get_project_path

router = APIRouter()


def check_dangerous(text: str) -> bool:
    return bool(config.DANGEROUS_PATTERN.search(text))


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
```

---

## Step 4: 后端 — App & Entry

### FILE: scripts/chat-server/app.py

```python
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from .routers import chat, sessions, files, board, projects

FRONTEND_DIR = Path(__file__).resolve().parent / "frontend"


def create_app() -> FastAPI:
    app = FastAPI(title="CCC Chat", docs_url=None, redoc_url=None)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(projects.router)
    app.include_router(chat.router)
    app.include_router(sessions.router)
    app.include_router(files.router)
    app.include_router(board.router)

    if FRONTEND_DIR.exists():
        app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")

    return app
```

### FILE: scripts/ccc-chat-server.py

```python
#!/usr/bin/env python3
"""ccc-chat-server.py — CCC Chat Server v2 (模块化架构)"""
import os
import sys
import threading
import webbrowser

import uvicorn

from scripts.chat_server.config import HOST, PORT, AUTH_USER, AUTH_PASS
from scripts.chat_server.app import create_app

app = create_app()


def main():
    import argparse
    bind_host = HOST
    bind_port = PORT

    parser = argparse.ArgumentParser(description="CCC Chat Server v2")
    parser.add_argument("--port", type=int, default=int(os.environ.get("CCC_CHAT_PORT", bind_port)))
    parser.add_argument("--host", default=os.environ.get("CCC_CHAT_HOST", bind_host))
    parser.add_argument("--no-open", action="store_true", default=os.environ.get("CCC_CHAT_NO_OPEN", "0") == "1")
    args = parser.parse_args()
    bind_port = args.port
    bind_host = args.host

    print("  CCC Chat Server v2")
    print("  ─────────────────────")
    print(f"  地址: http://{bind_host}:{bind_port}")
    print(f"  本地: http://localhost:{bind_port}")
    print(f"  账号: {AUTH_USER} / {AUTH_PASS}")

    if not args.no_open and bind_host in ("0.0.0.0", "127.0.0.1", "localhost"):
        def _open():
            try:
                webbrowser.open(f"http://localhost:{bind_port}")
            except Exception as exc:
                print(f"  WARN: 自动打开浏览器失败: {exc}")
        threading.Timer(1.2, _open).start()

    uvicorn.run(app, host=bind_host, port=bind_port, log_level="info")


if __name__ == "__main__":
    main()
```

---

## Step 5: 前端 — CSS

### FILE: scripts/chat-server/frontend/css/variables.css

```css
:root {
  /* 背景 */
  --ccc-bg-deep: #f5f5f7;
  --ccc-bg-base: #ffffff;
  --ccc-bg-surface: #ffffff;
  --ccc-bg-layer: #f0f0f2;
  --ccc-bg-hover: rgba(0, 0, 0, 0.04);
  --ccc-bg-accent: #007aff;
  --ccc-bg-user: #007aff;
  --ccc-bg-code: #f0f0f2;

  /* 文字 */
  --ccc-text-base: #1d1d1f;
  --ccc-text-muted: #86868b;
  --ccc-text-faint: #aeaeb2;
  --ccc-text-inverse: #ffffff;
  --ccc-text-accent: #007aff;

  /* 图标 */
  --ccc-icon-base: #555557;
  --ccc-icon-muted: #aeaeb2;

  /* 边框 */
  --ccc-border-subtle: rgba(0, 0, 0, 0.06);
  --ccc-border-base: rgba(0, 0, 0, 0.1);
  --ccc-border-accent: #007aff;

  /* 阴影 */
  --ccc-shadow-sm: 0 0.5px 1px rgba(0, 0, 0, 0.05);
  --ccc-shadow-md: 0 1px 3px rgba(0, 0, 0, 0.08);
  --ccc-shadow-lg: 0 4px 12px rgba(0, 0, 0, 0.1);
  --ccc-shadow-floating: 0 8px 24px rgba(0, 0, 0, 0.12);

  /* 圆角 */
  --ccc-radius-sm: 4px;
  --ccc-radius-md: 8px;
  --ccc-radius-lg: 16px;
  --ccc-radius-xl: 20px;

  /* 排版 */
  --ccc-font-sans: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", sans-serif;
  --ccc-font-mono: "SF Mono", "Menlo", "Consolas", monospace;
  --ccc-font-size-xs: 11px;
  --ccc-font-size-sm: 13px;
  --ccc-font-size-base: 15px;

  /* 间距 */
  --ccc-space-xs: 4px;
  --ccc-space-sm: 8px;
  --ccc-space-md: 12px;
  --ccc-space-lg: 16px;
  --ccc-space-xl: 24px;

  /* 布局 */
  --ccc-sidebar-w: 280px;
  --ccc-titlebar-h: 44px;
  --ccc-composer-max-h: 200px;
  --ccc-max-w: 760px;

  /* 过渡 */
  --ccc-transition-fast: 0.15s ease;
  --ccc-transition-normal: 0.25s ease;

  /* 动画 */
  --ccc-overlay-scrim: rgba(0, 0, 0, 0.3);
}
```

### FILE: scripts/chat-server/frontend/css/themes.css

```css
[data-theme="dark"] {
  --ccc-bg-deep: #1c1c1e;
  --ccc-bg-base: #2c2c2e;
  --ccc-bg-surface: #2c2c2e;
  --ccc-bg-layer: #3a3a3c;
  --ccc-bg-hover: rgba(255, 255, 255, 0.08);
  --ccc-bg-accent: #0a84ff;
  --ccc-bg-user: #0a84ff;
  --ccc-bg-code: #3a3a3c;

  --ccc-text-base: #f5f5f7;
  --ccc-text-muted: #98989d;
  --ccc-text-faint: #636366;
  --ccc-text-inverse: #ffffff;
  --ccc-text-accent: #0a84ff;

  --ccc-icon-base: #c7c7cc;
  --ccc-icon-muted: #636366;

  --ccc-border-subtle: rgba(255, 255, 255, 0.06);
  --ccc-border-base: rgba(255, 255, 255, 0.12);
  --ccc-border-accent: #0a84ff;

  --ccc-shadow-sm: 0 0.5px 1px rgba(0, 0, 0, 0.2);
  --ccc-shadow-md: 0 1px 3px rgba(0, 0, 0, 0.3);
  --ccc-shadow-lg: 0 4px 12px rgba(0, 0, 0, 0.4);
  --ccc-shadow-floating: 0 8px 24px rgba(0, 0, 0, 0.5);

  --ccc-overlay-scrim: rgba(0, 0, 0, 0.5);
}
```

### FILE: scripts/chat-server/frontend/css/base.css

```css
*, *::before, *::after {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html, body {
  height: 100%;
  overflow: hidden;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

body {
  font-family: var(--ccc-font-sans);
  font-size: var(--ccc-font-size-base);
  color: var(--ccc-text-base);
  background: var(--ccc-bg-deep);
  transition: background var(--ccc-transition-normal), color var(--ccc-transition-normal);
}

#app {
  display: flex;
  flex-direction: column;
  height: 100dvh;
  max-width: 100vw;
  overflow: hidden;
}

/* Scrollbar */
::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}
::-webkit-scrollbar-track {
  background: transparent;
}
::-webkit-scrollbar-thumb {
  background: var(--ccc-icon-muted);
  border-radius: 3px;
}
::-webkit-scrollbar-thumb:hover {
  background: var(--ccc-text-muted);
}

/* Skeleton animation */
@keyframes skeleton-pulse {
  0%, 100% { opacity: 0.4; }
  50% { opacity: 0.8; }
}
.skeleton {
  background: var(--ccc-bg-layer);
  border-radius: var(--ccc-radius-md);
  animation: skeleton-pulse 1.5s ease-in-out infinite;
}

/* Typing dots */
@keyframes typing-dot {
  0%, 60%, 100% { opacity: 0.3; transform: translateY(0); }
  30% { opacity: 1; transform: translateY(-3px); }
}
.typing-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--ccc-text-muted);
  animation: typing-dot 1.4s infinite;
}
.typing-dot:nth-child(2) { animation-delay: 0.2s; }
.typing-dot:nth-child(3) { animation-delay: 0.4s; }

/* Message fade in */
@keyframes msg-in {
  from { opacity: 0; transform: translateY(4px); }
  to { opacity: 1; transform: translateY(0); }
}

/* Dialog overlay */
.dialog-overlay {
  position: fixed;
  inset: 0;
  z-index: 50;
  background: var(--ccc-overlay-scrim);
  animation: fade-in 0.15s ease;
}
@keyframes fade-in {
  from { opacity: 0; }
  to { opacity: 1; }
}
```

### FILE: scripts/chat-server/frontend/css/components.css

```css
/* ================================================================
   Titlebar
   ================================================================ */
#titlebar {
  display: flex;
  align-items: center;
  height: var(--ccc-titlebar-h);
  padding: 0 var(--ccc-space-sm);
  background: var(--ccc-bg-base);
  border-bottom: 0.5px solid var(--ccc-border-base);
  flex-shrink: 0;
  gap: 2px;
  -webkit-app-region: drag;
}
.titlebar-tab {
  display: flex;
  align-items: center;
  gap: 6px;
  height: 28px;
  padding: 0 12px;
  border-radius: var(--ccc-radius-sm);
  font-size: var(--ccc-font-size-sm);
  color: var(--ccc-text-muted);
  cursor: pointer;
  -webkit-app-region: no-drag;
  transition: background var(--ccc-transition-fast), color var(--ccc-transition-fast);
  border: none;
  background: transparent;
  user-select: none;
  white-space: nowrap;
}
.titlebar-tab:hover {
  background: var(--ccc-bg-hover);
  color: var(--ccc-text-base);
}
.titlebar-tab.active {
  background: var(--ccc-bg-layer);
  color: var(--ccc-text-base);
}
.titlebar-tab .close-btn {
  display: none;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  border: none;
  background: transparent;
  color: var(--ccc-icon-muted);
  font-size: 10px;
  cursor: pointer;
  align-items: center;
  justify-content: center;
  padding: 0;
}
.titlebar-tab:hover .close-btn {
  display: flex;
}
.titlebar-tab .close-btn:hover {
  background: var(--ccc-bg-hover);
  color: var(--ccc-text-base);
}
.titlebar-spacer {
  flex: 1;
}
.titlebar-btn {
  width: 28px;
  height: 28px;
  border: none;
  border-radius: var(--ccc-radius-sm);
  background: transparent;
  color: var(--ccc-icon-base);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 15px;
  -webkit-app-region: no-drag;
  transition: background var(--ccc-transition-fast);
}
.titlebar-btn:hover {
  background: var(--ccc-bg-hover);
}

/* ================================================================
   Layout: sidebar + main
   ================================================================ */
#layout {
  display: flex;
  flex: 1;
  overflow: hidden;
}

/* ================================================================
   Sidebar
   ================================================================ */
#sidebar {
  width: var(--ccc-sidebar-w);
  background: var(--ccc-bg-base);
  border-right: 0.5px solid var(--ccc-border-base);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  transition: transform 0.3s cubic-bezier(0.32, 0.72, 0, 1);
}
#sidebar.hidden {
  display: none;
}
.sidebar-header {
  padding: var(--ccc-space-md) var(--ccc-space-lg);
  border-bottom: 0.5px solid var(--ccc-border-base);
}
.sidebar-search {
  width: 100%;
  height: 32px;
  padding: 0 var(--ccc-space-md);
  border: 0.5px solid var(--ccc-border-base);
  border-radius: var(--ccc-radius-md);
  background: var(--ccc-bg-layer);
  color: var(--ccc-text-base);
  font-size: var(--ccc-font-size-sm);
  outline: none;
}
.sidebar-search:focus {
  border-color: var(--ccc-border-accent);
}
.sidebar-list {
  flex: 1;
  overflow-y: auto;
  padding: var(--ccc-space-xs) 0;
}
.sidebar-group-label {
  padding: var(--ccc-space-md) var(--ccc-space-lg) var(--ccc-space-xs);
  font-size: var(--ccc-font-size-xs);
  color: var(--ccc-text-faint);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.session-item {
  padding: var(--ccc-space-sm) var(--ccc-space-lg);
  cursor: pointer;
  transition: background var(--ccc-transition-fast);
  border-left: 2px solid transparent;
}
.session-item:hover {
  background: var(--ccc-bg-hover);
}
.session-item.active {
  background: var(--ccc-bg-hover);
  border-left-color: var(--ccc-border-accent);
}
.session-item-title {
  font-size: var(--ccc-font-size-sm);
  color: var(--ccc-text-base);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.session-item-meta {
  font-size: var(--ccc-font-size-xs);
  color: var(--ccc-text-faint);
  margin-top: 2px;
}

/* ================================================================
   Chat panel
   ================================================================ */
#chat-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

/* ================================================================
   Messages
   ================================================================ */
#messages {
  flex: 1;
  overflow-y: auto;
  padding: var(--ccc-space-lg);
  padding-bottom: var(--ccc-space-sm);
  display: flex;
  flex-direction: column;
  gap: var(--ccc-space-md);
}
.msg {
  animation: msg-in 0.2s ease-out;
  display: flex;
  flex-direction: column;
}
.msg.user {
  align-items: flex-end;
}
.msg.assistant {
  align-items: flex-start;
}
.msg .bubble {
  max-width: 80%;
  padding: 10px 14px;
  border-radius: var(--ccc-radius-xl);
  line-height: 1.55;
  font-size: var(--ccc-font-size-base);
  word-wrap: break-word;
  position: relative;
}
.msg.user .bubble {
  background: var(--ccc-bg-user);
  color: var(--ccc-text-inverse);
  border-bottom-right-radius: var(--ccc-radius-sm);
}
.msg.assistant .bubble {
  background: var(--ccc-bg-surface);
  border: 0.5px solid var(--ccc-border-base);
  border-bottom-left-radius: var(--ccc-radius-sm);
  color: var(--ccc-text-base);
  box-shadow: var(--ccc-shadow-sm);
}
.msg .time {
  font-size: var(--ccc-font-size-xs);
  color: var(--ccc-text-faint);
  margin-top: 4px;
  padding: 0 4px;
}

/* Bubble content styles */
.bubble p {
  margin-bottom: 8px;
}
.bubble p:last-child {
  margin-bottom: 0;
}
.bubble pre {
  background: var(--ccc-bg-code);
  border-radius: var(--ccc-radius-md);
  padding: 12px;
  overflow-x: auto;
  margin: 8px 0;
  font-size: var(--ccc-font-size-sm);
  font-family: var(--ccc-font-mono);
  line-height: 1.4;
  position: relative;
}
.bubble code {
  background: var(--ccc-bg-code);
  padding: 2px 6px;
  border-radius: var(--ccc-radius-sm);
  font-size: var(--ccc-font-size-sm);
  font-family: var(--ccc-font-mono);
}
.bubble pre code {
  background: none;
  padding: 0;
}
.bubble ul, .bubble ol {
  margin: 8px 0;
  padding-left: 20px;
}
.bubble li {
  margin-bottom: 4px;
}
.bubble h1, .bubble h2, .bubble h3 {
  margin: 12px 0 6px;
  font-weight: 600;
}
.bubble h1 { font-size: 1.3em; }
.bubble h2 { font-size: 1.15em; }
.bubble h3 { font-size: 1.05em; }
.bubble blockquote {
  border-left: 3px solid var(--ccc-border-accent);
  padding-left: 12px;
  margin: 8px 0;
  color: var(--ccc-text-muted);
}
.bubble table {
  border-collapse: collapse;
  margin: 8px 0;
  width: 100%;
  font-size: var(--ccc-font-size-sm);
}
.bubble th, .bubble td {
  border: 0.5px solid var(--ccc-border-base);
  padding: 6px 10px;
  text-align: left;
}
.bubble th {
  background: var(--ccc-bg-layer);
  font-weight: 600;
}
.bubble a {
  color: var(--ccc-text-accent);
  text-decoration: none;
}
.bubble a:hover {
  text-decoration: underline;
}
.bubble hr {
  border: none;
  border-top: 0.5px solid var(--ccc-border-base);
  margin: 12px 0;
}
.bubble img {
  max-width: 100%;
  border-radius: var(--ccc-radius-md);
  margin: 8px 0;
}
.code-block-wrap {
  position: relative;
  margin: 8px 0;
}
.code-block-wrap .copy-btn {
  position: absolute;
  top: 8px;
  right: 8px;
  padding: 2px 8px;
  font-size: var(--ccc-font-size-xs);
  color: var(--ccc-text-faint);
  background: var(--ccc-bg-layer);
  border: 0.5px solid var(--ccc-border-base);
  border-radius: var(--ccc-radius-sm);
  cursor: pointer;
  opacity: 0;
  transition: opacity var(--ccc-transition-fast);
}
.code-block-wrap:hover .copy-btn {
  opacity: 1;
}

/* Tool card */
.tool-card {
  margin: 8px 0;
  border: 0.5px solid var(--ccc-border-base);
  border-radius: var(--ccc-radius-md);
  overflow: hidden;
  background: var(--ccc-bg-surface);
  box-shadow: var(--ccc-shadow-sm);
  transition: border-color var(--ccc-transition-fast);
}
.tool-card:hover {
  border-color: var(--ccc-border-accent);
}
.tool-card summary {
  padding: 8px 12px;
  cursor: pointer;
  font-size: var(--ccc-font-size-sm);
  font-weight: 500;
  color: var(--ccc-text-accent);
  list-style: none;
  display: flex;
  align-items: center;
  gap: 6px;
}
.tool-card summary::-webkit-details-marker { display: none; }
.tool-card pre {
  padding: 8px 12px;
  font-size: var(--ccc-font-size-sm);
  overflow-x: auto;
  border-top: 0.5px solid var(--ccc-border-base);
  white-space: pre-wrap;
  margin: 0;
}

/* Cost info */
.cost-info {
  font-size: var(--ccc-font-size-xs);
  color: var(--ccc-text-faint);
  margin-top: 4px;
  padding-left: 4px;
}

/* Message edit */
.edit-textarea {
  width: 100%;
  padding: 8px;
  border-radius: var(--ccc-radius-md);
  border: 0.5px solid rgba(255,255,255,0.3);
  background: rgba(255,255,255,0.15);
  color: #fff;
  font-size: var(--ccc-font-size-base);
  font-family: inherit;
  resize: vertical;
  min-height: 60px;
  outline: none;
}
.edit-actions {
  display: flex;
  gap: 6px;
  margin-top: 6px;
  justify-content: flex-end;
}
.edit-actions button {
  padding: 4px 12px;
  border-radius: 12px;
  border: none;
  font-size: var(--ccc-font-size-xs);
  cursor: pointer;
}
.edit-save { background: rgba(255,255,255,0.9); color: #007aff; }
.edit-cancel { background: rgba(255,255,255,0.2); color: rgba(255,255,255,0.8); }

/* ================================================================
   Composer
   ================================================================ */
#composer {
  padding: var(--ccc-space-md) var(--ccc-space-lg);
  padding-bottom: calc(var(--ccc-space-md) + env(safe-area-inset-bottom, 0px));
  background: var(--ccc-bg-base);
  border-top: 0.5px solid var(--ccc-border-base);
}
#composer-inner {
  max-width: var(--ccc-max-w);
  margin: 0 auto;
}
.composer-toolbar {
  display: flex;
  align-items: center;
  gap: var(--ccc-space-sm);
  margin-bottom: var(--ccc-space-sm);
}
.model-select {
  font-size: var(--ccc-font-size-xs);
  padding: 4px 8px;
  border-radius: var(--ccc-radius-sm);
  border: 0.5px solid var(--ccc-border-base);
  background: var(--ccc-bg-layer);
  color: var(--ccc-text-base);
  outline: none;
  cursor: pointer;
}
.context-indicator {
  font-size: var(--ccc-font-size-xs);
  color: var(--ccc-text-faint);
}
.composer-input-wrap {
  display: flex;
  align-items: flex-end;
  gap: var(--ccc-space-sm);
  background: var(--ccc-bg-layer);
  border: 0.5px solid var(--ccc-border-base);
  border-radius: var(--ccc-radius-lg);
  padding: var(--ccc-space-xs) var(--ccc-space-sm);
  transition: border-color var(--ccc-transition-fast);
}
.composer-input-wrap:focus-within {
  border-color: var(--ccc-border-accent);
}
#composer-input {
  flex: 1;
  border: none;
  background: transparent;
  color: var(--ccc-text-base);
  font-size: var(--ccc-font-size-base);
  font-family: inherit;
  resize: none;
  outline: none;
  min-height: 24px;
  max-height: var(--ccc-composer-max-h);
  line-height: 1.4;
  padding: 4px 0;
}
#composer-input::placeholder {
  color: var(--ccc-text-faint);
}
.composer-btn {
  width: 32px;
  height: 32px;
  border: none;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  font-size: 16px;
  flex-shrink: 0;
  transition: background var(--ccc-transition-fast), opacity var(--ccc-transition-fast);
}
#send-btn {
  background: var(--ccc-bg-accent);
  color: white;
}
#send-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
#send-btn:not(:disabled):hover {
  opacity: 0.9;
}
#cancel-btn {
  background: transparent;
  color: var(--ccc-icon-base);
  display: none;
}
#cancel-btn:hover {
  background: var(--ccc-bg-hover);
}

/* ================================================================
   Scroll FAB
   ================================================================ */
.scroll-fab {
  position: absolute;
  bottom: 80px;
  right: 24px;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  border: 0.5px solid var(--ccc-border-base);
  background: var(--ccc-bg-surface);
  color: var(--ccc-icon-base);
  box-shadow: var(--ccc-shadow-md);
  cursor: pointer;
  display: none;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  z-index: 5;
  transition: opacity var(--ccc-transition-fast);
}
.scroll-fab.show {
  display: flex;
}
#chat-panel { position: relative; }

/* ================================================================
   Settings Dialog
   ================================================================ */
.settings-dialog {
  position: fixed;
  inset: 0;
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: center;
}
.settings-panel {
  background: var(--ccc-bg-surface);
  border-radius: var(--ccc-radius-lg);
  box-shadow: var(--ccc-shadow-floating);
  width: 420px;
  max-width: calc(100vw - 32px);
  max-height: calc(100vh - 64px);
  overflow-y: auto;
  z-index: 101;
  animation: msg-in 0.2s ease-out;
}
.settings-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--ccc-space-lg) var(--ccc-space-xl);
  border-bottom: 0.5px solid var(--ccc-border-base);
}
.settings-title {
  font-size: 16px;
  font-weight: 600;
}
.settings-close {
  width: 28px;
  height: 28px;
  border: none;
  border-radius: 50%;
  background: transparent;
  color: var(--ccc-icon-base);
  cursor: pointer;
  font-size: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.settings-close:hover {
  background: var(--ccc-bg-hover);
}
.settings-body {
  padding: var(--ccc-space-lg) var(--ccc-space-xl);
}
.settings-group {
  margin-bottom: var(--ccc-space-xl);
}
.settings-group-title {
  font-size: var(--ccc-font-size-sm);
  font-weight: 600;
  margin-bottom: var(--ccc-space-sm);
  color: var(--ccc-text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.settings-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--ccc-space-sm) 0;
}
.settings-label {
  font-size: var(--ccc-font-size-sm);
}
.settings-select {
  padding: 4px 8px;
  border-radius: var(--ccc-radius-sm);
  border: 0.5px solid var(--ccc-border-base);
  background: var(--ccc-bg-layer);
  color: var(--ccc-text-base);
  font-size: var(--ccc-font-size-sm);
  outline: none;
}

/* ================================================================
   Mobile
   ================================================================ */
@media (max-width: 768px) {
  #sidebar {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    z-index: 30;
    transform: translateX(-100%);
  }
  #sidebar.open {
    transform: translateX(0);
  }
  .sidebar-overlay {
    display: none;
    position: fixed;
    inset: 0;
    background: var(--ccc-overlay-scrim);
    z-index: 29;
  }
  .sidebar-overlay.show {
    display: block;
  }
  #titlebar {
    padding: 0 var(--ccc-space-xs);
  }
  #messages {
    padding: var(--ccc-space-sm);
  }
  #composer {
    padding: var(--ccc-space-sm);
  }
  .msg .bubble {
    max-width: 90%;
  }
}
```

---

## Step 6: 前端 — JavaScript

### FILE: scripts/chat-server/frontend/js/utils.js

```javascript
export function escapeHtml(text) {
  const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' };
  return String(text).replace(/[&<>"]/g, c => map[c]);
}

export function ts() {
  const d = new Date();
  return String(d.getHours()).padStart(2, '0') + ':' +
         String(d.getMinutes()).padStart(2, '0');
}

export function scrollToBottom(el) {
  if (el) el.scrollTop = el.scrollHeight;
}

export function generateId() {
  if (crypto.randomUUID) return crypto.randomUUID();
  return Date.now().toString(36) + Math.random().toString(36).slice(2);
}

export function debounce(fn, ms) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), ms);
  };
}
```

### FILE: scripts/chat-server/frontend/js/state.js

```javascript
class State {
  constructor() {
    this.listeners = {};
    this.data = {
      sessions: [],
      currentSessionId: null,
      currentMessages: [],
      currentProject: 'ccc',
      streaming: false,
      abortController: null,
      tabs: [],
      activeTabId: null,
    };
  }

  get(key) { return this.data[key]; }
  set(key, value) {
    this.data[key] = value;
    this.emit(key, value);
  }

  on(event, fn) {
    (this.listeners[event] = this.listeners[event] || []).push(fn);
  }
  emit(event, data) {
    (this.listeners[event] || []).forEach(fn => fn(data));
  }
}

export const state = new State();
```

### FILE: scripts/chat-server/frontend/js/api.js

```javascript
import { state } from './state.js';

const AUTH = 'Basic ' + btoa('ccc:claude2026');

export async function apiGet(path) {
  const resp = await fetch(path, { headers: { Authorization: AUTH } });
  if (!resp.ok) throw new Error(`GET ${path} ${resp.status}`);
  return resp.json();
}

export async function apiDelete(path) {
  const resp = await fetch(path, { method: 'DELETE', headers: { Authorization: AUTH } });
  return resp.json();
}

export async function loadProjects() {
  const data = await apiGet('/api/projects');
  return data.projects;
}

export async function loadHistory(project) {
  const data = await apiGet(`/api/history?project=${encodeURIComponent(project)}`);
  return data.sessions;
}

export async function loadSession(id, project) {
  return await apiGet(`/api/history/${id}?project=${encodeURIComponent(project)}`);
}

export async function deleteSession(id, project) {
  return await apiDelete(`/api/history/${id}?project=${encodeURIComponent(project)}`);
}

export async function streamChat(messages, sessionId, project, onEvent, onDone, onError) {
  const abortController = new AbortController();
  state.set('abortController', abortController);

  try {
    const resp = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: AUTH },
      body: JSON.stringify({
        messages,
        session_id: sessionId,
        project,
        timeout: 120,
      }),
      signal: abortController.signal,
    });

    if (!resp.ok) {
      const errText = resp.status === 400 ? '危险指令已被拦截'
        : resp.status === 429 ? '前一个执行中，请稍候'
        : `请求失败: HTTP ${resp.status}`;
      onError(errText);
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
            onEvent('delta', data.content);
          } else if (data.type === 'tool_use') {
            onEvent('tool_use', data);
          } else if (data.type === 'tool_result') {
            onEvent('tool_result', data);
          } else if (data.type === 'cost') {
            onEvent('cost', data);
          } else if (data.type === 'done') {
            onDone(data.session_id || sessionId);
          } else if (data.type === 'error') {
            onError(data.content);
          }
        } catch (e) { /* skip bad json */ }
      }
    }
  } catch (e) {
    if (e.name !== 'AbortError') {
      onError('网络错误: ' + e.message);
    }
  } finally {
    state.set('abortController', null);
  }
}

export function cancelStream() {
  const ac = state.get('abortController');
  if (ac) ac.abort();
}
```

### FILE: scripts/chat-server/frontend/js/markdown.js

```javascript
import { escapeHtml } from './utils.js';

export function renderMarkdown(text) {
  if (!text) return '';

  // Guard tool_call XML
  const toolCalls = [];
  text = text.replace(/<tool_call>[\s\S]*?<\/tool_call>/g, (m) => {
    const i = toolCalls.length;
    toolCalls.push(m);
    return '\x00TC' + i + '\x00';
  });

  // Guard code blocks
  const codeBlocks = [];
  let h = escapeHtml(text);
  h = h.replace(/```(\w*)\n?([\s\S]*?)```/g, (_, lang, code) => {
    const i = codeBlocks.length;
    const langClass = lang ? ' class="lang-' + lang + '"' : '';
    codeBlocks.push(
      '<div class="code-block-wrap">' +
      '<pre><code' + langClass + '>' + code + '</code></pre>' +
      '<button class="copy-btn" onclick="copyCode(this)">复制</button>' +
      '</div>'
    );
    return '\x00CB' + i + '\x00';
  });

  // Guard inline code
  const inlineCodes = [];
  h = h.replace(/`([^`]+)`/g, (_, c) => {
    const i = inlineCodes.length;
    inlineCodes.push('<code>' + c + '</code>');
    return '\x00IC' + i + '\x00';
  });

  // Block-level transforms
  const lines = h.split('\n');
  const out = [];
  let inTable = false;
  let inList = false;
  let listType = null;

  function closeList() {
    if (inList) {
      out.push(listType === 'ol' ? '</ol>' : '</ul>');
      inList = false;
      listType = null;
    }
  }

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trimEnd();

    // HR
    if (/^[-*_]{3,}\s*$/.test(line.trim())) {
      closeList(); inTable = false;
      out.push('<hr>');
      continue;
    }

    // Headers
    const h1 = line.match(/^# (.+)$/);
    if (h1) { closeList(); inTable = false; out.push('<h1>' + h1[1] + '</h1>'); continue; }
    const h2 = line.match(/^## (.+)$/);
    if (h2) { closeList(); inTable = false; out.push('<h2>' + h2[1] + '</h2>'); continue; }
    const h3 = line.match(/^### (.+)$/);
    if (h3) { closeList(); inTable = false; out.push('<h3>' + h3[1] + '</h3>'); continue; }
    const h4 = line.match(/^#### (.+)$/);
    if (h4) { closeList(); inTable = false; out.push('<h4>' + h4[1] + '</h4>'); continue; }

    // Blockquote
    const bq = line.match(/^> ?(.+)$/);
    if (bq) { closeList(); inTable = false; out.push('<blockquote>' + bq[1] + '</blockquote>'); continue; }

    // Unordered list
    const ul = line.match(/^[-*+] (.+)$/);
    if (ul) {
      if (!inList || listType !== 'ul') { closeList(); out.push('<ul>'); inList = true; listType = 'ul'; }
      out.push('<li>' + ul[1] + '</li>');
      continue;
    }

    // Ordered list
    const ol = line.match(/^\d+\.\s+(.+)$/);
    if (ol) {
      if (!inList || listType !== 'ol') { closeList(); out.push('<ol>'); inList = true; listType = 'ol'; }
      out.push('<li>' + ol[1] + '</li>');
      continue;
    }

    // Table
    if (line.includes('|')) {
      const cells = line.split('|').filter(Boolean);
      if (!inTable && i + 1 < lines.length && /^[\s|:-]+$/.test(lines[i+1].trim())) {
        closeList();
        out.push('<table><thead><tr>' + cells.map(c => '<th>' + c.trim() + '</th>').join('') + '</tr></thead><tbody>');
        inTable = true;
        i++;
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

    if (line.trim() === '') {
      out.push('</p><p>');
      continue;
    }

    out.push(line);
  }
  closeList();
  if (inTable) out.push('</tbody></table>');

  h = out.join('\n');

  // Wrap paragraphs
  h = h.replace(/^(?!<[a-z/]|$)(.+)$/gm, '<p>$1</p>');
  h = h.replace(/<\/p>\s*<p><\/p>/g, '</p><p>');

  // Inline transforms
  h = h.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
  h = h.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img src="$2" alt="$1" style="max-width:100%;border-radius:8px;margin:8px 0;">');
  h = h.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  h = h.replace(/(?<!\*)\*([^*]+)\*(?!\*)/g, '<em>$1</em>');

  // Restore inline code
  h = h.replace(/\x00IC(\d+)\x00/g, (_, i) => inlineCodes[parseInt(i)] || '');

  // Tool calls
  h = h.replace(/\x00TC(\d+)\x00/g, (_, i) => {
    const raw = toolCalls[parseInt(i)] || '';
    const nameMatch = raw.match(/<tool_call>[\s\S]*?"name"\s*:\s*"([^"]+)"/);
    const argMatch = raw.match(/<tool_call>[\s\S]*?"arguments"\s*:\s*\{([^}]+)\}/);
    const name = nameMatch ? nameMatch[1] : 'tool';
    const args = argMatch ? '{' + argMatch[1] + '}' : raw.replace(/<\/?tool_call>/g, '').trim();
    return '<details class="tool-card" style="margin:8px 0">' +
      '<summary><span>🛠</span> ' + escapeHtml(name) + '</summary>' +
      '<pre>' + escapeHtml(args) + '</pre></details>';
  });

  // Code blocks
  h = h.replace(/\x00CB(\d+)\x00/g, (_, i) => codeBlocks[parseInt(i)] || '');

  // Cleanup
  h = h.replace(/<p><\/p>/g, '');
  h = h.replace(/<p>\s*<\/p>/g, '');

  return h;
}
```

### FILE: scripts/chat-server/frontend/js/components/titlebar.js

```javascript
import { state } from '../state.js';
import { generateId } from '../utils.js';

export function initTitlebar() {
  const tabsEl = document.getElementById('tabs');
  const newBtn = document.getElementById('new-tab-btn');
  const settingsBtn = document.getElementById('settings-btn');
  const themeBtn = document.getElementById('theme-btn');

  // Init theme
  const saved = localStorage.getItem('ccc-chat-theme');
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  const isDark = saved ? saved === 'dark' : prefersDark;
  document.documentElement.setAttribute('data-theme', isDark ? 'dark' : 'light');
  if (themeBtn) themeBtn.textContent = isDark ? '☀️' : '🌙';

  // Theme toggle
  if (themeBtn) {
    themeBtn.addEventListener('click', () => {
      const current = document.documentElement.getAttribute('data-theme');
      const next = current === 'dark' ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', next);
      localStorage.setItem('ccc-chat-theme', next);
      themeBtn.textContent = next === 'dark' ? '☀️' : '🌙';
    });
  }

  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
    if (!localStorage.getItem('ccc-chat-theme')) {
      const isDark = e.matches;
      document.documentElement.setAttribute('data-theme', isDark ? 'dark' : 'light');
      if (themeBtn) themeBtn.textContent = isDark ? '☀️' : '🌙';
    }
  });

  // Settings
  if (settingsBtn) {
    settingsBtn.addEventListener('click', () => {
      import('./settings.js').then(m => m.openSettings());
    });
  }

  // New tab
  if (newBtn) {
    newBtn.addEventListener('click', () => {
      const event = new CustomEvent('new-tab');
      document.dispatchEvent(event);
    });
  }

  // Tab click delegation
  tabsEl.addEventListener('click', (e) => {
    const tab = e.target.closest('.titlebar-tab');
    if (!tab) return;
    if (e.target.closest('.close-btn')) {
      const event = new CustomEvent('close-tab', { detail: { id: tab.dataset.tabId } });
      document.dispatchEvent(event);
    } else {
      const event = new CustomEvent('switch-tab', { detail: { id: tab.dataset.tabId } });
      document.dispatchEvent(event);
    }
  });
}

export function renderTabs(tabs, activeId) {
  const tabsEl = document.getElementById('tabs');
  tabsEl.innerHTML = tabs.map(t => {
    const isActive = t.id === activeId;
    const title = t.title || '新对话';
    return '<div class="titlebar-tab' + (isActive ? ' active' : '') + '" data-tab-id="' + t.id + '">' +
      '<span>' + escapeDisplay(title) + '</span>' +
      (tabs.length > 1 ? '<button class="close-btn">×</button>' : '') +
      '</div>';
  }).join('');
}

function escapeDisplay(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
```

### FILE: scripts/chat-server/frontend/js/components/sidebar.js

```javascript
import { state } from '../state.js';
import { apiGet, loadHistory } from '../api.js';
import { escapeHtml } from '../utils.js';

export async function refreshSidebar() {
  const project = state.get('currentProject');
  const sessions = await loadHistory(project);
  state.set('sessions', sessions);
  renderSidebar(sessions);
}

export function renderSidebar(sessions) {
  const list = document.getElementById('session-list');

  if (!sessions || sessions.length === 0) {
    list.innerHTML = '<div style="padding:16px;text-align:center;color:var(--ccc-text-faint);font-size:13px;">暂无对话历史</div>';
    return;
  }

  // Group by date
  const groups = {};
  const today = new Date();
  const todayStr = today.toISOString().slice(0, 10);
  const yesterdayStr = new Date(today.getTime() - 86400000).toISOString().slice(0, 10);

  for (const s of sessions) {
    const date = (s.updated_at || '').slice(0, 10);
    let label;
    if (date === todayStr) label = '今天';
    else if (date === yesterdayStr) label = '昨天';
    else label = date || '更早';
    (groups[label] = groups[label] || []).push(s);
  }

  const order = ['今天', '昨天', ...Object.keys(groups).filter(k => k !== '今天' && k !== '昨天').sort().reverse()];

  let html = '';
  for (const label of order) {
    if (!groups[label]) continue;
    html += '<div class="sidebar-group-label">' + label + '</div>';
    for (const s of groups[label]) {
      const active = s.session_id === state.get('currentSessionId') ? ' active' : '';
      html += '<div class="session-item' + active + '" data-sid="' + s.session_id + '">' +
        '<div class="session-item-title">' + escapeHtml(s.title) + '</div>' +
        '<div class="session-item-meta">' + escapeHtml(s.updated_at || '') + '</div>' +
        '</div>';
    }
  }
  list.innerHTML = html;

  // Click handlers
  list.querySelectorAll('.session-item').forEach(el => {
    el.addEventListener('click', () => {
      const event = new CustomEvent('load-session', { detail: { id: el.dataset.sid } });
      document.dispatchEvent(event);
    });
  });
}

export function setupSidebarSearch() {
  const input = document.getElementById('sidebar-search');
  if (!input) return;
  input.addEventListener('input', () => {
    const q = input.value.toLowerCase();
    document.querySelectorAll('.session-item').forEach(el => {
      const title = el.querySelector('.session-item-title')?.textContent?.toLowerCase() || '';
      el.style.display = title.includes(q) ? '' : 'none';
    });
  });
}
```

### FILE: scripts/chat-server/frontend/js/components/message.js

```javascript
import { state } from '../state.js';
import { renderMarkdown } from '../markdown.js';
import { escapeHtml, ts, scrollToBottom } from '../utils.js';
import { streamChat } from '../api.js';
import { renderSidebar, refreshSidebar } from './sidebar.js';

let fullContent = '';
let toolCards = [];
let costInfo = null;

export function renderMessage(container, role, content) {
  const div = document.createElement('div');
  div.className = 'msg ' + role;
  div.innerHTML = '<div class="bubble">' + renderMarkdown(content) + '</div>' +
    '<div class="time">' + ts() + '</div>';
  container.appendChild(div);
  scrollToBottom(container);

  // Double-click edit on user messages
  if (role === 'user') {
    div.style.cursor = 'pointer';
    div.title = '双击编辑';
    div.addEventListener('dblclick', function () {
      if (event.target.closest('.edit-textarea, .edit-actions, button, .copy-btn')) return;
      editMessage(this, container);
    });
  }
  return div;
}

function editMessage(msgEl, container) {
  const bubble = msgEl.querySelector('.bubble');
  if (!bubble) return;
  const currentText = bubble.textContent || '';
  const safeText = escapeHtml(currentText).replace(/'/g, "\\'");
  bubble.innerHTML = '<div class="edit-area">' +
    '<textarea class="edit-textarea">' + safeText + '</textarea>' +
    '<div class="edit-actions">' +
    '<button class="edit-save" onclick="window.saveEdit(this)">保存</button>' +
    '<button class="edit-cancel" onclick="window.cancelEdit(this)">取消</button>' +
    '</div></div>';
  const ta = bubble.querySelector('.edit-textarea');
  ta.dataset.original = currentText;
  ta.focus();
  ta.setSelectionRange(ta.value.length, ta.value.length);
}

window.saveEdit = function (btn) {
  const area = btn.closest('.edit-area');
  const ta = area.querySelector('.edit-textarea');
  const newText = ta.value.trim();
  const orig = ta.dataset.original || '';
  if (!newText || newText === orig) { doCancelEdit(area, orig); return; }

  const msgEl = btn.closest('.msg');
  if (!msgEl) return;
  const container = document.getElementById('messages');
  const siblings = [];
  let next = msgEl.nextElementSibling;
  while (next) {
    if (next.classList.contains('msg') && !next.classList.contains('typing')) {
      siblings.push(next);
    }
    next = next.nextElementSibling;
  }
  siblings.forEach(s => s.remove());

  const bubble = msgEl.querySelector('.bubble');
  if (bubble) bubble.innerHTML = renderMarkdown(newText);

  let msgs = state.get('currentMessages') || [];
  const idx = msgs.findIndex(m => m.role === 'user');
  if (idx !== -1) {
    msgs = msgs.slice(0, idx + 1);
    msgs[idx].content = newText;
  }
  state.set('currentMessages', msgs);

  const input = document.getElementById('composer-input');
  if (input) {
    input.value = newText;
    input.dispatchEvent(new Event('input'));
  }
  document.getElementById('send-btn')?.click();
};

window.cancelEdit = function (btn) {
  const area = btn.closest('.edit-area');
  const ta = area?.querySelector('.edit-textarea');
  const orig = ta ? (ta.dataset.original || '') : '';
  doCancelEdit(area, orig);
};

function doCancelEdit(area, orig) {
  if (!area) return;
  const bubble = area.closest('.bubble');
  if (bubble) bubble.innerHTML = renderMarkdown(orig || '');
}

export function showTyping(container) {
  const el = document.createElement('div');
  el.className = 'msg assistant';
  el.id = 'typing-indicator';
  el.innerHTML = '<div class="bubble" style="display:flex;gap:4px;padding:14px 18px">' +
    '<span class="typing-dot"></span>' +
    '<span class="typing-dot"></span>' +
    '<span class="typing-dot"></span></div>';
  container.appendChild(el);
  scrollToBottom(container);
  return el;
}

export function removeTyping() {
  const el = document.getElementById('typing-indicator');
  if (el) el.remove();
}

export async function sendMessage(text) {
  const container = document.getElementById('messages');
  const project = state.get('currentProject');
  let msgs = state.get('currentMessages') || [];

  if (state.get('streaming')) return;

  // Add user message
  msgs.push({ role: 'user', content: text, mode: 'chat' });
  renderMessage(container, 'user', text);

  // Show typing
  showTyping(container);

  const sid = state.get('currentSessionId');
  fullContent = '';
  toolCards = [];
  costInfo = null;
  state.set('streaming', true);
  updateComposerState();

  let msgDiv = null;
  let bubble = null;

  await streamChat(
    msgs,
    sid,
    project,
    // onEvent
    (type, data) => {
      if (type === 'delta') {
        if (!msgDiv) {
          removeTyping();
          msgDiv = document.createElement('div');
          msgDiv.className = 'msg assistant';
          msgDiv.innerHTML = '<div class="bubble"></div><div class="time">' + ts() + '</div>';
          container.appendChild(msgDiv);
          bubble = msgDiv.querySelector('.bubble');
        }
        fullContent += data;
        bubble.innerHTML = renderMarkdown(fullContent);
        toolCards.forEach(c => bubble.appendChild(c));
        scrollToBottom(container);
      } else if (type === 'tool_use') {
        const card = document.createElement('details');
        card.className = 'tool-card';
        card.open = false;
        card.innerHTML = '<summary>🛠 ' + escapeHtml(data.name || 'tool') + '</summary>' +
          '<pre>' + escapeHtml(JSON.stringify(data.input, null, 2)) + '</pre>';
        toolCards.push(card);
        if (bubble) bubble.appendChild(card);
      } else if (type === 'tool_result') {
        if (toolCards.length) {
          const last = toolCards[toolCards.length - 1];
          const pre = document.createElement('pre');
          pre.textContent = typeof data.content === 'string' ? data.content : JSON.stringify(data.content, null, 2);
          last.appendChild(pre);
        }
      } else if (type === 'cost') {
        costInfo = data;
      }
    },
    // onDone
    (sessionId) => {
      state.set('currentSessionId', sessionId);
      if (costInfo && msgDiv) {
        const costEl = document.createElement('div');
        costEl.className = 'cost-info';
        costEl.textContent = 'Tokens: ' + (costInfo.tokens || 0) + ' · $' + (costInfo.usd || 0).toFixed(4);
        msgDiv.appendChild(costEl);
      }
      msgs.push({ role: 'assistant', content: fullContent, mode: 'chat' });
      state.set('currentMessages', msgs);
      state.set('streaming', false);
      updateComposerState();
      refreshSidebar();
    },
    // onError
    (errorText) => {
      removeTyping();
      renderMessage(container, 'assistant', errorText);
      msgs.push({ role: 'assistant', content: errorText, mode: 'chat' });
      state.set('currentMessages', msgs);
      state.set('streaming', false);
      updateComposerState();
    }
  );
}

export function loadMessages(data) {
  const container = document.getElementById('messages');
  container.innerHTML = '';
  const msgs = data.messages || [];
  state.set('currentMessages', msgs);
  for (const msg of msgs) {
    renderMessage(container, msg.role, msg.content);
  }
  // If there's a reply but no assistant message
  if (data.reply && !msgs.some(m => m.role === 'assistant')) {
    renderMessage(container, 'assistant', data.reply);
    msgs.push({ role: 'assistant', content: data.reply, mode: 'chat' });
    state.set('currentMessages', msgs);
  }
}

function updateComposerState() {
  const sendBtn = document.getElementById('send-btn');
  const cancelBtn = document.getElementById('cancel-btn');
  const streaming = state.get('streaming');
  if (sendBtn) sendBtn.style.display = streaming ? 'none' : 'flex';
  if (cancelBtn) cancelBtn.style.display = streaming ? 'flex' : 'none';
}

export function setupCancel() {
  document.getElementById('cancel-btn')?.addEventListener('click', () => {
    import('../api.js').then(m => m.cancelStream());
    state.set('streaming', false);
    updateComposerState();
    removeTyping();
  });
}
```

### FILE: scripts/chat-server/frontend/js/components/composer.js

```javascript
import { state } from '../state.js';
import { sendMessage } from './message.js';

export function initComposer() {
  const input = document.getElementById('composer-input');
  const sendBtn = document.getElementById('send-btn');
  const cancelBtn = document.getElementById('cancel-btn');

  // Auto-resize
  input.addEventListener('input', () => {
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 200) + 'px';
    sendBtn.disabled = !input.value.trim() || state.get('streaming');
  });

  // Enter to send
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      doSend();
    }
  });

  sendBtn.addEventListener('click', doSend);
  cancelBtn.addEventListener('click', () => {
    import('./message.js').then(m => {
      m.removeTyping();
      state.set('streaming', false);
      sendBtn.style.display = 'flex';
      cancelBtn.style.display = 'none';
      sendBtn.disabled = !input.value.trim();
    });
  });

  // Model select
  const modelSelect = document.getElementById('model-select');
  if (modelSelect) {
    modelSelect.addEventListener('change', () => {
      state.set('model', modelSelect.value);
    });
  }

  // Project select
  const projectSelect = document.getElementById('project-select');
  if (projectSelect) {
    projectSelect.addEventListener('change', () => {
      state.set('currentProject', projectSelect.value);
      const event = new CustomEvent('project-change');
      document.dispatchEvent(event);
    });
  }
}

export function setupProjectSelect(projects) {
  const sel = document.getElementById('project-select');
  if (!sel) return;
  sel.innerHTML = '';
  for (const p of projects) {
    const opt = document.createElement('option');
    opt.value = p.id;
    opt.textContent = p.name;
    if (p.id === state.get('currentProject')) opt.selected = true;
    sel.appendChild(opt);
  }
}

function doSend() {
  const input = document.getElementById('composer-input');
  const text = input.value.trim();
  if (!text || state.get('streaming')) return;
  input.value = '';
  input.style.height = 'auto';
  document.getElementById('send-btn').disabled = true;
  sendMessage(text);
}
```

### FILE: scripts/chat-server/frontend/js/components/settings.js

```javascript
import { state } from '../state.js';
import { loadProjects } from '../api.js';
import { setupProjectSelect } from './composer.js';

export async function openSettings() {
  // Remove existing dialog if any
  document.querySelector('.settings-dialog')?.remove();
  document.querySelector('.dialog-overlay')?.remove();

  const overlay = document.createElement('div');
  overlay.className = 'dialog-overlay';
  overlay.addEventListener('click', closeSettings);
  document.body.appendChild(overlay);

  const projects = await loadProjects();

  const dialog = document.createElement('div');
  dialog.className = 'settings-dialog';
  dialog.innerHTML =
    '<div class="settings-panel">' +
    '<div class="settings-header">' +
    '<span class="settings-title">设置</span>' +
    '<button class="settings-close" id="settings-close-btn">×</button>' +
    '</div>' +
    '<div class="settings-body">' +
    '<div class="settings-group">' +
    '<div class="settings-group-title">外观</div>' +
    '<div class="settings-row">' +
    '<span class="settings-label">主题</span>' +
    '<select class="settings-select" id="settings-theme">' +
    '<option value="system">跟随系统</option>' +
    '<option value="light">浅色</option>' +
    '<option value="dark">深色</option>' +
    '</select>' +
    '</div>' +
    '</div>' +
    '<div class="settings-group">' +
    '<div class="settings-group-title">项目</div>' +
    '<div class="settings-row">' +
    '<span class="settings-label">当前项目</span>' +
    '<select class="settings-select" id="settings-project"></select>' +
    '</div>' +
    '</div>' +
    '<div class="settings-group">' +
    '<div class="settings-group-title">关于</div>' +
    '<div class="settings-row">' +
    '<span class="settings-label">版本</span>' +
    '<span style="font-size:13px;color:var(--ccc-text-muted)">CCC Chat v2</span>' +
    '</div>' +
    '</div>' +
    '</div>' +
    '</div>';

  document.body.appendChild(dialog);

  // Theme select
  const themeSelect = document.getElementById('settings-theme');
  const savedScheme = localStorage.getItem('opencode-color-scheme') || 'system';
  themeSelect.value = savedScheme;
  themeSelect.addEventListener('change', () => {
    const val = themeSelect.value;
    localStorage.setItem('opencode-color-scheme', val);
    applyTheme(val);
  });

  // Project select
  const projSelect = document.getElementById('settings-project');
  for (const p of projects) {
    const opt = document.createElement('option');
    opt.value = p.id;
    opt.textContent = p.name;
    if (p.id === state.get('currentProject')) opt.selected = true;
    projSelect.appendChild(opt);
  }
  projSelect.addEventListener('change', () => {
    state.set('currentProject', projSelect.value);
    document.getElementById('project-select').value = projSelect.value;
    const event = new CustomEvent('project-change');
    document.dispatchEvent(event);
  });

  document.getElementById('settings-close-btn')?.addEventListener('click', closeSettings);

  // Close on Escape
  const escHandler = (e) => {
    if (e.key === 'Escape') { closeSettings(); document.removeEventListener('keydown', escHandler); }
  };
  document.addEventListener('keydown', escHandler);
}

function closeSettings() {
  document.querySelector('.settings-dialog')?.remove();
  document.querySelector('.dialog-overlay')?.remove();
}

function applyTheme(scheme) {
  const isDark = scheme === 'dark' || (scheme === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);
  document.documentElement.setAttribute('data-theme', isDark ? 'dark' : 'light');
  const themeBtn = document.getElementById('theme-btn');
  if (themeBtn) themeBtn.textContent = isDark ? '☀️' : '🌙';
}
```

### FILE: scripts/chat-server/frontend/js/app.js

```javascript
import { state } from './state.js';
import { generateId } from './utils.js';
import { loadProjects, loadSession, deleteSession } from './api.js';
import { initTitlebar, renderTabs } from './components/titlebar.js';
import { initComposer, setupProjectSelect } from './components/composer.js';
import { loadMessages, setupCancel } from './components/message.js';
import { refreshSidebar, setupSidebarSearch } from './components/sidebar.js';

async function init() {
  initTitlebar();
  initComposer();
  setupCancel();
  setupSidebarSearch();

  // Load projects
  try {
    const projects = await loadProjects();
    setupProjectSelect(projects);
  } catch (e) {
    console.warn('Failed to load projects', e);
  }

  // Create initial tab
  const tabId = generateId();
  const tabs = [{ id: tabId, title: '新对话' }];
  state.set('tabs', tabs);
  state.set('activeTabId', tabId);
  state.set('currentSessionId', tabId);
  renderTabs(tabs, tabId);

  // Refresh history
  refreshSidebar();

  // Tab events
  document.addEventListener('new-tab', () => {
    const id = generateId();
    const tabs = state.get('tabs') || [];
    tabs.push({ id, title: '新对话' });
    state.set('tabs', tabs);
    state.set('activeTabId', id);
    state.set('currentSessionId', id);
    state.set('currentMessages', []);
    document.getElementById('messages').innerHTML = '';
    document.getElementById('composer-input').value = '';
    document.getElementById('send-btn').disabled = true;
    renderTabs(tabs, id);
  });

  document.addEventListener('switch-tab', (e) => {
    const { id } = e.detail;
    const tabs = state.get('tabs') || [];
    state.set('activeTabId', id);
    // For now, all tabs share the same messages
    renderTabs(tabs, id);
  });

  document.addEventListener('close-tab', (e) => {
    let tabs = state.get('tabs') || [];
    const { id } = e.detail;
    if (tabs.length <= 1) return;
    tabs = tabs.filter(t => t.id !== id);
    state.set('tabs', tabs);
    const activeId = state.get('activeTabId');
    if (activeId === id) {
      const newActive = tabs[tabs.length - 1].id;
      state.set('activeTabId', newActive);
    }
    renderTabs(tabs, state.get('activeTabId'));
  });

  document.addEventListener('load-session', async (e) => {
    const { id } = e.detail;
    try {
      const data = await loadSession(id, state.get('currentProject'));
      state.set('currentSessionId', id);
      loadMessages(data);

      // Update tab title
      const tabs = state.get('tabs') || [];
      const tab = tabs.find(t => t.id === state.get('activeTabId'));
      if (tab) {
        tab.title = data.title || '对话';
        renderTabs(tabs, state.get('activeTabId'));
      }

      // Update sidebar active
      document.querySelectorAll('.session-item').forEach(el => {
        el.classList.toggle('active', el.dataset.sid === id);
      });

      // Close mobile sidebar
      document.getElementById('sidebar')?.classList.remove('open');
      document.querySelector('.sidebar-overlay')?.classList.remove('show');
    } catch (e) {
      console.warn('Failed to load session', e);
    }
  });

  document.addEventListener('project-change', () => {
    const container = document.getElementById('messages');
    container.innerHTML = '';
    state.set('currentMessages', []);
    state.set('currentSessionId', generateId());
    refreshSidebar();
  });
}

document.addEventListener('DOMContentLoaded', init);
```

### FILE: scripts/chat-server/frontend/index.html

```html
<!DOCTYPE html>
<html lang="zh-CN" data-theme="light">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="color-scheme" content="light dark">
<title>CCC Chat</title>
<link rel="stylesheet" href="/css/variables.css">
<link rel="stylesheet" href="/css/base.css">
<link rel="stylesheet" href="/css/themes.css">
<link rel="stylesheet" href="/css/components.css">
</head>
<body>
<div id="app">
  <div id="titlebar">
    <div id="tabs" style="display:flex;align-items:center;gap:2px;flex:1;overflow-x:auto;overflow-y:hidden;"></div>
    <div class="titlebar-spacer"></div>
    <button class="titlebar-btn" id="new-tab-btn" title="新对话">+</button>
    <button class="titlebar-btn" id="settings-btn" title="设置">⚙️</button>
    <button class="titlebar-btn" id="theme-btn" title="切换主题">🌙</button>
  </div>
  <div id="layout">
    <div id="sidebar">
      <div class="sidebar-header">
        <input class="sidebar-search" id="sidebar-search" type="text" placeholder="搜索对话...">
      </div>
      <div class="sidebar-list" id="session-list">
        <div class="skeleton" style="height:48px;margin:8px 16px;"></div>
        <div class="skeleton" style="height:48px;margin:8px 16px;"></div>
        <div class="skeleton" style="height:48px;margin:8px 16px;"></div>
      </div>
    </div>
    <div id="chat-panel">
      <div id="messages"></div>
      <button class="scroll-fab" id="scroll-fab">↓</button>
      <div id="composer">
        <div id="composer-inner">
          <div class="composer-toolbar">
            <select class="model-select" id="model-select">
              <option value="flash">flash</option>
              <option value="code">code</option>
            </select>
            <span class="context-indicator" id="context-indicator">项目: <span id="project-display">CCC</span></span>
          </div>
          <div class="composer-input-wrap">
            <textarea id="composer-input" rows="1" placeholder="输入消息..." autofocus></textarea>
            <button class="composer-btn" id="cancel-btn" title="取消">✕</button>
            <button class="composer-btn" id="send-btn" title="发送" disabled>↑</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</div>
<div class="sidebar-overlay" onclick="toggleMobileSidebar()"></div>
<select id="project-select" style="display:none;"></select>

<script>
// Mobile sidebar toggle (globally accessible)
function toggleMobileSidebar() {
  document.getElementById('sidebar')?.classList.remove('open');
  document.querySelector('.sidebar-overlay')?.classList.remove('show');
}

// Copy code button (globally accessible)
function copyCode(btn) {
  const pre = btn.closest('.code-block-wrap')?.querySelector('pre');
  const code = pre ? (pre.textContent || pre.innerText) : '';
  navigator.clipboard.writeText(code).then(() => {
    const orig = btn.textContent;
    btn.textContent = '已复制';
    setTimeout(() => btn.textContent = orig, 1500);
  }).catch(() => {
    btn.textContent = '复制失败';
  });
}

// Scroll FAB
document.addEventListener('DOMContentLoaded', function() {
  const fab = document.getElementById('scroll-fab');
  const messages = document.getElementById('messages');
  if (fab && messages) {
    messages.addEventListener('scroll', function() {
      const atBottom = messages.scrollTop + messages.clientHeight >= messages.scrollHeight - 200;
      fab.classList.toggle('show', !atBottom);
    });
    fab.addEventListener('click', function() {
      messages.scrollTop = messages.scrollHeight;
      fab.classList.remove('show');
    });
  }
});
</script>
<script type="module" src="/js/app.js"></script>
</body>
</html>
```

---

## Step 7: 验证

所有文件写入后，运行以下命令验证：

```bash
cd /Users/apple/program/CCC

# 1. Python 语法检查
python3 -c "import ast; ast.parse(open('scripts/ccc-chat-server.py').read()); print('OK: entry')"
python3 -c "import ast; ast.parse(open('scripts/chat-server/config.py').read()); print('OK: config')"
python3 -c "import ast; ast.parse(open('scripts/chat-server/models.py').read()); print('OK: models')"
python3 -c "import ast; ast.parse(open('scripts/chat-server/auth.py').read()); print('OK: auth')"
python3 -c "import ast; ast.parse(open('scripts/chat-server/services/session_store.py').read()); print('OK: session_store')"
python3 -c "import ast; ast.parse(open('scripts/chat-server/services/claude_client.py').read()); print('OK: claude_client')"
python3 -c "import ast; ast.parse(open('scripts/chat-server/services/board_client.py').read()); print('OK: board_client')"
python3 -c "import ast; ast.parse(open('scripts/chat-server/routers/projects.py').read()); print('OK: projects')"
python3 -c "import ast; ast.parse(open('scripts/chat-server/routers/chat.py').read()); print('OK: chat router')"
python3 -c "import ast; ast.parse(open('scripts/chat-server/routers/sessions.py').read()); print('OK: sessions router')"
python3 -c "import ast; ast.parse(open('scripts/chat-server/routers/files.py').read()); print('OK: files router')"
python3 -c "import ast; ast.parse(open('scripts/chat-server/routers/board.py').read()); print('OK: board router')"
python3 -c "import ast; ast.parse(open('scripts/chat-server/app.py').read()); print('OK: app')"

# 2. Python import 验证
python3 -c "from scripts.chat_server.config import *; print('OK: import config')"
python3 -c "from scripts.chat_server.models import *; print('OK: import models')"
python3 -c "from scripts.chat_server.auth import *; print('OK: import auth')"
python3 -c "from scripts.chat_server.app import create_app; print('OK: import app')"

# 3. FastAPI 启动测试（3 秒后退出）
timeout 5 python3 -c "
from scripts.chat_server.app import create_app
app = create_app()
print('FastAPI app created OK')
print('Routes:')
for route in app.routes:
    if hasattr(route, 'methods') and hasattr(route, 'path'):
        print(f'  {route.methods} {route.path}')
" 2>&1 || true

# 4. 前端文件检查
ls -la scripts/chat-server/frontend/index.html
ls -la scripts/chat-server/frontend/css/
ls -la scripts/chat-server/frontend/js/
ls -la scripts/chat-server/frontend/js/components/

echo ""
echo "=== 全部验证完成 ==="
```

---

## 完成

如果全部通过，运行新 chat-server：

```bash
cd /Users/apple/program/CCC
python3 scripts/ccc-chat-server.py --no-open
```

然后在另一个终端验证：

```bash
curl -u ccc:claude2026 http://localhost:8084/api/projects
curl -u ccc:claude2026 http://localhost:8084/ | head -5
```

测试通过后，浏览器打开 `http://localhost:8084` 查看新 UI。
