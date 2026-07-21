"""Hub → M1 Desktop Agent Sidecar reverse proxy (Remote Desktop Shell).

Browser talks only to Hub (:7777). Hub injects CCC_AGENT_TOKEN and
forwards to CCC_DESKTOP_AGENT_URL (default http://192.168.3.140:7788).
"""

from __future__ import annotations

import logging
import os
from typing import AsyncIterator
from urllib.parse import urljoin

import httpx
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import StreamingResponse

from ..auth import check_auth

router = APIRouter(prefix="/api/agent", tags=["agent-proxy"])
_log = logging.getLogger("ccc-hub.agent-proxy")

_HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "host",
    "content-length",
}


def _agent_base() -> str:
    return (
        os.environ.get("CCC_DESKTOP_AGENT_URL")
        or os.environ.get("CCC_AGENT_URL")
        or "http://192.168.3.140:7788"
    ).rstrip("/")


def _agent_token() -> str:
    tok = (os.environ.get("CCC_AGENT_TOKEN") or "").strip()
    if tok:
        return tok
    # Fallback: same file Desktop/sidecar use (when Hub runs on M1 for dev)
    path = os.path.expanduser("~/.ccc/agent-token")
    try:
        return open(path, encoding="utf-8").read().strip()
    except OSError:
        return ""


def _upstream_headers(request: Request, *, stream: bool) -> dict[str, str]:
    headers: dict[str, str] = {}
    ct = request.headers.get("content-type")
    if ct:
        headers["content-type"] = ct
    accept = request.headers.get("accept")
    if accept:
        headers["accept"] = accept
    elif stream:
        headers["accept"] = "text/event-stream"
    tok = _agent_token()
    if tok:
        headers["Authorization"] = f"Bearer {tok}"
        headers["X-CCC-Agent-Token"] = tok
    return headers


def _filter_resp_headers(src: httpx.Headers) -> dict[str, str]:
    out: dict[str, str] = {}
    for k, v in src.items():
        if k.lower() in _HOP_BY_HOP:
            continue
        out[k] = v
    return out


@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def proxy_agent(path: str, request: Request):
    """Transparent proxy: /api/agent/<path> → {AGENT}/{path}."""
    check_auth(request)
    base = _agent_base()
    if not _agent_token():
        raise HTTPException(
            status_code=503,
            detail="CCC_AGENT_TOKEN not configured on Hub (need M1 agent-token)",
        )
    target = urljoin(base + "/", path)
    if request.url.query:
        target = f"{target}?{request.url.query}"

    body = await request.body()
    wants_stream = (
        "text/event-stream" in (request.headers.get("accept") or "")
        or path.rstrip("/").endswith("api/chat")
        or path.rstrip("/").endswith("/chat")
    )

    timeout = httpx.Timeout(connect=10.0, read=None if wants_stream else 120.0, write=30.0, pool=10.0)
    headers = _upstream_headers(request, stream=wants_stream)

    if wants_stream:
        client = httpx.AsyncClient(timeout=timeout)

        async def generate() -> AsyncIterator[bytes]:
            try:
                async with client.stream(
                    request.method,
                    target,
                    headers=headers,
                    content=body if body else None,
                ) as resp:
                    if resp.status_code >= 400:
                        err = await resp.aread()
                        yield err
                        return
                    async for chunk in resp.aiter_bytes():
                        if await request.is_disconnected():
                            break
                        yield chunk
            except httpx.RequestError as exc:
                _log.warning("agent proxy stream error %s: %s", target, exc)
                msg = (
                    f'data: {{"type":"error","content":"agent unreachable: {exc}"}}\n\n'
                ).encode()
                yield msg
            finally:
                await client.aclose()

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.request(
                request.method,
                target,
                headers=headers,
                content=body if body else None,
            )
    except httpx.RequestError as exc:
        _log.warning("agent proxy error %s: %s", target, exc)
        raise HTTPException(
            status_code=502,
            detail=f"Desktop agent unreachable at {base}: {exc}",
        ) from exc

    return Response(
        content=resp.content,
        status_code=resp.status_code,
        headers=_filter_resp_headers(resp.headers),
        media_type=resp.headers.get("content-type"),
    )
