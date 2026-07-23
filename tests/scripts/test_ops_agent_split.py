"""App Agent 全功能（1A/2A）：默认 engineer + 板务本职。"""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(SCRIPTS / "chat_server"))


def test_wrap_unified_voice_has_board_steward():
    from chat_server.hub_voice import wrap_hub_prompt

    out = wrap_hub_prompt("清一下 qb 的 abnormal", project_id="qb")
    assert "看板管家" in out
    assert "hub_repair" in out
    assert "clear_blockers" in out
    assert "请打开左侧编排运维" not in out
    assert "短人话请用户打开" not in out


def test_wrap_ccc_uses_same_hub_voice_not_ops_split():
    from chat_server.hub_voice import HUB_BOSS_VOICE, wrap_hub_prompt

    out = wrap_hub_prompt("清板", project_id="ccc")
    assert "Desktop 对话人格" in out or "看板管家" in out
    assert "编排运维人格" not in out
    assert "看板管家" in HUB_BOSS_VOICE
    assert "clear_blockers" in HUB_BOSS_VOICE


def test_default_engineer_all_projects():
    from chat_server import config

    assert config.resolve_tool_mode(None, project_id="ccc") == "engineer"
    assert config.resolve_tool_mode(None, project_id="qb") == "engineer"
    assert config.resolve_tool_mode("", project_id="qb") == "engineer"
    assert config.resolve_tool_mode("discuss", project_id="qb") == "discuss"
    assert config.resolve_tool_mode("engineer", project_id="qb") == "engineer"
    assert config.resolve_tool_mode(None, user_text="帮我定稿转任务") == "engineer"


def test_discuss_discipline_allows_status_not_handoff():
    from chat_server.config import DISCUSS_TOOL_DISCIPLINE as d

    assert "打开编排运维" not in d
    assert "hub_repair" in d or "工程师模式" in d


def test_golden_handoff_ban_not_in_voice():
    from hub_voice import HUB_BOSS_VOICE, reply_has_user_visible_bans

    assert "请打开左侧编排运维" not in HUB_BOSS_VOICE
    assert "板务交接" not in HUB_BOSS_VOICE or "看板管家" in HUB_BOSS_VOICE
    bad = "请把这段贴到 Terminal.app：\ncat > transfer-outbox.json"
    assert reply_has_user_visible_bans(bad)
