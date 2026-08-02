"""server/web/server.py — HTTP API 服务端（零依赖，Python stdlib 实现）。

提供 5 个 GET 接口 + 对话/会话接口 + Bearer token 鉴权。

用法:
    $PYTHON_BIN -m server.web.server --port 9999

    # 使用默认端口（仅测试用）
    $PYTHON_BIN -m server.web.server

API:
    GET  /health              → {"status": "ok"}（无鉴权）
    POST /session             → 账号密码换 token（无鉴权）
    GET  /board/realtime      → 实时视图（需 Bearer token）
    GET  /board/recent        → 7 天回写视图（需 Bearer token）
    GET  /board/by_project    → 按项目分类（需 Bearer token）
    GET  /board/roadmap       → 线路图聚合（需 Bearer token）
    GET  /board/states        → 状态统计（需 Bearer token）
    POST /conversation        → 对话（转发配置的模型上游，需 Bearer token）
    GET  /conversation        → 对话历史（需 Bearer token）

鉴权: Bearer token 鉴权，token 通过 POST /session 获取。
      环境变量: CCC_WEB_USERNAME, CCC_WEB_PASSWORD_HASH, CCC_WEB_TOKEN_TTL。

对话上游: 通过 RELAY_UPSTREAM_URL / RELAY_UPSTREAM_KEY /
          CCC_CONV_MODEL_NAME / CCC_CONV_UPSTREAM_PATH 配置；
          缺配置返回 503，上游失败返回 502（不落历史）。
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.error
import urllib.request
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


# ── 对话上游配置（从环境变量读取；支持运行时刷新） ──
def _get_conv_upstream_base() -> str:
    """上游 base URL（如 http://<relay-host>:<port>），无尾斜杠。"""
    return os.environ.get("RELAY_UPSTREAM_URL", "").rstrip("/")


def _get_conv_upstream_key() -> str:
    """上游 Bearer 密钥（可空）。"""
    return os.environ.get("RELAY_UPSTREAM_KEY", "")


def _get_conv_model_name() -> str:
    """对话模型名（如 flash / Pro / code）。"""
    return os.environ.get("CCC_CONV_MODEL_NAME", "").strip()


def _get_conv_upstream_path() -> str:
    """上游 chat completions 路径（默认 /v1/chat/completions）。"""
    return os.environ.get("CCC_CONV_UPSTREAM_PATH", "/v1/chat/completions").strip() or "/v1/chat/completions"


def _get_conv_upstream_timeout() -> int:
    """上游请求超时（秒，默认 60）。"""
    try:
        return int(os.environ.get("CCC_CONV_UPSTREAM_TIMEOUT", "60"))
    except ValueError:
        return 60


# 内存 token 存储: {token: {"username": str, "expires_at": float}}
_tokens: dict[str, dict[str, Any]] = {}
# 对话历史（内存列表）
_conversations: list[dict[str, Any]] = []

# 对话历史转发给上游的最大轮数（user+assistant 算一轮）
_CONV_HISTORY_TURNS = 10


