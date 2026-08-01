"""Hub 会话 token 端点 — /api/auth/*（网页鉴权整改，窗口 A 前端登录页对接契约）。

契约（给前端/窗口 A）：
- POST /api/auth/token    Basic 凭证 → {token, role, expires_at}
  role: operator（写权限）| viewer（只读，需 CCC_HUB_VIEWER_PASS 且 user=viewer）
- POST /api/auth/logout   Bearer token → 吊销
- GET  /api/auth/session  Bearer/Basic → {valid, scheme, role}
写操作（/api/ops/daily-review/run、/api/transfer、/api/board 写端点等）默认要求
role=operator；viewer token 访问返回 403。
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request

from ..auth import (
    _client_ip,
    _issue_session,
    _principal_from_basic,
    _rate_limit_auth,
    _SESSION_TTL_S,
    check_auth,
    revoke_session,
)

router = APIRouter()


def _expires_at_iso() -> str:
    """token 过期时间（epoch + TTL）→ ISO 字符串。"""
    return (
        datetime.fromtimestamp(time.time() + _SESSION_TTL_S, tz=timezone.utc)
        .isoformat()
    )


@router.post("/api/auth/token")
async def login(request: Request):
    """Basic 凭证换发会话 token（Bearer）。401 on invalid/missing。"""
    ip = _client_ip(request)
    _rate_limit_auth(ip)
    principal = _principal_from_basic(request.headers.get("Authorization", ""))
    if principal is None:
        raise HTTPException(
            status_code=401,
            headers={"WWW-Authenticate": 'Basic realm="CCC Chat"'},
        )
    role = principal["role"]
    token = _issue_session(role)
    return {
        "token": token,
        "role": role,
        "scheme": "bearer",
        "expires_at": _expires_at_iso(),
        "ttl_s": int(_SESSION_TTL_S),
    }


@router.post("/api/auth/logout")
async def logout(request: Request):
    """吊销当前 Bearer token（幂等）。Basic 调用无 token 可吊销。"""
    principal = check_auth(request)
    if principal.get("scheme") == "bearer" and principal.get("token"):
        revoke_session(principal["token"])
    return {"ok": True}


@router.get("/api/auth/session")
async def session_info(request: Request):
    """探测当前凭证是否有效（Bearer/Basic 均可）。"""
    principal = check_auth(request)
    return {
        "valid": True,
        "scheme": principal["scheme"],
        "role": principal["role"],
    }
