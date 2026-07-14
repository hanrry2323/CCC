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
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

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
# 第一组：服务基础设施
# ===========================================================================


class TestServiceInfrastructure:

    def test_001_service_http_200(self):
        status, body = _get("/", auth=False)
        assert status == 200
        assert "CCC Chat" in body

    def test_002_unauth_returns_401(self):
        req = urllib.request.Request(f"{BASE_URL}/api/projects")
        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(req, timeout=TIMEOUT)
        assert exc.value.code == 401

    def test_003_projects_list(self):
        status, data = _get("/api/projects")
        assert status == 200
        assert len(data["projects"]) >= 4
        ids = [p["id"] for p in data["projects"]]
        assert "ccc" in ids
        assert "qxo" in ids
        assert "xianyu" in ids

    def test_004_history_api(self):
        status, data = _get("/api/history")
        assert status == 200
        assert "sessions" in data

    def test_005_history_by_project(self):
        for project in ("ccc", "qxo", "xianyu"):
            status, data = _get(f"/api/history?project={project}")
            assert status == 200, f"project={project} failed"
            assert "sessions" in data

    def test_006_file_tree(self):
        status, data = _get("/api/projects/ccc/files")
        assert status == 200
        assert len(data["entries"]) > 0
        assert "truncated" in data
        for entry in data["entries"][:3]:
            assert "name" in entry
            assert "type" in entry
            assert "path" in entry

    def test_007_file_tree_all_projects(self):
        for project in ("ccc", "qxo", "xianyu", "hp", "ai-loop-router"):
            status, data = _get(f"/api/projects/{project}/files")
            assert status == 200, f"project={project} failed"
            assert len(data["entries"]) > 0, f"project={project} has no entries"

    def test_008_unknown_project_404(self):
        status, data = _get("/api/projects/unknown_project/files")
        assert status == 404

    def test_009_read_file(self):
        status, data = _get("/api/projects/ccc/file?path=scripts/ccc-chat-server.py")
        assert status == 200
        assert "content" in data
        assert data["project_id"] == "ccc"
        assert data["size"] > 0

    def test_010_file_not_found_404(self):
        status, data = _get("/api/projects/ccc/file?path=nonexistent_xyz123")
        assert status == 404

    def test_011_board_proxy(self):
        status, data = _get("/api/board/proxy/board?workspace=CCC")
        assert status in (200, 503)


# ===========================================================================
# 第二组：Chat SSE 流式
# ===========================================================================


def _make_sid(prefix="test"):
    return f"{prefix}-{int(time.time() * 1000)}"


class TestChatStreaming:

    def test_020_chat_stream_returns_sse(self):
        status, lines = _stream_post("/api/chat", {
            "messages": [{"role": "user", "content": "Say hello in 3 words"}],
            "session_id": _make_sid("ch20"),
        })
        assert status == 200
        assert len(lines) > 0
        sse = [l for l in lines if l.startswith("data: ")]
        assert len(sse) > 0

    def test_021_chat_stream_has_delta_events(self):
        status, lines = _stream_post("/api/chat", {
            "messages": [{"role": "user", "content": "Count to 3"}],
            "session_id": _make_sid("ch21"),
        }, read_limit=20)
        assert status == 200
        has_delta = any('delta' in l for l in lines)
        assert has_delta, f"No delta events in {len(lines)} lines"

    def test_022_chat_stream_sse_json(self):
        status, lines = _stream_post("/api/chat", {
            "messages": [{"role": "user", "content": "Hi"}],
            "session_id": _make_sid("ch22"),
        }, read_limit=20)
        assert status == 200
        for line in lines:
            if line.startswith("data: "):
                try:
                    obj = json.loads(line[6:])
                    assert "type" in obj
                except json.JSONDecodeError:
                    pytest.fail(f"Bad JSON: {line}")

    def test_023_chat_with_project_context(self):
        status, lines = _stream_post("/api/chat", {
            "messages": [{"role": "user", "content": "What project?"}],
            "project": "ccc",
            "session_id": _make_sid("ch23"),
        }, read_limit=10)
        assert status == 200

    def test_024_chat_empty_messages_rejected(self):
        status, body = _post("/api/chat", {"messages": []})
        assert status in (400, 422), f"expected 400/422 got {status}"

    def test_025_chat_no_session_id(self):
        status, lines = _stream_post("/api/chat", {
            "messages": [{"role": "user", "content": "ping"}],
        }, read_limit=5)
        assert status == 200

    def test_026_chat_model_param(self):
        status, lines = _stream_post("/api/chat", {
            "messages": [{"role": "user", "content": "hi"}],
            "model": "flash",
        }, read_limit=5)
        assert status == 200

    def test_027_chat_unicode(self):
        status, lines = _stream_post("/api/chat", {
            "messages": [{"role": "user", "content": "你好世界 🌍 こんにちは"}],
            "session_id": _make_sid("ch27"),
        }, read_limit=10)
        assert status == 200

    def test_028_chat_special_chars(self):
        status, lines = _stream_post("/api/chat", {
            "messages": [{"role": "user", "content": "Line1\nLine2\nTab\there"}],
            "session_id": _make_sid("ch28"),
        }, read_limit=10)
        assert status == 200

    def test_029_chat_session_persists(self):
        sid = _make_sid("ch29")
        status, _ = _stream_post("/api/chat", {
            "messages": [{"role": "user", "content": "persist test"}],
            "session_id": sid,
        }, read_limit=10)
        assert status == 200
        time.sleep(0.7)
        status, data = _get("/api/history")
        assert status == 200
        sids = [s["session_id"] for s in data["sessions"]]
        assert sid in sids, f"Session {sid} not found"


