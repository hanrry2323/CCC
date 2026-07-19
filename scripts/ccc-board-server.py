#!/usr/bin/env python3
"""ccc-board-server.py — CCC 看板 HTTP 服务 (v0.20)

提供 REST API（默认 :7775，本机）；UI 已并入 CCC Hub :7777。
旧静态页（index/board）仅作 302 重定向到 Hub。
支持多 workspace（CCC / qxo 自动发现）。

依赖：Python 3.8+ 标准库
"""

from __future__ import annotations
import argparse
import hmac
import json
import os
import sys
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import ssl
import threading
import time
from typing import Optional
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from _config import Config, get_logger
from _board_store import COLUMNS, FileBoardStore
from _utils import sanitize_id as _utils_sanitize_id
from human_status import (
    enrich_task, enrich_abnormal,
    event_action_cn, hhmm, is_today,
)

_log = get_logger("board-server")

_cfg = Config()

# ── 配置 ──
CCC_HOME = _cfg.ccc_home
COLUMN_LABELS = {
    "backlog": "待办",
    "planned": "已计划",
    "in_progress": "开发中",
    "testing": "测试/验收",
    "verified": "已验证",
    "released": "已发布",
    "abnormal": "异常",
}
COLUMN_COLORS = {
    "backlog": "#94a3b8",
    "planned": "#6366f1",
    "in_progress": "#f59e0b",
    "testing": "#f97316",
    "verified": "#22c55e",
    "released": "#3b82f6",
    "abnormal": "#ef4444",
}
ROLES = ["product", "dev", "reviewer", "tester", "ops", "kb", "regress"]
MAX_CONTENT_LENGTH = 1_048_576


def sanitize_id(tid: str) -> str:
    """净化 task_id — v0.28.0 (H-003): 委托 _utils 实现。

    保留 os.path.basename 防传入路径形式（外部 input 场景）。
    """
    return _utils_sanitize_id(os.path.basename(tid))


# ── Workspace ──
_WS_CACHE: dict | None = None
_WS_CACHE_TS = 0.0
_WS_CACHE_TTL_S = float(os.environ.get("CCC_BOARD_WS_CACHE_TTL", "3"))


def discover_workspaces(*, force: bool = False) -> dict:
    """自动发现所有已注册的 workspace（带短 TTL 缓存，避免每请求扫盘）。

    1. 优先读 CCC_WORKSPACES env var（逗号分隔 name:path）
    2. 回退到默认扫描 ~/program/ 下含 .ccc/board 的项目
    """
    global _WS_CACHE, _WS_CACHE_TS
    now = time.monotonic()
    if (
        not force
        and _WS_CACHE is not None
        and (now - _WS_CACHE_TS) < _WS_CACHE_TTL_S
    ):
        return dict(_WS_CACHE)

    # 1. 显式注册
    ws: dict[str, str] = {"CCC": str(CCC_HOME)}
    env = os.environ.get("CCC_WORKSPACES", "").strip()
    if env:
        program_parent = Path.home() / "program"
        for entry in env.split(","):
            entry = entry.strip()
            if not entry or ":" not in entry:
                continue
            name, path = entry.split(":", 1)
            resolved = Path(path).expanduser().resolve()
            if not resolved.is_absolute():
                continue
            # F4: 只允许 ~/program/ 下或 CCC_HOME 自身的路径
            allowed = resolved == CCC_HOME
            allowed = allowed or resolved.is_relative_to(program_parent)
            if not allowed:
                continue
            if resolved.joinpath(".ccc", "board").exists():
                ws[name] = str(resolved)

    # 2. 自动扫描 ~/program/（含 server-layout: apps/、infra 旁业务仓）
    program_dir = Path.home() / "program"
    if program_dir.is_dir():
        scan_roots = [program_dir]
        for nested in ("apps", "projects"):
            nested_dir = program_dir / nested
            if nested_dir.is_dir():
                scan_roots.append(nested_dir)
        for root in scan_roots:
            for sub in root.iterdir():
                if not sub.is_dir():
                    continue
                # 跳过非业务顶层
                if root == program_dir and sub.name in (
                    "archive",
                    "infra",
                    "apps",
                    "projects",
                ):
                    continue
                board = sub / ".ccc" / "board"
                if not board.exists():
                    continue
                name = sub.name
                if name == "qx-observer":
                    name = "qxo"  # 别名兼容
                if name in ws:
                    continue
                if name == "qx" and ws.get("qxo"):
                    continue
                ws[name] = str(sub)

    _WS_CACHE = ws
    _WS_CACHE_TS = now
    return dict(ws)


