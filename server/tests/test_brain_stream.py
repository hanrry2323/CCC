"""test_brain_stream — 大脑流式输出 + 心智 prompt 测试（T41）。

覆盖：
1. prompt 心智升级：四段职责（规划/写任务卡/验收/看板维护）+ 工具契约 + 输出规范
2. _normalize_stream_event：meta / thinking / tool_use / text / tool_result /
   result(done) / stream_event(delta) / 未知跳过
3. _stream_claude：成功流（fake Popen）逐事件产出
4. stream_brain_events：未配置 503 / 忙 503 / 成功流 / 锁释放
"""

from __future__ import annotations

import pytest

from server.web import brain as brain_mod
from server.web.brain import _normalize_stream_event, stream_brain_events

_BRAIN_ENV_KEYS = (
    "CCC_BRAIN_MODEL",
    "CCC_BRAIN_BASE_URL",
    "CCC_BRAIN_AUTH_TOKEN",
    "CCC_BRAIN_TIMEOUT",
    "CCC_BRAIN_CLAUDE_BIN",
    "CCC_BRAIN_THINKING",
)


def _norm(ev):
    """归一化并断言非 None（测试输入均为合法事件行）。"""
    result = _normalize_stream_event(ev)
    assert result is not None, f"event not normalized: {ev!r}"
    return result


def _configure_brain(monkeypatch) -> None:
    monkeypatch.setenv("CCC_BRAIN_MODEL", "flash")
    monkeypatch.setenv("CCC_BRAIN_BASE_URL", "http://127.0.0.1:6100")
    monkeypatch.setenv("CCC_BRAIN_AUTH_TOKEN", "ccc-relay-flash")


# ════════════════════════════════════════════════════════════
# 1. prompt 心智升级
# ════════════════════════════════════════════════════════════


class TestBrainPrompt:
    """T41 心智：BRAIN_SYSTEM_PROMPT 为「全能智能体」四段职责 + 工具契约 + 输出规范。"""

    def test_prompt_has_four_roles(self):
        p = brain_mod.BRAIN_SYSTEM_PROMPT
        assert "大脑 Agent" in p  # 兼容既有断言
        for section in (
            "【职责一：规划】",
            "【职责二：写任务卡】",
            "【职责三：验收】",
            "【职责四：看板维护】",
            "【工具契约】",
            "【输出规范】",
        ):
            assert section in p, f"缺失 {section}"

    def test_prompt_writing_card_details(self):
        p = brain_mod.BRAIN_SYSTEM_PROMPT
        # 任务卡路径 + 防撞号
        assert "docs/dispatch/" in p
        assert "撞号" in p
        # 状态机五态
        assert "待分派 → 执行中 → 已回写 → 已关闭" in p
        # 验收判据
        assert "打回并附问题清单" in p
        # 引用契约文档
        assert "board-task-schema" in p
        assert "red-lines" in p

    def test_prompt_tool_contract(self):
        p = brain_mod.BRAIN_SYSTEM_PROMPT
        # 知识库优先 + 条目 id 标注
        assert "知识库" in p
        assert "BM25" in p
        assert "id" in p
        # 内置工具 + MCP
        assert "Read" in p
        assert "Bash" in p
        assert "WebFetch" in p
        assert "MCP" in p

    def test_prompt_output_spec(self):
        p = brain_mod.BRAIN_SYSTEM_PROMPT
        assert "结论先行" in p
        assert "不甩" in p or "不给" in p
        assert "选择题" in p


# ════════════════════════════════════════════════════════════
# 2. 事件归一化
# ════════════════════════════════════════════════════════════


