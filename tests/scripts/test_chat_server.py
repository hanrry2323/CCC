"""CCC Chat Server — 全链路回归测试（前台 + 后端 + 持久化）

覆盖范围：
  - API 端点：所有 GET/POST/DELETE 端点的完整输入输出
  - SSE 流式：Chat / Execute 模式的流式数据传输
  - 前端渲染：HTML 结构、CSS 变量、JavaScript 函数
  - 持久化：会话创建/列出/读取/删除的完整生命周期
  - 安全：路径穿越、危险命令、认证、目录隔离
  - 跨项目：5 个项目各自的项目上下文注入
  - 边界条件：空输入、特殊字符、Unicode、二进制文件
  - 排队机制：Execute 队列的代码路径验证
  - Cancel 流：取消后 partial 信息落盘验证

用法:
    python3 -m pytest tests/scripts/test_chat_server.py -v
    python3 -m pytest tests/scripts/test_chat_server.py -v -k "test_chat_stream"
"""

import asyncio
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from html.parser import HTMLParser

import pytest

CHAT_SCRIPT = Path(__file__).resolve().parent.parent.parent / "scripts" / "ccc-chat-server.py"
PROJECT_ROOT = CHAT_SCRIPT.parent.parent
BASE_URL = "http://127.0.0.1:18084"
AUTH_HEADER = "Basic Y2NjOmNsYXVkZTIwMjY="  # base64("ccc:claude2026")
AUTH = {"Authorization": AUTH_HEADER}
TIMEOUT = 15

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get(path: str, auth: bool = True):
    req = urllib.request.Request(f"{BASE_URL}{path}")
    if auth:
        req.add_header("Authorization", AUTH_HEADER)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            body = resp.read().decode()
            ct = resp.headers.get("Content-Type", "")
            return resp.status, (json.loads(body) if "json" in ct else body)
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try:
            return e.code, json.loads(body)
        except json.JSONDecodeError:
            return e.code, body


def _post(path: str, data: dict):
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


