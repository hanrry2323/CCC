"""项目 Agent vs CCC 编排运维 Agent 隔离。"""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(SCRIPTS / "chat_server"))


def test_wrap_routes_ccc_to_ops_voice():
    from hub_voice import wrap_hub_prompt

    out = wrap_hub_prompt("清一下 qb 的 abnormal", project_id="ccc")
    assert "编排运维人格" in out
    assert "hub_repair" in out
    assert "业务项目卡" in out or "业务项目" in out


def test_wrap_business_uses_project_voice_handoff():
    from hub_voice import HUB_BOSS_VOICE, wrap_hub_prompt

    out = wrap_hub_prompt("板堵了怎么定稿", project_id="qb")
    assert "Desktop 对话人格" in out
    assert "板务交接" in out or "编排运维" in HUB_BOSS_VOICE
    assert "看板管家 · 本职 · 卡点必兜底" not in HUB_BOSS_VOICE
    assert "交接" in HUB_BOSS_VOICE


def test_ops_voice_forbids_business_epic_on_orch():
    from ops_voice import OPS_BOSS_VOICE

    assert "R-15" in OPS_BOSS_VOICE or "业务" in OPS_BOSS_VOICE
    assert "禁止" in OPS_BOSS_VOICE and "orch" in OPS_BOSS_VOICE.lower()
    assert "hub_repair" in OPS_BOSS_VOICE


def test_ccc_defaults_to_engineer():
    from chat_server import config

    assert config.resolve_tool_mode(None, project_id="ccc") == "engineer"
    assert config.resolve_tool_mode("", project_id="ccc") == "engineer"
    assert config.resolve_tool_mode("discuss", project_id="ccc") == "discuss"
    assert config.resolve_tool_mode("engineer", project_id="qb") == "discuss"
    assert config.resolve_tool_mode(None, project_id="qb") == "discuss"


def test_discuss_discipline_is_handoff_not_self_repair():
    from chat_server import config

    d = config.DISCUSS_TOOL_DISCIPLINE
    assert "交接" in d or "编排运维" in d
    assert "禁止" in d and "hub_repair" in d


def test_qb_golden_handoff_not_outbox():
    import json

    from hub_voice import reply_has_user_visible_bans

    good = (
        "编排板还堵着，不是产品方案问题。"
        "请打开左侧「编排运维」对话清板；清完再回来定稿。"
    )
    assert reply_has_user_visible_bans(good) == []
    assert "transfer-outbox" not in good

    fixture = Path(__file__).resolve().parent / "fixtures" / "qb_ops_handoff_goldens.jsonl"
    if fixture.is_file():
        for line in fixture.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            assert reply_has_user_visible_bans(row["good_reply"]) == []
