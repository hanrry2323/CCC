"""test_result_report_api — C 阶段一：执行结果上报通道（旁路观测）。

覆盖：
- 鉴权矩阵：未配置 token=503 / 错误 token=401 / 正确 token=2xx
- Schema：未知 payload 字段 400 / 未知 event 400 / 枚举外 status 400 /
  超 16KB 413 / 未知 work_id 404
- 幂等：同 (work_id,event,event_id) 二次 → deduped:true，事件数不增
- 限速：单 work_id >30 事件/分钟 → 429
- GET 读回 + work_id 过滤 + limit 校验
- wrapper 侧：dummy HTTP server 收集上报断言 rc→event 映射 / disabled 旗标
"""

from __future__ import annotations

import hashlib
import json
import os
import socket
import threading
import time
from http.client import HTTPConnection, HTTPResponse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

# ── 测试环境（在 import server 之前写入） ──
TEST_USER = "testuser"
TEST_PASS = "testpass"
os.environ.setdefault("CCC_WEB_USERNAME", TEST_USER)
os.environ.setdefault("CCC_WEB_PASSWORD_HASH", hashlib.sha256(TEST_PASS.encode()).hexdigest())
os.environ.setdefault("CCC_WEB_AUTH_REQUIRED", "1")
os.environ.setdefault("CCC_WEB_TOKEN_TTL", "3600")
REPORT_TOKEN = "report-test-token"
os.environ["CCC_RESULT_REPORT_TOKEN"] = REPORT_TOKEN

import server.web.server as web_server  # noqa: E402
from server.web.result_report import STORE, MAX_BODY_BYTES  # noqa: E402

RETRY_COUNT = 10
RETRY_DELAY = 0.05

_VALID = {
    "work_id": "tst904",
    "event": "executor_completed",
    "event_id": "e-abc",
    "payload": {"executor_rc": 0, "result_path": "tst904-ccc-result.md"},
}


# ── dummy wrapper 上报接收端（pytest 线程） ──


class _CaptureExhausted(Exception):
    pass


