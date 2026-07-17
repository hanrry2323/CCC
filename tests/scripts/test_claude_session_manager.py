"""Unit tests for Hub continuous Claude session manager (mocked SDK)."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from chat_server.services import claude_session as mod
from chat_server.services.claude_session import ClaudeSessionManager


class _FakeText:
    def __init__(self, text: str):
        self.text = text


class _FakeAssistant:
    def __init__(self, text: str, session_id: str = "sid-1"):
        self.content = [_FakeText(text)]
        self.session_id = session_id


class _FakeResult:
    def __init__(self, session_id: str = "sid-1", result: str = "ok"):
        self.subtype = "success"
        self.duration_ms = 1
        self.duration_api_ms = 1
        self.is_error = False
        self.num_turns = 1
        self.session_id = session_id
        self.stop_reason = "end_turn"
        self.total_cost_usd = 0.0
        self.usage = {"input_tokens": 1, "output_tokens": 1}
        self.result = result
        self.structured_output = None
        self.model_usage = None
        self.permission_denials = None
        self.deferred_tool_use = None
        self.errors = None
        self.api_error_status = None
        self.uuid = None


class _FakeClient:
    instances: list["_FakeClient"] = []

    def __init__(self, options=None, transport=None):
        self.options = options
        self.connected = False
        self.queries: list[str] = []
        self._queue: asyncio.Queue = asyncio.Queue()
        _FakeClient.instances.append(self)

    async def connect(self, prompt=None):
        self.connected = True

    async def disconnect(self):
        self.connected = False

    async def query(self, prompt, session_id: str = "default"):
        self.queries.append(prompt)
        n = len(self.queries)
        await self._queue.put(_FakeAssistant(f"pong-{n}", session_id=f"sid-{n}"))
        await self._queue.put(_FakeResult(session_id=f"sid-{n}", result=f"pong-{n}"))
        await self._queue.put(None)

    async def interrupt(self):
        pass

    async def receive_response(self):
        while True:
            item = await self._queue.get()
            if item is None:
                return
            yield item


@pytest.fixture
def patched_sdk(monkeypatch):
    _FakeClient.instances.clear()
    monkeypatch.setattr(mod, "_SDK_IMPORT_ERROR", None)
    monkeypatch.setattr(mod, "ClaudeSDKClient", _FakeClient)
    monkeypatch.setattr(mod, "ClaudeAgentOptions", lambda **kw: SimpleNamespace(**kw))
    monkeypatch.setattr(mod, "AssistantMessage", _FakeAssistant)
    monkeypatch.setattr(mod, "ResultMessage", _FakeResult)
    monkeypatch.setattr(mod, "SystemMessage", type("Sys", (), {}))
    monkeypatch.setattr(mod, "UserMessage", type("Usr", (), {}))
    monkeypatch.setattr(mod, "TextBlock", _FakeText)
    monkeypatch.setattr(mod, "ToolUseBlock", type("TU", (), {}))
    monkeypatch.setattr(mod, "ToolResultBlock", type("TR", (), {}))
    monkeypatch.setattr(
        "chat_server.config.require_claude_bin",
        lambda: "/fake/claude",
    )
    yield


@pytest.mark.asyncio
async def test_two_turns_reuse_one_client(patched_sdk, tmp_path):
    mgr = ClaudeSessionManager(idle_ttl=3600, max_live=4)
    project = str(tmp_path)
    hub_sid = "hub-abc"

    events1 = []
    async for ev in mgr.stream_turn(
        "hello1", project, hub_sid, model="flash", idle_timeout=120, max_timeout=300
    ):
        events1.append(ev)
    assert any(e.get("type") == "delta" and "pong-1" in e.get("content", "") for e in events1)
    done1 = [e for e in events1 if e.get("type") == "done"][-1]
    assert done1.get("claude_session_id") == "sid-1"
    assert len(_FakeClient.instances) == 1

    events2 = []
    async for ev in mgr.stream_turn(
        "hello2",
        project,
        hub_sid,
        model="flash",
        resume_session_id="sid-1",
        idle_timeout=120,
        max_timeout=300,
    ):
        events2.append(ev)
    assert any(e.get("type") == "delta" and "pong-2" in e.get("content", "") for e in events2)
    assert len(_FakeClient.instances) == 1
    assert _FakeClient.instances[0].queries == ["hello1", "hello2"]
    assert _FakeClient.instances[0].connected is True

    await mgr.shutdown()


@pytest.mark.asyncio
async def test_cold_resume_creates_new_client(patched_sdk, tmp_path):
    mgr = ClaudeSessionManager(idle_ttl=3600, max_live=4)
    project = str(tmp_path)
    hub_sid = "hub-cold"

    async for _ in mgr.stream_turn(
        "a", project, hub_sid, model="flash", idle_timeout=60, max_timeout=120
    ):
        pass
    assert len(_FakeClient.instances) == 1

    key = mod._slot_key(project, hub_sid)
    await mgr._drop_slot(key, reason="test")
    assert len(mgr._slots) == 0

    events = []
    async for ev in mgr.stream_turn(
        "b",
        project,
        hub_sid,
        model="flash",
        resume_session_id="sid-1",
        idle_timeout=60,
        max_timeout=120,
    ):
        events.append(ev)
    assert len(_FakeClient.instances) == 2
    opts = _FakeClient.instances[1].options
    assert getattr(opts, "resume", None) == "sid-1"
    assert any(e.get("type") == "done" for e in events)

    await mgr.shutdown()
