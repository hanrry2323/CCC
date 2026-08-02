"""server/web/server.py — HTTP API 服务端（零依赖，Python stdlib 实现）。

提供 5 个 GET 接口，数据复用 board 查询（与 board.js 静态导出同源）。

用法:
    python3 -m server.web.server --port 9999

    # 使用默认端口（仅测试用）
    python3 -m server.web.server

API:
    GET /health              → {"status": "ok"}
    GET /board/realtime      → 实时视图（按状态分组）
    GET /board/recent        → 7 天回写视图
    GET /board/by_project    → 按项目分类
    GET /board/roadmap       → 线路图聚合（overview + by_project）

鉴权: 本卡仅只读接口，鉴权占位。
      上线前必须在所有接口前加账号密码 + 会话 token 鉴权。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
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

    def _send_404(self):
        self._send_json({"error": "not found"}, 404)

    def do_GET(self):
        path = self.path.rstrip("/")
        try:
            items = _load_board_items()
        except OSError as exc:
            self._send_json({"error": f"data load failed: {exc}"}, 500)
            return

        if path == "/health":
            self._send_json({"status": "ok"})
        elif path == "/board/realtime":
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