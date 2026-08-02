import base64
import hmac
import logging
import os
import secrets
import time
from collections import defaultdict

from fastapi import Request, HTTPException
from . import config

_log = logging.getLogger("ccc.chat_server.auth")

# IP → 失败时间戳列表（滑动窗口）
_auth_failures: dict[str, list[float]] = defaultdict(list)
_AUTH_WINDOW_S = 60.0
_AUTH_MAX_FAILS = 20
# 每次 check_auth 递增；每 _AUTH_PRUNE_INTERVAL 次全局清扫过期桶，
# 防轮换 IP 攻击者让 _auth_failures 无界增长（冷 IP 桶永不自行清理）。
_AUTH_PRUNE_INTERVAL = 100
_auth_call_count = 0

# ---- 会话 token（v0.66 网页鉴权整改）----
# opaque token → {role, created, expires}；内存存储，重启失效（非持久化凭据）。
# role: operator（可写，含 legacy Basic 全权）| viewer（只读，可选 CCC_HUB_VIEWER_PASS 签发）
ROLE_VIEWER = "viewer"
ROLE_OPERATOR = "operator"
_SESSION_TTL_S = 3600.0  # 1h
_sessions: dict[str, dict] = {}
_SESSION_PRUNE_INTERVAL = 64
_session_issue_count = 0


def viewer_password() -> str:
    """可选只读口令：CCC_HUB_VIEWER_PASS。未设 → 无 viewer 登录路径（恒 operator）。"""
    return os.environ.get("CCC_HUB_VIEWER_PASS", "").strip()


def require_bearer() -> bool:
    """CCC_AUTH_REQUIRE_BEARER=1 → 仅 Bearer 会话 token（拒绝 Basic，401）。

    默认 off → Basic 兼容（legacy 全权 + 迁移 debug 日志）。
    每次调用读 env（镜像 viewer_password），测试 monkeypatch 即切两态。
    """
    return os.environ.get("CCC_AUTH_REQUIRE_BEARER", "").strip().lower() in ("1", "true", "yes")


def _issue_session(role: str) -> str:
    global _session_issue_count
    token = secrets.token_urlsafe(32)
    now = time.monotonic()
    _sessions[token] = {
        "role": role,
        "created": now,
        "expires": now + _SESSION_TTL_S,
    }
    _session_issue_count += 1
    if _session_issue_count % _SESSION_PRUNE_INTERVAL == 0:
        _sweep_expired_sessions(now)
    return token


def _sweep_expired_sessions(now: float) -> None:
    stale = [t for t, s in _sessions.items() if now >= s["expires"]]
    for t in stale:
        _sessions.pop(t, None)


def revoke_session(token: str) -> None:
    _sessions.pop(token, None)


def _validate_session_bearer(request: Request) -> dict | None:
    """验证 Bearer 会话 token → principal {scheme:"bearer", role, token}。"""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth[7:].strip()
    if not token:
        return None
    s = _sessions.get(token)
    if not s:
        return None
    now = time.monotonic()
    if now >= s["expires"]:
        _sessions.pop(token, None)
        return None
    return {"scheme": "bearer", "role": s["role"], "token": token}


def _basic_credentials(auth_header: str) -> tuple[str, str] | None:
    """解析 Basic header → (user, passwd)。格式错返回 None。"""
    if not auth_header.startswith("Basic "):
        return None
    try:
        decoded = base64.b64decode(auth_header[6:]).decode()
        user, passwd = decoded.split(":", 1)
        return user, passwd
    except Exception:
        return None


def _principal_from_basic(auth_header: str) -> dict | None:
    """Basic 凭证 → principal。operator=Hub 主账密（legacy 全权）；
    viewer=可选 CCC_HUB_VIEWER_PASS（user 为 viewer）。"""
    creds = _basic_credentials(auth_header)
    if creds is None:
        return None
    user, passwd = creds
    if user == config.AUTH_USER and hmac.compare_digest(passwd, config.AUTH_PASS):
        return {"scheme": "basic", "role": ROLE_OPERATOR}
    vp = viewer_password()
    if vp and user == "viewer" and hmac.compare_digest(passwd, vp):
        return {"scheme": "basic", "role": ROLE_VIEWER}
    return None

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


def check_auth(request: Request) -> dict:
    """验证 Basic（legacy → operator）或 Bearer 会话 token。

    返回 principal {scheme, role}。invalid/missing → 401。
    request.state.ccc_auth_scheme 供响应中间件打 Basic 迁移告警头。
    """
    ip = _client_ip(request)
    _rate_limit_auth(ip)
    bearer = _validate_session_bearer(request)
    if bearer:
        request.state.ccc_auth_scheme = "bearer"
        return bearer
    if require_bearer():
        # REQUIRED（CCC_AUTH_REQUIRE_BEARER=1）：仅 Bearer；Basic → 401。
        # 例外：POST /api/auth/token 直调 _principal_from_basic（引导换 token），不经过本门。
        _log.warning(
            "basic auth rejected on %s (CCC_AUTH_REQUIRE_BEARER=1)",
            request.url.path,
        )
        _auth_failures[ip].append(time.monotonic())
        raise HTTPException(
            status_code=401,
            detail=(
                "Bearer session token required (CCC_AUTH_REQUIRE_BEARER=1); "
                "obtain via POST /api/auth/token"
            ),
            headers={"WWW-Authenticate": 'Bearer realm="CCC Chat"'},
        )
    principal = _principal_from_basic(request.headers.get("Authorization", ""))
    if principal is not None:
        request.state.ccc_auth_scheme = "basic"
        # 过渡期：legacy Basic（ccc:ccc）按 operator 全权兼容；迁移到会话 token
        _log.debug(
            "legacy basic auth on %s (role=%s) — migrate to session token",
            request.url.path,
            principal["role"],
        )
        return principal
    _auth_failures[ip].append(time.monotonic())
    raise HTTPException(
        status_code=401,
        headers={"WWW-Authenticate": 'Basic realm="CCC Chat"'},
    )


def require_write(request: Request) -> dict:
    """写操作提权门：operator 才放行。

    legacy Basic（Hub 主账密）→ operator（过渡期全权兼容）；
    viewer bearer/basic → 403；无凭证 → 401。
    """
    principal = check_auth(request)
    if principal["role"] != ROLE_OPERATOR:
        raise HTTPException(
            status_code=403,
            detail=(
                "write requires operator privilege; "
                "login with operator (or Hub Basic) and use the returned token"
            ),
        )
    return principal


def board_headers() -> dict:
    headers = {"Content-Type": "application/json"}
    if config.BOARD_TOKEN:
        headers["Authorization"] = f"Bearer {config.BOARD_TOKEN}"
    return headers
