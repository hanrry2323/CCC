"""7788 对话口账号密码鉴权（窗口 K · sidecar 共用模块）。

凭证（无默认弱口令）：
  - env `CCC_AGENT_AUTH_USER` / `CCC_AGENT_AUTH_PASS`（最高优先）
  - 或 `~/.ccc/agent-auth.json`（0600）`{"user","password"}`；`CCC_AGENT_AUTH_FILE` 可覆盖路径
  - 两者都必须非空才算已配置；未配置 → 登录拒绝并明确提示（绝不回退默认口令）

会话：内存 opaque token（`secrets.token_urlsafe(32)`），TTL `CCC_AGENT_SESSION_TTL`（默认 3600s）。
请求授权 `authorize_agent_request`：会话 token → 旧共享密钥（Desktop 兼容窗口）。

sidecar 侧：`app.include_router(AGENT_AUTH_ROUTER)` 挂登录端点；`_check_agent_auth` 调
`authorize_agent_request`。测试侧：本模块纯逻辑可直接 import，无需加载 sidecar 脚本。
"""

from __future__ import annotations

import hmac
import json
import logging
import os
import secrets
import time
from collections import defaultdict
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

_log = logging.getLogger("ccc.agent_auth")

# ── 会话 token ─────────────────────────────────────────────
SESSION_ROLE = "operator"
_sessions: dict[str, dict] = {}
_SESSION_PRUNE_INTERVAL = 64
_session_issue_count = 0

# ── 登录限速（IP 滑动窗口，镜像 chat_server.auth）──────────
_login_failures: dict[str, list[float]] = defaultdict(list)
_LOGIN_WINDOW_S = 60.0
_LOGIN_MAX_FAILS = 20
_LOGIN_PRUNE_INTERVAL = 64
_login_call_count = 0


def session_ttl() -> int:
    """会话 TTL 秒；`CCC_AGENT_SESSION_TTL` env 覆盖，非法/<=0 回落 3600。"""
    raw = os.environ.get("CCC_AGENT_SESSION_TTL", "").strip()
    try:
        v = int(raw)
        return v if v > 0 else 3600
    except ValueError:
        return 3600


def reset_agent_auth_state() -> None:
    """测试隔离：清空会话与限速桶。"""
    global _session_issue_count, _login_call_count
    _sessions.clear()
    _login_failures.clear()
    _session_issue_count = 0
    _login_call_count = 0


# ── 会话存储（内存，不落盘 / 不 commit）────────────────────

def _sweep_expired_sessions(now: float) -> None:
    stale = [t for t, s in _sessions.items() if now >= s["expires"]]
    for t in stale:
        _sessions.pop(t, None)


def issue_agent_session() -> str:
    global _session_issue_count
    token = secrets.token_urlsafe(32)
    now = time.monotonic()
    _sessions[token] = {"created": now, "expires": now + session_ttl()}
    _session_issue_count += 1
    if _session_issue_count % _SESSION_PRUNE_INTERVAL == 0:
        _sweep_expired_sessions(now)
    return token


def validate_agent_session(token: str) -> bool:
    if not token:
        return False
    s = _sessions.get(token)
    if not s:
        return False
    now = time.monotonic()
    if now >= s["expires"]:
        _sessions.pop(token, None)
        return False
    return True


def revoke_agent_session(token: str) -> None:
    _sessions.pop(token, None)


# ── 凭证配置（无默认）─────────────────────────────────────

def agent_auth_path() -> Path:
    raw = os.environ.get("CCC_AGENT_AUTH_FILE", "").strip()
    if raw:
        return Path(raw).expanduser()
    return Path.home() / ".ccc" / "agent-auth.json"


def _read_credentials_file(path: Path) -> tuple[str, str] | None:
    """读 `{"user","password"}`；缺键/空/坏 JSON → None。"""
    try:
        if not path.is_file():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    user = str(data.get("user") or "").strip()
    password = str(data.get("password") or "").strip()
    if not user or not password:
        return None
    return user, password


def agent_credentials() -> tuple[str, str] | None:
    """已配置 → (user, password)；未配置 → None。env 优先于文件；每次调用惰性读取。"""
    u = os.environ.get("CCC_AGENT_AUTH_USER", "").strip()
    p = os.environ.get("CCC_AGENT_AUTH_PASS", "").strip()
    if u and p:
        return u, p
    return _read_credentials_file(agent_auth_path())


def credentials_configured() -> bool:
    return agent_credentials() is not None


