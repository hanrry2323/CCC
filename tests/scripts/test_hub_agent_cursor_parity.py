"""hub_agent_tools + voice bans + qb golden reply shape."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(SCRIPTS / "chat_server"))


def test_user_visible_bans_catch_outbox_and_ab():
    from hub_voice import reply_has_user_visible_bans

    bad = (
        "请把这段贴到 Terminal.app：\n"
        "cat > \"$HOME/Library/Application Support/CCCDesktop/transfer-outbox.json\" <<EOF\n"
        "选 A：双策略  选 B：单跑\n"
    )
    hits = reply_has_user_visible_bans(bad)
    assert "transfer-outbox" in hits
    assert "cat >" in hits or "Terminal.app" in hits


def test_user_visible_bans_allow_inside_ccc_transfer():
    from hub_voice import reply_has_user_visible_bans

    good = (
        "异常已清。探针默认只跑套利主线，请点确认下达。\n"
        "```ccc-transfer\n"
        '{"executor_intent":"python","title":"VIP probe"}\n'
        "```\n"
    )
    assert reply_has_user_visible_bans(good) == []


def test_board_steward_locked_in_voice():
    from hub_voice import HUB_BOSS_VOICE

    assert "看板管家" in HUB_BOSS_VOICE
    assert "hub_repair" in HUB_BOSS_VOICE
    assert "clear_blockers" in HUB_BOSS_VOICE
    assert "请打开左侧编排运维" not in HUB_BOSS_VOICE
    assert "短人话请用户打开" not in HUB_BOSS_VOICE
    assert "transfer-outbox" in HUB_BOSS_VOICE  # as ban wording


def test_qb_golden_reply_shape():
    """qb 板堵+探针：好人话样本不得触碰禁止子串。"""
    from hub_voice import reply_has_user_visible_bans

    fixture = (
        Path(__file__).resolve().parent / "fixtures" / "qb_voice_goldens.jsonl"
    )
    assert fixture.is_file(), fixture
    rows = [
        json.loads(line)
        for line in fixture.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert rows
    for row in rows:
        reply = row["good_reply"]
        hits = reply_has_user_visible_bans(reply)
        assert hits == [], (row.get("id"), hits)
        assert "A/B" not in reply and "选 A" not in reply


def test_hub_repair_posts_board_repair():
    from chat_server.services import hub_agent_tools as hat

    captured: dict = {}

    def fake_request(method, url, *, body=None, timeout=20.0):
        captured["method"] = method
        captured["url"] = url
        captured["body"] = body
        return {"ok": True, "action": "clear_blockers", "archived": ["t1"]}

    with patch.object(hat, "_request", side_effect=fake_request):
        out = hat.hub_repair("qb", "clear_blockers")
    assert out["ok"] is True
    assert captured["method"] == "POST"
    assert captured["url"].endswith("/api/desktop/board-repair")
    assert captured["body"]["project_id"] == "qb"
    assert captured["body"]["action"] == "clear_blockers"


def test_hub_board_get():
    from chat_server.services import hub_agent_tools as hat

    with patch.object(
        hat,
        "_request",
        return_value={"ok": True, "counts": {"abnormal": 1}},
    ) as m:
        out = hat.hub_board("qb")
    assert out["counts"]["abnormal"] == 1
    assert m.call_args[0][0] == "GET"
    assert "/lens/qb/board" in m.call_args[0][1]


def test_mcp_server_config_shape():
    from chat_server.services.hub_agent_tools import mcp_server_config

    cfg = mcp_server_config(python_bin="/usr/bin/python3")
    assert cfg["type"] == "stdio"
    assert cfg["command"] == "/usr/bin/python3"
    assert cfg["args"][0].endswith("ccc-hub-agent-mcp.py")
    assert "CCC_HUB_URL" in cfg["env"]


def test_discuss_discipline_prefers_hub_tools():
    from chat_server import config

    d = config.DISCUSS_TOOL_DISCIPLINE
    assert "hub_board" in d
    assert "打开编排运维" not in d
    assert "transfer-outbox" in d or "Terminal" in d
    assert "一等" in d or "MCP" in d


def test_claude_session_injects_mcp_for_discuss(monkeypatch):
    from chat_server.services import claude_session as cs

    monkeypatch.setenv("CCC_HUB_MCP", "1")
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
    assert "mcp_servers" in opt.kwargs
    assert "ccc-hub" in opt.kwargs["mcp_servers"]
