"""对话面 tool_mode：discuss 恒全智力只读；engineer 全量可写。"""

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
    tools = config.tools_for_mode(
        "discuss",
        user_text="请帮我完整梳理产品方案并说明取舍与里程碑风险，不要只回一句话。" * 4,
        prompt_mode="full",
    )
    assert "Read" in tools
    assert "Glob" in tools
    assert "Bash" in tools
    assert "WebFetch" in tools and "WebSearch" in tools
    assert "Task" in tools or "Agent" in tools
    for banned in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
        assert banned not in tools


def test_discuss_always_full_tools_including_short_chat():
    """已取消 light 零工具：短闲聊仍有全集；永不含 Write。"""
    for label in (
        "对齐基线",
        "下一步",
        "定稿",
        "扫风险",
        "转任务",
        "方案",
        "先透镜 live",
        "只回两个字：收到",
    ):
        tools = config.tools_for_mode(
            "discuss", user_text=label, prompt_mode="light"
        )
        assert tools == config.CLAUDE_TOOL_ALLOWLIST_DISCUSS, label
        assert "Read" in tools and "Bash" in tools, label
        assert "WebFetch" in tools and "Task" in tools, label
        assert "Write" not in tools, label


def test_discuss_discipline_mentions_locate_and_risk_scan():
    d = config.DISCUSS_TOOL_DISCIPLINE
    assert "locate" in d
    assert "扫风险" in d
    assert "Write" in d or "硬禁" in d


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
        user_text="收到",
        prompt_mode="light",
    )
    # discuss 默认：空 allowlist = SDK 全开；只硬禁写
    assert captured.get("allowed_tools") == []
    deny = set(captured.get("disallowed_tools") or [])
    assert "Write" in deny and "Edit" in deny
    assert "Bash" not in deny and "Read" not in deny and "WebFetch" not in deny


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


def test_discuss_discipline_full_tools_except_write():
    d = config.DISCUSS_TOOL_DISCIPLINE
    assert "全开" in d or "MCP" in d
    assert "locate" in d
    assert "Write" in d or "硬禁" in d
    assert "ccc-hub-lens" in d


def test_hub_lens_auth_defaults_without_env(monkeypatch):
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[2] / "scripts" / "ccc-hub-lens.py"
    spec = importlib.util.spec_from_file_location("ccc_hub_lens", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.delenv("CCC_HUB_AUTH", raising=False)
    monkeypatch.delenv("CCC_CHAT_USER", raising=False)
    monkeypatch.delenv("CCC_CHAT_PASS", raising=False)
    assert mod.resolve_hub_basic_auth() == "ccc:ccc"
    headers = mod._auth_header()
    assert headers.get("Authorization", "").startswith("Basic ")


def test_resolve_prompt_mode_always_full():
    from chat_server.hub_voice import resolve_prompt_mode, wrap_hub_prompt

    assert resolve_prompt_mode("hi", requested="light") == "full"
    assert resolve_prompt_mode("定稿", requested=None) == "full"
    wrapped = wrap_hub_prompt("先透镜 live 看一下", mode="light")
    assert "【Desktop 对话人格 · 老板模式" in wrapped
    assert "【用户请求】" in wrapped
    assert "先透镜 live 看一下" in wrapped
    assert "完整人格" not in wrapped