def verify_credentials(user: str, password: str) -> bool:
    """常量时间比较；未配置恒 False。"""
    creds = agent_credentials()
    if creds is None:
        return False
    exp_user, exp_pass = creds
    return hmac.compare_digest(user or "", exp_user) and hmac.compare_digest(
        password or "", exp_pass
    )


# ── 登录限速 ──────────────────────────────────────────────

def _client_ip(request: Request) -> str:
    """仅显式 `CCC_TRUST_PROXY=1` 时信任 X-Forwarded-For（防伪造绕过 IP 限速）。"""
    if os.environ.get("CCC_TRUST_PROXY", "").strip() == "1":
        xff = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
        if xff:
            return xff
    if request.client:
        return request.client.host or "unknown"
    return "unknown"


def _sweep_stale_buckets(now: float) -> None:
    stale = [
        ip
        for ip, ts in _login_failures.items()
        if not ts or now - ts[-1] >= _LOGIN_WINDOW_S
    ]
    for ip in stale:
        _login_failures.pop(ip, None)


def _check_login_rate(ip: str) -> None:
    global _login_call_count
    now = time.monotonic()
    _login_call_count += 1
    if _login_call_count % _LOGIN_PRUNE_INTERVAL == 0:
        _sweep_stale_buckets(now)
    bucket = [t for t in _login_failures[ip] if now - t < _LOGIN_WINDOW_S]
    _login_failures[ip] = bucket
    if len(bucket) >= _LOGIN_MAX_FAILS:
        raise HTTPException(status_code=429, detail="too many login attempts")


def _record_login_failure(ip: str) -> None:
    _login_failures[ip].append(time.monotonic())


# ── 请求授权（sidecar `_check_agent_auth` 用）───────────────

def _bearer_token(auth_header: str) -> str:
    auth = (auth_header or "").strip()
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return ""


def authorize_agent_request(auth_header: str, x_token: str, legacy_token: str) -> str | None:
    """返回命中方案 `"session"` | `"legacy"`；未授权 `None`。

    session = agent-login 会话 token（首选）；legacy = 旧共享密钥（Desktop 兼容窗口，
    窗口 2 迁移后移除）。
    """
    tok = _bearer_token(auth_header)
    if validate_agent_session(tok):
        return "session"
    legacy = (legacy_token or "").strip()
    if legacy:
        got = tok or (x_token or "").strip()
        if got and hmac.compare_digest(got, legacy):
            _log.debug("agent auth via legacy shared-secret (compat window)")
            return "legacy"
    return None


# ── 登录端点（sidecar `app.include_router` 挂载）────────────

UNCONFIGURED_DETAIL = (
    "未配置登录凭证：请配置 CCC_AGENT_AUTH_USER/PASS 或 ~/.ccc/agent-auth.json（0600）"
)

AGENT_AUTH_ROUTER = APIRouter()


@AGENT_AUTH_ROUTER.post("/api/auth/agent-login")
async def agent_login(request: Request):
    ip = _client_ip(request)
    _check_login_rate(ip)
    body: dict = {}
    try:
        raw = await request.json()
        if isinstance(raw, dict):
            body = raw
    except Exception:
        pass
    user = str(body.get("user") or "").strip()
    password = str(body.get("password") or "").strip()
    if not credentials_configured():
        return JSONResponse({"detail": UNCONFIGURED_DETAIL}, status_code=503)
    if not verify_credentials(user, password):
        _record_login_failure(ip)
        return JSONResponse({"detail": "账号或密码错误"}, status_code=401)
    token = issue_agent_session()
    _log.debug("agent login ok user=%s ip=%s", user, ip)
    return {
        "token": token,
        "role": SESSION_ROLE,
        "expires_in": session_ttl(),
    }


@AGENT_AUTH_ROUTER.get("/api/auth/agent-session")
async def agent_session(request: Request):
    tok = _bearer_token(request.headers.get("authorization") or "")
    if not validate_agent_session(tok):
        return JSONResponse({"detail": "unauthorized"}, status_code=401)
    return {"valid": True, "role": SESSION_ROLE, "expires_in": session_ttl()}


@AGENT_AUTH_ROUTER.post("/api/auth/agent-logout")
async def agent_logout(request: Request):
    tok = _bearer_token(request.headers.get("authorization") or "")
    if tok:
        revoke_agent_session(tok)
        _log.debug("agent session revoked")
    return {"ok": True}