class TestNormalizeStreamEvent:
    """claude stream-json 单行事件 → 归一化 (event, payload)。"""

    def test_system_init_meta(self):
        ev = {
            "type": "system",
            "subtype": "init",
            "model": "flash",
            "tools": ["Read", "Bash"],
            "mcp_servers": [{"name": "memory", "status": "connected"}],
            "skills": ["verify"],
        }
        name, payload = _norm(ev)
        assert name == "meta"
        assert payload["model"] == "flash"
        assert payload["tools"] == ["Read", "Bash"]
        assert payload["mcp_servers"][0]["name"] == "memory"
        assert payload["skills"] == ["verify"]

    def test_assistant_thinking(self):
        ev = {
            "type": "assistant",
            "message": {"content": [{"type": "redacted_thinking", "data": "先规划"}]},
        }
        name, payload = _norm(ev)
        assert name == "thinking"
        assert payload["data"] == "先规划"

    def test_assistant_tool_use(self):
        ev = {
            "type": "assistant",
            "message": {
                "content": [
                    {"type": "tool_use", "id": "call_1", "name": "Read", "input": {"file_path": "/x"}},
                ]
            },
        }
        name, payload = _norm(ev)
        assert name == "tool_use"
        assert payload["id"] == "call_1"
        assert payload["name"] == "Read"
        assert payload["input"] == {"file_path": "/x"}

    def test_assistant_text(self):
        ev = {
            "type": "assistant",
            "message": {"content": [{"type": "text", "text": "你好"}]},
        }
        name, payload = _norm(ev)
        assert name == "text"
        assert payload["text"] == "你好"

    def test_assistant_multiple_text_blocks_no_loss(self):
        """C8：assistant.message.content 含多个 text 块不得丢字——需完整拼接顺序输出。"""
        ev = {
            "type": "assistant",
            "message": {
                "content": [
                    {"type": "text", "text": "第一段。"},
                    {"type": "text", "text": "第二段。"},
                    {"type": "text", "text": "第三段。"},
                ]
            },
        }
        name, payload = _norm(ev)
        assert name == "text"
        # 三段文本按原序完整拼接：不丢字、不重复
        assert payload["text"] == "第一段。第二段。第三段。"

    def test_assistant_text_blocks_interleaved_not_lost(self):
        """C8：text 块与 tool_use / thinking 穿插时，text 内容不得被吞。"""
        ev = {
            "type": "assistant",
            "message": {
                "content": [
                    {"type": "text", "text": "开头。"},
                    {"type": "thinking", "data": "不该出现在 text 事件"},
                    {"type": "tool_use", "id": "tu9", "name": "Read", "input": {}},
                    {"type": "text", "text": "结尾。"},
                ]
            },
        }
        name, payload = _norm(ev)
        # 本事件应产出 text；thinking/tool_use 由后续事件/分块负责，text 事件只含文本
        assert name == "text"
        assert payload["text"] == "开头。结尾。"

    def test_user_tool_result_str(self):
        ev = {
            "type": "user",
            "message": {
                "content": [
                    {"type": "tool_result", "tool_use_id": "call_1", "content": "ok"},
                ]
            },
        }
        name, payload = _norm(ev)
        assert name == "tool_result"
        assert payload["tool_use_id"] == "call_1"
        assert payload["content"] == "ok"

    def test_user_tool_result_list(self):
        ev = {
            "type": "user",
            "message": {
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "call_2",
                        "content": [{"type": "text", "text": "a"}, {"type": "text", "text": "b"}],
                    },
                ]
            },
        }
        name, payload = _norm(ev)
        assert payload["content"] == "a b"

    def test_result_done_success(self):
        ev = {"type": "result", "is_error": False, "result": "最终答复"}
        name, payload = _norm(ev)
        assert name == "done"
        assert payload["is_error"] is False
        assert payload["text"] == "最终答复"

    def test_result_done_error(self):
        ev = {"type": "result", "is_error": True, "api_error_status": "rate limit"}
        name, payload = _norm(ev)
        assert name == "done"
        assert payload["is_error"] is True
        assert payload["error"] == "rate limit"

    def test_stream_event_text_delta(self):
        ev = {
            "type": "stream_event",
            "event": {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "片段"}},
        }
        name, payload = _norm(ev)
        assert name == "text"
        assert payload["text"] == "片段"

    def test_unknown_skipped(self):
        assert _normalize_stream_event({"type": "system", "subtype": "status"}) is None
        assert _normalize_stream_event({"type": "garbage"}) is None
        assert _normalize_stream_event({}) is None


# ════════════════════════════════════════════════════════════
# 3. _stream_claude 成功流（fake Popen）
# ════════════════════════════════════════════════════════════


class _FakeProc:
    """模拟 Popen：stdout 为行迭代器，kill/wait 无副作用。"""

    def __init__(self, lines):
        self._lines = list(lines)
        self.stdout = iter(self._lines)
        self.stderr = None
        self._rc = 0
        self.killed = False
        self.pid = 424242  # 供 _terminate_proc / killpg 路径安全读取

    def poll(self):
        return self._rc if self.killed else None

    def wait(self, timeout=None):
        return self._rc

    def kill(self):
        self.killed = True


_SAMPLE_STREAM_LINES = [
    '{"type":"system","subtype":"init","model":"flash","tools":["Read"],'
    '"mcp_servers":[{"name":"memory","status":"connected"}],"skills":[]}',
    '{"type":"assistant","message":{"content":[{"type":"text","text":"你好"}]}}',
    '{"type":"result","is_error":false,"result":"你好"}',
]