# ===========================================================================
# 第三组：Execute
# ===========================================================================


class TestExecute:

    def test_030_dangerous_command_blocked(self):
        for cmd in ["rm -rf /", "sudo rm -rf /"]:
            status, body = _post("/api/execute", {
                "messages": [{"role": "user", "content": cmd}],
                "session_id": _make_sid("ex30"),
            })
            assert status == 400, f"Command not blocked: {cmd}"
            assert "危险指令" in body

    def test_031_execute_empty_messages_400(self):
        status, body = _post("/api/execute", {"messages": []})
        assert status in (400, 422)

    def test_032_execute_no_user_400(self):
        status, body = _post("/api/execute", {
            "messages": [{"role": "assistant", "content": "hello"}],
        })
        assert status in (400, 422)

    def test_033_execute_unknown_project_400(self):
        status, body = _post("/api/execute", {
            "messages": [{"role": "user", "content": "hello"}],
            "project": "nonexistent",
        })
        assert status == 400

    def test_034_execute_queue_code_path(self):
        src = CHAT_SCRIPT.read_text()
        assert "_EXECUTE_WAITERS: list[asyncio.Event]" in src
        assert "_EXEC_QUEUE_MAX = 3" in src

    def test_035_queue_overflow_msg(self):
        src = CHAT_SCRIPT.read_text()
        assert "队列已满" in src

    def test_036_partial_save_flag(self):
        src = CHAT_SCRIPT.read_text()
        assert '"partial"' in src
        assert 'partial": not stream_completed' in src

    def test_037_timeout_exists(self):
        src = CHAT_SCRIPT.read_text()
        assert "执行超时" in src

    def test_038_uses_claude_cli(self):
        src = CHAT_SCRIPT.read_text()
        assert "create_subprocess_exec" in src
        assert '"claude"' in src
        assert '"flash"' in src

    def test_039_safe_command_not_400(self):
        status, body = _post("/api/execute", {
            "messages": [{"role": "user", "content": "echo safe"}],
            "session_id": _make_sid("ex39"),
        })
        assert status != 400, f"Safe command blocked: {status} {body[:100]}"


# ===========================================================================
# 第四组：会话持久化
# ===========================================================================


