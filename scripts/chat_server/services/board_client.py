"""board_client — Hub → Board API 代理客户端（Phase 2.1：复用 httpx 连接 + ETag/304）"""
import json
import hashlib

import httpx
from fastapi.responses import Response

from .. import config
from ..auth import board_headers

# 模块级共享 client：复用连接池，避免每次请求重建 TCP/TLS
_client: httpx.AsyncClient | None = None
# ETag 缓存：url -> (etag, content, content_hash)；上限防长期运行泄漏
_etag_cache: dict[str, tuple[str, bytes, str]] = {}
_ETAG_CACHE_MAX = 128


def _etag_cache_put(key: str, value: tuple[str, bytes, str]) -> None:
    if key in _etag_cache:
        _etag_cache[key] = value
        return
    if len(_etag_cache) >= _ETAG_CACHE_MAX:
        # 简单 FIFO：丢掉最早插入的键
        try:
            oldest = next(iter(_etag_cache))
            del _etag_cache[oldest]
        except StopIteration:
            pass
    _etag_cache[key] = value


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
            cache_key = url
            if params:
                # 稳定 key：参数排序，避免同参不同序 miss 缓存
                q = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
                cache_key = f"{url}?{q}"
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
                _etag_cache_put(
                    cache_key, (etag, content, hashlib.md5(content).hexdigest())
                )
            return Response(
                content=content,
                status_code=resp.status_code,
                media_type="application/json",
                headers={"ETag": etag} if etag else {},
            )
        elif method.upper() == "POST":
            resp = await client.post(url, json=json_body, headers=headers)
            return Response(
                content=resp.content,
                status_code=resp.status_code,
                media_type="application/json",
            )
        elif method.upper() == "PUT":
            resp = await client.put(url, json=json_body, headers=headers)
            return Response(
                content=resp.content,
                status_code=resp.status_code,
                media_type="application/json",
            )
        elif method.upper() == "DELETE":
            resp = await client.delete(url, params=params, headers=headers)
            return Response(
                content=resp.content,
                status_code=resp.status_code,
                media_type="application/json",
            )
        else:
            return Response(
                content=json.dumps(
                    {"error": f"unsupported method: {method}"}, ensure_ascii=False
                ),
                status_code=405,
                media_type="application/json",
            )
    except (httpx.ConnectError, httpx.TimeoutException):
        return Response(
            content=json.dumps({"error": "看板服务离线", "detail": "Board Server 不可用"}),
            status_code=503,
            media_type="application/json",
        )
