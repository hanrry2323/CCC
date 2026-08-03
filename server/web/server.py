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
    POST /conversation        → 对话（调用 2017 Claude Code 大脑 Agent，需 Bearer token）
    GET  /conversation        → 对话历史（需 Bearer token）

鉴权: Bearer token 鉴权，token 通过 POST /session 获取。
      环境变量: CCC_WEB_USERNAME, CCC_WEB_PASSWORD_HASH, CCC_WEB_TOKEN_TTL。

对话大脑（T29）: /conversation 调用本机 Claude Code CLI（走 6100 Anthropic 出口），
      携带 CCC 大脑人格 + 历史上下文，返回真实 Agent 输出。配置见 server/web/brain.py：
      CCC_BRAIN_MODEL / CCC_BRAIN_BASE_URL / CCC_BRAIN_AUTH_TOKEN / CCC_BRAIN_TIMEOUT；
      缺配置返回 503，忙返回 503，超时返回 504，失败返回 502（均不落历史）。

流式对话（T41）: POST /conversation 请求体带 ``"stream": true`` → 返回 SSE
      （text/event-stream），逐事件转发 meta / thinking / tool_use / text /
      tool_result / done / error；错误以 ``event: error`` 流式返回（HTTP 200）。
      body 不带 stream 或为 false → 同步 JSON（向后兼容）。
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import mimetypes
import os
import sys
import time
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
from server.board.models import STATES, UNKNOWN, BoardItem, base_state
from server.engine.cluster import (
    check_service_status,
    check_tcp_reachable,
    parse_cluster_services,
    parse_cluster_targets,
)
from server.web.brain import call_brain, stream_brain_events

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
_NO_AUTH_PATHS = frozenset({"/health", "/session", "/config"})


# ── 静态托管（T23：浏览器直开 7788 看页面；T25：旧对话页 legacy-chat/） ──
# 白名单：仅这些路径免鉴权返回静态文件（页面本身是登录入口）。
_STATIC_WEB_ROOT = _PROJECT_ROOT / "server" / "web"
# 旧对话页根目录（T25：legacy-chat/ 下的文件通过前缀匹配自动托管）
_STATIC_LEGACY_CHAT_ROOT = _STATIC_WEB_ROOT / "legacy-chat"
# 路径 → 磁盘文件相对 web 根的映射（显式白名单，禁止目录穿越）
_STATIC_WHITELIST: dict[str, str] = {
    "/": "legacy-chat/index.html",
    "/index.html": "legacy-chat/index.html",
    "/js/app.js": "legacy-chat/js/app.js",
    "/data/board.js": "data/board.js",
    "/data/cluster.js": "data/cluster.js",
}


def _resolve_static_file(path: str) -> tuple[Path, str] | None:
    """将请求路径解析为磁盘文件 + Content-Type；非白名单或穿越返回 None。

    防穿越策略：
    1. 白名单命中优先（显式映射）；
    2. 白名单未命中时尝试 legacy-chat/ 目录（T25：旧对话页资源）；
    3. resolve() 后必须仍在对应的根目录内；
    4. 必须是普通文件。
    """
    # 去 query + fragment，path 已是 do_GET 处理后的纯 path
    rel = _STATIC_WHITELIST.get(path)
    if rel:
        target = (_STATIC_WEB_ROOT / rel).resolve()
        try:
            target.relative_to(_STATIC_WEB_ROOT.resolve())
        except ValueError:
            return None
        if target.is_file():
            ctype, _ = mimetypes.guess_type(target.name)
            return target, ctype or "application/octet-stream"
        return None
    # 白名单未命中 → 尝试 legacy-chat/ 目录（T25）
    legacy_path = (_STATIC_LEGACY_CHAT_ROOT / path.lstrip("/")).resolve()
    try:
        legacy_path.relative_to(_STATIC_LEGACY_CHAT_ROOT.resolve())
    except ValueError:
        return None
    if legacy_path.is_file():
        ctype, _ = mimetypes.guess_type(legacy_path.name)
        return legacy_path, ctype or "application/octet-stream"
    return None


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