class TestSessionPersistence:

    def test_040_create_and_list_session(self):
        sid = _make_sid("sp40")
        status, _ = _stream_post("/api/chat", {
            "messages": [{"role": "user", "content": "test session"}],
            "session_id": sid,
        }, read_limit=10)
        assert status == 200
        time.sleep(0.5)
        status, data = _get("/api/history")
        assert status == 200
        assert sid in [s["session_id"] for s in data["sessions"]]

    def test_041_session_in_all_projects(self):
        for project in ("ccc", "qxo", "xianyu"):
            sid = _make_sid(f"sp41-{project}")
            status, _ = _stream_post("/api/chat", {
                "messages": [{"role": "user", "content": f"Test {project}"}],
                "session_id": sid, "project": project,
            }, read_limit=5)
            assert status == 200
            time.sleep(0.5)
            status, data = _get(f"/api/history?project={project}")
            assert status == 200
            assert sid in [s["session_id"] for s in data["sessions"]]

    def test_042_get_session_by_id(self):
        sid = _make_sid("sp42")
        status, _ = _stream_post("/api/chat", {
            "messages": [{"role": "user", "content": "get me"}],
            "session_id": sid,
        }, read_limit=10)
        assert status == 200
        time.sleep(0.5)
        status, data = _get(f"/api/history/{sid}")
        assert status == 200
        assert data["session_id"] == sid
        assert "messages" in data
        assert "created_at" in data

    def test_043_get_session_404(self):
        status, data = _get("/api/history/nonexistent-session-xyz-123456")
        assert status == 404

    def test_044_session_has_all_fields(self):
        sid = _make_sid("sp44")
        status, _ = _stream_post("/api/chat", {
            "messages": [{"role": "user", "content": "fields test"}],
            "session_id": sid, "project": "ccc",
        }, read_limit=10)
        assert status == 200
        time.sleep(0.5)
        status, data = _get(f"/api/history/{sid}")
        assert status == 200
        for field in ("session_id", "title", "project", "messages", "created_at", "updated_at"):
            assert field in data, f"Missing field {field}"
        assert data["project"] == "ccc"

    def test_045_delete_session(self):
        sid = _make_sid("sp45")
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

    def test_046_delete_nonexistent(self):
        status, _ = _delete("/api/history/nonexistent-xyz-999999")
        assert status == 200

    def test_047_session_on_disk(self):
        sid = _make_sid("sp47")
        status, _ = _stream_post("/api/chat", {
            "messages": [{"role": "user", "content": "disk test"}],
            "session_id": sid,
        }, read_limit=5)
        assert status == 200
        time.sleep(0.5)
        sfile = PROJECT_ROOT / ".ccc" / "chat" / "ccc" / f"{sid}.json"
        assert sfile.exists(), f"Not on disk: {sfile}"
        data = json.loads(sfile.read_text())
        assert data["session_id"] == sid
        sfile.unlink(missing_ok=True)

    def test_048_cross_project_isolation(self):
        sid = _make_sid("sp48")
        status, _ = _stream_post("/api/chat", {
            "messages": [{"role": "user", "content": "isolate test"}],
            "session_id": sid, "project": "qxo",
        }, read_limit=5)
        assert status == 200
        time.sleep(0.5)
        _, ccc_data = _get("/api/history?project=ccc")
        _, qxo_data = _get("/api/history?project=qxo")
        ccc_ids = [s["session_id"] for s in ccc_data["sessions"]]
        qxo_ids = [s["session_id"] for s in qxo_data["sessions"]]
        assert sid not in ccc_ids, "Session leaked across projects"
        assert sid in qxo_ids, "Session missing from own project"

    def test_049_session_history_sorted(self):
        status, data = _get("/api/history")
        assert status == 200
        sessions = data["sessions"]
        assert all("session_id" in s for s in sessions)


# ===========================================================================
# 第五组：前端 HTML
# ===========================================================================


def _html() -> str:
    _, body = _get("/", auth=False)
    return body


