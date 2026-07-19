"""board_client — Hub → Board API 代理客户端（Phase 2.1：复用 httpx 连接 + ETag/304）"""
import json
import hashlib

import httpx
from fastapi.responses import Response

from .. import config
from ..auth import board_headers

# 模块级共享 client：复用连接池，避免每次请求重建 TCP/TLS
_client: httpx.AsyncClient | None = None
# ETag 缓存：url -> (etag, content, content_hash)
_etag_cache: dict[str, tuple[str, bytes, str]] = {}


def get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=10.0, limits=httpx.Limits(max_connections=20))
    return _client


async def close_client() -> None:
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
    _client = None
    _etag_cache.clear()


async def board_proxy(
    method: str,
    path: str,
    params: dict | None = None,
    json_body: dict | None = None,
):
    """代理 Board API 请求。GET 走 ETag/304；POST/PUT 透传。"""
    url = f"{config.BOARD_URL}{path}"
    client = get_client()
    headers = board_headers()
    try:
        if method == "GET":
            # ETag 协商：带 If-None-Match
            cache_key = url + (f"?{params}" if params else "")
            cached = _etag_cache.get(cache_key)
            if cached and cached[0]:
                headers = {**headers, "If-None-Match": cached[0]}
            resp = await client.get(url, params=params, headers=headers)
            # 304 → 返回缓存内容
            if resp.status_code == 304 and cached:
                return Response(
                    content=cached[1],
                    status_code=200,
                    media_type="application/json",
                    headers={"ETag": cached[0]},
                )
            etag = resp.headers.get("ETag") or resp.headers.get("etag")
            content = resp.content
            if etag:
                _etag_cache[cache_key] = (etag, content, hashlib.md5(content).hexdigest())
            return Response(
                content=content,
                status_code=resp.status_code,
                media_type="application/json",
                headers={"ETag": etag} if etag else {},
            )
        else:
            resp = await client.post(url, json=json_body, headers=headers)
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