class TestStreamClaude:
    """_stream_claude 经 fake Popen 逐事件产出归一化序列。"""

    def test_success_flow(self, monkeypatch):
        _configure_brain(monkeypatch)

        def _fake_popen(*args, **kwargs):
            return _FakeProc(_SAMPLE_STREAM_LINES)

        monkeypatch.setattr("server.web.brain.subprocess.Popen", _fake_popen)
        events = list(brain_mod._stream_claude("hi"))
        names = [e[0] for e in events]
        assert names == ["meta", "text", "done"]
        assert events[1][1]["text"] == "你好"
        assert events[2][1]["is_error"] is False

    def test_spawn_failure_error_502(self, monkeypatch):
        _configure_brain(monkeypatch)
        monkeypatch.setenv("CCC_BRAIN_BASE_URL", "http://127.0.0.1:23456")

        def _boom(*args, **kwargs):
            raise OSError("no such file")

        monkeypatch.setattr("server.web.brain.subprocess.Popen", _boom)
        events = list(brain_mod._stream_claude("hi"))
        assert events[0][0] == "error"
        assert events[0][1]["status"] == 502

    def test_thinking_flag_default_enabled(self, monkeypatch):
        """T46 B5：CCC_BRAIN_THINKING 缺省 enabled → CLI 带 --thinking enabled。"""
        _configure_brain(monkeypatch)
        monkeypatch.delenv("CCC_BRAIN_THINKING", raising=False)
        captured = {}

        def _fake_popen(*args, **kwargs):
            captured["popen_args"] = kwargs.get("args", args[0] if args else None)
            return _FakeProc(_SAMPLE_STREAM_LINES)

        monkeypatch.setattr("server.web.brain.subprocess.Popen", _fake_popen)
        list(brain_mod._stream_claude("hi"))
        assert captured.get("popen_args") == [
            "claude", "-p", "hi", "--output-format", "stream-json", "--verbose",
            "--thinking", "enabled", "-y",
        ]

    def test_thinking_flag_disabled_via_env(self, monkeypatch):
        """CCC_BRAIN_THINKING="" → 不传 --thinking（模型/中继不支持时可静态关闭）。"""
        _configure_brain(monkeypatch)
        monkeypatch.setenv("CCC_BRAIN_THINKING", "")
        captured = {}

        def _fake_popen(*args, **kwargs):
            captured["popen_args"] = kwargs.get("args", args[0] if args else None)
            return _FakeProc(_SAMPLE_STREAM_LINES)

        monkeypatch.setattr("server.web.brain.subprocess.Popen", _fake_popen)
        list(brain_mod._stream_claude("hi"))
        assert captured["popen_args"] == [
            "claude", "-p", "hi", "--output-format", "stream-json", "--verbose", "-y",
        ]


# ════════════════════════════════════════════════════════════
# 4. stream_brain_events 错误路径 + 锁
# ════════════════════════════════════════════════════════════


class TestStreamBrainEvents:
    """stream_brain_events 入口契约：503 未配置/忙、成功流、锁释放。"""

    @pytest.fixture(autouse=True)
    def _clean_env(self, monkeypatch):
        for k in _BRAIN_ENV_KEYS:
            monkeypatch.delenv(k, raising=False)
        yield

    def test_not_configured_yields_error_503(self):
        events = list(stream_brain_events("hi", []))
        assert len(events) == 1
        name, payload = events[0]
        assert name == "error"
        assert payload["status"] == 503
        assert "not configured" in payload["message"]
        # 未配置不持有锁
        assert not brain_mod._brain_lock.locked()

    def test_busy_yields_error_503(self, monkeypatch):
        _configure_brain(monkeypatch)
        acquired = brain_mod._brain_lock.acquire(blocking=False)
        assert acquired
        try:
            events = list(stream_brain_events("hi", []))
        finally:
            brain_mod._brain_lock.release()
        assert len(events) == 1
        assert events[0][0] == "error"
        assert events[0][1]["status"] == 503
        assert "busy" in events[0][1]["message"]

    def test_success_flow_releases_lock(self, monkeypatch):
        _configure_brain(monkeypatch)

        def _fake_stream(prompt):
            yield ("meta", {"model": "flash"})
            yield ("text", {"text": "你好"})
            yield ("done", {"is_error": False, "text": "你好"})

        monkeypatch.setattr("server.web.brain._stream_claude", _fake_stream)
        events = list(stream_brain_events("hi", []))
        names = [e[0] for e in events]
        assert names == ["meta", "text", "done"]
        assert not brain_mod._brain_lock.locked()

    def test_generator_close_releases_lock(self, monkeypatch):
        """客户端提前断开：generator 未消费完关闭时锁必须释放。"""
        _configure_brain(monkeypatch)

        def _fake_stream(prompt):
            yield ("meta", {"model": "flash"})
            yield ("text", {"text": "半截"})

        monkeypatch.setattr("server.web.brain._stream_claude", _fake_stream)
        gen = stream_brain_events("hi", [])
        next(gen)  # 消费 meta（此时锁已持有）
        assert brain_mod._brain_lock.locked()
        gen.close()
        assert not brain_mod._brain_lock.locked()