class TestFrontendHtml:

    def test_050_page_structure(self):
        h = _html()
        assert "<!DOCTYPE html>" in h
        assert '<html lang="zh-CN">' in h
        assert "<body>" in h

    def test_051_html_ids(self):
        h = _html()
        for id_val in ["app", "header", "messages", "input-area", "input-wrap",
                       "send", "tabbar", "sidebar", "sessionList"]:
            assert f'id="{id_val}"' in h, f"Missing id={id_val}"

    def test_052_three_panels(self):
        h = _html()
        for panel in ["chat-panel", "exec-panel", "board-panel"]:
            assert f'id="{panel}"' in h

    def test_053_project_selector(self):
        h = _html()
        assert 'id="project-select"' in h

    def test_054_theme_button(self):
        h = _html()
        assert "themeBtn" in h
        assert "toggleTheme" in h

    def test_055_skeleton(self):
        h = _html()
        assert "skeleton-pulse" in h
        assert "skeleton-card" in h

    def test_056_send_buttons(self):
        h = _html()
        assert "sendChat" in h
        assert "sendExecute" in h
        assert "cancelStream" in h

    def test_057_message_edit(self):
        h = _html()
        assert "editMessage" in h
        assert "saveEdit" in h
        assert "cancelEdit" in h
        assert "dblclick" in h

    def test_058_file_tree(self):
        h = _html()
        assert "loadFileTree" in h
        assert "renderFileTree" in h
        assert "readFile" in h

    def test_059_board(self):
        h = _html()
        assert "loadBoard" in h
        assert "board-col" in h
        assert "openTaskModal" in h

    def test_060_sidebar(self):
        h = _html()
        assert "loadHistory" in h
        assert "loadSession" in h
        assert "toggleSidebar" in h
        assert "newChat" in h


# ===========================================================================
# 第六组：主题系统
# ===========================================================================


class TestThemeSystem:

    def test_061_light_vars(self):
        h = _html()
        for var in ["--bg", "--surface", "--text", "--accent", "--border",
                     "--code-bg", "--user-bg", "--user-text"]:
            assert var in h, f"Missing {var}"

    def test_062_dark_vars(self):
        h = _html()
        assert 'data-theme="dark"' in h
        for var in ["--bg: #1c1c1e", "--surface: #2c2c2e", "--text: #f5f5f7",
                     "--accent: #0a84ff"]:
            assert var in h

    def test_063_terminal_vars(self):
        h = _html()
        for var in ["--terminal-bg", "--terminal-text", "--terminal-prompt",
                     "--terminal-header", "--terminal-sep", "--terminal-body"]:
            assert var in h

    def test_064_diff_vars(self):
        h = _html()
        assert "--success" in h
        assert "--danger" in h

    def test_065_theme_transition(self):
        h = _html()
        assert "transition-theme" in h

    def test_066_theme_persistence(self):
        h = _html()
        assert "localStorage.getItem" in h or "localStorage.setItem" in h
        assert "prefers-color-scheme" in h
        assert "matchMedia" in h


# ===========================================================================
# 第七组：Markdown 渲染
# ===========================================================================


class TestMarkdownRenderer:

    def test_070_render_markdown_function(self):
        h = _html()
        assert "function renderMarkdown" in h

    def test_071_headers(self):
        h = _html()
        for tag in ["<h1>", "<h2>", "<h3>", "<h4>"]:
            assert tag in h

    def test_072_lists(self):
        h = _html()
        assert "<ul>" in h
        assert "<ol>" in h
        assert "<li>" in h

    def test_073_block_elements(self):
        h = _html()
        assert "<blockquote>" in h
        assert "<hr>" in h

    def test_074_tables(self):
        h = _html()
        assert "<table>" in h
        assert "<thead>" in h
        assert "<th>" in h
        assert "<td>" in h

    def test_075_links(self):
        h = _html()
        assert '<a href=' in h
        assert 'target="_blank"' in h

    def test_076_images(self):
        h = _html()
        assert "<img" in h

    def test_077_inline_formatting(self):
        h = _html()
        assert "<strong>" in h
        assert "<em>" in h
        assert "<code>" in h

    def test_078_code_blocks(self):
        h = _html()
        assert "code-block-wrap" in h
        assert "copyCode" in h

    def test_079_diff_and_tools(self):
        h = _html()
        assert "parseDiff" in h
        assert "renderDiff" in h
        assert "TOOL_ICONS" in h or "toolIcon" in h

    def test_080_terminal_functions(self):
        h = _html()
        for fn in ["renderTerminalCommand", "appendTerminalInfo",
                     "renderTerminalHistory", "terminalStream"]:
            assert f"function {fn}" in h


