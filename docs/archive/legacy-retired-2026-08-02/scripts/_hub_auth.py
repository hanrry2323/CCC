"""Hub 会话 token 统一认证辅助（scripts 侧 Basic → Bearer 迁移，窗口 G）。

所有 scripts/ 下工具与服务统一经此获取 Hub 认证头，不再各自拼 Basic：

- Bearer 获取：POST {hub}/api/auth/token（Basic 凭证一次）→ 内存缓存 + TTL 前刷新
- 401 重取：hub_invalidate() 清缓存，调用方收到 401 后重试一次
- 降级：token 换发失败 → 回退 Basic（开关 off 期间不断链；on 时下游 401 →
  调用方 invalidate + 重试 → 重新换发自愈）
- 凭据解析（与既有脚本完全一致）：
  CCC_HUB_AUTH(user:pass) → CCC_CHAT_USER/CCC_CHAT_PASS → 默认 ccc:ccc
- Hub URL：CCC_HUB_URL → CCC_HUB_BASE → 默认 http://127.0.0.1:17777（可传 base 覆盖）

注意：本模块是「迁移辅助」，不含服务端鉴权逻辑（服务端 auth 只读不动）。
"""

from __future__ import annotations

import base64
import json
import os
import time
import urllib.request
from typing import Any

DEFAULT_HUB = "http://127.0.0.1:17777"
_REFRESH_MARGIN_S = 60.0  # TTL 前 60s 视为过期，提前重取
_FETCH_TIMEOUT_S = 8.0

# base → (token, expires_monotonic)；进程内缓存
_TOKEN_CACHE: dict[str, tuple[str, float]] = {}


def hub_url(base: str | None = None) -> str:
    """解析 Hub base URL。显式 base 优先；否则 CCC_HUB_URL → CCC_HUB_BASE → 默认。"""
    if base and base.strip():
        return base.strip().rstrip("/")
    env = (
        (os.environ.get("CCC_HUB_URL") or "").strip()
        or (os.environ.get("CCC_HUB_BASE") or "").strip()
    )
    return (env or DEFAULT_HUB).rstrip("/")


def hub_creds() -> tuple[str, str]:
    """Hub 凭据 (user, passwd)。CCC_HUB_AUTH(user:pass) → CCC_CHAT_USER/PASS → ccc:ccc。"""
    explicit = (os.environ.get("CCC_HUB_AUTH") or "").strip()
    if explicit:
        user, sep, passwd = explicit.partition(":")
        return (user or "ccc").strip(), (passwd or "ccc").strip() if sep else ""
    user = (os.environ.get("CCC_CHAT_USER") or "ccc").strip() or "ccc"
    passwd = (os.environ.get("CCC_CHAT_PASS") or "ccc").strip() or "ccc"
    return user, passwd


def _basic_value(user: str, passwd: str) -> str:
    return base64.b64encode(f"{user}:{passwd}".encode()).decode()


def basic_headers(base: str | None = None, *, content_type: bool = False) -> dict[str, str]:
    """显式 Basic 头（token 登录换发 / 测试用；普通调用方请用 hub_headers）。"""
    user, passwd = hub_creds()
    h = {"Authorization": f"Basic {_basic_value(user, passwd)}"}
    if content_type:
        h["Content-Type"] = "application/json"
    return h


def _fetch_token(base: str) -> str:
    """POST /api/auth/token（Basic 换 Bearer）。失败返回 ""，不抛（降级由调用方决定）。"""
    user, passwd = hub_creds()
    req = urllib.request.Request(
        hub_url(base).rstrip("/") + "/api/auth/token",
        data=None,
        method="POST",
        headers={"Authorization": f"Basic {_basic_value(user, passwd)}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=_FETCH_TIMEOUT_S) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        data: dict[str, Any] = json.loads(raw) if raw.strip() else {}
    except Exception:
        return ""
    token = str(data.get("token") or "").strip()
    if not token:
        return ""
    try:
        ttl_s = float(data.get("ttl_s") or 3600.0)
    except (TypeError, ValueError):
        ttl_s = 3600.0
    expires = time.monotonic() + max(ttl_s - _REFRESH_MARGIN_S, 60.0)
    _TOKEN_CACHE[hub_url(base)] = (token, expires)
    return token


def hub_bearer(base: str | None = None) -> str:
    """返回有效 Bearer token；缓存命中即返，否则换发。失败返回 ""。"""
    key = hub_url(base)
    cached = _TOKEN_CACHE.get(key)
    now = time.monotonic()
    if cached and now < cached[1]:
        return cached[0]
    return _fetch_token(key)


def hub_invalidate(base: str | None = None) -> None:
    """清缓存（401 重取前调用）。"""
    _TOKEN_CACHE.pop(hub_url(base), None)


def hub_headers(base: str | None = None, *, content_type: bool = False) -> dict[str, str]:
    """统一 Hub 认证头：Bearer 优先；token 换发失败回退 Basic（开关 off 不断链）。"""
    tok = hub_bearer(base)
    if tok:
        h = {"Authorization": f"Bearer {tok}"}
    else:
        h = basic_headers(base)
    if content_type:
        h["Content-Type"] = "application/json"
    return h
