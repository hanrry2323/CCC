#!/usr/bin/env python3
"""CCC Desktop local Agent Sidecar — loop-code on localhost.

Hot path: Desktop → 127.0.0.1:7788 → ClaudeSDKClient → vendor/loop-code/cli → Router
Hub remains for threads sync / transfer / flow SSE (not on the chat hot path).

Security (2026-07-19):
  - /api/chat + /warm require CCC_AGENT_TOKEN (Bearer or X-CCC-Agent-Token)
  - project_path 必须落在 allowlist 根下
  - /health 不暴露完整 cli 路径

Usage:
  CCC_AGENT_PORT=7788 CCC_AGENT_TOKEN=... ANTHROPIC_BASE_URL=http://192.168.3.116:4000 \\
    .venv-hub/bin/python scripts/ccc-agent-sidecar.py
"""

from __future__ import annotations

import asyncio
import hmac
import json
import os
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

# Ensure loop-code before chat_server config resolves CLI
os.environ.setdefault("CCC_EXECUTOR", "loop-code")
os.environ.setdefault(
    "ANTHROPIC_BASE_URL",
    os.environ.get("CCC_AGENT_ROUTER", "http://192.168.3.116:4000"),
)

from fastapi import FastAPI, Request  # noqa: E402
from fastapi.responses import JSONResponse, StreamingResponse  # noqa: E402
import uvicorn  # noqa: E402

from chat_server.services.claude_client import (  # noqa: E402
    resolve_chat_timeouts,
    resolve_model,
    stream_chat,
)
from chat_server.hub_voice import wrap_hub_prompt  # noqa: E402
from _claude_cli import resolve_claude_cli  # noqa: E402

HOST = os.environ.get("CCC_AGENT_HOST", "127.0.0.1")
PORT = int(os.environ.get("CCC_AGENT_PORT", "7788"))
DEFAULT_CWD = os.environ.get("CCC_AGENT_CWD", str(ROOT))

app = FastAPI(title="CCC Agent Sidecar", docs_url=None, redoc_url=None)


def _load_token_file() -> str:
    p = Path.home() / ".ccc" / "agent-token"
    try:
        if p.is_file():
            return p.read_text(encoding="utf-8").strip()
    except OSError:
        pass
    return ""


def _effective_token() -> str:
    return (os.environ.get("CCC_AGENT_TOKEN") or "").strip() or _load_token_file()


def _check_agent_auth(request: Request) -> JSONResponse | None:
    """Require shared secret for mutating/chat endpoints."""
    expected = _effective_token()
    if not expected:
        return JSONResponse(
            {
                "detail": "CCC_AGENT_TOKEN unset — run: bash scripts/install-agent-sidecar-plist.sh --start",
            },
            status_code=503,
        )
    auth = (request.headers.get("authorization") or "").strip()
    got = ""
    if auth.lower().startswith("bearer "):
        got = auth[7:].strip()
    if not got:
        got = (request.headers.get("x-ccc-agent-token") or "").strip()
    if not got or not hmac.compare_digest(got, expected):
        return JSONResponse({"detail": "unauthorized"}, status_code=401)
    return None


def _allowed_roots() -> list[Path]:
    """project_path 白名单根。"""
    roots: list[Path] = []
    raw = os.environ.get("CCC_AGENT_ALLOWED_ROOTS", "").strip()
    if raw:
        for part in raw.split(":"):
            part = part.strip()
            if part:
                roots.append(Path(part).expanduser().resolve())
    else:
        home = Path.home()
        roots.extend(
            [
                (home / "program").resolve(),
                Path(DEFAULT_CWD).expanduser().resolve(),
                ROOT.resolve(),
            ]
        )
        # Desktop Application Support sessions cwd sometimes under Library
        roots.append((home / "Library" / "Application Support" / "CCCDesktop").resolve())
    return roots


def _path_allowed(project_path: str) -> bool:
    try:
        cand = Path(project_path).expanduser().resolve()
    except OSError:
        return False
    if not cand.is_dir():
        return False
    for root in _allowed_roots():
        try:
            cand.relative_to(root)
            return True
        except ValueError:
            continue
    return False


