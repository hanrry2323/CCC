import base64
import hmac
import time
from collections import defaultdict

from fastapi import Request, HTTPException
from . import config

# IP → 失败时间戳列表（滑动窗口）
_auth_failures: dict[str, list[float]] = defaultdict(list)
_AUTH_WINDOW_S = 60.0
_AUTH_MAX_FAILS = 20


def _client_ip(request: Request) -> str:
    xff = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    if xff:
        return xff
    if request.client:
        return request.client.host or "unknown"
    return "unknown"


def _rate_limit_auth(ip: str) -> None:
    now = time.monotonic()
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