# ── 前端只读配置注入（T33：替代前端硬编码 IP/路径） ──
# 白名单字段：仅这些非敏感字段可经 /config 免鉴权返回给前端。
_PUBLIC_CONFIG_KEYS: tuple[str, ...] = (
    "WEB_PORT",
    "BOARD_PORT",
    "ENGINE_PORT",
    "RELAY_PORT",
)


def _build_public_config() -> dict[str, Any]:
    """构造前端可读的非敏感配置子集（替代前端硬编码 IP/路径/端口）。

    仅返回 _PUBLIC_CONFIG_KEYS 白名单字段；密钥/路径/上游地址等敏感字段一律不返回。
    workspace_map 默认空对象（前端不再硬编码本机路径，由用户在设置页填）。
    """
    return {
        "ports": {
            "web": os.environ.get("WEB_PORT", ""),
            "board": os.environ.get("BOARD_PORT", ""),
            "engine": os.environ.get("ENGINE_PORT", ""),
            "relay": os.environ.get("RELAY_PORT", ""),
        },
        # workspace_map 留空：业务仓路径由用户在设置页填，服务端不臆造
        "workspace_map": {},
        "version": "v0.70.0",
    }


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


# ── 运维接口辅助（T21：/ops/summary，cluster 采集 + board 派生 severity） ──


def _collect_ops_nodes() -> list[dict[str, Any]]:
    """采集集群节点状态（TCP 可达性），返回 OpsMachine 兼容字典列表。

    目标来自 CLUSTER_TARGETS env（逗号分隔 host:port）；空则返回空列表。
    """
    cfg = {"CLUSTER_TARGETS": os.environ.get("CLUSTER_TARGETS", "")}
    targets = parse_cluster_targets(cfg)
    machines: list[dict[str, Any]] = []
    for host, port in targets:
        ns = check_tcp_reachable(host, port)
        # 端口名走 env 映射（CLUSTER_PORT_NAMES=7788:web-server,4100:relay-anthropic），
        # 无配置则用通用名 port-{port}，避免硬编码端口到名称的映射
        port_names_env = os.environ.get("CLUSTER_PORT_NAMES", "")
        port_names: dict[int, str] = {}
        for pair in port_names_env.split(","):
            pair = pair.strip()
            if ":" in pair:
                k, v = pair.split(":", 1)
                try:
                    port_names[int(k.strip())] = v.strip()
                except ValueError:
                    continue
        port_name = port_names.get(port, f"port-{port}")
        machines.append(
            {
                "name": port_name,
                "ip": host,
                "role": port_name,
                "reachable": ns.reachable,
                "alive_ports": 1 if ns.reachable else 0,
                "port_count": 1,
            }
        )
    return machines


def _collect_ops_services() -> list[dict[str, Any]]:
    """采集本机服务进程状态（pgrep），返回服务状态字典列表。

    服务清单来自 CLUSTER_SERVICES env（逗号分隔 name:keyword）；零硬编码。
    未配置则返回空列表（运维页显示「服务清单未配置」）。
    """
    cfg = {"CLUSTER_SERVICES": os.environ.get("CLUSTER_SERVICES", "")}
    services_cfg = parse_cluster_services(cfg)
    services: list[dict[str, Any]] = []
    for name, keyword in services_cfg:
        ss = check_service_status(name, keyword)
        services.append(
            {
                "name": name,
                "running": ss.running,
                "pid": ss.pid,
            }
        )
    return services