def now_iso() -> str:
    """v0.28.1: 北京时间 +08:00（与 _utils 一致）"""
    from _utils import now_iso as _utils_now_iso
    return _utils_now_iso()


def board_path(workspace: str) -> Optional[Path]:
    ws = discover_workspaces().get(workspace)
    if ws is None:
        return None
    return Path(ws) / ".ccc" / "board"


def validate_workspace(workspace: str) -> bool:
    return workspace in discover_workspaces()


# ── 看板操作（委托 FileBoardStore）──
def _store_for(workspace: str) -> FileBoardStore | None:
    bp = board_path(workspace)
    if bp is None:
        return None
    return FileBoardStore(bp.parent.parent)  # /workspace/.ccc/board → /workspace


def list_tasks(
    column: str, workspace: str, *, include_hidden: bool = False
) -> list[dict]:
    s = _store_for(workspace)
    if s is None:
        return []
    tasks = s.list_tasks(column, include_hidden=include_hidden)
    for t in tasks:
        t["_column"] = column
    return tasks


def get_board_state(workspace: str, *, include_hidden: bool = False) -> dict:
    return {
        col: list_tasks(col, workspace, include_hidden=include_hidden)
        for col in COLUMNS
    }


def move_task(task_id: str, from_col: str, to_col: str, workspace: str) -> bool:
    s = _store_for(workspace)
    if s is None:
        return False
    task_id = sanitize_id(task_id)
    return s.move_task(task_id, from_col, to_col)


def create_task(data: dict, workspace: str = "CCC", column: str = "backlog") -> bool:
    s = _store_for(workspace)
    if s is None:
        return False
    task_data = dict(data)
    task_data.pop("workspace", None)  # HTTP 控制字段，非 Board Protocol 数据
    task_data["id"] = sanitize_id(task_data.get("id", ""))
    if column == "backlog":
        task_data.setdefault("card_kind", "epic")
        task_data.setdefault("split_status", "pending")
    else:
        task_data.setdefault("card_kind", "work")
    return s.create_task(task_data, column=column)


def hide_completed_epics(workspace: str) -> int:
    """ui_hidden=true for done epics in backlog. Returns count."""
    s = _store_for(workspace)
    if s is None:
        return 0
    n = 0
    for t in s.list_tasks("backlog", include_hidden=True):
        if t.get("card_kind") == "epic" and t.get("split_status") == "done":
            if s.patch_task(t["id"], {"ui_hidden": True}):
                n += 1
    return n


# ── 时间线 ──
def get_timeline(workspace: str, limit: int = 20) -> list[dict]:
    """获取最近任务流动 + 角色执行事件"""
    events = []
    state = get_board_state(workspace)
    for col in COLUMNS:
        for task in state[col]:
            events.append(
                {
                    "type": "task",
                    "time": task.get("updated_at", task.get("created_at", "")),
                    "task_id": task["id"],
                    "title": task.get("title", ""),
                    "column": col,
                    "label": COLUMN_LABELS.get(col, col),
                    "color": COLUMN_COLORS.get(col, "#666"),
                }
            )
    # 角色执行日志
    log_dir = Path.home() / ".ccc" / "logs"
    if log_dir.exists():
        for f in sorted(
            log_dir.glob("role-*.log"), key=lambda p: p.stat().st_mtime, reverse=True
        )[:30]:
            fname = f.name
            role = fname.split("-")[1] if "-" in fname else "?"
            exit_code = "?"
            try:
                content = f.read_text()
            except (FileNotFoundError, OSError):
                continue
            for line in content.strip().split("\n"):
                if "exit=" in line:
                    exit_code = line.split("exit=")[-1]
            events.append(
                {
                    "type": "role_run",
                    "time": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
                    "role": role,
                    "exit_code": exit_code,
                    "size": f.stat().st_size,
                }
            )
    events.sort(key=lambda e: e.get("time", ""), reverse=True)
    return events[:limit]


