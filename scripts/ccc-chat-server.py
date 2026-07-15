#!/usr/bin/env python3
"""ccc-chat-server.py — CCC Chat Server v2 (模块化架构)"""
import os
import sys
import threading
import webbrowser
from pathlib import Path

# Ensure project root is on sys.path when launched as `python3 scripts/ccc-chat-server.py`
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import uvicorn

from scripts.chat_server.config import HOST, PORT, AUTH_USER, validate_auth_config
from scripts.chat_server.app import create_app

app = create_app()


def main():
    import argparse
    # F-SEC-01: 未设强口令则拒启
    validate_auth_config()

    bind_host = HOST
    bind_port = PORT

    parser = argparse.ArgumentParser(description="CCC Chat Server v2")
    parser.add_argument("--port", type=int, default=int(os.environ.get("CCC_CHAT_PORT", bind_port)))
    parser.add_argument("--host", default=os.environ.get("CCC_CHAT_HOST", bind_host))
    parser.add_argument("--no-open", action="store_true", default=os.environ.get("CCC_CHAT_NO_OPEN", "0") == "1")
    args = parser.parse_args()
    bind_port = args.port
    bind_host = args.host

    print("  CCC Chat Server v2")
    print("  ─────────────────────")
    print(f"  地址: http://{bind_host}:{bind_port}")
    print(f"  本地: http://localhost:{bind_port}")
    # F-SEC-02: 永不打印密码
    print(f"  认证: Basic Auth 已启用（用户 {AUTH_USER}）")

    if not args.no_open and bind_host in ("0.0.0.0", "127.0.0.1", "localhost"):
        def _open():
            try:
                webbrowser.open(f"http://localhost:{bind_port}")
            except Exception as exc:
                print(f"  WARN: 自动打开浏览器失败: {exc}")
        threading.Timer(1.2, _open).start()

    uvicorn.run(app, host=bind_host, port=bind_port, log_level="info")


if __name__ == "__main__":
    main()