def _forward_to_upstream(message: str, history: list[dict[str, Any]]) -> tuple[bool, str, int]:
    """转发用户消息到配置的模型上游（OpenAI chat completions 格式）。

    返回 (success, reply_or_error, status_code)：
    - 缺配置 → (False, "upstream not configured", 503)
    - 上游成功 → (True, reply, 200)
    - 上游失败 → (False, error_msg, 502)
    """
    base = _get_conv_upstream_base()
    model = _get_conv_model_name()
    if not base or not model:
        return (False, "upstream not configured (RELAY_UPSTREAM_URL / CCC_CONV_MODEL_NAME)", 503)
    url = base + _get_conv_upstream_path()
    # 构造 messages：最近 N 轮历史 + 当前消息
    messages: list[dict[str, str]] = []
    recent = history[-(2 * _CONV_HISTORY_TURNS):] if history else []
    for entry in recent:
        role = entry.get("role", "")
        content = entry.get("message", "")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": message})
    payload = json.dumps({
        "model": model,
        "messages": messages,
        "stream": False,
    }).encode("utf-8")
    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    key = _get_conv_upstream_key()
    if key:
        req.add_header("Authorization", f"Bearer {key}")
    try:
        with urllib.request.urlopen(req, timeout=_get_conv_upstream_timeout()) as resp:
            raw = resp.read().decode("utf-8")
            data = json.loads(raw)
            # OpenAI 格式：choices[0].message.content
            choices = data.get("choices") or []
            if not choices:
                return (False, "upstream returned no choices", 502)
            reply = (choices[0].get("message") or {}).get("content", "")
            if not reply:
                return (False, "upstream returned empty content", 502)
            return (True, reply, 200)
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", errors="replace")[:200]
        except OSError:
            pass
        return (False, f"upstream HTTP {exc.code}: {body}", 502)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return (False, f"upstream connect failed: {exc}", 502)
    except (json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
        return (False, f"upstream decode failed: {exc}", 502)

# ── 免鉴权的路径前缀 ──
_NO_AUTH_PATHS = frozenset({"/health", "/session"})


# ── 看板兼容接口辅助（T20：BoardSnapshot / BoardSummaries / TaskDetail） ──

def _item_to_board_task(item: BoardItem) -> dict[str, Any]:
    """BoardItem → 桌面端 BoardTask 兼容字典。

    字段映射：state→status；card_kind 统一 "work"（任务卡都是 work 卡）；
    parent_id/split_status/note 任务卡无结构化对应，留空。
    """
    return {
        "id": item.id,
        "title": item.title,
        "card_kind": "work",
        "parent_id": "",
        "status": item.state,
        "note": "",
        "executor": item.executor,
        "split_status": "",
    }


def _build_snapshot(items: list[BoardItem], workspace: str = "") -> dict[str, Any]:
    """构造 BoardSnapshot 兼容结构：columns（状态→BoardTask 列表）+ counts + workspace。

    workspace 非空时按 project 过滤；include_hidden 参数接受但任务卡无 hidden 标记，
    看板是派生视图（契约 §4），不另行过滤。
    """
    from server.board.models import STATES, UNKNOWN, base_state
    filtered = [i for i in items if not workspace or i.project == workspace]
    columns: dict[str, list[dict]] = {}
    for item in filtered:
        b = base_state(item.state)
        bucket = b if b in STATES else UNKNOWN
        columns.setdefault(bucket, []).append(_item_to_board_task(item))
    counts = {state: len(columns.get(state, [])) for state in STATES}
    return {
        "columns": columns,
        "counts": counts,
        "workspace": workspace or "all",
    }


def _parse_task_acceptance(card_id: str) -> str:
    """从任务卡文件解析 `## 验收标准` section 文本（简单文本拼接，未找到返回空串）。"""
    import re
    # 任务卡命名：T19-xxx.md；用前缀 glob 定位
    candidates = sorted(_DISPATCH_DIR.glob(f"{card_id}-*.md"))
    if not candidates:
        candidates = sorted(_DISPATCH_DIR.glob(f"*{card_id}*.md"))
    if not candidates:
        return ""
    try:
        text = candidates[0].read_text(encoding="utf-8")
    except OSError:
        return ""
    # 匹配 `## 验收标准...` 到下一个 `## ` 或文件末
    m = re.search(r"^##\s*验收标准[^\n]*\n(.*?)(?=^##\s|\Z)", text, re.MULTILINE | re.DOTALL)
    return m.group(1).strip() if m else ""


def _find_task_detail(items: list[BoardItem], task_id: str) -> dict[str, Any] | None:
    """按 id 查找任务卡详情；未找到返回 None。"""
    item = next((i for i in items if i.id == task_id), None)
    if item is None:
        return None
    return {
        "id": item.id,
        "title": item.title,
        "card_kind": "work",
        "parent_id": "",
        "status": item.state,
        "note": "",
        "executor": item.executor,
        "split_status": "",
        "acceptance": _parse_task_acceptance(item.id),
        "phases": [],
        "events": [],
    }


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
        """POST /conversation：转发到配置的模型上游并返回回复。"""
        body = self._read_body()
        if not body:
            self._send_json({"error": "invalid request body"}, 400)
            return
        message = body.get("message", "")
        if not message:
            self._send_json({"error": "message required"}, 400)
            return
        success, reply, status = _forward_to_upstream(message, list(_conversations))
        if not success:
            # 上游未配置(503)或失败(502)：不落历史
            self._send_json({"error": reply}, status)
            return
        now = datetime.now(timezone.utc).isoformat()
        _conversations.append({"role": "user", "message": message, "timestamp": now})
        _conversations.append({"role": "assistant", "message": reply, "timestamp": now})
        self._send_json({"reply": reply})

    def _handle_conversation_get(self):
        """GET /conversation：返回对话历史。"""
        self._send_json({"messages": list(_conversations)})

    def _handle_board_snapshot(self, items: list[BoardItem]):
        """GET /board/snapshot?workspace=X&include_hidden=0 → BoardSnapshot 兼容结构。"""
        from urllib.parse import parse_qs
        qs = parse_qs(self.path.split("?", 1)[1]) if "?" in self.path else {}
        workspace = (qs.get("workspace", [""])[0]).strip()
        # include_hidden 参数接受但任务卡无 hidden 标记（契约 §4 派生视图）
        self._send_json(_build_snapshot(items, workspace))

    def _handle_board_summaries(self, items: list[BoardItem]):
        """GET /board/summaries?workspaces=a,b → {summaries: {项目: BoardSnapshot}}。"""
        from urllib.parse import parse_qs
        qs = parse_qs(self.path.split("?", 1)[1]) if "?" in self.path else {}
        raw = (qs.get("workspaces", [""])[0]).strip()
        workspaces = [w.strip() for w in raw.split(",") if w.strip()] if raw else []
        if not workspaces:
            # 无参数 → 全部项目各自一个 snapshot
            workspaces = sorted({i.project for i in items})
        summaries = {ws: _build_snapshot(items, ws) for ws in workspaces}
        self._send_json({"summaries": summaries})

    def _handle_task_detail(self, items: list[BoardItem], task_id: str):
        """GET /tasks/{id} → BoardTaskDetail；未找到 404。"""
        detail = _find_task_detail(items, task_id)
        if detail is None:
            self._send_json({"error": f"task not found: {task_id}"}, 404)
            return
        self._send_json(detail)

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
        elif path == "/board/snapshot":
            self._handle_board_snapshot(items)
        elif path == "/board/summaries":
            self._handle_board_summaries(items)
        elif path.startswith("/tasks/"):
            task_id = path[len("/tasks/"):].strip("/")
            if not task_id:
                self._send_404()
                return
            self._handle_task_detail(items, task_id)
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
    print(f"[web] 提示: 本服务 board 接口已启用 Bearer token 鉴权（/health 与 /session 免鉴权）", file=sys.stderr)
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