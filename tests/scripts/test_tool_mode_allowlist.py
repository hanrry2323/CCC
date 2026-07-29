"""对话面 tool_mode：默认 engineer 全功能；显式 discuss 只读。"""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from chat_server import config  # noqa: E402


def test_resolve_tool_mode_default_engineer():
    assert config.resolve_tool_mode(None) == "engineer"
    assert config.resolve_tool_mode("") == "engineer"
    assert config.resolve_tool_mode("discuss") == "discuss"


def test_resolve_tool_mode_engineer_explicit_and_phrase():
    assert config.resolve_tool_mode("engineer") == "engineer"
    assert config.resolve_tool_mode(None, user_text="请开工程师模式改一下") == "engineer"
    assert config.resolve_tool_mode(None, user_text="直接改本机 README") == "engineer"
    assert config.resolve_tool_mode(None, user_text="帮我定稿转任务") == "engineer"
    # 业务仓不再强制打回 discuss
    assert config.resolve_tool_mode("engineer", project_id="ccc-demo") == "engineer"
    assert config.resolve_tool_mode("engineer", project_id="ccc") == "engineer"
    assert config.resolve_tool_mode(None, project_id="qb") == "engineer"


def test_engineer_allowlist_includes_writes():
    tools = config.tools_for_mode("engineer")
    assert "Write" in tools
    assert "Edit" in tools


def test_sdk_full_open_tools_engineer_only():
    assert config.sdk_full_open_tools("engineer") is True
    assert config.sdk_full_open_tools("discuss") is False
    assert config.sdk_full_open_tools("") is False


def test_claude_session_engineer_no_write_ban(monkeypatch):
    """engineer = Cursor 级全开：空 allowlist、不禁 Write。"""
    import chat_server.services.claude_session as cs

    monkeypatch.setenv("CCC_HUB_MCP", "0")
    mgr = cs.ClaudeSessionManager()

    class _Opt:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    monkeypatch.setattr(cs, "ClaudeAgentOptions", _Opt)
    monkeypatch.setattr(cs.config, "require_claude_bin", lambda: "/bin/true")
    monkeypatch.setattr(cs.config, "build_claude_env", lambda: {})
    monkeypatch.setattr(mgr, "_ensure_sdk", lambda: None)

    opt = mgr._build_options(
        project_path="/tmp",
        model="flash",
        resume_session_id=None,
        tool_mode="engineer",
    )
    assert opt.kwargs.get("allowed_tools") == []
    assert "disallowed_tools" not in opt.kwargs
    assert "Write" not in (opt.kwargs.get("disallowed_tools") or [])


def test_claude_session_discuss_bans_write(monkeypatch):
    import chat_server.services.claude_session as cs

    monkeypatch.setenv("CCC_HUB_MCP", "0")
    mgr = cs.ClaudeSessionManager()

    class _Opt:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    monkeypatch.setattr(cs, "ClaudeAgentOptions", _Opt)
    monkeypatch.setattr(cs.config, "require_claude_bin", lambda: "/bin/true")
    monkeypatch.setattr(cs.config, "build_claude_env", lambda: {})
    monkeypatch.setattr(mgr, "_ensure_sdk", lambda: None)

    opt = mgr._build_options(
        project_path="/tmp",
        model="flash",
        resume_session_id=None,
        tool_mode="discuss",
    )
    assert opt.kwargs.get("allowed_tools") == []
    assert "Write" in opt.kwargs.get("disallowed_tools", [])