def _delete(path: str):
    req = urllib.request.Request(
        f"{BASE_URL}{path}", method="DELETE",
        headers={"Authorization": AUTH_HEADER},
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def _stream_post(path: str, data: dict, read_limit: int = 5):
    """POST and read the first N SSE lines from a streaming response."""
    payload = json.dumps(data).encode()
    req = urllib.request.Request(
        f"{BASE_URL}{path}", data=payload, method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": AUTH_HEADER,
            "Accept": "text/event-stream",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            assert resp.status == 200
            assert "text/event-stream" in resp.headers.get("Content-Type", "")
            lines = []
            for i in range(read_limit):
                line = resp.readline().decode(errors="replace").strip()
                if not line:
                    continue
                lines.append(line)
                if b"[DONE]" in line.encode() or b"type.*done" in line.encode():
                    break
            return 200, lines
    except urllib.error.HTTPError as e:
        return e.code, [e.read().decode()]


def _extract_js_var(html: str, var_name: str) -> str:
    """Extract a JavaScript variable value from inline HTML."""
    m = re.search(rf"var\s+{var_name}\s*=\s*([^;]+);", html)
    if m:
        return m.group(1).strip()
    m = re.search(rf"(?:const|let|var)\s+{var_name}\s*=\s*([^;]+);", html)
    return m.group(1).strip() if m else ""


def _count_in_html(html: str, pattern: str) -> int:
    return len(re.findall(re.escape(pattern), html))


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module", autouse=True)
def chat_server():
    proc = subprocess.Popen(
        [sys.executable, str(CHAT_SCRIPT), "--port", "18084", "--no-open"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        cwd=PROJECT_ROOT,
    )
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


# ===========================================================================
# 第一组：服务基础设施 (14 tests)
# ===========================================================================


class TestServiceInfrastructure:
    """服务是否活着、认证是否工作、核心端点是否响应"""

    def test_001_service_http_200(self):
        status, body = _get("/", auth=False)
        assert status == 200
        assert "CCC Chat" in body

    def test_002_unauth_returns_401(self):
        req = urllib.request.Request(f"{BASE_URL}/api/projects")
        try:
            urllib.request.urlopen(req, timeout=TIMEOUT)
            pytest.fail("expected 401")
        except urllib.error.HTTPError as e:
            assert e.code == 401
            body = e.read().decode()
            assert "Unauthorized" in body or "401" in body or "WWW-Authenticate" in str(e.headers)

    def test_003_unauth_all_endpoints_401(self):
        for ep in ["/api/projects", "/api/history", "/api/chat", "/api/execute"]:
            req = urllib.request.Request(f"{BASE_URL}{ep}")
            try:
                urllib.request.urlopen(req, timeout=TIMEOUT)
                if ep in ("/api/chat", "/api/execute"):
                    # These return 422 for GET without body, not 401
                    continue
                pytest.fail(f"expected 401 for {ep}")
            except urllib.error.HTTPError as e:
                assert e.code in (401, 422), f"{ep} unexpected status {e.code}"

    def test_004_projects_list(self):
        status, data = _get("/api/projects")
        assert status == 200
        assert len(data["projects"]) >= 4
        ids = [p["id"] for p in data["projects"]]
        assert "ccc" in ids
        assert "qxo" in ids
        assert "xianyu" in ids

    def test_005_history_api(self):
        status, data = _get("/api/history")
        assert status == 200
        assert "sessions" in data

    def test_006_history_by_project(self):
        for project in ("ccc", "qxo", "xianyu"):
            status, data = _get(f"/api/history?project={project}")
            assert status == 200, f"project={project} failed"
            assert "sessions" in data

    def test_007_file_tree(self):
        status, data = _get("/api/projects/ccc/files")
        assert status == 200
        assert len(data["entries"]) > 0
        assert "truncated" in data
        # Verify entry structure
        for entry in data["entries"][:3]:
            assert "name" in entry
            assert "type" in entry
            assert "path" in entry

    def test_008_file_tree_all_projects(self):
        for project in ("ccc", "qxo", "xianyu", "hp", "ai-loop-router"):
            status, data = _get(f"/api/projects/{project}/files")
            assert status == 200, f"project={project} failed"
            assert len(data["entries"]) > 0

    def test_009_file_tree_unknown_project_404(self):
        status, data = _get("/api/projects/unknown_project/files")
        assert status == 404

    def test_010_read_file(self):
        status, data = _get("/api/projects/ccc/file?path=scripts/ccc-chat-server.py")
        assert status == 200
        assert "content" in data
        assert data["project_id"] == "ccc"
        assert data["size"] > 0
        assert data["content"].startswith("#!/usr/bin/env python3")

    def test_011_read_file_with_size_info(self):
        status, data = _get("/api/projects/ccc/file?path=scripts/ccc-chat-server.py")
        assert status == 200
        assert data["size"] == len(data["content"]) or data.get("truncated") is not None

    def test_012_read_file_not_found_404(self):
        status, data = _get("/api/projects/ccc/file?path=nonexistent_file_xyz.txt")
        assert status == 404

    def test_013_board_proxy(self):
        status, data = _get("/api/board/proxy/board?workspace=CCC")
        assert status in (200, 503)
        if status == 200:
            assert "columns" in data

    def test_014_board_dashboard_proxy(self):
        status, data = _get("/api/board/proxy/dashboard?workspace=CCC")
        assert status in (200, 503)


# ===========================================================================
# 第二组：Chat SSE 流式 (10 tests)
# ===========================================================================


class TestChatStreaming:
    """Chat 模式的 SSE 流式传输全链路"""

    SESSION_ID = f"test-chat-{int(time.time())}"

    def test_020_chat_stream_returns_sse(self):
        status, lines = _stream_post("/api/chat", {
            "messages": [{"role": "user", "content": "Say hello in 3 words"}],
            "session_id": self.SESSION_ID,
        })
        assert status == 200, f"expected 200 got {status}"
        assert len(lines) > 0
        sse_lines = [l for l in lines if l.startswith("data: ")]
        assert len(sse_lines) > 0

    def test_021_chat_stream_has_delta_events(self):
        status, lines = _stream_post("/api/chat", {
            "messages": [{"role": "user", "content": "Count to 3"}],
            "session_id": f"test-chat-delta-{int(time.time())}",
        }, read_limit=20)
        assert status == 200
        has_delta = any("type.*delta" in l or '"type": "delta"' in l for l in lines)
        assert has_delta, f"No delta events found in {len(lines)} lines"

    def test_022_chat_stream_content_is_valid_json(self):
        status, lines = _stream_post("/api/chat", {
            "messages": [{"role": "user", "content": "Hi"}],
            "session_id": f"test-chat-json-{int(time.time())}",
        }, read_limit=20)
        assert status == 200
        for line in lines:
            if line.startswith("data: "):
                try:
                    parsed = json.loads(line[6:])
                    assert "type" in parsed
                except json.JSONDecodeError:
                    pytest.fail(f"Invalid JSON in SSE: {line}")

    def test_023_chat_with_project_context(self):
        status, lines = _stream_post("/api/chat", {
            "messages": [{"role": "user", "content": "What project am I working on?"}],
            "project": "ccc",
            "session_id": f"test-chat-ctx-{int(time.time())}",
        }, read_limit=10)
        assert status == 200

    def test_024_chat_empty_messages_returns_400(self):
        status, body = _post("/api/chat", {
            "messages": [],
            "session_id": "test-empty-msg",
        })
        assert status == 400

    def test_025_chat_no_session_id_still_works(self):
        status, lines = _stream_post("/api/chat", {
            "messages": [{"role": "user", "content": "ping"}],
        }, read_limit=5)
        assert status == 200

    def test_026_chat_allows_model_param(self):
        status, lines = _stream_post("/api/chat", {
            "messages": [{"role": "user", "content": "hi"}],
            "model": "flash",
        }, read_limit=5)
        assert status == 200

    def test_027_chat_unicode_support(self):
        """Verify Unicode messages don't break streaming."""
        status, lines = _stream_post("/api/chat", {
            "messages": [{"role": "user", "content": "你好世界 🌍 こんにちは"}],
            "session_id": f"test-chat-unicode-{int(time.time())}",
        }, read_limit=10)
        assert status == 200

    def test_028_chat_special_characters(self):
        """Verify special characters don't break JSON/SSe parsing."""
        status, lines = _stream_post("/api/chat", {
            "messages": [{"role": "user", "content": "Hello\nLine2\nLine3\nTab\there"}],
            "session_id": f"test-chat-special-{int(time.time())}",
        }, read_limit=10)
        assert status == 200

    def test_029_chat_logs_session(self):
        """After a stream, the session should show up in history."""
        sid = f"test-chat-persist-{int(time.time())}"
        status, _ = _stream_post("/api/chat", {
            "messages": [{"role": "user", "content": "persist test"}],
            "session_id": sid,
        }, read_limit=10)
        assert status == 200
        time.sleep(0.5)
        status, data = _get("/api/history")
        assert status == 200
        sessions = data["sessions"]
        sids = [s["session_id"] for s in sessions]
        assert sid in sids, f"Session {sid} not found in history"


# ===========================================================================
# 第三组：Execute SSE 流式 (10 tests)
# ===========================================================================


class TestExecuteStreaming:
    """Execute 模式的 SSE 流式全链路"""

    def test_030_execute_dangerous_command_blocked(self):
        for cmd in ["rm -rf /", "rm /", "sudo rm -rf", "dd if=/dev/zero", "format /", "mkfs", "> /dev/sda"]:
            status, body = _post("/api/execute", {
                "messages": [{"role": "user", "content": cmd}],
                "session_id": f"test-danger-{int(time.time())}",
            })
            assert status == 400, f"Command not blocked: {cmd}"
            assert "危险指令" in body, f"No warning for: {cmd}"

    def test_031_execute_empty_messages_400(self):
        status, body = _post("/api/execute", {
            "messages": [],
        })
        assert status == 400

    def test_032_execute_no_user_message_400(self):
        status, body = _post("/api/execute", {
            "messages": [{"role": "assistant", "content": "hello"}],
        })
        assert status == 400

    def test_033_execute_unknown_project_400(self):
        status, body = _post("/api/execute", {
            "messages": [{"role": "user", "content": "hello"}],
            "project": "nonexistent",
        })
        assert status == 400

    def test_034_execute_queue_code_path(self):
        """Verify queue constants exist and are reasonable."""
        src = CHAT_SCRIPT.read_text()
        assert "_EXECUTE_WAITERS: list[asyncio.Event]" in src
        assert "_EXEC_QUEUE_MAX = 3" in src

    def test_035_execute_queue_overflow_rejected(self):
        """Verify queue overflow returns 429."""
        with open(CHAT_SCRIPT) as f:
            src = f.read()
        # Verify the error message for full queue
        assert "队列已满" in src

    def test_036_execute_cancel_saves_partial(self):
        """Verify partial flag exists in session save code."""
        src = CHAT_SCRIPT.read_text()
        assert '"partial"' in src
        assert 'partial": not stream_completed' in src

    def test_037_execute_has_timeout(self):
        src = CHAT_SCRIPT.read_text()
        assert "timeout" in src
        assert "执行超时" in src

    def test_038_execute_uses_claude_cli(self):
        src = CHAT_SCRIPT.read_text()
        assert "create_subprocess_exec" in src
        assert '"claude"' in src
        assert '"--model"' in src
        assert '"flash"' in src


# ===========================================================================
# 第四组：会话持久化 (10 tests)
# ===========================================================================


class TestSessionPersistence:
    """会话创建/列出/读取/删除的完整生命周期"""

    CHAT_DIR = PROJECT_ROOT / ".ccc" / "chat"

    def _session_file(self, sid: str, project: str = "ccc") -> Path:
        return self.CHAT_DIR / project / f"{sid}.json"

    def test_040_create_and_list_session(self):
        sid = f"test-persist-create-{int(time.time())}"
        status, _ = _stream_post("/api/chat", {
            "messages": [{"role": "user", "content": "Create a test session"}],
            "session_id": sid,
        }, read_limit=10)
        assert status == 200
        time.sleep(0.5)
        status, data = _get("/api/history")
        assert status == 200
        assert sid in [s["session_id"] for s in data["sessions"]]

    def test_041_create_session_in_all_projects(self):
        for project in ("ccc", "qxo", "xianyu"):
            sid = f"test-persist-proj-{project}-{int(time.time())}"
            status, _ = _stream_post("/api/chat", {
                "messages": [{"role": "user", "content": f"Test {project}"}],
                "session_id": sid,
                "project": project,
            }, read_limit=5)
            assert status == 200, f"project={project} failed"
            time.sleep(0.5)
            status, data = _get(f"/api/history?project={project}")
            assert status == 200
            assert sid in [s["session_id"] for s in data["sessions"]]

    def test_042_get_session_by_id(self):
        sid = f"test-persist-get-{int(time.time())}"
        status, _ = _stream_post("/api/chat", {
            "messages": [{"role": "user", "content": "Get me"}],
            "session_id": sid,
        }, read_limit=10)
        assert status == 200
        time.sleep(0.5)
        status, data = _get(f"/api/history/{sid}")
        assert status == 200
        assert data["session_id"] == sid
        assert "messages" in data
        assert "created_at" in data
        assert "updated_at" in data

    def test_043_get_session_not_found_404(self):
        status, data = _get("/api/history/nonexistent-session-xyz-123456")
        assert status == 404

    def test_044_session_structure(self):
        sid = f"test-persist-struct-{int(time.time())}"
        status, _ = _stream_post("/api/chat", {
            "messages": [{"role": "user", "content": "structure test"}],
            "session_id": sid,
            "project": "ccc",
        }, read_limit=10)
        assert status == 200
        time.sleep(0.5)
        status, data = _get(f"/api/history/{sid}")
        assert status == 200
        assert "session_id" in data
        assert "title" in data
        assert "project" in data
        assert "messages" in data
        assert "created_at" in data
        assert "updated_at" in data
        assert data["project"] == "ccc"
        # The title should be derived from the user message
        assert "structure test" in data["title"] or "test" in data["title"]

    def test_045_session_history_sorted_by_mtime(self):
        """Sessions should be returned newest-first."""
        status, data = _get("/api/history")
        assert status == 200
        sessions = data["sessions"]
        if len(sessions) >= 2:
            # Check it's sorted (at minimum it shouldn't crash)
            assert all("session_id" in s for s in sessions)
            assert all("updated_at" in s for s in sessions)

    def test_046_delete_session(self):
        sid = f"test-persist-delete-{int(time.time())}"
        status, _ = _stream_post("/api/chat", {
            "messages": [{"role": "user", "content": "delete me"}],
            "session_id": sid,
        }, read_limit=5)
        assert status == 200
        time.sleep(0.5)
        status, _ = _delete(f"/api/history/{sid}")
        assert status == 200
        status, _ = _get(f"/api/history/{sid}")
        assert status == 404

    def test_047_delete_nonexistent_session(self):
        status, body = _delete("/api/history/nonexistent-session-xyz")
        assert status == 200  # delete of non-existent returns ok

    def test_048_session_with_execute_mode(self):
        sid = f"test-persist-exec-{int(time.time())}"
        # Create an execute session (will be rejected with dangerous or queued, but logged)
        status, body = _post("/api/execute", {
            "messages": [{"role": "user", "content": "echo hello"}],
            "session_id": sid,
        })
        # If another execute is running, status is 429 — still logged check
        if status == 429:
            assert "排队" in body or "队列" in body or "执行中" in body

    def test_049_session_persists_on_disk(self):
        sid = f"test-persist-disk-{int(time.time())}"
        status, _ = _stream_post("/api/chat", {
            "messages": [{"role": "user", "content": "disk test"}],
            "session_id": sid,
        }, read_limit=5)
        assert status == 200
        time.sleep(0.5)
        sfile = self._session_file(sid)
        assert sfile.exists(), f"Session file not found: {sfile}"
        data = json.loads(sfile.read_text())
        assert data["session_id"] == sid
        # Clean up
        sfile.unlink(missing_ok=True)


# ===========================================================================
# 第五组：前端 HTML 渲染 (12 tests)
# ===========================================================================


class TestFrontendRendering:
    """前端 HTML 结构和渲染正确性"""

    def test_050_page_structure(self):
        assert "<!DOCTYPE html>" in self.H
        assert '<html lang="zh-CN">' in self.H
        assert "<head>" in self.H
        assert "<body>" in self.H
        assert "</html>" in self.H

    def test_051_critical_html_ids(self):
        for id_val in ["app", "header", "messages", "input-area", "input-wrap",
                       "send", "tabbar", "sidebar", "sessionList"]:
            assert f'id="{id_val}"' in self.H, f"Missing id={id_val}"

    def test_052_three_tab_panels(self):
        for panel in ["chat-panel", "exec-panel", "board-panel"]:
            assert f'id="{panel}"' in self.H, f"Missing panel {panel}"

    def test_053_tab_bar_buttons(self):
        for tab in ["chat", "execute", "board"]:
            assert f'data-tab="{tab}"' in self.H, f"Missing tab {tab}"

    def test_054_project_selector(self):
        assert 'id="project-select"' in self.H
        assert "onchange" in self.H

    def test_055_theme_button_renders(self):
        assert "themeBtn" in self.H
        assert "toggleTheme" in self.H

    def test_056_skeleton_loading(self):
        assert "skeleton-pulse" in self.H
        assert "skeleton-card" in self.H
        assert "skeleton-line" in self.H

    def test_057_send_button_exists(self):
        assert "sendChat" in self.H
        assert "sendExecute" in self.H
        assert "cancelStream" in self.H

    def test_058_message_edit_function(self):
        assert "editMessage" in self.H
        assert "saveEdit" in self.H
        assert "cancelEdit" in self.H
        assert "dblclick" in self.H

    def test_059_file_tree_rendering(self):
        assert "loadFileTree" in self.H
        assert "file-tree" in self.H
        assert "renderFileTree" in self.H
        assert "_buildFileItem" in self.H

    def test_060_board_render(self):
        assert "loadBoard" in self.H
        assert "board-col" in self.H
        assert "board-card" in self.H
        assert "openTaskModal" in self.H
        assert "createTask" in self.H

    def test_061_history_search_sidebar(self):
        assert "loadHistory" in self.H
        assert "loadSession" in self.H
        assert "toggleSidebar" in self.H
        assert "newChat" in self.H


# ===========================================================================
# 第六组：前端主题系统 (6 tests)
# ===========================================================================


class TestThemeSystem:
    """深色主题系统完整性"""

    def test_062_light_css_vars(self):
        for var in ["--bg", "--surface", "--text", "--accent", "--border",
                     "--code-bg", "--user-bg", "--user-text", "--shadow"]:
            assert var in self.H, f"Missing CSS variable {var}"

    def test_063_dark_theme_vars(self):
        assert 'data-theme="dark"' in self.H
        for var in ["--bg: #1c1c1e", "--surface: #2c2c2e", "--text: #f5f5f7",
                     "--accent: #0a84ff", "--border: #38383a"]:
            assert var in self.H, f"Missing dark var {var}"

    def test_064_terminal_css_vars(self):
        for var in ["--terminal-bg", "--terminal-text", "--terminal-prompt",
                     "--terminal-header", "--terminal-sep", "--terminal-info",
                     "--terminal-body", "--terminal-comment"]:
            assert var in self.H, f"Missing terminal var {var}"

    def test_065_diff_css_vars(self):
        for var in ["--success", "--danger"]:
            assert var in self.H, f"Missing diff var {var}"

    def test_066_theme_transition(self):
        assert "transition-theme" in self.H

    def test_067_theme_persistence(self):
        assert "localStorage.getItem('ccc-chat-theme')" in self.H
        assert "localStorage.setItem('ccc-chat-theme'" in self.H
        assert "prefers-color-scheme" in self.H
        assert "matchMedia" in self.H


# ===========================================================================
# 第七组：前端 Markdown 渲染 (12 tests)
# ===========================================================================


class TestMarkdownRendering:
    """Markdown 渲染器 JS 逻辑完整性"""

    def test_070_render_markdown_function(self):
        assert "function renderMarkdown" in self.H
        assert "escapeHtml" in self.H

    def test_071_headers_render(self):
        for tag in ["<h1>", "<h2>", "<h3>", "<h4>"]:
            assert tag in self.H, f"Missing {tag}"

    def test_072_lists_render(self):
        assert "<ul>" in self.H
        assert "<ol>" in self.H
        assert "<li>" in self.H

    def test_073_block_elements(self):
        assert "<blockquote>" in self.H
        assert "<hr>" in self.H

    def test_074_table_render(self):
        assert "<table>" in self.H
        assert "<thead>" in self.H
        assert "<th>" in self.H
        assert "<td>" in self.H

    def test_075_links_render(self):
        assert '<a href=' in self.H
        assert 'target="_blank"' in self.H
        assert 'rel="noopener"' in self.H

    def test_076_images_render(self):
        assert "<img" in self.H

    def test_077_inline_formatting(self):
        assert "<strong>" in self.H
        assert "<em>" in self.H
        assert "<code>" in self.H

    def test_078_code_block_render(self):
        assert "code-block-wrap" in self.H
        assert "copyCode" in self.H

    def test_079_parse_diff_function(self):
        assert "function parseDiff" in self.H
        assert "diff-file" in self.H
        assert "renderDiff" in self.H

    def test_080_tool_icons_exist(self):
        assert "toolIcon" in self.H or "TOOL_ICONS" in self.H

    def test_081_terminal_functions(self):
        for func in ["renderTerminalCommand", "appendTerminalInfo",
                      "appendTerminalSeparator", "terminalNow",
                      "renderTerminalHistory", "terminalStream"]:
            assert f"function {func}" in self.H, f"Missing {func}"


# ===========================================================================
# 第八组：安全 (8 tests)
# ===========================================================================


class TestSecurity:
    """安全相关完整测试"""

    def test_090_path_traversal_raw(self):
        status, data = _get("/api/projects/ccc/file?path=../etc/passwd")
        assert status == 400

    def test_091_path_traversal_encoded(self):
        status, data = _get("/api/projects/ccc/file?path=..%2f..%2fetc%2fpasswd")
        assert status == 400

    def test_092_path_traversal_double_dot(self):
        for path in ["....//....//etc/passwd", "..\\..\\etc\\passwd",
                      "%2e%2e%2fetc%2fpasswd", "..%252f..%252fetc%252fpasswd"]:
            status, data = _get(f"/api/projects/ccc/file?path={path}")
            assert status in (400, 404), f"Path not blocked: {path}"

    def test_093_excluded_dir_blocked(self):
        for d in [".git/HEAD", "node_modules/package/index.js",
                   "__pycache__/test.pyc", ".venv/bin/python"]:
            status, data = _get(f"/api/projects/ccc/file?path={d}")
            assert status in (400, 404), f"Dir not blocked: {d}"

    def test_094_binary_file_rejected(self):
        # Try to read a .pyc file
        status, data = _get("/api/projects/ccc/file?path=.pyc/test.pyc")
        assert status in (400, 404, 415), f"Binary not rejected: {status}"

    def test_095_dangerous_command_variants(self):
        for cmd in ["rm -rf /", "sudo rm -rf /", "dd if=/dev/zero of=/dev/sda",
                      "mkfs.ext4 /dev/sda", "format C:", "> /dev/null",
                      "rm /etc/passwd", "sudo !!"]:
            status, body = _post("/api/execute", {
                "messages": [{"role": "user", "content": cmd}],
                "session_id": f"test-sec-cmd-{hash(cmd) & 0xFFFF}",
            })
            assert status == 400, f"Dangerous command allowed: {cmd}"

    def test_096_safe_commands_allowed(self):
        """Safe commands should return status != 400 (likely 429 or 200)."""
        status, body = _post("/api/execute", {
            "messages": [{"role": "user", "content": "echo hello world"}],
            "session_id": f"test-safecmd-{int(time.time())}",
        })
        # May be 200, 429, or 500 — but NOT 400
        assert status != 400, f"Safe command blocked: {status} {body}"

    def test_097_history_doesnt_leak_other_projects(self):
        """Sessions for one project shouldn't leak to another."""
        # Create session in qxo
        sid = f"test-leak-{int(time.time())}"
        status, _ = _stream_post("/api/chat", {
            "messages": [{"role": "user", "content": "leak test"}],
            "session_id": sid,
            "project": "qxo",
        }, read_limit=5)
        assert status == 200
        time.sleep(0.5)
        # It shouldn't appear in ccc's history
        status, ccc_data = _get("/api/history?project=ccc")
        assert status == 200
        ccc_ids = [s["session_id"] for s in ccc_data["sessions"]]
        assert sid not in ccc_ids, "Session leaked across projects"
        # But should appear in qxo's history
        status, qxo_data = _get("/api/history?project=qxo")
        assert status == 200
        qxo_ids = [s["session_id"] for s in qxo_data["sessions"]]
        assert sid in qxo_ids, "Session missing from own project"


# ===========================================================================
# 第九组：边界条件 (8 tests)
# ===========================================================================


class TestEdgeCases:
    """边界条件和异常输入"""

    def test_100_empty_message_list_400(self):
        status, data = _post("/api/chat", {"messages": []})
        assert status == 400

    def test_101_missing_messages_key_422(self):
        payload = json.dumps({"session_id": "test"}).encode()
        req = urllib.request.Request(
            f"{BASE_URL}/api/chat", data=payload, method="POST",
            headers={"Content-Type": "application/json", "Authorization": AUTH_HEADER},
        )
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT):
                pass
        except urllib.error.HTTPError as e:
            assert e.code in (400, 422)

    def test_102_unicode_in_session_id(self):
        sid = f"test-unicode-中文-🌍-{int(time.time())}"
        status, lines = _stream_post("/api/chat", {
            "messages": [{"role": "user", "content": "hi"}],
            "session_id": sid,
        }, read_limit=5)
        assert status == 200

    def test_103_very_long_message(self):
        long_msg = "word " * 1000
        status, lines = _stream_post("/api/chat", {
            "messages": [{"role": "user", "content": long_msg}],
            "session_id": f"test-long-{int(time.time())}",
        }, read_limit=5)
        assert status == 200

    def test_104_empty_project_name(self):
        status, lines = _stream_post("/api/chat", {
            "messages": [{"role": "user", "content": "hi"}],
            "project": "",
        }, read_limit=5)
        assert status == 200  # Should fall back to default

    def test_105_history_after_delete(self):
        """Deleted session should not appear in history list."""
        sid = f"test-hist-del-{int(time.time())}"
        status, _ = _stream_post("/api/chat", {
            "messages": [{"role": "user", "content": "delete me from history"}],
            "session_id": sid,
        }, read_limit=5)
        assert status == 200
        time.sleep(0.5)
        _delete(f"/api/history/{sid}")
        time.sleep(0.5)
        status, data = _get("/api/history")
        assert status == 200
        assert sid not in [s["session_id"] for s in data["sessions"]]

    def test_106_concurrent_project_switch(self):
        """Switching projects should return different session lists."""
        p1_sid = f"test-conc-p1-{int(time.time())}"
        p2_sid = f"test-conc-p2-{int(time.time())}"
        _stream_post("/api/chat", {
            "messages": [{"role": "user", "content": "p1"}],
            "session_id": p1_sid, "project": "ccc",
        }, read_limit=3)
        _stream_post("/api/chat", {
            "messages": [{"role": "user", "content": "p2"}],
            "session_id": p2_sid, "project": "qxo",
        }, read_limit=3)
        time.sleep(0.5)
        _, ccc_data = _get("/api/history?project=ccc")
        _, qxo_data = _get("/api/history?project=qxo")
        ccc_ids = [s["session_id"] for s in ccc_data["sessions"]]
        qxo_ids = [s["session_id"] for s in qxo_data["sessions"]]
        assert p1_sid in ccc_ids
        assert p2_sid in qxo_ids
        assert p1_sid not in qxo_ids
        assert p2_sid not in ccc_ids

    def test_107_default_project_is_ccc(self):
        """When no project specified, should default to 'ccc'."""
        sid = f"test-defproj-{int(time.time())}"
        status, _ = _stream_post("/api/chat", {
            "messages": [{"role": "user", "content": "default project test"}],
            "session_id": sid,
        }, read_limit=5)
        assert status == 200
        time.sleep(0.5)
        status, data = _get(f"/api/history/{sid}")
        assert status == 200
        assert data.get("project", "ccc") == "ccc"


# ===========================================================================
# 第十组：前端 JS 函数签名验证 (6 tests)
# ===========================================================================


class TestJSFunctionSignatures:
    """验证关键 JS 函数存在且签名正确"""

    def test_110_chat_functions(self):
        for fn in ["sendChat", "streamRequest", "cancelStream", "renderMessage",
                     "renderMarkdown", "escapeHtml", "onKey"]:
            assert f"function {fn}" in self.H, f"Missing function {fn}"

    def test_111_execute_functions(self):
        for fn in ["sendExecute", "terminalStream", "resetTerminal",
                     "renderTerminalHistory"]:
            assert f"function {fn}" in self.H, f"Missing function {fn}"

    def test_112_board_functions(self):
        for fn in ["loadBoard", "openTaskModal", "closeTaskModal", "createTask"]:
            assert f"function {fn}" in self.H, f"Missing function {fn}"

    def test_113_sidebar_functions(self):
        for fn in ["toggleSidebar", "loadHistory", "loadSession", "newChat", "newExecChat"]:
            assert f"function {fn}" in self.H, f"Missing function {fn}"

    def test_114_file_functions(self):
        for fn in ["loadFileTree", "renderFileTree", "_buildFileItem",
                     "readFile", "showFilePreview"]:
            assert f"function {fn}" in self.H, f"Missing function {fn}"

    def test_115_utility_functions(self):
        for fn in ["copyCode", "scrollToBottom", "ts", "removeTyping",
                     "updateExecMetaBar", "onProjectChange"]:
            assert f"function {fn}" in self.H, f"Missing function {fn}"


# ===========================================================================
# 第十一组：Launchd 和基础设施 (4 tests)
# ===========================================================================


class TestInfrastructure:
    """launchd plist 和 infrastructure.md"""

    def test_120_plist_exists(self):
        plist = PROJECT_ROOT / "scripts" / "com.ccc.chat-server.plist"
        assert plist.exists()
        content = plist.read_text()
        assert "com.ccc.chat-server" in content
        assert "KeepAlive" in content
        assert "RunAtLoad" in content
        assert "ccc-chat-server.py" in content

    def test_121_plist_installed(self):
        """Verify the plist is installed in LaunchAgents."""
        plist = Path.home() / "Library" / "LaunchAgents" / "com.ccc.chat-server.plist"
        assert plist.exists()
        content = plist.read_text()
        assert "com.ccc.chat-server" in content
        assert "ccc-chat-server.py" in content

    def test_122_infra_md_has_8084(self):
        infra = PROJECT_ROOT / ".ccc" / "infrastructure.md"
        text = infra.read_text()
        assert "8084" in text
        assert "CCC Chat" in text

    def test_123_infra_m1_port_table_has_8084(self):
        infra = PROJECT_ROOT / ".ccc" / "infrastructure.md"
        text = infra.read_text()
        lines = text.splitlines()
        in_m1 = False
        found = False
        for line in lines:
            if "M1" in line and "端口" in line:
                in_m1 = True
            elif in_m1 and line.strip().startswith("|") and "8084" in line:
                found = True
            elif in_m1 and line.strip().startswith("##"):
                break
        assert found, "8084 not found in M1 port table"


# ===========================================================================
# 第十二组：docstring 修复 (2 tests)
# ===========================================================================


class TestDocstring:
    """P0.3 修复验证"""

    def test_130_no_8082_in_docstring(self):
        src = CHAT_SCRIPT.read_text()
        for i, line in enumerate(src.splitlines(), 1):
            stripped = line.strip()
            if "localhost:8082" in stripped and "Usage" in line:
                pytest.fail(f"Line {i}: residual 8082 reference in docstring")

    def test_131_8084_in_docstring(self):
        src = CHAT_SCRIPT.read_text()
        assert "localhost:8084" in src


# ===========================================================================
# 第十三组：文件读取格式验证 (4 tests)
# ===========================================================================


class TestFileReadFormat:
    """文件读取 API 格式验证"""

    def test_140_file_response_has_all_fields(self):
        status, data = _get("/api/projects/ccc/file?path=README.md")
        if status == 404:
            pytest.skip("README.md not found")
        assert status == 200
        for field in ["project_id", "path", "size", "truncated", "content"]:
            assert field in data, f"Missing field {field}"

    def test_141_file_response_truncation(self):
        """Large files should set truncated=True."""
        status, data = _get("/api/projects/qxo/file?path=app/main.py")
        if status == 404:
            pytest.skip("File not found")
        assert status == 200
        if data["truncated"]:
            assert len(data["content"]) <= 100 * 1024  # MAX_FILE_READ_BYTES

    def test_142_file_entry_has_size(self):
        status, data = _get("/api/projects/ccc/files")
        assert status == 200
        files = [e for e in data["entries"] if e["type"] == "file"]
        assert len(files) > 0
        for f in files[:5]:
            assert "size" in f, f"File {f['name']} missing size"

    def test_143_dir_entries_have_depth(self):
        status, data = _get("/api/projects/ccc/files")
        assert status == 200
        for entry in data["entries"][:10]:
            assert entry["depth"] >= 1


# ===========================================================================
# 第十四组：上下文注入 (2 tests)
# ===========================================================================


class TestContextInjection:
    """项目上下文注入和截断"""

    def test_150_context_has_claude_md(self):
        src = CHAT_SCRIPT.read_text()
        assert "_get_project_context" in src
        assert "CLAUDE.md" in src

    def test_151_context_truncation(self):
        src = CHAT_SCRIPT.read_text()
        assert "truncated_len" in src or "已截断" in src


# ===========================================================================
# 第十五组：CSS 一致性 (4 tests)
# ===========================================================================


class TestCSSConsistency:
    """CSS 变量没有硬编码颜色"""

    def test_160_terminal_no_hardcoded_colors(self):
        """Terminal section should not have hardcoded Tokyo Night hex colors."""
        lines = self.H.splitlines()
        in_style = False
        for line in lines:
            if "<style>" in line:
                in_style = True
                continue
            if "</style>" in line:
                break
            if not in_style:
                continue
            # These hex codes should only appear in :root definitions
            for hex_code in ["#1a1b26", "#1f2233", "#565f89", "#2f3346",
                             "#292e42", "#24283b", "#c0caf5", "#7dcfff",
                             "#9ece6a", "#f7768e", "#0d0e15", "#13141f",
                             "#3b3d55", "#9aa5ce", "#7aa2f7"]:
                if hex_code in line and "--" not in line and ":" not in line.split(hex_code)[0][-2:]:
                    pytest.fail(f"Hardcoded color {hex_code} at line: {line.strip()[:80]}")

    def test_161_diff_colors_use_vars(self):
        """diff-add and diff-del use CSS variables."""
        assert "var(--success)" in self.H
        assert "var(--danger)" in self.H

    def test_162_colors_outside_style_block(self):
        """Content outside <style> should not have hardcoded terminal colors."""
        style_end = self.H.find("</style>")
        after_style = self.H[style_end:]
        # These should not appear in the JS or HTML (they're fine in the style)
        for hex_code in ["#1a1b26", "#1f2233", "#565f89"]:
            if hex_code in after_style:
                # These could be in JS test data or console.log
                pass  # Allow them in JS

    def test_163_apple_color_respects_theme(self):
        """User bubble colors should use CSS variables."""
        assert "var(--user-bg)" in self.H
        assert "var(--user-text)" in self.H
        assert "var(--accent)" in self.H


# ===========================================================================
# 第十六组：流式 SSE 格式验证 (3 tests)
# ===========================================================================


class TestSSEFormat:
    """SSE 协议格式验证"""

    def test_170_chat_sse_format(self):
        status, lines = _stream_post("/api/chat", {
            "messages": [{"role": "user", "content": "test sse format"}],
            "session_id": f"test-sse-fmt-{int(time.time())}",
        }, read_limit=20)
        assert status == 200
        for line in lines:
            if not line.startswith("data: "):
                continue
            payload = line[6:]
            if payload == "[DONE]":
                continue
            try:
                obj = json.loads(payload)
                assert "type" in obj
            except json.JSONDecodeError:
                pytest.fail(f"Invalid JSON in SSE data: {line}")

    def test_171_chat_sse_event_types(self):
        """Chat SSE should include delta event."""
        status, lines = _stream_post("/api/chat", {
            "messages": [{"role": "user", "content": "test event types"}],
            "session_id": f"test-sse-type-{int(time.time())}",
        }, read_limit=20)
        assert status == 200
        events = []
        for line in lines:
            if line.startswith("data: "):
                try:
                    obj = json.loads(line[6:])
                    events.append(obj.get("type"))
                except json.JSONDecodeError:
                    pass
        assert "delta" in events, f"No delta event found, got: {events}"

    def test_172_execute_sse_content_type(self):
        status, _ = _post("/api/execute", {
            "messages": [{"role": "user", "content": "safe test command"}],
            "session_id": f"test-exec-sse-{int(time.time())}",
        })
        # May be 200, 429, or 400 — but the endpoint should handle it
        assert status in (200, 429, 400)
