#!/usr/bin/env python3
"""ccc-board-server.py — CCC 看板 HTTP 服务 (v0.20)

提供 REST API + 前端 UI，绑定 :7777。
支持多 workspace（CCC / qxo 自动发现）。

依赖：Python 3.8+ 标准库
"""

from __future__ import annotations
import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import ssl
import threading
import time
from typing import Optional
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from _config import Config
from _board_store import COLUMNS, FileBoardStore

_cfg = Config()

# ── 配置 ──
CCC_HOME = _cfg.ccc_home
COLUMN_LABELS = {
    "backlog": "待办",
    "planned": "已计划",
    "in_progress": "开发中",
    "testing": "测试中",
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
    return re.sub(r"[^a-zA-Z0-9_-]", "", os.path.basename(tid))


# ── Workspace ──
def discover_workspaces() -> dict:
    """自动发现所有已注册的 workspace

    1. 优先读 CCC_WORKSPACES env var（逗号分隔 name:path）
    2. 回退到默认扫描 ~/program/ 下含 .ccc/board 的项目
    """
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

    # 2. 自动扫描 ~/program/
    program_dir = Path.home() / "program"
    if program_dir.is_dir():
        for sub in program_dir.iterdir():
            if not sub.is_dir():
                continue
            board = sub / ".ccc" / "board"
            if not board.exists():
                continue
            name = sub.name
            if name == "qx-observer":
                name = "qxo"  # 别名兼容
            # 别占用 qxo 已注册的 slot
            if name in ws:
                continue
            # projects/ 下要带上层目录名（避免 qx 和 projects/qx 冲突）
            if name == "qx" and ws.get("qxo"):
                continue
            ws[name] = str(sub)
        # projects/ 子目录额外扫描
        projects = program_dir / "projects"
        if projects.is_dir():
            for sub in projects.iterdir():
                if not sub.is_dir():
                    continue
                board = sub / ".ccc" / "board"
                if not board.exists():
                    continue
                name = sub.name
                if name in ws:
                    continue
                ws[name] = str(sub)
    return ws


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


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


def list_tasks(column: str, workspace: str) -> list[dict]:
    s = _store_for(workspace)
    if s is None:
        return []
    tasks = s.list_tasks(column)
    for t in tasks:
        t["_column"] = column
    return tasks


def get_board_state(workspace: str) -> dict:
    return {col: list_tasks(col, workspace) for col in COLUMNS}


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
    task_data.pop("workspace", None)           # HTTP 控制字段，非 Board Protocol 数据
    task_data["id"] = sanitize_id(task_data.get("id", ""))
    return s.create_task(task_data, column=column)


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


# ── HTTP Handler ──
class BoardHTTPHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(
            *args, directory=str(CCC_HOME / "scripts" / "ccc-board-ui"), **kwargs
        )

    def _allowed_origin(self) -> str:
        origin = self.headers.get("Origin", "")
        if not origin:
            return ""
        try:
            o = urlparse(origin)
            if o.hostname in ("localhost", "127.0.0.1", "[::1]"):
                return origin
        except Exception:
            pass
        return ""

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
        is_local = client_ip in ("127.0.0.1", "::1", "[::1]")
        token = os.environ.get("QX_BOARD_TOKEN", "").strip()
        if not token:
            if is_local:
                return True
            self._json({"error": "unauthorized: non-local request without token"}, 401)
            return False
        auth = self.headers.get("Authorization", "")
        if auth.startswith("Bearer ") and auth[7:] == token:
            return True
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

        if not validate_workspace(ws):
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
            state = get_board_state(ws)
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
                                except json.JSONDecodeError:
                                    pass
                except FileNotFoundError:
                    pass
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
            # 非 /api/* 路径 → 委托父类 serve 静态文件（scripts/ccc-board-ui/）
            # 修 v0.23.13: 之前 else 兜底返 JSON 404，导致 GET / 和 /index.html 全 404
            super().do_GET()

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
                    data["created_at"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
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
            if create_task(task_data, workspace=ws, column="backlog"):
                self._json({"ok": True, "task_id": tid}, 201)
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
            elif move_task(tid, fr, to, ws):
                self._json({"ok": True, "id": tid, "from": fr, "to": to})
            else:
                self._json({"error": f"{tid} not in {fr}"}, 404)

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
    main()