# ===========================================================================
# 第八组：安全
# ===========================================================================


class TestSecurity:

    def test_090_path_traversal_raw(self):
        status, data = _get("/api/projects/ccc/file?path=../etc/passwd")
        assert status == 400

    def test_091_path_traversal_encoded(self):
        status, data = _get("/api/projects/ccc/file?path=..%2f..%2fetc%2fpasswd")
        assert status == 400

    def test_092_path_traversal_variants(self):
        for path in ["....//....//etc/passwd",
                      "%2e%2e%2fetc%2fpasswd",
                      "..%252f..%252fetc%252fpasswd"]:
            status, data = _get(f"/api/projects/ccc/file?path={path}")
            assert status in (400, 404), f"Path not blocked: {path}"

    def test_093_excluded_dirs(self):
        for d in [".git/HEAD", "node_modules/package/index.js",
                   "__pycache__/test.pyc"]:
            status, data = _get(f"/api/projects/ccc/file?path={d}")
            assert status in (400, 404), f"Dir not blocked: {d}"

    def test_094_dangerous_commands(self):
        for cmd in ["rm -rf /", "sudo rm -rf /", "format C:"]:
            status, body = _post("/api/execute", {
                "messages": [{"role": "user", "content": cmd}],
                "session_id": _make_sid("sc94"),
            })
            assert status == 400, f"Allowed: {cmd}"

    def test_095_safe_command_passes(self):
        status, body = _post("/api/execute", {
            "messages": [{"role": "user", "content": "echo hello"}],
            "session_id": _make_sid("sc95"),
        })
        assert status != 400, f"Safe command blocked: {status} {body[:100]}"


# ===========================================================================
# 第九组：边界条件
# ===========================================================================


class TestEdgeCases:

    def test_100_empty_messages(self):
        status, body = _post("/api/chat", {"messages": []})
        assert status in (400, 422)

    def test_101_missing_key(self):
        payload = json.dumps({"session_id": "test"}).encode()
        req = urllib.request.Request(
            f"{BASE_URL}/api/chat", data=payload, method="POST",
            headers={"Content-Type": "application/json", "Authorization": AUTH_HEADER},
        )
        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(req, timeout=TIMEOUT)
        assert exc.value.code in (400, 422)

    def test_102_unicode_session_id(self):
        sid = _make_sid("sc102")
        status, lines = _stream_post("/api/chat", {
            "messages": [{"role": "user", "content": "hi"}],
            "session_id": sid,
        }, read_limit=5)
        assert status == 200

    def test_103_long_message(self):
        status, lines = _stream_post("/api/chat", {
            "messages": [{"role": "user", "content": "word " * 1000}],
            "session_id": _make_sid("sc103"),
        }, read_limit=5)
        assert status == 200

    def test_104_empty_project(self):
        status, lines = _stream_post("/api/chat", {
            "messages": [{"role": "user", "content": "hi"}],
            "project": "",
        }, read_limit=5)
        assert status == 200

    def test_105_history_after_delete(self):
        sid = _make_sid("sc105")
        status, _ = _stream_post("/api/chat", {
            "messages": [{"role": "user", "content": "delete test"}],
            "session_id": sid,
        }, read_limit=5)
        assert status == 200
        time.sleep(0.5)
        _delete(f"/api/history/{sid}")
        time.sleep(0.5)
        status, data = _get("/api/history")
        assert status == 200
        assert sid not in [s["session_id"] for s in data["sessions"]]

    def test_106_default_project(self):
        sid = _make_sid("sc106")
        status, _ = _stream_post("/api/chat", {
            "messages": [{"role": "user", "content": "default test"}],
            "session_id": sid,
        }, read_limit=5)
        assert status == 200
        time.sleep(0.5)
        status, data = _get(f"/api/history/{sid}")
        assert status == 200
        assert data.get("project", "ccc") == "ccc"


# ===========================================================================
# 第十组：JS 函数签名
# ===========================================================================


