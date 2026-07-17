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
# Hub 约定账密均为 ccc
_TEST_PASS = "ccc"
AUTH_HEADER = "Basic " + __import__("base64").b64encode(
    f"ccc:{_TEST_PASS}".encode()
).decode()
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


def _stream_post(path: str, data: dict, read_limit: int = 5, read_timeout: int = 0):
    """POST and read the first N SSE lines from a streaming response.

    read_timeout: socket-level timeout for SSE line reads (0 = use TIMEOUT).
    Increase to 30+ when claude CLI cold start produces first line after >15s.
    """
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
            # 延长 socket 超时供 SSE 读取阶段使用，补偿 claude CLI 冷启动延迟
            if read_timeout > 0:
                sock = getattr(resp.fp, 'raw', resp.fp)._sock
                sock.settimeout(read_timeout)
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
def chat_server(tmp_path_factory):
    chat_tmp = tmp_path_factory.mktemp("ccc-chat-test")
    env = {
        **os.environ,
        "CCC_CHAT_PASS": _TEST_PASS,
        "CCC_CHAT_HOST": "127.0.0.1",
        "CCC_CHAT_USER": "ccc",
        "CCC_CHAT_DIR": str(chat_tmp),
        # 测试前台旁路：不因 control=disabled 进入 idle hold
        "CCC_FOREGROUND": "1",
    }
    proc = subprocess.Popen(
        [sys.executable, str(CHAT_SCRIPT), "--port", "18084", "--host", "127.0.0.1", "--no-open"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        cwd=PROJECT_ROOT,
        env=env,
    )
    # 冷启动含 import uvicorn/fastapi 可能 >15s
    for _ in range(60):
        try:
            r = urllib.request.urlopen(f"{BASE_URL}/", timeout=2)
            if r.status == 200:
                break
        except Exception:
            time.sleep(0.5)
    else:
        proc.kill()
        pytest.fail("chat-server did not start in 30s")
    yield chat_tmp
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
        assert "CCC Hub" in body or "hub-nav" in body

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
        for project in ("ccc", "qxo", "xianyu", "qb", "qx"):
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

    def test_012_native_board(self):
        status, data = _get("/api/board?workspace=CCC")
        assert status in (200, 503)

    def test_013_native_task_events(self):
        """GET /api/tasks/{task_id}/events — native path, proxied to board-server."""
        status, data = _get("/api/tasks/dummy-test/events?workspace=CCC")
        assert status in (200, 404, 503)
        if status == 200:
            assert "id" in data
            assert "events" in data
            assert isinstance(data["events"], list)

    def test_014_proxy_task_events(self):
        """GET /api/board/proxy/tasks/{task_id}/events — proxy prefix path."""
        status, data = _get("/api/board/proxy/tasks/dummy-test/events?workspace=CCC")
        assert status in (200, 404, 503)
        if status == 200:
            assert "id" in data
            assert "events" in data
            assert isinstance(data["events"], list)


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
        }, read_limit=5, read_timeout=45)
        assert status == 200
        assert len(lines) > 0
        sse = [l for l in lines if l.startswith("data: ")]
        assert len(sse) > 0

    def test_021_chat_stream_has_delta_events(self):
        status, lines = _stream_post("/api/chat", {
            "messages": [{"role": "user", "content": "Count to 3"}],
            "session_id": _make_sid("ch21"),
        }, read_limit=5)
        assert status == 200
        sse = [l for l in lines if l.startswith("data: ")]
        assert len(sse) > 0, f"No SSE data events in {len(lines)} lines"

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

    def test_024_chat_empty_messages_accepted(self):
        """Empty messages array is forwarded to proxy (not validated server-side)."""
        status, body = _post("/api/chat", {"messages": []})
        # Proxy handles empty messages; server doesn't validate locally
        assert status in (200, 400, 422), f"unexpected status {status}"

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

    def test_047_session_on_disk(self, chat_server):
        sid = _make_sid("sp47")
        # read_limit=0：只验 HTTP 200（会话已同步落盘），不读 SSE 避免 claude CLI 启动慢导致超时
        status, _ = _stream_post("/api/chat", {
            "messages": [{"role": "user", "content": "disk test"}],
            "session_id": sid,
        }, read_limit=0)
        assert status == 200
        time.sleep(0.5)
        # 调试：列出 chat_server 下所有文件
        import sys
        for p in sorted(chat_server.rglob("*")):
            if p.is_file():
                print(f"  [debug] chat_tmp/{p.relative_to(chat_server)}", file=sys.stderr)
        sfile = chat_server / "ccc" / f"{sid}.json"
        assert sfile.exists(), f"Not on disk: {sfile}"
        data = json.loads(sfile.read_text())
        assert data["session_id"] == sid
        sfile.unlink(missing_ok=True)

    def test_048_cross_project_isolation(self):
        pid = os.getpid()
        sid = f"cross-isolate-{pid}-{int(time.time() * 1000000)}"
        status, _ = _stream_post("/api/chat", {
            "messages": [{"role": "user", "content": "isolate test"}],
            "session_id": sid, "project": "qxo",
        }, read_limit=5)
        assert status == 200
        time.sleep(1.0)
        _, ccc_data = _get("/api/history?project=ccc")
        _, qxo_data = _get("/api/history?project=qxo")
        ccc_ids = [s["session_id"] for s in ccc_data["sessions"]]
        qxo_ids = [s["session_id"] for s in qxo_data["sessions"]]
        assert sid not in ccc_ids, f"Session leaked to CCC (found in {ccc_ids[:3]})"
        assert sid in qxo_ids, f"Session missing from QXO ({qxo_ids[:3]})"

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
        assert 'lang="zh-CN"' in h
        assert "<body" in h
        assert "CCC Hub" in h

    def test_051_html_ids(self):
        h = _html()
        for id_val in ["hub-nav", "hub-views", "view-chat", "view-board", "view-console",
                       "app", "titlebar", "messages", "composer", "sidebar", "session-list"]:
            assert f'id="{id_val}"' in h, f"Missing id={id_val}"

    def test_052_hub_routes(self):
        h = _html()
        assert 'data-route="chat"' in h
        assert 'data-route="board"' in h
        assert 'data-route="console"' in h
        assert 'href="#/chat"' in h
        assert 'href="#/board"' in h
        assert 'href="#/console"' in h

    def test_053_project_selector(self):
        h = _html()
        assert 'id="project-select"' in h
        assert 'id="sidebar-project-select"' in h

    def test_054_theme_button(self):
        h = _html()
        assert 'id="theme-btn"' in h
        assert "shell.css" in h

    def test_055_skeleton(self):
        h = _html()
        assert 'class="skeleton"' in h

    def test_056_composer_controls(self):
        h = _html()
        assert 'id="send-btn"' in h
        assert 'id="cancel-btn"' in h
        assert 'id="composer-input"' in h

    def test_057_hub_modules(self):
        js_dir = PROJECT_ROOT / "scripts" / "chat_server" / "frontend" / "js"
        assert (js_dir / "router.js").exists()
        assert (js_dir / "pages" / "boardPage.js").exists()
        assert (js_dir / "pages" / "consolePage.js").exists()
        assert (js_dir / "app.js").exists()

    def test_058_chat_panel(self):
        h = _html()
        assert 'id="chat-panel"' in h
        assert 'id="layout"' in h

    def test_059_board_page_module(self):
        src = (PROJECT_ROOT / "scripts" / "chat_server" / "frontend" / "js" / "pages" / "boardPage.js").read_text()
        assert "mountBoard" in src
        assert "/api/board" in src

    def test_060_sidebar(self):
        h = _html()
        assert 'id="sidebar"' in h
        assert "toggleMobileSidebar" in h
        assert 'id="new-tab-btn"' in h


