#!/usr/bin/env python3
"""ccc-board-server.py — CCC 看板 HTTP 服务 (v0.18)

提供 REST API + 前端 UI，绑定 :7777。
支持多 workspace（CCC 自身 / qxo 等）。

依赖：Python 3.8+ 标准库（无第三方包）
"""
import argparse
import json
import os
import shutil
import socketserver
import subprocess
import sys
from datetime import datetime, timezone
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

# ── 配置 ──────────────────────────────────────────────────────────
CCC_HOME = Path(__file__).resolve().parent.parent
COLUMNS = ["backlog", "planned", "in_progress", "testing", "verified", "released"]
COLUMN_LABELS = {
    "backlog": "待办",
    "planned": "已计划",
    "in_progress": "开发中",
    "testing": "测试中",
    "verified": "已验证",
    "released": "已发布",
}
COLUMN_COLORS = {
    "backlog": "#94a3b8",
    "planned": "#6366f1",
    "in_progress": "#f59e0b",
    "testing": "#f97316",
    "verified": "#22c55e",
    "released": "#3b82f6",
}

# ── Workspace 发现 ────────────────────────────────────────────────
DEFAULT_WORKSPACES = {
    "CCC": str(CCC_HOME),
}


def discover_workspaces() -> dict:
    """扫描所有有 .ccc/board/ 的项目"""
    workspaces = dict(DEFAULT_WORKSPACES)
    # 常用项目路径
    candidates = [
        ("qxo", Path.home() / "program" / "qx-observer"),
        ("xianyu", Path.home() / "program" / "xianyu"),
    ]
    for name, path in candidates:
        if (path / ".ccc" / "board").exists():
            workspaces[name] = str(path)
    return workspaces


# ── 看板操作 ──────────────────────────────────────────────────────
def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def board_path(workspace: str) -> Path:
    ws = discover_workspaces().get(workspace, str(CCC_HOME))
    return Path(ws) / ".ccc" / "board"


def list_tasks(column: str, workspace: str) -> list[dict]:
    """读某列所有 task（JSONL）"""
    col_dir = board_path(workspace) / column
    if not col_dir.exists():
        return []
    tasks = []
    for f in sorted(col_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True):
        with open(f) as fp:
            for line in fp:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    obj["_file"] = f.name
                    obj["_column"] = column
                    tasks.append(obj)
                except json.JSONDecodeError:
                    pass
    return tasks


def get_board_state(workspace: str) -> dict:
    """完整看板状态"""
    state = {}
    for col in COLUMNS:
        state[col] = list_tasks(col, workspace)
    return state


def move_task(task_id: str, from_col: str, to_col: str, workspace: str) -> bool:
    """把 task 从 from_col 挪到 to_col"""
    board = board_path(workspace)
    src = board / from_col / f"{task_id}.jsonl"
    if not src.exists():
        return False
    task = None
    with open(src) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if obj.get("id") == task_id:
                    task = obj
                    break
            except json.JSONDecodeError:
                pass
    if not task:
        return False

    task["status"] = to_col
    task["updated_at"] = now_iso()

    dst = board / to_col / f"{task_id}.jsonl"
    with open(dst, "w") as f:
        f.write(json.dumps(task, ensure_ascii=False) + "\n")
    src.unlink(missing_ok=True)
    return True


def create_task(task_id: str, title: str, description: str = "", workspace: str = "CCC") -> bool:
    """在 backlog 创建新 task"""
    task = {
        "id": task_id,
        "title": title,
        "description": description,
        "status": "backlog",
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "assignee": None,
        "tags": [],
    }
    dst = board_path(workspace) / "backlog" / f"{task_id}.jsonl"
    dst.parent.mkdir(parents=True, exist_ok=True)
    with open(dst, "w") as f:
        f.write(json.dumps(task, ensure_ascii=False) + "\n")
    return True


def get_logs(lines: int = 50) -> list[dict]:
    """获取最近的角色执行日志"""
    log_dir = Path.home() / ".ccc" / "logs"
    if not log_dir.exists():
        return []
    entries = []
    for f in sorted(log_dir.glob("role-*.log"), key=lambda p: p.stat().st_mtime, reverse=True)[:20]:
        # 解析日志格式： [HH:MM:SS] role tick | role exit=N
        with open(f) as fp:
            content = fp.read()
        # 取文件名推导角色名
        fname = f.name  # role-<role>-<ts>.log
        role = fname.split("-")[1] if "-" in fname else "?"
        entries.append({
            "file": fname,
            "role": role,
            "mtime": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
            "size": f.stat().st_size,
            "snippet": content[-300:] if content else "",
        })
    return entries[:lines]


