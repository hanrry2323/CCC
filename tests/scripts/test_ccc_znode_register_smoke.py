"""Smoke tests for ccc-znode-register.py.

Verifies:
1. 正常注册: 起一个本地 HTTP server mock cluster-bus,验证 POST payload
2. bus 不可达: exit 0 + warning(非致命)
3. 缺参数: argparse exit 2
4. 心跳线程: 启动后能用 SIGINT 干净退出

Note: 因为 subprocess 启动新 Python 进程,urllib mock 不可跨进程,
所以用本地真实 HTTP server (http.server.ThreadingHTTPServer) 模拟 bus。
"""
from __future__ import annotations

import json
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT = ROOT / "scripts" / "ccc-znode-register.py"


# ---- 本地 mock cluster-bus ----------------------------------------------
class _MockBusHandler(BaseHTTPRequestHandler):
    """记录所有收到的 POST payload 到共享变量。"""

    records: list[dict] = []
    response_status: int = 201
    response_body: dict = {"node_id": "test", "status": "registered"}

    def log_message(self, format, *args):
        pass  # 静音 access log

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8") if length else "{}"
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            payload = {"_raw": body}

        if "/api/node/register" in self.path:
            _MockBusHandler.records.append({"endpoint": "register", "payload": payload})
        elif "/api/node/heartbeat" in self.path:
            _MockBusHandler.records.append({"endpoint": "heartbeat", "payload": payload})
        else:
            _MockBusHandler.records.append({"endpoint": self.path, "payload": payload})

        resp = json.dumps(_MockBusHandler.response_body).encode()
        self.send_response(_MockBusHandler.response_status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(resp)))
        self.end_headers()
        self.wfile.write(resp)


@pytest.fixture
def mock_bus():
    """起一个本地 mock cluster-bus,返回 (port, records_list_ref)。"""
    _MockBusHandler.records = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), _MockBusHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield port
    server.shutdown()
    server.server_close()


def _run_register(*args: str, timeout: int = 15) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


# ---- 测试 ----------------------------------------------------------------
def test_help_exits_zero():
    """--help 打印帮助并 exit 0。"""
    p = _run_register("--help")
    assert p.returncode == 0
    assert "Register" in p.stdout or "register" in p.stdout


def test_register_with_mock_bus_exits_zero(mock_bus):
    """Mock bus 200 → 正常 register 调用,exit 0 + 打印 OK。"""
    p = _run_register(
        "--node-id", "zcode-test",
        "--bus-url", f"http://127.0.0.1:{mock_bus}",
        "--capabilities", "zcode", "glm-5",
    )

    assert p.returncode == 0, f"stderr={p.stderr}"
    assert "OK" in p.stdout
    assert "registered" in p.stdout.lower()
    assert "zcode-test" in p.stdout


def test_register_with_bus_unreachable_exits_zero():
    """bus 不可达时仍 exit 0(单任务场景不依赖 bus,non-fatal warning)。"""
    # 用一个肯定不会监听的端口
    p = _run_register(
        "--node-id", "zcode-lonely",
        "--bus-url", "http://127.0.0.1:1",  # port 1 = 几乎肯定拒绝连接
    )

    assert p.returncode == 0
    assert "WARN" in p.stderr or "warning" in p.stderr.lower()


def test_register_payload_has_required_fields(mock_bus):
    """验证 register payload 包含必要字段(供 ccc-dispatch.py 路由用)。"""
    _run_register(
        "--node-id", "zcode-payload",
        "--bus-url", f"http://127.0.0.1:{mock_bus}",
        "--anthropic-base-url", "https://test.example/api/anthropic",
        "--model", "glm-5",
        "--capabilities", "zcode", "glm-5", "claude-p",
    )

    # 检查 mock bus 收到的 payload
    register_calls = [r for r in _MockBusHandler.records if r["endpoint"] == "register"]
    assert len(register_calls) == 1, f"应收到 1 个 register 调用,实际 {len(register_calls)}"

    payload = register_calls[0]["payload"]
    assert payload["node_id"] == "zcode-payload"
    assert payload["host"] == socket.gethostname()
    # Bug fix (zcode-blindspot-fill): cluster-bus Pydantic schema requires port >= 1,
    # so ZCode uses 65535 sentinel + listens_on_tcp=false metadata
    assert payload["port"] == 65535
    assert payload["metadata"]["listens_on_tcp"] is False
    assert "zcode" in payload["capabilities"]
    assert "glm-5" in payload["capabilities"]
    assert "claude-p" in payload["capabilities"]
    assert payload["metadata"]["provider"] == "glm"
    assert payload["metadata"]["model"] == "glm-5"
    assert payload["metadata"]["anthropic_base_url"] == "https://test.example/api/anthropic"


def test_default_capabilities_include_zcode_and_glm(mock_bus):
    """不传 --capabilities 时,默认应包含 zcode + glm-5(本 adapter 核心声明)。"""
    _run_register(
        "--node-id", "zcode-defaults",
        "--bus-url", f"http://127.0.0.1:{mock_bus}",
    )

    register_calls = [r for r in _MockBusHandler.records if r["endpoint"] == "register"]
    assert len(register_calls) == 1
    payload = register_calls[0]["payload"]
    caps = payload["capabilities"]
    assert "zcode" in caps, "zcode capability 必需"
    assert "glm-5" in caps, "glm-5 capability 必需"
    assert "claude-p" in caps, "claude-p capability 必需"
    assert "shell" in caps
    assert "git" in caps


def test_heartbeat_thread_exits_on_interrupt(mock_bus):
    """--daemon 模式启动心跳后,SIGINT 干净退出,且收到 heartbeat 请求。"""
    import signal

    proc = subprocess.Popen(
        [sys.executable, str(SCRIPT),
         "--node-id", "zcode-hb",
         "--bus-url", f"http://127.0.0.1:{mock_bus}",
         "--daemon"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    # 等几秒让心跳跑 1-2 次(默认 30s 一次太慢,但脚本会立刻打 "[heartbeat] started")
    time.sleep(2.0)
    proc.send_signal(signal.SIGINT)
    try:
        stdout, stderr = proc.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        stdout, stderr = proc.communicate()

    assert "heartbeat" in stdout.lower(), f"stdout={stdout!r} stderr={stderr!r}"
    assert proc.returncode == 0, f"rc={proc.returncode} stderr={stderr}"

    # 至少收到 1 个 register (daemon 启动前) + 0+ heartbeat (2s 内可能没跑完一次)
    register_calls = [r for r in _MockBusHandler.records if r["endpoint"] == "register"]
    assert len(register_calls) == 1, "daemon 启动前应 register 一次"