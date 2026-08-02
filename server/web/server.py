"""server/web/server.py — HTTP API 服务端（零依赖，Python stdlib 实现）。

提供 5 个 GET 接口 + 对话/会话接口 + Bearer token 鉴权。

用法:
    python3 -m server.web.server --port 9999

    # 使用默认端口（仅测试用）
    python3 -m server.web.server

API:
    GET  /health              → {"status": "ok"}（无鉴权）
    POST /session             → 账号密码换 token（无鉴权）
    GET  /board/realtime      → 实时视图（需 Bearer token）
    GET  /board/recent        → 7 天回写视图（需 Bearer token）
    GET  /board/by_project    → 按项目分类（需 Bearer token）
    GET  /board/roadmap       → 线路图聚合（需 Bearer token）
    GET  /board/states        → 状态统计（需 Bearer token）
    POST /conversation        → 对话（回声占位，需 Bearer token）
    GET  /conversation        → 对话历史（需 Bearer token）

鉴权: Bearer token 鉴权，token 通过 POST /session 获取。
      环境变量: CCC_WEB_USERNAME, CCC_WEB_PASSWORD_HASH, CCC_WEB_TOKEN_TTL。
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import sys
import time
from collections import OrderedDict
from datetime import date, datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any

# ── 项目根路径探测 ──
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from server.board.loader import load_dispatch_cards
from server.board.queries import (
    roadmap_overview,
    roadmap_by_project,
    state_counts,
    view_by_project,
    view_recent,
    view_realtime,
)

# ── 默认参数（仅测试用，生产禁止使用） ──
_DEFAULT_PORT = int(os.environ.get("WEB_PORT", "0"))  # 0=随机端口，仅测试用
_DISPATCH_DIR = _PROJECT_ROOT / "docs" / "dispatch"

# ── 鉴权配置（从环境变量读取；支持运行时刷新，测试可覆盖） ──
_AUTH_USERNAME = os.environ.get("CCC_WEB_USERNAME", "")
_AUTH_PASSWORD_HASH = os.environ.get("CCC_WEB_PASSWORD_HASH", "")
_SERVER_SECRET = os.urandom(32).hex()


def _get_token_ttl() -> int:
    """读取 token 有效期（秒），支持运行时环境变量注入。"""
    return int(os.environ.get("CCC_WEB_TOKEN_TTL", "3600"))

# 内存 token 存储: {token: {"username": str, "expires_at": float}}
_tokens: dict[str, dict[str, Any]] = {}
# 对话历史（内存列表）
_conversations: list[dict[str, Any]] = []

# ── 免鉴权的路径前缀 ──
_NO_AUTH_PATHS = frozenset({"/health", "/session"})


def _password_hash(password: str) -> str:
    """计算密码的 SHA-256 哈希。"""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _generate_token(username: str) -> str:
    """生成 Bearer token（HMAC-SHA256），存入内存。"""
    expires_at = time.time() + _get_token_ttl()
    raw = f"{username}:{expires_at}"
    token = hmac.new(
        _SERVER_SECRET.encode("utf-8"),
        raw.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    _tokens[token] = {"username": username, "expires_at": expires_at}
    return token


def _validate_token(token: str) -> dict[str, Any] | None:
    """校验 Bearer token：存在且未过期。返回 token 数据或 None。"""
    data = _tokens.get(token)
    if data is None:
        return None
    if time.time() > data["expires_at"]:
        _tokens.pop(token, None)
        return None
    return data


def _clean_expired_tokens():
    """清理过期 token（惰性，每次调用清除全部过期项）。"""
    now = time.time()
    expired = [t for t, d in _tokens.items() if now > d["expires_at"]]
    for t in expired:
        _tokens.pop(t, None)


def _json_response(data: Any, status: int = 200) -> tuple[str, str, bytes]:
    """构建 JSON 响应 (status_line, content_type, body)。"""
    body = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
    return ("200 OK" if status == 200 else f"{status} Error", "application/json", body)


def _load_board_items():
    """加载任务卡数据。"""
    return load_dispatch_cards(_DISPATCH_DIR)


class _APIHandler(BaseHTTPRequestHandler):
    """HTTP API 请求处理器。"""

    # 禁用父类日志（测试不污染 stdout）
    def log_message(self, fmt, *args):
        pass

    def _send_json(self, data: dict, status: int = 200):
        status_line, content_type, body = _json_response(data, status)
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_401(self, msg: str = "unauthorized"):
        self._send_json({"error": msg}, 401)

    def _send_404(self):
        self._send_json({"error": "not found"}, 404)

    def _check_auth(self) -> bool:
        """鉴权中间件。返回 True 通过，False 已发送 401。"""
        path = self.path.rstrip("/").split("?")[0]
        if path in _NO_AUTH_PATHS:
            return True
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            self._send_401("missing or invalid Authorization header")
            return False
        token = auth[len("Bearer "):]
        if _validate_token(token) is None:
            self._send_401("token expired or invalid")
            return False
        return True

    def _read_body(self) -> dict[str, Any] | None:
        """读取并解析 JSON 请求体。失败返回 None。"""
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return None
        raw = self.rfile.read(length)
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None

    def _handle_session(self):
        """POST /session：账号密码校验 → 签发 token。"""
        body = self._read_body()
        if not body:
            self._send_json({"error": "invalid request body"}, 400)
            return
        username = body.get("username", "")
        password = body.get("password", "")
        if not username or not password:
            self._send_json({"error": "username and password required"}, 400)
            return
        if not _AUTH_USERNAME or not _AUTH_PASSWORD_HASH:
            self._send_json({"error": "server auth not configured"}, 500)
            return
        if username != _AUTH_USERNAME or _password_hash(password) != _AUTH_PASSWORD_HASH:
            self._send_json({"error": "invalid username or password"}, 401)
            return
        _clean_expired_tokens()
        ttl = _get_token_ttl()
        token = _generate_token(username)
        expires_at = datetime.fromtimestamp(
            time.time() + ttl, tz=timezone.utc
        ).isoformat()
        self._send_json({"token": token, "expires_at": expires_at, "ttl_s": ttl})

    def _handle_conversation_post(self):
        """POST /conversation：对话（回声占位）。"""
        body = self._read_body()
        if not body:
            self._send_json({"error": "invalid request body"}, 400)
            return
        message = body.get("message", "")
        if not message:
            self._send_json({"error": "message required"}, 400)
            return
        reply = f"echo: {message}"
        entry = {
            "role": "user",
            "message": message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        _conversations.append(entry)
        reply_entry = {
            "role": "assistant",
            "message": reply,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        _conversations.append(reply_entry)
        self._send_json({"reply": reply})

    def _handle_conversation_get(self):
        """GET /conversation：返回对话历史。"""
        self._send_json({"messages": list(_conversations)})

    def do_GET(self):
        if not self._check_auth():
            return
        path = self.path.rstrip("/").split("?")[0]
        if path == "/health":
            self._send_json({"status": "ok"})
            return
        if path == "/conversation":
            self._handle_conversation_get()
            return
        try:
            items = _load_board_items()
        except OSError as exc:
            self._send_json({"error": f"data load failed: {exc}"}, 500)
            return

        if path == "/board/realtime":
            self._send_json(view_realtime(items))
        elif path == "/board/recent":
            self._send_json(view_recent(items, now=date.today(), days=7))
        elif path == "/board/by_project":
            self._send_json(view_by_project(items))
        elif path == "/board/roadmap":
            self._send_json({
                "overview": roadmap_overview(items),
                "by_project": roadmap_by_project(items),
            })
        elif path == "/board/states":
            self._send_json(state_counts(items))
        else:
            self._send_404()

    def do_POST(self):
        if not self._check_auth():
            return
        path = self.path.rstrip("/").split("?")[0]
        if path == "/session":
            self._handle_session()
        elif path == "/conversation":
            self._handle_conversation_post()
        else:
            self._send_404()


def create_server(host: str = "127.0.0.1", port: int = 0) -> HTTPServer:
    """创建 HTTP 服务实例（不启动）。"""
    server = HTTPServer((host, port), _APIHandler)
    return server


def serve_forever(host: str = "127.0.0.1", port: int = 0) -> HTTPServer:
    """创建并启动 HTTP 服务（阻塞）。"""
    server = create_server(host, port)
    addr = server.server_address
    print(f"[web] HTTP API 启动于 http://{addr[0]}:{addr[1]}", file=sys.stderr)
    print(f"[web] 数据源: {_DISPATCH_DIR}", file=sys.stderr)
    print(f"[web] 警告: 本服务仅只读，未加鉴权，禁止用于生产", file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print(file=sys.stderr)
        print("[web] 收到中断，关闭", file=sys.stderr)
        server.server_close()
    return server


def main():
    parser = argparse.ArgumentParser(description="CCC HTTP API 服务端")
    parser.add_argument(
        "--port",
        type=int,
        default=_DEFAULT_PORT,
        help=f"监听端口（默认 {_DEFAULT_PORT}，0=随机，仅测试用）",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="监听地址（默认 127.0.0.1）",
    )
    args = parser.parse_args()
    serve_forever(host=args.host, port=args.port)


if __name__ == "__main__":
    main()