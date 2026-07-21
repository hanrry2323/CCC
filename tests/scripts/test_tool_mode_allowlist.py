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
    # 业务仓旁路收死
    assert config.resolve_tool_mode("engineer", project_id="ccc-demo") == "discuss"
    assert config.resolve_tool_mode("engineer", project_id="ccc") == "engineer"


def test_discuss_allowlist_excludes_writes():
    # 长文 + full：外网工具可用（全集）；Bash 只读探查可用
    tools = config.tools_for_mode(
        "discuss",
        user_text="请帮我完整梳理产品方案并说明取舍与里程碑风险，不要只回一句话。" * 4,
        prompt_mode="full",
    )
    assert "Read" in tools
    assert "Glob" in tools
    assert "Bash" in tools
    assert "WebFetch" in tools and "WebSearch" in tools
    for banned in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
        assert banned not in tools


def test_discuss_critical_flow_keeps_repo_tools():
    # 短标签主路径：不得零工具，须含 Bash；推迟外网
    for label in ("对齐基线", "下一步", "定稿", "扫风险", "转任务"):
        tools = config.tools_for_mode(
            "discuss", user_text=label, prompt_mode="light"
        )
        assert "Read" in tools, label
        assert "Bash" in tools, label
        assert "Write" not in tools, label
        assert "WebFetch" not in tools, label


def test_discuss_defers_web_on_light_short_turn():
    # 超短 light：零工具直答
    tools = config.tools_for_mode(
        "discuss", user_text="只回两个字：收到", prompt_mode="light"
    )
    assert tools == frozenset()
    # 中等 light（>40 字）：本地探查，无 Web*
    tools_mid = config.tools_for_mode(
        "discuss",
        user_text="用三到五句话说明这个产品现在处在什么阶段，主要用户是谁，以及你建议的下一步工作重点是什么",
        prompt_mode="light",
    )
    assert "Read" in tools_mid
    assert "Bash" in tools_mid
    assert "WebFetch" not in tools_mid
    # 显式要上网 → 不推迟
    tools_web = config.tools_for_mode(
        "discuss", user_text="请搜一下官网文档", prompt_mode="light"
    )
    assert "WebFetch" in tools_web


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
        user_text="请帮我完整梳理产品方案并说明取舍与里程碑风险，不要只回一句话。" * 4,
        prompt_mode="full",
    )
    allowed = set(captured.get("allowed_tools") or [])
    assert "Write" not in allowed
    assert "Read" in allowed


def test_build_options_preserves_empty_allowlist(monkeypatch):
    """空 frozenset 是合法的「零工具」，不得因 falsy 回退成全量。"""
    mgr = ClaudeSessionManager()
    monkeypatch.setattr(mgr, "_ensure_sdk", lambda: None)
    monkeypatch.setattr(config, "require_claude_bin", lambda: "/usr/bin/true")
    captured = {}

    class _Opts:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    import chat_server.services.claude_session as cs

    monkeypatch.setattr(cs, "ClaudeAgentOptions", _Opts)
    mgr._build_options(
        project_path="/tmp/demo",
        model="flash",
        resume_session_id=None,
        tool_mode="discuss",
        allowed_tools=frozenset(),
    )
    assert captured.get("allowed_tools") == []
    # SDK 空 allowlist = 不加 --allowedTools；必须靠 disallowed 真正禁工具
    deny = captured.get("disallowed_tools") or []
    assert "WebFetch" in deny and "Bash" in deny and "Read" in deny
