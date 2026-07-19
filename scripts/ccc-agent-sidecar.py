#!/usr/bin/env python3
"""CCC Desktop local Agent Sidecar — loop-code on localhost.

Hot path: Desktop → 127.0.0.1:7788 → ClaudeSDKClient → vendor/loop-code/cli → Router
Hub remains for threads sync / transfer / flow SSE (not on the chat hot path).

Usage:
  CCC_AGENT_PORT=7788 ANTHROPIC_BASE_URL=http://192.168.3.116:4000 \\
    .venv-hub/bin/python scripts/ccc-agent-sidecar.py
"""

from __future__ import annotations

import asyncio
import json
import os
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


@app.get("/health")
async def health():
    cli = resolve_claude_cli(require=False) or ""
    return {
        "ok": True,
        "product": "CCC Agent Sidecar",
        "agent_runtime": "loop-code" if "loop-code" in cli.replace("\\", "/") else "claude",
        "agent_cli": cli,
        "router": os.environ.get("ANTHROPIC_BASE_URL", ""),
        "default_cwd": DEFAULT_CWD,
    }


@app.post("/warm")
async def warm():
    """Keep-warm：确认 cli 可执行 + router 环境；供 Desktop 定时预热。"""
    import time

    t0 = time.perf_counter()
    cli = resolve_claude_cli(require=False) or ""
    ok = bool(cli) and Path(cli).exists()
    router = os.environ.get("ANTHROPIC_BASE_URL", "")
    ms = int((time.perf_counter() - t0) * 1000)
    return {
        "ok": ok,
        "warmed_at": time.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
        "ttfb_ms": ms,
        "agent_cli": cli,
        "router": router,
    }


@app.post("/api/chat")
async def chat(request: Request):
    body = await request.json()
    messages = body.get("messages") or []
    session_id = str(body.get("session_id") or body.get("thread_id") or "local")
    model = resolve_model(body.get("model"))
    project_path = (
        (body.get("project_path") or "").strip()
        or DEFAULT_CWD
    )
    if not Path(project_path).is_dir():
        return JSONResponse(
            {"detail": f"project_path not a directory: {project_path}"},
            status_code=400,
        )

    user_msgs = [m for m in messages if m.get("role") == "user"]
    if not user_msgs:
        return JSONResponse({"detail": "messages required"}, status_code=400)
    prompt = (user_msgs[-1].get("content") or "").strip()
    if not prompt:
        return JSONResponse({"detail": "prompt required"}, status_code=400)

    prompt_mode = str(body.get("prompt_mode") or body.get("promptMode") or "").strip()
    prompt = wrap_hub_prompt(prompt, mode=prompt_mode or None)
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
    print(f"[ccc-agent] cli={cli}", flush=True)
    print(f"[ccc-agent] router={os.environ.get('ANTHROPIC_BASE_URL')}", flush=True)
    print(f"[ccc-agent] listen=http://{HOST}:{PORT}", flush=True)
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")


if __name__ == "__main__":
    main()
