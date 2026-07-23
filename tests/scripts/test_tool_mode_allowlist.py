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