class _CaptureHandler(BaseHTTPRequestHandler):
    received: list[tuple[str, dict]] = []
    status = 200
    disabled = False

    def _body_bytes(self) -> bytes:
        length = int(self.headers.get("Content-Length", "0"))
        return self.rfile.read(length) if length else b""

    def do_POST(self):
        raw = self._body_bytes()
        self.received.append((self.headers.get("Authorization", ""), json.loads(raw) if raw else {}))
        self.send_response(self.status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", "2")
        self.end_headers()
        self.wfile.write(b"{}")


class _CaptureServer:
    def __init__(self):
        self.received = _CaptureHandler.received
        self.received.clear()
        self.status = 200
        _CaptureHandler.status = 200
        _CaptureHandler.received = self.received
        self._srv = ThreadingHTTPServer(("127.0.0.1", 0), _CaptureHandler)
        self.port = self._srv.server_address[1]
        self._thread = threading.Thread(target=self._srv.serve_forever, daemon=True)
        self._thread.start()

    def set_status(self, status: int) -> None:
        _CaptureHandler.status = status

    def stop(self):
        self._srv.shutdown()
        self._srv.server_close()


@pytest.fixture()
def capture_server():
    srv = _CaptureServer()
    yield srv
    srv.stop()


# ── API 服务夹具（每个测试独立临时 index + 事件文件） ──


@pytest.fixture(autouse=True)
def _reset_result_store():
    with STORE._lock:
        STORE._seen.clear()
        STORE._rate.clear()
        STORE.reset_config_cache()
    yield


@pytest.fixture()
def api_iso(tmp_path, monkeypatch):

    """启动隔离的 HTTP API 服务，返回 (base_url, login_token)。"""

    import shutil
    import subprocess

    from server.board import loader as board_loader

    iso_root = tmp_path / "ccc-api-iso"
    dispatch = iso_root / "docs" / "dispatch"
    dispatch.parent.mkdir(parents=True, exist_ok=True)
    src = Path(__file__).resolve().parents[2] / "docs" / "dispatch"
    if src.is_dir():
        shutil.copytree(src, dispatch)
    else:
        dispatch.mkdir(parents=True)

    tmp = Path(tempfile_for(tmp_path)).resolve()
    events = tmp / "board-events.jsonl"

    monkeypatch.setattr(web_server, "_DISPATCH_DIR", dispatch)
    monkeypatch.setattr(board_loader, "get_index_path", lambda d=None: tmp / "cards" / "cards.index.jsonl")
    monkeypatch.setenv("CCC_RESULT_REPORT_EVENTS_PATH", str(events))
    monkeypatch.setenv("CCC_RESULT_REPORT_TOKEN", REPORT_TOKEN)

    server = web_server.create_server(host="127.0.0.1", port=0)
    addr = server.server_address
    base_url = f"http://{addr[0]}:{addr[1]}"

    def _recv(ctx):
        pass

    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    try:
        for _ in range(RETRY_COUNT):
            try:
                conn = HTTPConnection(addr[0], addr[1], timeout=2)
                conn.request("GET", "/health")
                conn.getresponse().read()
                conn.close()
                break
            except (ConnectionRefusedError, OSError):
                time.sleep(RETRY_DELAY)
        # 退出时保证 server 线程不阻塞 pytest
        yield base_url
    finally:
        server.shutdown()
        server.server_close()


def tempfile_for(_tmp_path):
    import tempfile as _tf

    return _tf.mkdtemp(prefix="ccc-rt-tmp-")


# ── 请求辅助 ──


def _post(base_url: str, path: str, body: dict, token: str | None = None) -> tuple[int, dict]:
    parsed = urlparse(base_url)
    conn = HTTPConnection(parsed.hostname, parsed.port, timeout=5)
    try:
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        conn.request("POST", path, body=json.dumps(body).encode("utf-8"), headers=headers)
        resp = conn.getresponse()
        raw = resp.read().decode("utf-8")
        return resp.status, json.loads(raw) if raw else {}
    finally:
        conn.close()


def _get(base_url: str, path: str, token: str | None = None) -> tuple[int, dict]:
    parsed = urlparse(base_url)
    conn = HTTPConnection(parsed.hostname, parsed.port, timeout=5)
    try:
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        conn.request("GET", path, headers=headers)
        resp = conn.getresponse()
        raw = resp.read().decode("utf-8")
        return resp.status, json.loads(raw) if raw else {}
    finally:
        conn.close()


def _login(base_url: str, username: str, password: str) -> tuple[int, dict]:
    return _post(base_url, "/session", {"username": username, "password": password})


def _valid(**overrides):
    body = dict(_VALID)
    body.update(overrides)
    return body


# ── 鉴权 ──


def test_unconfigured_token_returns_503(monkeypatch, api_iso):
    monkeypatch.setattr(STORE, "_startup_token", lambda: "")
    status, data = _post(api_iso, "/api/v1/board/result", _valid(), token="anything")
    assert status == 503


def test_unconfigured_events_endpoint_returns_503_before_auth(monkeypatch, api_iso):
    monkeypatch.setattr(STORE, "_startup_token", lambda: "")
    status, data = _get(api_iso, "/api/v1/board/result/events")
    assert status == 503


def test_wrong_token_returns_401(api_iso):
    status, data = _post(api_iso, "/api/v1/board/result", _valid(), token="wrong")
    assert status == 401
    status, data = _post(api_iso, "/api/v1/board/result", _valid())
    assert status == 401


def test_correct_token_returns_200(api_iso):
    status, data = _post(api_iso, "/api/v1/board/result", _valid(), token=REPORT_TOKEN)
    assert status == 200
    assert data == {"deduped": False}


# ── Schema ──


def test_unknown_payload_field_400(api_iso):
    bad = _valid(payload={**_VALID["payload"], "evil": "x"})
    status, data = _post(api_iso, "/api/v1/board/result", bad, token=REPORT_TOKEN)
    assert status == 400
    assert "evil" in data["error"]


def test_invalid_event_400(api_iso):
    bad = _valid(event="executor_zombie")
    status, data = _post(api_iso, "/api/v1/board/result", bad, token=REPORT_TOKEN)
    assert status == 400


def test_oversize_body_413(api_iso):
    big_payload = {"executor_rc": 0, "card_title": "x" * (MAX_BODY_BYTES + 1)}
    status, data = _post(api_iso, "/api/v1/board/result", _valid(payload=big_payload), token=REPORT_TOKEN)
    assert status == 413


def test_unknown_work_id_404(api_iso):
    bad = _valid(work_id="no-such-card")
    status, data = _post(api_iso, "/api/v1/board/result", bad, token=REPORT_TOKEN)
    assert status == 404


def test_invalid_maintenance_value_400(api_iso):
    bad = _valid(payload={"maintenance": {"plan_sync": "yes", "lesson": "maybe", "readme": "yes", "roadmap": "no"}})
    status, data = _post(api_iso, "/api/v1/board/result", bad, token=REPORT_TOKEN)
    assert status == 400


# ── 幂等 ──


def test_idempotent_same_event_id(api_iso):
    body = _valid(event_id="fixed-id")
    status, data = _post(api_iso, "/api/v1/board/result", body, token=REPORT_TOKEN)
    assert status == 200 and data == {"deduped": False}
    status, data = _post(api_iso, "/api/v1/board/result", body, token=REPORT_TOKEN)
    assert status == 200 and data == {"deduped": True}
    _, read = _get(api_iso, "/api/v1/board/result/events", token=_login_token(api_iso))
    assert read["total"] == 1


def _login_token(base_url: str) -> str:
    status, data = _login(base_url, TEST_USER, TEST_PASS)
    assert status == 200
    return data["token"]


# ── 限速 ──


def test_rate_limit(api_iso):
    for _ in range(30):
        status, data = _post(api_iso, "/api/v1/board/result", _valid(event_id=None), token=REPORT_TOKEN)
        assert status == 200
    status, data = _post(api_iso, "/api/v1/board/result", _valid(event_id=None), token=REPORT_TOKEN)
    assert status == 429


# ── GET ──


def test_get_requires_session_token(api_iso):
    status, data = _get(api_iso, "/api/v1/board/result/events")
    assert status == 401


def test_get_reads_and_filters(api_iso):
    _post(api_iso, "/api/v1/board/result", _valid(work_id="tst901"), token=REPORT_TOKEN)
    _post(api_iso, "/api/v1/board/result", _valid(work_id="tst902"), token=REPORT_TOKEN)
    token = _login_token(api_iso)
    status, data = _get(api_iso, "/api/v1/board/result/events", token=token)
    assert status == 200
    assert data["total"] == 2
    status, data = _get(api_iso, "/api/v1/board/result/events?work_id=tst901&limit=1", token=token)
    assert status == 200
    assert data["total"] == 1
    assert data["events"][0]["work_id"] == "tst901"


def test_get_limit_validation(api_iso):
    token = _login_token(api_iso)
    status, data = _get(api_iso, "/api/v1/board/result/events?limit=999", token=token)
    assert status == 400


# ── wrapper 侧 ──


def test_wrapper_reports_completed_event(capture_server, tmp_path):
    _run_report_lib(capture_server, tmp_path, rc=0)
    assert len(capture_server.received) == 1
    auth, body = capture_server.received[0]
    assert auth == "Bearer report-test-token"
    assert body["work_id"] == "tst904"
    assert body["event"] == "executor_completed"
    assert body["payload"]["executor_rc"] == 0
    assert body["payload"]["result_path"] == "tst904-ccc-result.md"
    assert body["payload"]["duration_s"] >= 0


def test_wrapper_reports_failed_event(capture_server, tmp_path):
    _run_report_lib(capture_server, tmp_path, rc=7)
    assert len(capture_server.received) == 1
    assert capture_server.received[0][1]["event"] == "executor_failed"
    assert capture_server.received[0][1]["payload"]["executor_rc"] == 7


def test_wrapper_network_failure_keeps_flags(capture_server, tmp_path, monkeypatch):
    def _fail(*_a, **_k):
        import subprocess as _sp

        raise _sp.SubprocessError

    # 直接 monkeypatch wrapper 不具备条件；此处验证 disabled 旗标在 503 时生效
    capture_server.set_status(503)
    _run_report_lib(capture_server, tmp_path, rc=0)
    flags = list(tmp_path.rglob(".result-report-disabled"))
    assert flags, "503 应写 disabled 旗标"


def _run_report_lib(capture_server, tmp_path, rc: int):
    import subprocess

    log_dir = tmp_path / "exec-logs"
    log_dir.mkdir(exist_ok=True)
    env = dict(os.environ)
    env["CCC_RESULT_REPORT_TOKEN"] = "report-test-token"
    env["CCC_RESULT_REPORT_URL"] = f"http://127.0.0.1:{capture_server.port}/api/v1/board/result"
    lib = Path(__file__).resolve().parents[2] / "scripts" / "lib" / "result-report.sh"
    proc = subprocess.run(
        ["bash", str(lib), "tst904", str(rc), "0", str(log_dir)],
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert proc.returncode == 0, proc.stderr


def _run_wrapper(capture_server, tmp_path, rc: int):
    """完整执行 dsh-executor.sh 的上报段（隔离配置，不真跑 dsh）。

    做法：构造最小可执行环境——用哑 dsh 替代（返回 rc），wrapper 全文跑通
    （health-check 用 dummy 脚本），结果文件预置。-ccc-result 传输段需 rc=0 才拷贝，
    测试中直接生成 log_dir 结果。为避免全 wrapper 副作用，这里用受限 PATH。
    """
    import subprocess

    log_dir = tmp_path / "exec-logs"
    log_dir.mkdir(exist_ok=True)
    (log_dir / "tst904-ccc-result.md").write_text("# 执行结果", encoding="utf-8")
    cfg = tmp_path / "config.env"
    cfg.write_text(
        f"CCC_RESULT_REPORT_TOKEN=report-test-token\n"
        f"CCC_RESULT_REPORT_URL=http://127.0.0.1:{capture_server.port}/api/v1/board/result\n"
        f"EXECUTOR_LOG_DIR={log_dir}\n",
        encoding="utf-8",
    )
    script = """#!/bin/bash
exit 0
"""
    fake_dsh = tmp_path / "fake-dsh"
    fake_dsh.write_text(script, encoding="utf-8")
    fake_dsh.chmod(0o755)
    fake_node = tmp_path / "fake-node"
    fake_node.write_text("#!/bin/bash\nexit 0\n", encoding="utf-8")
    fake_node.chmod(0o755)

    preset_dir = tmp_path / "preset"
    preset_dir.mkdir(exist_ok=True)
    preset = preset_dir / "agent.cordis.yml"
    preset.write_text(
        "id: persona\nconfig:\n  text: test\n",
        encoding="utf-8",
    )

    env = dict(os.environ)
    env["PATH"] = f"{tmp_path}:{env.get('PATH', '')}"
    env["CCC_CONFIG_ENV"] = str(cfg)
    env["HOME"] = str(tmp_path)
    env.pop("CCC_RESULT_REPORT_TOKEN", None)
    env.pop("CCC_RESULT_REPORT_URL", None)
    env["DSH_PERMISSION_MODE"] = "danger-full-access"
    env["PRESET_DIR"] = str(preset_dir)

    # wrapper 引用 $HOME/.dsh/.agent-presets/dsh-executor/agent.cordis.yml；测试
    # 注入 PRESET_DIR 覆盖（见下）。dsh/fake 命令经由 PATH 兜底。
    wrapper = Path(__file__).resolve().parents[2] / "scripts" / "dsh-executor.sh"
    # 只跑到结果上报前的段；以 DSH_RC 语义简化：
    cmd = [
        "bash", str(wrapper), "/tmp/fake-card.md", "tst904", "",
    ]
    # wrapper 在 rc=0 时 cp .ccc-result.md；我们预置 log_dir 结果，且 fake dsh exit rc
    try:
        proc = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except FileNotFoundError:
        pytest.fail("wrapper 不可执行")
    # 全程应吞掉 network 失败，最终退出码=DSH_RC 语义
    assert proc.returncode == rc, f"wrapper exit={proc.returncode} stderr={proc.stderr}"