@app.get("/health")
async def health():
    cli = resolve_claude_cli(require=False) or ""
    # 最小化暴露：只回 basename，不回完整路径
    cli_name = Path(cli).name if cli else ""
    return {
        "ok": True,
        "product": "CCC Agent Sidecar",
        "agent_runtime": "loop-code" if "loop-code" in cli.replace("\\", "/") else "claude",
        "agent_cli": cli_name,
        "auth_required": bool(_effective_token()),
        "default_cwd": DEFAULT_CWD,
    }


@app.post("/warm")
async def warm(request: Request):
    """Keep-warm：预连 ClaudeSDKClient live slot（真正省掉首条 15–30s 冷启动）。

    body 可选：project_path / session_id / tool_mode / model
    无 project_path 时只检查 cli（兼容旧客户端）。
    """
    denied = _check_agent_auth(request)
    if denied is not None:
        return denied
    import time

    t0 = time.perf_counter()
    cli = resolve_claude_cli(require=False) or ""
    cli_ok = bool(cli) and Path(cli).exists()
    body: dict = {}
    try:
        raw = await request.json()
        if isinstance(raw, dict):
            body = raw
    except Exception:
        body = {}

    project_path = str(body.get("project_path") or "").strip()
    session_id = str(body.get("session_id") or "conversation").strip() or "conversation"
    tool_mode = str(body.get("tool_mode") or "discuss").strip().lower() or "discuss"
    model = str(body.get("model") or "flash").strip().lower() or "flash"

    slot_info: dict = {}
    if project_path and _path_allowed(project_path) and cli_ok:
        from chat_server.services.claude_session import session_manager

        try:
            slot_info = await session_manager.warm(
                project_path,
                session_id,
                model=model,
                tool_mode=tool_mode,
            )
        except Exception as exc:
            slot_info = {"ok": False, "error": str(exc), "connected": False}

    ms = int((time.perf_counter() - t0) * 1000)
    ok = cli_ok and (not project_path or bool(slot_info.get("ok")))
    return {
        "ok": ok,
        "warmed_at": time.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
        "ttfb_ms": ms,
        "agent_cli": Path(cli).name if cli else "",
        "slot": slot_info or None,
    }


@app.post("/api/session/drop")
async def session_drop(request: Request):
    """丢弃 ClaudeSDKClient live slot（重置对话用）。

    不删 loop-code 的 claude_session_id 历史，只让下次 query 冷启动。
    """
    denied = _check_agent_auth(request)
    if denied is not None:
        return denied
    body = await request.json()
    project_path = (body.get("project_path") or "").strip()
    session_id = str(body.get("session_id") or "local")
    if not project_path or not _path_allowed(project_path):
        return JSONResponse(
            {"detail": "project_path required and must be allowed"},
            status_code=400,
        )
    from chat_server.services.claude_session import session_manager, _slot_key

    tool_mode = str(body.get("tool_mode") or "discuss").strip().lower() or "discuss"
    key = _slot_key(project_path, session_id, tool_mode)
    dropped = await session_manager._drop_slot(key, reason="user-reset")
    return {"ok": True, "dropped": bool(dropped), "key": key}


@app.post("/api/session/compact")
async def session_compact(request: Request):
    """压缩 agent session：drop slot + 存摘要待下次 query 注入。"""
    denied = _check_agent_auth(request)
    if denied is not None:
        return denied
    body = await request.json()
    project_path = (body.get("project_path") or "").strip()
    session_id = str(body.get("session_id") or "local")
    summary = body.get("summary")
    tool_mode = str(body.get("tool_mode") or "discuss").strip().lower() or "discuss"
    model = str(body.get("model") or "flash").strip().lower() or "flash"
    if not project_path or not _path_allowed(project_path):
        return JSONResponse(
            {"detail": "project_path required and must be allowed"},
            status_code=400,
        )
    from chat_server.services.claude_session import session_manager

    used = await session_manager.compact_session(
        project_path=project_path,
        hub_session_id=session_id,
        summary=summary,
        tool_mode=tool_mode,
        model=model,
    )
    return {"ok": True, "summary": used, "session_id": session_id}


