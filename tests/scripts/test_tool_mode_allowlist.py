"""对话面 tool_mode：discuss 无写工具；engineer 全量。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from chat_server import config  # noqa: E402
from chat_server.services.claude_session import ClaudeSessionManager  # noqa: E402


def test_resolve_tool_mode_default_discuss():
    assert config.resolve_tool_mode(None) == "discuss"
    assert config.resolve_tool_mode("") == "discuss"
    assert config.resolve_tool_mode("discuss") == "discuss"


def test_resolve_tool_mode_engineer_explicit_and_phrase():
    assert config.resolve_tool_mode("engineer") == "engineer"
    assert config.resolve_tool_mode(None, user_text="请开工程师模式改一下") == "engineer"
    assert config.resolve_tool_mode(None, user_text="直接改本机 README") == "engineer"
    assert config.resolve_tool_mode(None, user_text="帮我定稿转任务") == "discuss"


def test_discuss_allowlist_excludes_writes():
    tools = config.tools_for_mode("discuss")
    assert "Read" in tools
    assert "Glob" in tools
    for banned in ("Write", "Edit", "MultiEdit", "NotebookEdit", "Bash"):
        assert banned not in tools


def test_engineer_allowlist_includes_writes():
    tools = config.tools_for_mode("engineer")
    assert "Write" in tools and "Edit" in tools and "Bash" in tools


def test_build_options_uses_discuss_tools(monkeypatch):
    mgr = ClaudeSessionManager()
    monkeypatch.setattr(mgr, "_ensure_sdk", lambda: None)
    monkeypatch.setattr(config, "require_claude_bin", lambda: "/usr/bin/true")

    captured = {}

    class _Opts:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setitem(sys.modules, "chat_server.services.claude_session", sys.modules[
        "chat_server.services.claude_session"
    ])
    import chat_server.services.claude_session as cs

    monkeypatch.setattr(cs, "ClaudeAgentOptions", _Opts)
    mgr._build_options(
        project_path="/tmp/demo",
        model="flash",
        resume_session_id=None,
        tool_mode="discuss",
    )
    allowed = set(captured.get("allowed_tools") or [])
    assert "Write" not in allowed
    assert "Read" in allowed