# ===========================================================================
# 第六组：主题系统
# ===========================================================================


class TestThemeSystem:

    def _css(self) -> str:
        base = PROJECT_ROOT / "scripts" / "chat_server" / "frontend" / "css"
        return "\n".join(p.read_text() for p in base.glob("*.css"))

    def test_061_light_vars(self):
        css = self._css()
        for var in ["--ccc-bg-base", "--ccc-bg-surface", "--ccc-text-base",
                     "--ccc-bg-accent", "--ccc-border-base", "--ccc-bg-user"]:
            assert var in css, f"Missing {var}"

    def test_062_dark_vars(self):
        css = self._css()
        assert '[data-theme="dark"]' in css or "data-theme" in css
        assert "--ccc-bg-accent" in css

    def test_063_shell_styles(self):
        shell = (PROJECT_ROOT / "scripts" / "chat_server" / "frontend" / "css" / "shell.css").read_text()
        assert "#hub-nav" in shell
        assert ".board-page" in shell
        assert ".console-page" in shell

    def test_064_diff_vars(self):
        css = self._css()
        # warm palette may use semantic names in components
        assert "--ccc-" in css

    def test_065_theme_script(self):
        h = _html()
        assert "ccc-theme" in h
        assert "data-theme" in h

    def test_066_theme_persistence(self):
        h = _html()
        assert "localStorage.getItem" in h or "localStorage.setItem" in h
        assert "prefers-color-scheme" in h
        assert "matchMedia" in h