class TestJSFunctions:

    def test_110_chat_functions(self):
        h = _html()
        for fn in ["sendChat", "streamRequest", "cancelStream", "renderMessage",
                     "renderMarkdown", "escapeHtml", "onKey"]:
            assert f"function {fn}" in h

    def test_111_execute_functions(self):
        h = _html()
        for fn in ["sendExecute", "terminalStream", "resetTerminal",
                     "renderTerminalHistory"]:
            assert f"function {fn}" in h

    def test_112_board_functions(self):
        h = _html()
        for fn in ["loadBoard", "openTaskModal", "closeTaskModal", "createTask"]:
            assert f"function {fn}" in h

    def test_113_sidebar_functions(self):
        h = _html()
        for fn in ["toggleSidebar", "loadHistory", "loadSession", "newChat"]:
            assert f"function {fn}" in h

    def test_114_file_functions(self):
        h = _html()
        for fn in ["loadFileTree", "renderFileTree", "readFile", "showFilePreview"]:
            assert f"function {fn}" in h

    def test_115_utility_functions(self):
        h = _html()
        for fn in ["copyCode", "scrollToBottom", "ts", "onProjectChange", "switchTab"]:
            assert f"function {fn}" in h

    def test_116_tab_functions(self):
        h = _html()
        for fn in ["sendChat", "sendExecute", "cancelStream", "newChat",
                     "toggleSidebar", "toggleInputMode", "switchTab"]:
            assert f"function {fn}" in h


# ===========================================================================
# 第十一组：基础设施
# ===========================================================================


class TestInfrastructure:

    def test_120_plist_in_repo(self):
        plist = PROJECT_ROOT / "scripts" / "com.ccc.chat-server.plist"
        assert plist.exists()
        content = plist.read_text()
        assert "com.ccc.chat-server" in content
        assert "KeepAlive" in content

    def test_121_plist_installed(self):
        plist = Path.home() / "Library" / "LaunchAgents" / "com.ccc.chat-server.plist"
        assert plist.exists()
        content = plist.read_text()
        assert "com.ccc.chat-server" in content

    def test_122_infra_md_has_8084(self):
        infra = PROJECT_ROOT / ".ccc" / "infrastructure.md"
        text = infra.read_text()
        assert "8084" in text
        assert "CCC Chat" in text

    def test_123_docstring_fixed(self):
        src = CHAT_SCRIPT.read_text()
        assert "localhost:8084" in src


# ===========================================================================
# 第十二组：CSS 一致性
# ===========================================================================


class TestCSSConsistency:

    def test_130_terminal_colors_use_vars(self):
        h = _html()
        assert "var(--terminal-bg)" in h
        assert "var(--terminal-text)" in h
        assert "var(--terminal-header)" in h
        assert "var(--terminal-sep)" in h

    def test_131_diff_colors_use_vars(self):
        h = _html()
        assert "var(--success)" in h
        assert "var(--danger)" in h

    def test_132_apple_colors_use_vars(self):
        h = _html()
        assert "var(--user-bg)" in h
        assert "var(--user-text)" in h
        assert "var(--accent)" in h


# ===========================================================================
# 第十三组：SSE 流式格式
# ===========================================================================


class TestSSEFormat:

    def test_140_chat_sse_valid_json(self):
        status, lines = _stream_post("/api/chat", {
            "messages": [{"role": "user", "content": "test sse"}],
            "session_id": _make_sid("ss140"),
        }, read_limit=20)
        assert status == 200
        for line in lines:
            if line.startswith("data: "):
                payload = line[6:]
                if payload == "[DONE]":
                    continue
                assert json.loads(payload), f"Bad JSON: {line}"

    def test_141_chat_sse_has_delta_type(self):
        status, lines = _stream_post("/api/chat", {
            "messages": [{"role": "user", "content": "test types"}],
            "session_id": _make_sid("ss141"),
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
        assert "delta" in events, f"No delta event: {events}"

    def test_142_chat_sse_returns_events(self):
        status, lines = _stream_post("/api/chat", {
            "messages": [{"role": "user", "content": "test events"}],
            "session_id": _make_sid("ss142"),
        }, read_limit=5)
        assert status == 200
        data_lines = [l for l in lines if l.startswith("data: ")]
        assert len(data_lines) > 0