def _build_ops_summary() -> dict[str, Any]:
    """构造 OpsSummary 兼容子集（对齐桌面端可消费字段）。

    数据源：cluster 采集（nodes/services/collected_at）+ board 派生（severity/human_line）。
    字段缺失容错：旧 Hub 大字段（risks/workspaces/daily/...）一律置空/省略，桌面端容错。

    severity 派生规则：
    - 全部节点可达 + 关键服务运行 → green
    - 部分可达或部分服务运行 → amber
    - 全断或采集失败 → red
    """
    import datetime

    machines = _collect_ops_nodes()
    services = _collect_ops_services()
    collected_at = datetime.datetime.now().isoformat(timespec="seconds")

    # down_ports：不可达节点
    down_ports: list[dict[str, Any]] = []
    for m in machines:
        if not m.get("reachable"):
            down_ports.append(
                {
                    "port": 0,  # 节点级，无具体端口
                    "name": m.get("name", ""),
                    "host": m.get("ip", ""),
                }
            )

    # severity 派生
    total = len(machines)
    reachable = sum(1 for m in machines if m.get("reachable"))
    if total == 0:
        # 无采集配置 → amber（需配置，非故障）
        severity = "amber"
        human_line = "运维采集未配置（CLUSTER_TARGETS 为空），请配置后重启服务"
    elif reachable == total:
        severity = "green"
        human_line = f"集群全活（{reachable}/{total} 节点可达）"
    elif reachable == 0:
        severity = "red"
        human_line = f"集群全断（0/{total} 节点可达），请检查"
    else:
        severity = "amber"
        human_line = f"集群部分可达（{reachable}/{total} 节点可达）"

    # 服务运行情况补充到 human_line
    svc_running = sum(1 for s in services if s.get("running"))
    if services:
        human_line += f" · 服务 {svc_running}/{len(services)} 运行"

    # 派生看板计数（abnormal 卡数 → risk 提示）
    try:
        items = _load_board_items()
        abnormal = sum(1 for i in items if base_state(i.state) == "打回")
        if abnormal > 0:
            human_line += f" · {abnormal} 张打回卡"
    except OSError:
        pass

    return {
        "overview": {
            "machines": machines,
            "alert_count": len(down_ports),
            "down_ports": down_ports,
            "generated_at": collected_at,
        },
        "severity": severity,
        "human_line": human_line,
        # 旧 Hub 大字段置空，桌面端容错（OpsView 只读区降级显示）
        "risks": None,
        "workspaces": None,
        "daily": None,
        "quality": None,
        "docs": None,
        "kb": None,
        "deploy": None,
        "ports": None,
        "auto": None,
        "resources": None,
        "resources_history": None,
        "logistics": None,
        "control": None,
        "ready_to_dispatch": None,
        "recent_failures": None,
        "abnormal_cards": None,
        "alerts": None,
        "amber_notes": None,
        "domains": None,
        "agent_minds": None,
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

    def _send_static(self, path: str) -> bool:
        """处理静态白名单路径（免鉴权）。命中返回 True，未命中返回 False。

        T23：浏览器直开 7788 看页面，静态资源（HTML/CSS/JS/data）放行。
        非白名单路径不处理，由 do_GET 继续走鉴权 + API 路由。
        """
        resolved = _resolve_static_file(path)
        if resolved is None:
            return False
        target, ctype = resolved
        try:
            body = target.read_bytes()
        except OSError:
            self._send_404()
            return True
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)
        return True

    def _check_auth(self) -> bool:
        """鉴权中间件。返回 True 通过，False 已发送 401。"""
        path = self.path.rstrip("/").split("?")[0]
        if path in _NO_AUTH_PATHS:
            return True
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            self._send_401("missing or invalid Authorization header")
            return False
        token = auth[len("Bearer ") :]
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
        expires_at = datetime.fromtimestamp(time.time() + ttl, tz=timezone.utc).isoformat()
        self._send_json({"token": token, "expires_at": expires_at, "ttl_s": ttl})

    def _handle_conversation_post(self):
        """POST /conversation：调用 2017 Claude Code 大脑 Agent 并返回回复。

        body.stream=true → SSE 流式输出（text/event-stream）；否则同步 JSON（向后兼容）。
        """
        body = self._read_body()
        if not body:
            self._send_json({"error": "invalid request body"}, 400)
            return
        message = body.get("message", "")
        if not message:
            self._send_json({"error": "message required"}, 400)
            return
        if body.get("stream"):
            self._handle_conversation_stream(message)
            return
        success, reply, status = call_brain(message, list(_conversations))
        if not success:
            # 未配置(503)/忙(503)/失败(502)/超时(504)：不落历史
            self._send_json({"error": reply}, status)
            return
        now = datetime.now(timezone.utc).isoformat()
        _conversations.append({"role": "user", "message": message, "timestamp": now})
        _conversations.append({"role": "assistant", "message": reply, "timestamp": now})
        self._send_json({"reply": reply})

    def _handle_conversation_stream(self, message: str):
        """POST /conversation {stream:true}：SSE 逐事件转发大脑流式输出。

        错误（未配置/忙/超时/失败）也以 ``event: error`` 流式返回（HTTP 200），
        客户端统一按事件消费；仅 ``done{is_error:false}`` 时回写历史（与同步一致）。
        客户端断开（BrokenPipe/Reset）时关闭 generator 以释放大脑锁。
        """
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        gen = stream_brain_events(message, list(_conversations))
        text_parts: list[str] = []
        done_text = ""
        finished_error: bool | None = None
        try:
            for event, payload in gen:
                if event == "text":
                    text_parts.append(payload.get("text", "") or "")
                if event == "done":
                    finished_error = bool(payload.get("is_error"))
                    done_text = payload.get("text", "") or ""
                data = json.dumps(payload, ensure_ascii=False)
                self.wfile.write(f"event: {event}\ndata: {data}\n\n".encode())
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            gen.close()
        if finished_error is False:
            reply = "".join(text_parts).strip() or done_text.strip()
            if reply:
                now = datetime.now(timezone.utc).isoformat()
                _conversations.append({"role": "user", "message": message, "timestamp": now})
                _conversations.append({"role": "assistant", "message": reply, "timestamp": now})

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

    def _handle_ops_summary(self):
        """GET /ops/summary → OpsSummary 兼容子集（cluster 采集 + board 派生 severity）。

        缺采集配置或采集失败：返回 200 + 空结构 + error 字段（容错，不 500）。
        """
        try:
            summary = _build_ops_summary()
            self._send_json(summary)
        except OSError as exc:
            # subprocess.TimeoutExpired 是 OSError 子类；采集失败不 500
            self._send_json(
                {
                    "overview": {"machines": [], "alert_count": 0, "down_ports": [], "generated_at": ""},
                    "severity": "red",
                    "human_line": f"运维采集失败: {exc}",
                    "error": str(exc),
                },
                200,
            )

    def do_GET(self):
        # T23：静态白名单路径免鉴权（页面本身是登录入口）
        raw_path = self.path.split("?")[0]
        path = raw_path.rstrip("/") or "/"
        if self._send_static(path):
            return
        if path == "/health":
            # T30：/health 返回鉴权配置，供前端登录门判断
            # auth_required：受保护端点是否需 Bearer token（始终 true）
            # auth_configured：服务端是否已配置登录凭证（账号 + 密码哈希）
            self._send_json(
                {
                    "status": "ok",
                    "auth_required": True,
                    "auth_configured": bool(_AUTH_USERNAME and _AUTH_PASSWORD_HASH),
                }
            )
            return
        if path == "/config":
            # T33：前端只读配置注入（免鉴权白名单，仅非敏感字段）
            self._send_json(_build_public_config())
            return
        if not self._check_auth():
            return
        if path == "/conversation":
            self._handle_conversation_get()
            return
        if path == "/ops/summary":
            self._handle_ops_summary()
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
            self._send_json(
                {
                    "overview": roadmap_overview(items),
                    "by_project": roadmap_by_project(items),
                }
            )
        elif path == "/board/states":
            self._send_json(state_counts(items))
        elif path == "/board/snapshot":
            self._handle_board_snapshot(items)
        elif path == "/board/summaries":
            self._handle_board_summaries(items)
        elif path.startswith("/tasks/"):
            task_id = path[len("/tasks/") :].strip("/")
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
    print("[web] 提示: 本服务 board 接口已启用 Bearer token 鉴权（/health 与 /session 免鉴权）", file=sys.stderr)
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
