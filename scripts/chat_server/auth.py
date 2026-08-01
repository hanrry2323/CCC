import base64
import hmac
import os
import time
from collections import defaultdict

from fastapi import Request, HTTPException
from . import config

# IP → 失败时间戳列表（滑动窗口）
_auth_failures: dict[str, list[float]] = defaultdict(list)
_AUTH_WINDOW_S = 60.0
_AUTH_MAX_FAILS = 20
# 每次 check_auth 递增；每 _AUTH_PRUNE_INTERVAL 次全局清扫过期桶，
# 防轮换 IP 攻击者让 _auth_failures 无界增长（冷 IP 桶永不自行清理）。
_AUTH_PRUNE_INTERVAL = 100
_auth_call_count = 0

# v0.51.0 (P1-1): 默认不信任 X-Forwarded-For（防伪造绕过 IP 限速）。
# 仅当部署在反向代理后且显式配置 CCC_TRUST_PROXY=1 时启用。

def _trust_proxy_enabled() -> bool:
    return os.environ.get("CCC_TRUST_PROXY", "").strip() == "1"


def _client_ip(request: Request) -> str:
    if _trust_proxy_enabled():
        xff = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
        if xff:
            return xff
    if request.client:
        return request.client.host or "unknown"
    return "unknown"


def _sweep_stale_auth_buckets(now: float) -> None:
    """周期清理：桶内最近失败已滑出窗口（或空）的 IP 直接移除。"""
    stale = [
        ip
        for ip, ts in _auth_failures.items()
        if not ts or now - ts[-1] >= _AUTH_WINDOW_S
    ]
    for ip in stale:
        _auth_failures.pop(ip, None)


def _rate_limit_auth(ip: str) -> None:
    global _auth_call_count
    now = time.monotonic()
    _auth_call_count += 1
    if _auth_call_count % _AUTH_PRUNE_INTERVAL == 0:
        _sweep_stale_auth_buckets(now)
    bucket = [t for t in _auth_failures[ip] if now - t < _AUTH_WINDOW_S]
    _auth_failures[ip] = bucket
    if len(bucket) >= _AUTH_MAX_FAILS:
        raise HTTPException(status_code=429, detail="too many auth failures")


def check_auth(request: Request):
    ip = _client_ip(request)
    _rate_limit_auth(ip)
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Basic "):
        _auth_failures[ip].append(time.monotonic())
        raise HTTPException(
            status_code=401,
            headers={"WWW-Authenticate": 'Basic realm="CCC Chat"'},
        )
    try:
        decoded = base64.b64decode(auth[6:]).decode()
        user, passwd = decoded.split(":", 1)
    except Exception:
        _auth_failures[ip].append(time.monotonic())
        raise HTTPException(status_code=401)
    user_ok = hmac.compare_digest(user, config.AUTH_USER)
    pass_ok = hmac.compare_digest(passwd, config.AUTH_PASS)
    if not (user_ok and pass_ok):
        _auth_failures[ip].append(time.monotonic())
        raise HTTPException(status_code=401)
    return True


def board_headers() -> dict:
    headers = {"Content-Type": "application/json"}
    if config.BOARD_TOKEN:
        headers["Authorization"] = f"Bearer {config.BOARD_TOKEN}"
    return headers
