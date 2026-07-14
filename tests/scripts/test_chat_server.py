"""Regression tests for CCC Chat Server (ccc-chat-server.py, port 8084).

Usage:
    python3 -m pytest tests/scripts/test_chat_server.py -v
    python3 -m pytest tests/scripts/test_chat_server.py -v -k "markdown"

This test file SERVES the chat server in background — no manual setup needed.
"""

import json
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

CHAT_SCRIPT = Path(__file__).resolve().parent.parent.parent / "scripts" / "ccc-chat-server.py"
BASE_URL = "http://127.0.0.1:18084"  # use a non-default port to avoid collision
AUTH_HEADER = "Basic Y2NjOmNsYXVkZTIwMjY="  # base64("ccc:claude2026")
AUTH = {"Authorization": AUTH_HEADER}
AUTH_USER = "ccc"
AUTH_PASS = "claude2026"
TIMEOUT = 10

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module", autouse=True)
def chat_server():
    """Start chat server on :18084 for the module lifetime."""
    proc = subprocess.Popen(
        [sys.executable, str(CHAT_SCRIPT), "--port", "18084", "--no-open"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        cwd=CHAT_SCRIPT.parent.parent,
    )
    # Wait for startup
    for _ in range(30):
        try:
            r = urllib.request.urlopen(f"{BASE_URL}/", timeout=2)
            if r.status == 200:
                break
        except Exception:
            time.sleep(0.5)
    else:
        proc.kill()
        pytest.fail("chat-server did not start in 15s")
    yield
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


def _get(path: str, auth: bool = True) -> dict | str:
    """GET request. Returns parsed JSON or raw body."""
    req = urllib.request.Request(f"{BASE_URL}{path}")
    if auth:
        req.add_header("Authorization", AUTH_HEADER)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            body = resp.read().decode()
            ct = resp.headers.get("Content-Type", "")
            return json.loads(body) if "json" in ct else body
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try:
            return {"_http_status": e.code, "_body": json.loads(body)}
        except json.JSONDecodeError:
            return {"_http_status": e.code, "_body": body}


def _post(path: str, data: dict) -> tuple[int, str]:
    """POST request. Returns (status_code, raw_body)."""
    payload = json.dumps(data).encode()
    req = urllib.request.Request(
        f"{BASE_URL}{path}", data=payload, method="POST",
        headers={"Content-Type": "application/json", "Authorization": AUTH_HEADER},
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCoreAPI:
    """R01-R10: 核心 API 功能"""

    def test_r01_service_http_200(self):
        r = urllib.request.urlopen(f"{BASE_URL}/", timeout=TIMEOUT)
        assert r.status == 200

    def test_r02_unauth_401(self):
        req = urllib.request.Request(f"{BASE_URL}/api/projects")
        try:
            urllib.request.urlopen(req, timeout=TIMEOUT)
            pytest.fail("expected 401")
        except urllib.error.HTTPError as e:
            assert e.code == 401

    def test_r03_auth_200(self):
        r = _get("/api/projects")
        assert "projects" in r

    def test_r05_projects_min_count(self):
        r = _get("/api/projects")
        assert len(r["projects"]) >= 4
        ids = [p["id"] for p in r["projects"]]
        assert "ccc" in ids and "qxo" in ids

    def test_r06_history(self):
        r = _get("/api/history")
        assert "sessions" in r

    def test_r07_file_tree(self):
        r = _get("/api/projects/ccc/files")
        assert len(r["entries"]) > 0
        assert "truncated" in r

    def test_r08_path_traversal(self):
        r = _get("/api/projects/ccc/file?path=../etc/passwd")
        assert r.get("_http_status") == 400

    def test_r09_file_read(self):
        r = _get("/api/projects/ccc/file?path=scripts/ccc-chat-server.py")
        assert "content" in r
        assert r["project_id"] == "ccc"

    def test_r10_board_proxy(self):
        r = _get("/api/board/proxy/board?workspace=CCC")
        assert r.get("_http_status", 200) == 200 or "columns" in r


class TestFrontendFeatures:
    """R11-R23: UI features in HTML"""

    HTML = None

    @classmethod
    def setup_class(cls):
        cls.HTML = _get("/", auth=False)

    def test_r11_theme_button(self):
        assert "themeBtn" in self.HTML

    def test_r12_toggle_theme(self):
        assert "toggleTheme" in self.HTML

    def test_r13_message_edit(self):
        assert "editMessage" in self.HTML

    def test_r14_skeleton(self):
        assert "skeleton-pulse" in self.HTML

    def test_r15_markdown_renderer(self):
        assert "renderMarkdown" in self.HTML

    def test_r16_data_theme_attr(self):
        assert "data-theme" in self.HTML

    def test_r17_theme_transition(self):
        assert "transition-theme" in self.HTML

    def test_r18_terminal_css_vars(self):
        assert "var(--terminal-bg)" in self.HTML

    def test_r19_skeleton_card(self):
        assert "skeleton-card" in self.HTML

    def test_r20_dblclick_edit(self):
        assert "dblclick" in self.HTML

    def test_r21_markdown_links(self):
        assert 'target="_blank"' in self.HTML

    def test_r22_markdown_tables(self):
        assert "<table>" in self.HTML

    def test_r23_markdown_blockquote(self):
        assert "<blockquote>" in self.HTML


class TestMarkdownRenderer:
    """renderMarkdown function features"""

    HTML = None

    @classmethod
    def setup_class(cls):
        cls.HTML = _get("/", auth=False)

    def test_headers(self):
        assert "<h1>" in self.HTML and "<h4>" in self.HTML

    def test_lists(self):
        assert "<ul>" in self.HTML and "<li>" in self.HTML

    def test_hr(self):
        assert "<hr>" in self.HTML

    def test_link_render(self):
        assert '<a href=' in self.HTML

    def test_image_render(self):
        assert "<img" in self.HTML

    def test_strong(self):
        assert "<strong>" in self.HTML

    def test_italic(self):
        assert "<em>" in self.HTML

    def test_inline_code(self):
        assert "<code>" in self.HTML

    def test_code_block(self):
        assert "code-block-wrap" in self.HTML

    def test_ordered_list(self):
        assert "<ol>" in self.HTML


class TestSecurity:
    """安全功能"""

    def test_path_traversal_raw(self):
        r = _get("/api/projects/ccc/file?path=../etc/passwd")
        assert r.get("_http_status") == 400

    def test_path_traversal_encoded(self):
        r = _get("/api/projects/ccc/file?path=..%2f..%2fetc%2fpasswd")
        assert r.get("_http_status") == 400

    def test_excluded_dir_blocked(self):
        r = _get("/api/projects/ccc/file?path=.git/HEAD")
        # Should return 400 (excluded) or 404 (not found)
        assert r.get("_http_status") in (400, 404)

    def test_dangerous_command_blocked(self):
        status, body = _post("/api/execute", {
            "messages": [{"role": "user", "content": "rm -rf /"}],
            "session_id": "test-security-001",
        })
        assert status == 400
        assert "危险指令" in body

    def test_dangerous_command_sudo(self):
        status, body = _post("/api/execute", {
            "messages": [{"role": "user", "content": "sudo rm -rf /"}],
            "session_id": "test-security-002",
        })
        assert status == 400


class TestExecuteQueue:
    """P1.4 Execute 排队机制"""

    def test_queue_globals_defined(self):
        src = CHAT_SCRIPT.read_text()
        assert "_EXECUTE_WAITERS" in src
        assert "_EXEC_QUEUE_MAX" in src


class TestPartialSave:
    """P1.3 取消流式保存"""

    def test_partial_flag(self):
        src = CHAT_SCRIPT.read_text()
        assert '"partial"' in src


class TestDocstringTypo:
    """P0.3 docstring fix"""

    def test_no_8082_residue(self):
        src = CHAT_SCRIPT.read_text()
        # The only "8082" should be in the variable definition or CSS, not the docstring
        for i, line in enumerate(src.splitlines(), 1):
            stripped = line.strip()
            if "localhost:8082" in stripped and not stripped.startswith("#"):
                if "8082" not in stripped.split("#")[0]:
                    continue
                pytest.fail(f"Line {i}: residual 8082 reference: {stripped}")


class TestCockpitIntegration:
    """集成：Cockpit 相关功能"""

    def test_infra_has_8084(self):
        infra = Path(__file__).resolve().parent.parent.parent / ".ccc" / "infrastructure.md"
        text = infra.read_text()
        assert "8084" in text
        assert "CCC Chat" in text


class TestLegacyFixes:
    """P1 缺陷修复"""

    def test_truncation_indicator(self):
        src = CHAT_SCRIPT.read_text()
        assert "truncated_len" in src or "已截断" in src

    def test_execute_history_rich_replay(self):
        src = CHAT_SCRIPT.read_text()
        assert "execution_results" in src
        assert "renderTerminalHistory" in src