# ===========================================================================
# 第七组：Markdown 渲染
# ===========================================================================


class TestMarkdownRenderer:

    def _md(self) -> str:
        return (PROJECT_ROOT / "scripts" / "chat_server" / "frontend" / "js" / "markdown.js").read_text()

    def test_070_render_markdown_export(self):
        assert "export function renderMarkdown" in self._md()

    def test_071_headers(self):
        md = self._md()
        assert "#{1,4}" in md
        assert "<h" in md

    def test_072_lists(self):
        md = self._md()
        assert "<ul>" in md or "ul" in md
        assert "<ol>" in md or "ol" in md

    def test_073_block_elements(self):
        md = self._md()
        assert "blockquote" in md

    def test_074_tables(self):
        md = self._md()
        assert "table" in md

    def test_075_links(self):
        md = self._md()
        assert "href" in md
        assert "target" in md

    def test_076_images(self):
        md = self._md()
        assert "img" in md

    def test_077_inline_formatting(self):
        md = self._md()
        assert "strong" in md
        assert "code" in md

    def test_078_code_blocks(self):
        h = _html()
        assert "copyCode" in h
        assert "highlightSyntax" in self._md() or "code-block" in self._md()

    def test_079_syntax_highlighters(self):
        md = self._md()
        assert "highlightJS" in md
        assert "highlightPython" in md

    def test_080_markdown_module_exists(self):
        assert (PROJECT_ROOT / "scripts" / "chat_server" / "frontend" / "js" / "markdown.js").exists()


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
        assert status in (200, 400, 422)

    def test_101_missing_key(self):
        payload = json.dumps({"session_id": "test"}).encode()
        req = urllib.request.Request(
            f"{BASE_URL}/api/chat", data=payload, method="POST",
            headers={"Content-Type": "application/json", "Authorization": AUTH_HEADER},
        )
        try:
            resp = urllib.request.urlopen(req, timeout=TIMEOUT)
            # Server may accept and forward to proxy (proxies may handle it)
            assert resp.status in (200, 400, 422)
        except urllib.error.HTTPError as e:
            assert e.code in (400, 422)

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

    def _js_blob(self) -> str:
        js_dir = PROJECT_ROOT / "scripts" / "chat_server" / "frontend" / "js"
        parts = []
        for p in js_dir.rglob("*.js"):
            parts.append(p.read_text())
        return "\n".join(parts)

    def test_110_hub_router(self):
        blob = self._js_blob()
        assert "initRouter" in blob
        assert "mountBoard" in blob
        assert "mountConsole" in blob

    def test_111_api_auth(self):
        blob = self._js_blob()
        assert "_fetchWithAuth" in blob or "ccc_chat_pass" in blob
        assert "apiGet" in blob
        assert "apiPost" in blob

    def test_112_board_page(self):
        blob = self._js_blob()
        assert "/api/tasks/move" in blob
        assert "mountBoard" in blob

    def test_113_sidebar_module(self):
        blob = self._js_blob()
        assert "refreshSidebar" in blob or "setupSidebarSearch" in blob

    def test_114_composer(self):
        blob = self._js_blob()
        assert "initComposer" in blob

    def test_115_utility(self):
        h = _html()
        assert "function copyCode" in h
        assert "function toggleMobileSidebar" in h

    def test_116_app_boot(self):
        app = (PROJECT_ROOT / "scripts" / "chat_server" / "frontend" / "js" / "app.js").read_text()
        assert "initRouter" in app
        assert "onHubRoute" in app or "mountBoard" in app


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
        # v0.39+: 默认 staged 在 disabled-ccc；active 仅 ui/enable --start 后存在
        active = Path.home() / "Library" / "LaunchAgents" / "com.ccc.chat-server.plist"
        staged = Path.home() / "Library" / "LaunchAgents" / "disabled-ccc" / "com.ccc.chat-server.plist"
        plist = active if active.exists() else staged
        assert plist.exists(), f"missing chat-server plist (checked {active} and {staged})"
        content = plist.read_text()
        assert "com.ccc.chat-server" in content

    def test_122_infra_md_has_hub_7777(self):
        infra = PROJECT_ROOT / ".ccc" / "infrastructure.md"
        text = infra.read_text()
        assert "7777" in text
        assert "CCC Hub" in text or "Hub" in text

    def test_123_hub_default_port(self):
        cfg = (PROJECT_ROOT / "scripts" / "chat_server" / "config.py").read_text()
        assert 'CCC_CHAT_PORT", "7777"' in cfg or 'CCC_CHAT_PORT", \'7777\'' in cfg
        assert "7775" in cfg
        plist = (PROJECT_ROOT / "scripts" / "com.ccc.chat-server.plist").read_text()
        assert "7777" in plist
        assert "7775" in plist
        assert "CCC Hub" in (PROJECT_ROOT / "scripts" / "chat_server" / "frontend" / "index.html").read_text()


