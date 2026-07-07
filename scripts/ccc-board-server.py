#!/usr/bin/env python3
"""ccc-board-server.py — CCC 看板 HTTP 服务 (v0.18)

提供 REST API + 前端 UI，绑定 :7777。
支持多 workspace（CCC / qxo 自动发现）。

依赖：Python 3.8+ 标准库
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

# ── 配置 ──
CCC_HOME = Path(__file__).resolve().parent.parent
COLUMNS = ["backlog", "planned", "in_progress", "testing", "verified", "released"]
COLUMN_LABELS = {
    "backlog": "待办", "planned": "已计划", "in_progress": "开发中",
    "testing": "测试中", "verified": "已验证", "released": "已发布",
}
COLUMN_COLORS = {
    "backlog": "#94a3b8", "planned": "#6366f1", "in_progress": "#f59e0b",
    "testing": "#f97316", "verified": "#22c55e", "released": "#3b82f6",
}
ROLES = ["product", "dev", "reviewer", "tester", "ops", "kb", "regress"]
MAX_CONTENT_LENGTH = 1_048_576


def sanitize_id(tid: str) -> str:
    return re.sub(r'[^a-zA-Z0-9_-]', '', os.path.basename(tid))


# ── Workspace ──
def discover_workspaces() -> dict:
    ws = {"CCC": str(CCC_HOME)}
    for name, path in [("qxo", Path.home() / "program" / "qx-observer")]:
        if (path / ".ccc" / "board").exists():
            ws[name] = str(path)
    return ws


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def board_path(workspace: str) -> Path | None:
    ws = discover_workspaces().get(workspace)
    if ws is None:
        return None
    return Path(ws) / ".ccc" / "board"


def validate_workspace(workspace: str) -> bool:
    return workspace in discover_workspaces()


# ── 看板操作 ──
def list_tasks(column: str, workspace: str) -> list[dict]:
    col_dir = board_path(workspace)
    if col_dir is None:
        return []
    col_dir = col_dir / column
    if not col_dir.exists():
        return []
    tasks = []
    for f in sorted(col_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
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
                        print(f"bad jsonl line in {f}: {line}", file=sys.stderr)
        except FileNotFoundError:
            pass
    return tasks


def get_board_state(workspace: str) -> dict:
    return {col: list_tasks(col, workspace) for col in COLUMNS}


def move_task(task_id: str, from_col: str, to_col: str, workspace: str) -> bool:
    task_id = sanitize_id(task_id)
    board = board_path(workspace)
    if board is None:
        return False
    src = board / from_col / f"{task_id}.jsonl"
    if not src.exists():
        return False
    task = None
    try:
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
                    print(f"bad jsonl line in {src}: {line}", file=sys.stderr)
    except FileNotFoundError:
        return False
    if not task:
        return False
    task["status"] = to_col
    task["updated_at"] = now_iso()
    task.setdefault("moves", []).append({"from": from_col, "to": to_col, "at": now_iso()})
    dst = board / to_col / f"{task_id}.jsonl"
    try:
        with open(dst, "w") as f:
            f.write(json.dumps(task, ensure_ascii=False) + "\n")
    except FileNotFoundError:
        return False
    src.unlink(missing_ok=True)
    return True


def create_task(task_id: str, title: str, description: str = "", workspace: str = "CCC") -> bool:
    task_id = sanitize_id(task_id)
    bp = board_path(workspace)
    if bp is None:
        return False
    task = {
        "id": task_id, "title": title, "description": description,
        "status": "backlog", "created_at": now_iso(), "updated_at": now_iso(),
        "moves": [],
    }
    dst = bp / "backlog" / f"{task_id}.jsonl"
    dst.parent.mkdir(parents=True, exist_ok=True)
    with open(dst, "w") as f:
        f.write(json.dumps(task, ensure_ascii=False) + "\n")
    return True


# ── 时间线 ──
def get_timeline(workspace: str, limit: int = 20) -> list[dict]:
    """获取最近任务流动 + 角色执行事件"""
    events = []
    state = get_board_state(workspace)
    for col in COLUMNS:
        for task in state[col]:
            events.append({
                "type": "task",
                "time": task.get("updated_at", task.get("created_at", "")),
                "task_id": task["id"],
                "title": task.get("title", ""),
                "column": col,
                "label": COLUMN_LABELS.get(col, col),
                "color": COLUMN_COLORS.get(col, "#666"),
            })
    # 角色执行日志
    log_dir = Path.home() / ".ccc" / "logs"
    if log_dir.exists():
        for f in sorted(log_dir.glob("role-*.log"), key=lambda p: p.stat().st_mtime, reverse=True)[:30]:
            try:
                with open(f) as fp:
                    content = fp.read()
            except FileNotFoundError:
                continue
            fname = f.name
            role = fname.split("-")[1] if "-" in fname else "?"
            exit_code = "?"
            for line in content.strip().split("\n"):
                if "exit=" in line:
                    exit_code = line.split("exit=")[-1]
            events.append({
                "type": "role_run",
                "time": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
                "role": role,
                "exit_code": exit_code,
                "size": f.stat().st_size,
                "snippet": content[-200:] if content else "",
            })
    events.sort(key=lambda e: e.get("time", ""), reverse=True)
    return events[:limit]


def get_role_status() -> list[dict]:
    """7 角色最新执行状态"""
    status = []
    log_dir = Path.home() / ".ccc" / "logs"
    for role in ROLES:
        last = {"role": role, "status": "idle", "last_run": None, "exit_code": None}
        if log_dir.exists():
            logs = sorted(log_dir.glob(f"role-{role}-*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
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
                last["last_run"] = datetime.fromtimestamp(latest.stat().st_mtime).isoformat()
        status.append(last)
    return status


# ── HTTP Handler ──
class BoardHTTPHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(CCC_HOME / "scripts" / "ccc-board-ui"), **kwargs)

    def _json(self, data: dict, status: int = 200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def _body(self) -> dict | None:
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
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        qs = parse_qs(parsed.query)
        ws = qs.get("workspace", ["CCC"])[0]

        if not validate_workspace(ws):
            self._json({"error": f"unknown workspace: {ws}"}, 400)
            return

        if path == "/api":
            self._json({"api": "CCC Board v0.18", "endpoints": [
                "GET /api/board", "GET /api/config", "GET /api/timeline",
                "GET /api/roles", "GET /api/logs",
                "POST /api/tasks", "POST /api/tasks/move",
            ]})

        elif path == "/api/board":
            state = get_board_state(ws)
            self._json({"columns": state, "counts": {c: len(state[c]) for c in COLUMNS},
                        "workspace": ws, "workspaces": discover_workspaces()})

        elif path == "/api/config":
            self._json({"workspaces": discover_workspaces(), "columns": COLUMNS,
                        "labels": COLUMN_LABELS, "colors": COLUMN_COLORS,
                        "roles": ROLES, "labels_cn": dict(product="产品经理", dev="开发",
                            reviewer="审查", tester="测试", ops="运维", kb="归档", regress="回归")})

        elif path.startswith("/api/tasks/") and len(path.split("/")) == 4:
            task_id = sanitize_id(path.split("/")[-1])
            # 在所有列中找这个 task
            found = None
            for col in COLUMNS:
                for t in list_tasks(col, ws):
                    if t.get("id") == task_id:
                        found = t
                        found["_column"] = col
                        break
                if found:
                    break
            if found:
                self._json(found)
            else:
                self._json({"error": "not found"}, 404)

        elif path == "/api/timeline":
            self._json({"events": get_timeline(ws, int(qs.get("limit", [20])[0]))})

        elif path == "/api/roles":
            self._json({"roles": get_role_status()})

        elif path == "/api/logs":
            entries = []
            log_dir = Path.home() / ".ccc" / "logs"
            if log_dir.exists():
                for f in sorted(log_dir.glob("role-*.log"), key=lambda p: p.stat().st_mtime, reverse=True)[:25]:
                    try:
                        with open(f) as fp:
                            content = fp.read()
                    except FileNotFoundError:
                        continue
                    fname = f.name
                    role = fname.split("-")[1] if "-" in fname else "?"
                    rc = "?"
                    for line in content.split("\n"):
                        if "exit=" in line:
                            rc = line.split("exit=")[-1]
                    entries.append({
                        "role": role, "size": f.stat().st_size,
                        "mtime": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
                        "exit_code": rc,
                        "snippet": content[-200:],
                    })
            self._json({"logs": entries})

        else:
            super().do_GET()

    def do_POST(self):
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
            tid = sanitize_id(data.get("id", f"t{int(datetime.now().timestamp())}"))
            if create_task(tid, data.get("title", ""), data.get("description", ""), ws):
                self._json({"ok": True, "id": tid})
            else:
                self._json({"error": "create failed"}, 500)

        elif path == "/api/tasks/move":
            tid = sanitize_id(data.get("id"))
            fr, to = data.get("from"), data.get("to")
            if not all([tid, fr, to]):
                self._json({"error": "missing id/from/to"}, 400)
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


# ── 启动 ──
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=None)
    ap.add_argument("--host", default=None)
    args = ap.parse_args()

    # fallback: 环境变量 → 硬编码默认
    if args.port is None:
        args.port = int(os.environ.get("BOARD_PORT", "7777"))
    if args.host is None:
        args.host = os.environ.get("BOARD_HOST", "127.0.0.1")

    ui_dir = CCC_HOME / "scripts" / "ccc-board-ui"
    ui_dir.mkdir(parents=True, exist_ok=True)

    srv = HTTPServer((args.host, args.port), BoardHTTPHandler)
    print(f"CCC Board → http://{args.host}:{args.port}")
    print(f"  ws: {list(discover_workspaces().keys())}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.server_close()


if __name__ == "__main__":
    main()
