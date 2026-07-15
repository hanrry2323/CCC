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