# ── HTTP Handler ──────────────────────────────────────────────────
class BoardHTTPHandler(SimpleHTTPRequestHandler):
    """CCC 看板 HTTP Handler"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(CCC_HOME / "scripts" / "ccc-board-ui"), **kwargs)

    def _send_json(self, data: dict, status: int = 200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"))

    def _send_text(self, text: str, status: int = 200, ctype: str = "text/plain"):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(text.encode("utf-8"))

    def _get_workspace(self) -> str:
        """从 query 取 workspace，默认 CCC"""
        qs = parse_qs(urlparse(self.path).query)
        return qs.get("workspace", ["CCC"])[0]

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PATCH, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        # API 路由
        if path == "/api/board":
            ws = self._get_workspace()
            state = get_board_state(ws)
            # 同时返回 index 摘要
            counts = {col: len(state[col]) for col in COLUMNS}
            self._send_json({
                "columns": state,
                "counts": counts,
                "workspace": ws,
                "workspaces": discover_workspaces(),
            })

        elif path == "/api/config":
            self._send_json({
                "workspaces": discover_workspaces(),
                "columns": COLUMNS,
                "labels": COLUMN_LABELS,
                "colors": COLUMN_COLORS,
                "default_workspace": "CCC",
            })

        elif path == "/api/logs":
            qs = parse_qs(parsed.query)
            n = int(qs.get("lines", [50])[0])
            self._send_json({"logs": get_logs(n)})

        elif path == "/api" or path == "":
            self._send_json({
                "api": "CCC Board Server v0.18",
                "endpoints": {
                    "GET /api/board": "看板状态（?workspace=）",
                    "GET /api/config": "配置信息",
                    "GET /api/logs": "执行日志（?lines=N）",
                    "POST /api/tasks": "创建任务",
                    "POST /api/tasks/move": "移动任务",
                }
            })

        else:
            # 静态文件
            super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len) if content_len else b"{}"
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            self._send_json({"error": "invalid JSON"}, 400)
            return

        ws = data.get("workspace", self._get_workspace())

        if path == "/api/tasks":
            task_id = data.get("id", f"task-{int(datetime.now().timestamp())}")
            title = data.get("title", "未命名任务")
            description = data.get("description", "")
            if create_task(task_id, title, description, ws):
                self._send_json({"status": "ok", "id": task_id})
            else:
                self._send_json({"error": "create failed"}, 500)

        elif path == "/api/tasks/move":
            task_id = data.get("id")
            from_col = data.get("from")
            to_col = data.get("to")
            if not all([task_id, from_col, to_col]):
                self._send_json({"error": "missing id/from/to"}, 400)
                return
            # 验证列名
            if to_col not in COLUMNS:
                self._send_json({"error": f"invalid column: {to_col}"}, 400)
                return
            if move_task(task_id, from_col, to_col, ws):
                self._send_json({"status": "ok", "id": task_id, "from": from_col, "to": to_col})
            else:
                self._send_json({"error": f"task {task_id} not found in {from_col}"}, 404)

        else:
            self._send_json({"error": "not found"}, 404)

    def log_message(self, format, *args):
        # 安静一点
        if "GET /api/" in str(args[0]) or "POST /api/" in str(args[0]):
            return  # 不打印 API 请求
        sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), format % args))


# ── 启动 ──────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description="CCC 看板 HTTP 服务")
    ap.add_argument("--port", type=int, default=7777, help="监听端口 (默认 7777)")
    ap.add_argument("--host", default="0.0.0.0", help="监听地址 (默认 0.0.0.0)")
    args = ap.parse_args()

    # 确保 UI 目录存在
    ui_dir = CCC_HOME / "scripts" / "ccc-board-ui"
    ui_dir.mkdir(parents=True, exist_ok=True)

    server = HTTPServer((args.host, args.port), BoardHTTPHandler)
    print(f"CCC Board Server running on http://{args.host}:{args.port}")
    print(f"  UI:     http://localhost:{args.port}/")
    print(f"  API:    http://localhost:{args.port}/api")
    print(f"  Board:  http://localhost:{args.port}/api/board")
    print(f"  Config: http://localhost:{args.port}/api/config")
    print(f"  Logs:   http://localhost:{args.port}/api/logs")
    print(f"  Workspaces: {json.dumps(discover_workspaces(), indent=2)}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.server_close()


if __name__ == "__main__":
    main()