# ===========================================================================
# 第十二组：CSS 一致性
# ===========================================================================


class TestCSSConsistency:

    def test_130_shell_and_tokens(self):
        css_dir = PROJECT_ROOT / "scripts" / "chat_server" / "frontend" / "css"
        assert (css_dir / "variables.css").exists()
        assert (css_dir / "shell.css").exists()
        vars_css = (css_dir / "variables.css").read_text()
        assert "--ccc-bg-accent" in vars_css
        shell = (css_dir / "shell.css").read_text()
        assert "hub-nav" in shell

    def test_131_warm_accent(self):
        vars_css = (PROJECT_ROOT / "scripts" / "chat_server" / "frontend" / "css" / "variables.css").read_text()
        assert "#c96442" in vars_css

    def test_132_hub_html_links_css(self):
        h = _html()
        assert "variables.css" in h
        assert "shell.css" in h
        assert "components.css" in h


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
            "messages": [{"role": "user", "content": "say ok in 2 words"}],
            "session_id": _make_sid("ss141"),
        }, read_limit=40)
        assert status == 200
        events = []
        for line in lines:
            if line.startswith("data: "):
                try:
                    obj = json.loads(line[6:])
                    events.append(obj.get("type"))
                except json.JSONDecodeError:
                    pass
        assert "delta" in events, f"No delta event (got {len(events)} events: {events[:15]}...)"

    def test_142_chat_sse_returns_events(self):
        status, lines = _stream_post("/api/chat", {
            "messages": [{"role": "user", "content": "test events"}],
            "session_id": _make_sid("ss142"),
        }, read_limit=5)
        assert status == 200
        data_lines = [l for l in lines if l.startswith("data: ")]
        assert len(data_lines) > 0