def get_role_status() -> list[dict]:
    """7 角色最新执行状态"""
    status = []
    log_dir = Path.home() / ".ccc" / "logs"
    for role in ROLES:
        last = {"role": role, "status": "idle", "last_run": None, "exit_code": None}
        if log_dir.exists():
            logs = sorted(
                log_dir.glob(f"role-{role}-*.log"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if logs:
                latest = logs[0]
                try:
                    with open(latest) as f:
                        content = f.read()
                except FileNotFoundError:
                    continue
                for line in content.split("\n"):
                    if "exit=" in line:
                        ec = line.split("exit=")[-1].strip()
                        last["exit_code"] = ec
                        last["status"] = "ok" if ec == "0" else "fail"
                last["last_run"] = datetime.fromtimestamp(
                    latest.stat().st_mtime
                ).isoformat()
        status.append(last)
    return status


# ── Rate limiter ──
class _RateLimiter:
    def __init__(self, rate: int = 60, per_seconds: int = 60):
        self.rate = rate
        self.per = per_seconds
        self._buckets: dict[str, tuple[int, float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        with self._lock:
            now = time.monotonic()
            tokens, last = self._buckets.get(key, (self.rate, now))
            elapsed = now - last
            tokens = min(self.rate, tokens + elapsed * (self.rate / self.per))
            if tokens < 1:
                return False
            self._buckets[key] = (tokens - 1, now)
            return True


_rate_limiter = _RateLimiter()


# ── Dashboard thread-safe 缓存 ──
class _DashboardCache:
    """3s TTL 的 dashboard 缓存，ThreadingHTTPServer 安全"""
    def __init__(self, ttl_s: float = 3.0):
        self._cache: dict[str, tuple[dict, float]] = {}
        self._ttl = ttl_s
        self._lock = threading.Lock()

    def get(self, key: str) -> dict | None:
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            data, ts = entry
            if time.monotonic() - ts >= self._ttl:
                del self._cache[key]
                return None
            return data

    def set(self, key: str, data: dict) -> None:
        with self._lock:
            self._cache[key] = (data, time.monotonic())


_dash_cache = _DashboardCache()


# ── HTTP Handler ──
class BoardHTTPHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(
            *args, directory=str(CCC_HOME / "scripts" / "ccc-board-ui"), **kwargs
        )

    def _allowed_origin(self) -> str:
        # 本机任意端口可跨域（Board 仅绑 127.0.0.1；origin 含端口由浏览器区分）
        origin = self.headers.get("Origin", "")
        if not origin:
            return ""
        try:
            o = urlparse(origin)
            if o.hostname in ("localhost", "127.0.0.1", "[::1]"):
                return origin
        except Exception as e:
            _log.warning("origin parse failed for %r: %s", origin, e)

    def _json(self, data: dict, status: int = 200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        origin = self._allowed_origin()
        if origin:
            self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def _verify_auth(self) -> bool:
        client_ip, client_port = self.client_address
        token = os.environ.get("QX_BOARD_TOKEN", "").strip()
        # A24-11 + F-SEC-05 调和: 无 token 时仅检查本机 IP
        # 绑定 0.0.0.0 后 LAN IP 也是本机，用 socket 自动发现所有本机 IP
        if not token:
            allow_local = os.environ.get("CCC_BOARD_ALLOW_LOCAL_NO_TOKEN", "").strip() == "1"
            if allow_local:
                return True
            # 自动发现本机所有 IP（含 LAN IP），避免硬编码
            import socket as _sock
            _own_ips = set()
            try:
                _own_ips.update(
                    info[4][0]
                    for info in _sock.getaddrinfo(_sock.gethostname(), None)
                    if info[4] and info[4][0]
                )
            except OSError:
                pass
            _own_ips.add("127.0.0.1")
            _own_ips.add("::1")
            if client_ip in _own_ips:
                return True
            if not _rate_limiter.allow(f"auth:{client_ip}"):
                self._json({"error": "rate_limited"}, 429)
                return False
            _log.warning(
                "auth failed: QX_BOARD_TOKEN unset (client=%s not in own_ips)",
                client_ip,
            )
            self._json(
                {
                    "error": "unauthorized: QX_BOARD_TOKEN required "
                    "(or CCC_BOARD_ALLOW_LOCAL_NO_TOKEN=1 to allow any origin)"
                },
                401,
            )
            return False
        auth = self.headers.get("Authorization", "")
        if auth.startswith("Bearer ") and hmac.compare_digest(auth[7:], token):
            return True
        # v0.28.0 (M-005): bad token 也限速 + log
        if not _rate_limiter.allow(f"auth:{client_ip}"):
            self._json({"error": "rate_limited"}, 429)
            return False
        _log.warning("auth failed: bad token from %s", client_ip)
        self._json({"error": "unauthorized"}, 401)
        return False

    def _body(self) -> Optional[dict]:
        n = int(self.headers.get("Content-Length", 0))
        if n > MAX_CONTENT_LENGTH:
            self.send_error(413)
            return None
        b = self.rfile.read(n) if n else b"{}"
        try:
            return json.loads(b) if b else {}
        except json.JSONDecodeError:
            return {}

    def do_OPTIONS(self):
        origin = self._allowed_origin()
        self.send_response(204)
        if origin:
            self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        qs = parse_qs(parsed.query)
        ws = qs.get("workspace", ["CCC"])[0]

        # dashboard 支持 workspace=all（多看板聚合）；其余 API 必须是已知 workspace
        if not (path == "/api/dashboard" and ws == "all") and not validate_workspace(ws):
            self._json({"error": f"unknown workspace: {ws}"}, 400)
            return

        # v0.24.6 (A24-11): GET /api/* 也走 token 校验（仅在 QX_BOARD_TOKEN 设置时）
        # 之前只对 POST 校验；远端部署时 GET 可枚举全部 task
        if not self._verify_auth():
            return

        if path == "/api":
            self._json(
                {
                    "api": "CCC Board v0.18",
                    "endpoints": [
                        "GET /api/board",
                        "GET /api/config",
                        "GET /api/timeline",
                        "GET /api/roles",
                        "GET /api/logs",
                        "POST /api/tasks",
                        "POST /api/tasks/move",
                    ],
                }
            )

        elif path == "/api/board":
            fields = qs.get("fields", [None])[0]
            include_hidden = qs.get("include_hidden", ["0"])[0] in (
                "1",
                "true",
                "yes",
            )
            state = get_board_state(ws, include_hidden=include_hidden)
            for col, tasks in state.items():
                for t in tasks:
                    if fields == "summary":
                        t.pop("description", None)
                        t.pop("tags", None)
                        t.pop("assignee", None)
                    elif "description" in t and len(t["description"]) > 120:
                        t["description"] = t["description"][:120] + "..."
            self._json(
                {
                    "columns": state,
                    "counts": {c: len(state[c]) for c in COLUMNS},
                    "workspace": ws,
                    "workspaces": discover_workspaces(),
                }
            )

        elif path == "/api/config":
            self._json(
                {
                    "workspaces": discover_workspaces(),
                    "columns": COLUMNS,
                    "labels": COLUMN_LABELS,
                    "colors": COLUMN_COLORS,
                    "roles": ROLES,
                    "labels_cn": dict(
                        product="产品经理",
                        dev="开发",
                        reviewer="审查",
                        tester="测试",
                        ops="运维",
                        kb="归档",
                        regress="回归",
                    ),
                }
            )

        elif path.startswith("/api/tasks/") and len(path.split("/")) == 4:
            task_id = sanitize_id(path.split("/")[-1])
            # 在所有列中找这个 task
            found = None
            for col in COLUMNS:
                for t in list_tasks(col, ws):
                    if t.get("id") == task_id:
                        found = dict(t)
                        found["_column"] = col
                        break
                if found:
                    break
            if found:
                self._json(found)
            else:
                self._json({"error": "not found"}, 404)

        elif (
            path.startswith("/api/tasks/")
            and path.endswith("/events")
            and len(path.split("/")) == 5
        ):
            # GET /api/tasks/<id>/events — 返回任务详情 + 事件流
            task_id = sanitize_id(path.split("/")[-2])
            found = None
            for col in COLUMNS:
                for t in list_tasks(col, ws):
                    if t.get("id") == task_id:
                        found = dict(t)
                        found["_column"] = col
                        break
                if found:
                    break
            if not found:
                self._json({"error": "task not found"}, 404)
                return
            # 读 events 文件
            board = board_path(ws)
            if board is None:
                self._json({"error": "board not found"}, 500)
                return
            events = []
            ev_file = board / "events" / f"{task_id}.events.jsonl"
            if ev_file.exists():
                try:
                    with open(ev_file) as f:
                        for line in f:
                            line = line.strip()
                            if line:
                                try:
                                    events.append(json.loads(line))
                                except json.JSONDecodeError as e:
                                    _log.warning("skip malformed event line for %s: %s", task_id, e)
                except FileNotFoundError as e:
                    _log.warning("events file disappeared for %s: %s", task_id, e)
            found["events"] = events
            self._json(found)

        elif path == "/api/timeline":
            state = get_board_state(ws)
            events = []
            for col in COLUMNS:
                for task in state[col]:
                    events.append(
                        {
                            "type": "task",
                            "time": task.get("updated_at", task.get("created_at", "")),
                            "task_id": task["id"],
                            "title": task.get("title", ""),
                            "column": col,
                            "label": COLUMN_LABELS.get(col, col),
                            "color": COLUMN_COLORS.get(col, "#666"),
                        }
                    )
            # 修 v0.27: 之前漏掉 self._json() → 永远 404。这里补上。
            self._json({"events": events[:50]})

        elif path == "/api/dashboard":
            # v0.27 控制台首页聚合（多 workspace 合并）
            # 3s 内存缓存：同样请求在 3s 内直接返回旧数据，不重新扫盘
            _cache_key = qs.get("workspace", ["all"])[0]
            cached = _dash_cache.get(_cache_key)
            if cached is not None:
                self._json(cached)
                return

            ws_filter = _cache_key
            workspaces = discover_workspaces()
            if ws_filter != "all" and ws_filter not in workspaces:
                self._json({"error": f"unknown workspace: {ws_filter}"}, 400)
                return

            target_ws = list(workspaces.keys()) if ws_filter == "all" else [ws_filter]

            kpi = {
                "in_progress": 0,
                "testing": 0,
                "abnormal": 0,
                "ready_to_release": 0,
                "released_today": 0,
                "today": {"fixed": 0, "released": 0, "moved": 0},
            }
            active_tasks = []
            abnormal_tasks = []
            today_events = []

            for ws_name in target_ws:
                s = _store_for(ws_name)
                if s is None:
                    continue
                # 一次性读取各列，避免重复 IO
                ip_tasks = s.list_tasks("in_progress")
                te_tasks = s.list_tasks("testing")
                ab_tasks = s.list_tasks("abnormal")
                ve_tasks = s.list_tasks("verified")
                # KPI — 列计数与控制台字段对齐（不再把 testing 并入 in_progress）
                kpi["in_progress"] += len(ip_tasks)
                kpi["testing"] += len(te_tasks)
                kpi["abnormal"] += len(ab_tasks)
                kpi["ready_to_release"] += len(te_tasks) + len(ve_tasks)
                # Active
                for t in ip_tasks + te_tasks:
                    t["workspace"] = ws_name
                    active_tasks.append(enrich_task(t))
                # Abnormal
                for t in ab_tasks:
                    t["workspace"] = ws_name
                    abnormal_tasks.append(enrich_abnormal(t))
                # Today's events
                for ev in s.get_timeline():
                    if ev.get("event") != "move":
                        continue
                    ts = ev.get("timestamp", "")
                    if not is_today(ts):
                        continue
                    to = ev.get("to", "")
                    today_events.append({
                        "time": hhmm(ts),
                        "task_id": ev.get("task_id", ""),
                        "to_column": to,
                        "action_cn": event_action_cn(to),
                        "workspace": ws_name,
                    })
                    if to == "released":
                        kpi["today"]["released"] += 1
                        kpi["released_today"] += 1
                    elif to == "verified":
                        kpi["today"]["fixed"] += 1
                    else:
                        kpi["today"]["moved"] += 1

            # 排序 + 补 title
            today_events.sort(key=lambda e: e.get("time", ""), reverse=True)
            active_tasks.sort(key=lambda t: t.get("updated_at") or t.get("created_at") or "", reverse=True)

            title_cache = {}
            for ev in today_events:
                key = (ev["workspace"], ev["task_id"])
                if key in title_cache:
                    ev["task_title"] = title_cache[key]
                    continue
                s = _store_for(ev["workspace"])
                if s is None:
                    ev["task_title"] = ""
                    continue
                title = ""
                for col in ("in_progress", "testing", "verified", "released", "abnormal", "backlog", "planned"):
                    for t in s.list_tasks(col):
                        if t.get("id") == ev["task_id"]:
                            title = t.get("title", "")
                            break
                    if title:
                        break
                title_cache[key] = title
                ev["task_title"] = title

            result = {
                "kpi": kpi,
                "workspaces": workspaces,
                "active_tasks": active_tasks,
                "abnormal_tasks": abnormal_tasks,
                "today_events": today_events[:20],
                "generated_at": now_iso(),
                "filter": ws_filter,
            }
            _dash_cache.set(_cache_key, result)
            self._json(result)

        elif path == "/api/roles":
            self._json({"roles": get_role_status()})

        elif path == "/api/logs":
            entries = []
            show_snippet = qs.get("snippet", ["0"])[0] == "1"
            log_dir = Path.home() / ".ccc" / "logs"
            if log_dir.exists():
                for f in sorted(
                    log_dir.glob("role-*.log"),
                    key=lambda p: p.stat().st_mtime,
                    reverse=True,
                )[:25]:
                    fname = f.name
                    role = fname.split("-")[1] if "-" in fname else "?"
                    rc = "?"
                    snippet = ""
                    if show_snippet:
                        try:
                            content = f.read_text()
                        except (FileNotFoundError, OSError):
                            continue
                        for line in content.split("\n"):
                            if "exit=" in line:
                                rc = line.split("exit=")[-1]
                        snippet = content[-80:]
                    entries.append(
                        {
                            "role": role,
                            "size": f.stat().st_size,
                            "mtime": datetime.fromtimestamp(
                                f.stat().st_mtime
                            ).isoformat(),
                            "exit_code": rc,
                            "snippet": snippet,
                        }
                    )
            self._json({"logs": entries})

        elif path.startswith("/api/"):
            self._json({"error": "not found"}, 404)

        else:
            # UI 已迁入 CCC Hub :7777；Board 仅 API，旧 HTML 一律 302 到 Hub（禁缓存）
            hub = os.environ.get("CCC_HUB_URL", "http://127.0.0.1:7777").rstrip("/")
            if "board" in path:
                loc = hub + "/#/board"
            else:
                loc = hub + "/#/console"
            self.send_response(302)
            self.send_header("Location", loc)
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.end_headers()

    def do_POST(self):
        if not self._verify_auth():
            return
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        data = self._body()
        if data is None:
            return  # 413 already sent by _body
        ws = data.get("workspace", "CCC")

        if not validate_workspace(ws):
            self._json({"error": f"unknown workspace: {ws}"}, 400)
            return

        if path == "/api/tasks":
            # v0.26 Protocol v1: 用 validate_task_jsonl 校验 + 结构化 error
            try:
                from _board_store import validate_task_jsonl
            except ImportError:
                validate_task_jsonl = None
            if validate_task_jsonl is not None:
                # 自动补 created_at/updated_at 以满足校验（IDE 不一定知道）
                if "created_at" not in data:
                    data["created_at"] = now_iso()
                if "updated_at" not in data:
                    data["updated_at"] = data["created_at"]
                ok, errors = validate_task_jsonl(data)
                if not ok:
                    self._json({
                        "ok": False,
                        "error": "validation_failed",
                        "message": "task 校验未通过（CCC Board Protocol v1）",
                        "details": [
                            {"field": _field_of(err), "rule": _rule_of(err), "got": _got_of(err)}
                            for err in errors
                        ],
                        "fix_hint": _fix_hint_for(errors),
                    }, 400)
                    return
            # validate 通过或 validate 不可用 → 走原流程
            raw_tid = data.get("id", f"t{int(datetime.now().timestamp())}")
            if not isinstance(raw_tid, str) or not raw_tid.strip():
                self._json({"error": "invalid id"}, 400)
                return
            tid = sanitize_id(raw_tid)
            title = data.get("title", "")
            if not isinstance(title, str) or not title.strip():
                self._json({"error": "title required"}, 400)
                return
            description = data.get("description", "")
            if not isinstance(description, str):
                description = ""
            if len(title) > 500 or len(description) > 10000:
                self._json({"error": "title or description too long"}, 400)
                return
            task_data = dict(data)
            task_data.pop("workspace", None)
            task_data["id"] = tid
            # 安全（2026-07-19）：HTTP 创建 backlog 只能 epic（禁止直写 work）
            kind = str(task_data.get("card_kind") or "").strip().lower()
            if kind == "work":
                self._json({
                    "ok": False,
                    "error": "role_lock_violation",
                    "message": "API 禁止创建 card_kind=work；请走 Desktop transfer（epic）",
                }, 400)
                return
            task_data["card_kind"] = "epic"
            if create_task(task_data, workspace=ws, column="backlog"):
                # v0.41/v0.42.1: 下达 = enabled + 登记 workspace + 唤醒 Engine
                engine_wake = None
                try:
                    from _engine_wake import ensure_engine_for_task

                    root = discover_workspaces().get(ws)
                    engine_wake = ensure_engine_for_task(
                        reason="task_dispatch",
                        task_id=tid,
                        workspace=root,
                        workspace_name=ws,
                    )
                except Exception as exc:
                    engine_wake = {"ok": False, "error": str(exc)[:200]}
                self._json(
                    {"ok": True, "task_id": tid, "engine_wake": engine_wake}, 201
                )
            else:
                self._json({
                    "ok": False,
                    "error": "create_failed",
                    "message": "task 写入失败（id 重复或文件锁拒绝）",
                    "fix_hint": "检查 id 是否已存在；workspace 是否可写",
                }, 500)

        elif path == "/api/tasks/move":
            tid = sanitize_id(data.get("id"))
            fr, to = data.get("from"), data.get("to")
            if not all([tid, fr, to]):
                self._json({"error": "missing id/from/to"}, 400)
            elif fr == to:
                self._json({"error": "from and to must differ"}, 400)
            elif fr not in COLUMNS:
                self._json({"error": f"bad column: {fr}"}, 400)
            elif to not in COLUMNS:
                self._json({"error": f"bad column: {to}"}, 400)
            elif fr == "backlog" and to != "backlog":
                # 仅 epic 大卡禁止离开待办；误入 backlog 的 work 允许救出
                store = _store_for(ws)
                kind = None
                if store is not None:
                    try:
                        _col, task = store.find_task(tid)
                        if task is not None:
                            kind = task.get("card_kind")
                    except Exception:
                        kind = None
                if kind == "epic":
                    self._json(
                        {
                            "error": "epic_immobile",
                            "message": "待办大卡不可移入流转列；由 Claude 扇出子卡",
                        },
                        400,
                    )
                elif move_task(tid, fr, to, ws):
                    self._json({"ok": True, "id": tid, "from": fr, "to": to})
                else:
                    self._json({"error": f"{tid} not in {fr} (or epic blocked)"}, 404)
            elif move_task(tid, fr, to, ws):
                self._json({"ok": True, "id": tid, "from": fr, "to": to})
            else:
                self._json({"error": f"{tid} not in {fr} (or epic blocked)"}, 404)

        elif path == "/api/tasks/hide-completed-epics":
            n = hide_completed_epics(ws)
            self._json({"ok": True, "hidden": n})

        elif path == "/api/tasks/reopen":
            # v0.42: failures → 一键重开 + wake
            tid = sanitize_id(data.get("id") or data.get("task_id") or "")
            to_col = data.get("to") or "planned"
            if not tid:
                self._json({"error": "missing id"}, 400)
                return
            root = discover_workspaces().get(ws)
            if not root:
                self._json({"error": f"unknown workspace: {ws}"}, 400)
                return
            try:
                from _task_reopen import reopen_task

                result = reopen_task(Path(root), tid, to_col=str(to_col), wake=True)
            except Exception as exc:
                self._json({"ok": False, "error": str(exc)[:300]}, 500)
                return
            if result.get("ok"):
                self._json(result)
            else:
                self._json(result, 400)

        else:
            self._json({"error": "not found"}, 404)

    def log_message(self, fmt, *args):
        if "/api/" in str(args[0]):
            return
        sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), fmt % args))


# ── v0.26 Protocol v1: 结构化 error helper ──

def _field_of(error: str) -> str:
    """从 validate_task_jsonl error 字符串提取字段名（'id: required' → 'id'）"""
    return error.split(":", 1)[0].strip() if ":" in error else error


def _rule_of(error: str) -> str:
    """提取校验规则描述"""
    return error.split(":", 1)[1].strip() if ":" in error else error


def _got_of(error: str) -> str:
    """提取触发错误的值（如 'todo' / 'task 001'）"""
    # 匹配 'status: 'todo' not in COLUMNS' → got=todo
    import re as _re
    m = _re.search(r"'([^']+)'", error)
    return m.group(1) if m else ""


def _fix_hint_for(errors: list[str]) -> str:
    """从 errors 列表生成 1-2 句修复建议（≤ 200 字符）"""
    if not errors:
        return ""
    fields = [_field_of(e) for e in errors[:3]]
    hint_parts = []
    for f in fields:
        if f == "id":
            hint_parts.append("id 仅允许 a-zA-Z0-9_-")
        elif f == "title":
            hint_parts.append("title 必填且非空 ≤ 500 字符")
        elif f == "status":
            hint_parts.append("status ∈ backlog/planned/in_progress/testing/verified/released/abnormal")
        elif f in ("created_at", "updated_at"):
            hint_parts.append(f"{f} 需 ISO 8601 格式 YYYY-MM-DDTHH:MM:SSZ")
        elif f == "color_group":
            hint_parts.append("color_group ∈ [A-Z] 单字符")
        elif f == "color_depth":
            hint_parts.append("color_depth ≥ 0 整数")
    return "；".join(hint_parts)[:200]


# ── 启动 ──
def main():
    # v0.39.2: disabled 拒启；CCC_FOREGROUND=1（hub-dev）或 ui/enabled 可跑
    try:
        from _ccc_control import foreground_bypass, is_disabled, get_mode, may_start_ui
    except ImportError:
        is_disabled = lambda: (Path.home() / ".ccc" / "DISABLED").is_file()  # noqa: E731
        get_mode = lambda: "disabled" if is_disabled() else "enabled"  # noqa: E731
        may_start_ui = lambda: not is_disabled()  # noqa: E731
        foreground_bypass = lambda: os.environ.get("CCC_FOREGROUND", "") in (  # noqa: E731
            "1",
            "true",
            "yes",
        )

    if not foreground_bypass() and is_disabled():
        _log.warning("CCC control=%s — board idle hold (not listening)", get_mode())
        while is_disabled() and not foreground_bypass():
            time.sleep(60)
        _log.info("CCC control=%s — board starting", get_mode())
    elif not foreground_bypass() and not may_start_ui():
        _log.warning("CCC control=%s — UI not allowed", get_mode())
        while not may_start_ui() and not foreground_bypass():
            time.sleep(60)

    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=None)
    ap.add_argument("--host", default=None)
    args = ap.parse_args()

    # fallback: 环境变量 → Config 默认
    if args.port is None:
        args.port = int(os.environ.get("BOARD_PORT", str(_cfg.board_port)))
    if args.host is None:
        args.host = os.environ.get("BOARD_HOST", _cfg.board_host)

    ui_dir = CCC_HOME / "scripts" / "ccc-board-ui"
    ui_dir.mkdir(parents=True, exist_ok=True)

    srv = ThreadingHTTPServer((args.host, args.port), BoardHTTPHandler)
    cert_file = os.environ.get("CCC_BOARD_CERT")
    key_file = os.environ.get("CCC_BOARD_KEY")
    proto = "http"
    if cert_file and key_file:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(cert_file, key_file)
        srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
        proto = "https"
    print(f"CCC Board → {proto}://{args.host}:{args.port}")
    print(f"  ws: {list(discover_workspaces().keys())}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.server_close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