@app.post("/api/chat")
async def chat(request: Request):
    denied = _check_agent_auth(request)
    if denied is not None:
        return denied

    body = await request.json()
    messages = body.get("messages") or []
    session_id = str(body.get("session_id") or body.get("thread_id") or "local")
    model = resolve_model(body.get("model"))
    project_path = (
        (body.get("project_path") or "").strip()
        or DEFAULT_CWD
    )
    if not _path_allowed(project_path):
        return JSONResponse(
            {
                "detail": (
                    f"project_path not allowed: {project_path}. "
                    "Must be under CCC_AGENT_ALLOWED_ROOTS (default ~/program)."
                )
            },
            status_code=403,
        )

    user_msgs = [m for m in messages if m.get("role") == "user"]
    if not user_msgs:
        return JSONResponse({"detail": "messages required"}, status_code=400)
    prompt = (user_msgs[-1].get("content") or "").strip()
    if not prompt:
        return JSONResponse({"detail": "prompt required"}, status_code=400)

    prompt_mode = str(body.get("prompt_mode") or body.get("promptMode") or "").strip()
    prompt = wrap_hub_prompt(prompt, mode=prompt_mode or None)
    from chat_server import config as _agent_cfg

    tool_mode = _agent_cfg.resolve_tool_mode(
        body.get("tool_mode") or body.get("toolMode"),
        user_text=prompt,
    )
    idle_s, max_s = resolve_chat_timeouts(body.get("timeout"))
    client_gone = {"v": False}

    async def _watch():
        try:
            while not client_gone["v"]:
                if await request.is_disconnected():
                    client_gone["v"] = True
                    return
                await asyncio.sleep(0.35)
        except asyncio.CancelledError:
            return

    async def generate():
        watch = asyncio.create_task(_watch(), name="ccc-agent-disconnect")
        try:
            async for event in stream_chat(
                prompt,
                project_path,
                lambda: client_gone["v"],
                timeout=body.get("timeout"),
                model=model,
                resume_session_id=body.get("claude_session_id"),
                idle_timeout=idle_s,
                max_timeout=max_s,
                hub_session_id=session_id,
                tool_mode=tool_mode,
            ):
                evt = event.get("type")
                if evt == "ping":
                    yield f": ping {event.get('ts', '')}\n\n"
                    yield f"data: {json.dumps(event)}\n\n"
                    continue
                if evt == "done":
                    partial = bool(event.get("partial")) or client_gone["v"]
                    payload = {
                        "type": "done",
                        "session_id": session_id,
                        "claude_session_id": event.get("claude_session_id") or "",
                        "partial": partial,
                        "via": "local-agent",
                    }
                    yield f"data: {json.dumps(payload)}\n\n"
                    continue
                yield f"data: {json.dumps(event)}\n\n"
        except (GeneratorExit, asyncio.CancelledError):
            client_gone["v"] = True
            raise
        finally:
            watch.cancel()
            try:
                await watch
            except (asyncio.CancelledError, Exception):
                pass

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "X-CCC-Agent": "local-sidecar",
        },
    )


def main() -> None:
    cli = resolve_claude_cli(require=True)
    tok = _effective_token()
    if not tok:
        # 启动时自动生成，避免未装 plist 时裸奔
        tok = secrets.token_hex(32)
        token_path = Path.home() / ".ccc" / "agent-token"
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(tok + "\n", encoding="utf-8")
        os.chmod(token_path, 0o600)
        os.environ["CCC_AGENT_TOKEN"] = tok
        print(f"[ccc-agent] generated token → {token_path}", flush=True)
    print(f"[ccc-agent] cli={cli}", flush=True)
    print(f"[ccc-agent] router={os.environ.get('ANTHROPIC_BASE_URL')}", flush=True)
    print(f"[ccc-agent] auth=required listen=http://{HOST}:{PORT}", flush=True)
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")


if __name__ == "__main__":
    main()
