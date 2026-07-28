"""Ops confidence pack — probe helpers (ready_to_dispatch, board counts)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

# Stub MCP so envelope tests don't hit live opencode/cursor configs
_MCP_OK = {
    "ok": True,
    "mcp_probed": True,
    "servers": [{"name": "stub", "ok": True, "type": "local"}],
    "list": ["stub"],
    "failed": [],
    "note": "test stub ok",
}
_MCP_NONE = {
    "ok": None,
    "mcp_probed": True,
    "servers": [],
    "list": [],
    "failed": [],
    "note": "未配置 MCP（非红）",
}


def test_ready_to_dispatch_blockers():
    from _ops_probe import ready_to_dispatch

    r = ready_to_dispatch(
        control={
            "mode": "enabled",
            "engine_running": True,
            "hub_port_7777": True,
            "invent_hard_disabled": True,
        },
        risks={"high": 0},
        workspaces=[{"workspace": "demo", "abnormal": 0}],
        resources_history={"summary": {"verdict": "headroom"}},
    )
    assert r["ok"] is True
    assert r["blockers"] == []

    bad = ready_to_dispatch(
        control={
            "mode": "ui",
            "engine_running": False,
            "hub_port_7777": False,
            "invent_hard_disabled": True,
        },
        risks={"high": 2},
        workspaces=[{"workspace": "demo", "abnormal": 1}],
        resources_history={"summary": {"verdict": "saturated"}},
    )
    assert bad["ok"] is False
    assert len(bad["blockers"]) >= 4


def test_ops_health_envelope_green_amber_red():
    from _ops_probe import ops_health_envelope

    green = ops_health_envelope(
        control={
            "mode": "enabled",
            "engine_running": True,
            "hub_port_7777": True,
            "invent_hard_disabled": True,
        },
        risks={"high": 0, "risks": []},
        ready={"ok": True, "reason": "可下达", "blockers": []},
        logistics={"needs_attention": False},
        resources_history={"summary": {"verdict": "headroom"}},
        ports={"ports": {"7777": {"ok": True}, "7775": {"ok": True}}},
        overview={"down_ports": [], "alert_count": 0},
        agent_mcp=_MCP_OK,
    )
    assert green["severity"] == "green"
    assert green["alerts"] == []
    assert "可以放心" in green["human_line"]
    assert green["domains"]["agent_mcp"]["mcp_probed"] is True
    assert green["domains"]["cluster"]["ports"][0]["ok"] is True

    amber = ops_health_envelope(
        control={
            "mode": "enabled",
            "engine_running": True,
            "hub_port_7777": True,
            "invent_hard_disabled": True,
        },
        risks={
            "high": 0,
            "risks": [
                {
                    "id": "dirty-x",
                    "severity": "medium",
                    "source": "git",
                    "title": "脏树偏大",
                    "detail": "可稍后处理",
                }
            ],
        },
        ready={"ok": True, "blockers": []},
        logistics={"needs_attention": False},
        resources_history={"summary": {"verdict": "headroom"}},
        ports={"ports": {"7777": {"ok": True}, "7775": {"ok": True}}},
        overview={"down_ports": []},
        agent_mcp=_MCP_NONE,
    )
    assert amber["severity"] == "amber"
    assert amber["alerts"] == []
    assert amber["amber_notes"]
    assert amber["domains"]["agent_mcp"]["ok"] is None

    red = ops_health_envelope(
        control={
            "mode": "ui",
            "engine_running": False,
            "hub_port_7777": False,
            "invent_hard_disabled": True,
        },
        risks={
            "high": 1,
            "risks": [
                {
                    "id": "engine-down",
                    "severity": "high",
                    "source": "engine",
                    "title": "Engine 未运行",
                    "detail": "启动 Engine",
                }
            ],
        },
        ready={
            "ok": False,
            "reason": "暂缓",
            "blockers": ["Engine 未运行", "运维红灯 1"],
        },
        logistics={"needs_attention": True},
        resources_history={"summary": {"verdict": "saturated", "note": "满载"}},
        ports={"ports": {"7777": {"ok": False, "error": "refused"}, "7775": {"ok": True}}},
        overview={"down_ports": []},
        agent_mcp=_MCP_OK,
    )
    assert red["severity"] == "red"
    assert len(red["alerts"]) >= 1
    for a in red["alerts"]:
        assert a["severity"] == "red"
        assert "【CCC 运维红灯】" in a["copy_payload"]
        assert a.get("id")
    ids = {a["id"] for a in red["alerts"]}
    assert "engine-down" in ids
    assert "capacity-saturated" in ids or any("saturated" in i for i in ids)


def test_ops_health_envelope_alive_maps_to_ok():
    """P0 schema: ports may only have alive; envelope maps to domains.cluster.ports[].ok."""
    from _ops_probe import ops_health_envelope

    env = ops_health_envelope(
        control={
            "mode": "enabled",
            "engine_running": True,
            "hub_port_7777": True,
            "invent_hard_disabled": True,
        },
        risks={"high": 0, "risks": []},
        ready={"ok": True, "blockers": []},
        logistics={"needs_attention": False},
        resources_history={"summary": {"verdict": "headroom"}},
        ports={
            "ports": {
                "7777": {"alive": True, "host": "127.0.0.1"},
                "7775": {"alive": False, "host": "127.0.0.1", "label": "未响应"},
            }
        },
        overview={"down_ports": [], "alert_count": 0},
        agent_mcp=_MCP_OK,
    )
    by_port = {p["port"]: p["ok"] for p in env["domains"]["cluster"]["ports"]}
    assert by_port[7777] is True
    assert by_port[7775] is False
    assert env["severity"] == "red"
    assert any(a["id"] == "port-7775" for a in env["alerts"])


def test_ops_health_envelope_feiniu_down_is_amber_not_red():
    """非 CCC 控制面宕口（feiniu Money Printer）不得拉总红。"""
    from _ops_probe import ops_health_envelope

    env = ops_health_envelope(
        control={
            "mode": "enabled",
            "engine_running": True,
            "hub_port_7777": True,
            "invent_hard_disabled": True,
        },
        risks={"high": 0, "risks": []},
        ready={"ok": True, "blockers": []},
        logistics={"needs_attention": False},
        resources_history={"summary": {"verdict": "headroom"}},
        ports={"ports": {"7777": {"ok": True}, "7775": {"ok": True}}},
        overview={
            "down_ports": [
                {
                    "port": 18080,
                    "name": "Money Printer Turbo",
                    "host": "192.168.3.131",
                    "machine": "feiniu",
                    "alive": False,
                }
            ],
            "alert_count": 1,
        },
        agent_mcp={
            "ok": None,
            "mcp_probed": True,
            "servers": [],
            "list": [],
            "failed": [],
            "note": "未配置 MCP（非红）",
        },
    )
    assert env["severity"] == "amber"
    assert env["alerts"] == []
    assert env["domains"]["cluster"]["engine_running"] is True
    assert env["domains"]["cluster"]["down_ports_n"] == 0
    assert any("18080" in n or "非CCC" in n for n in (env.get("amber_notes") or []))

    from _ops_probe import ops_health_envelope

    bad_mcp = {
        "ok": False,
        "mcp_probed": True,
        "servers": [
            {
                "name": "hp-kb",
                "ok": False,
                "type": "remote",
                "detail": "TCP refused",
            }
        ],
        "list": ["hp-kb"],
        "failed": ["hp-kb"],
        "note": "1/1 个 MCP 探测失败",
    }
    env = ops_health_envelope(
        control={
            "mode": "enabled",
            "engine_running": True,
            "hub_port_7777": True,
            "invent_hard_disabled": True,
        },
        risks={"high": 0, "risks": []},
        ready={"ok": True, "blockers": []},
        logistics={"needs_attention": False},
        resources_history={"summary": {"verdict": "headroom"}},
        ports={"ports": {"7777": {"ok": True}, "7775": {"ok": True}}},
        overview={"down_ports": []},
        agent_mcp=bad_mcp,
    )
    assert env["severity"] == "red"
    assert env["domains"]["agent_mcp"]["mcp_probed"] is True
    assert env["domains"]["agent_mcp"]["ok"] is False
    mcp_alerts = [a for a in env["alerts"] if a["id"] == "mcp-probe-failed"]
    assert len(mcp_alerts) == 1
    assert "【CCC 运维红灯】" in mcp_alerts[0]["copy_payload"]
    assert "hp-kb" in mcp_alerts[0]["copy_payload"]


def test_ops_health_envelope_mcp_unconfigured_not_red():
    from _ops_probe import ops_health_envelope

    env = ops_health_envelope(
        control={
            "mode": "enabled",
            "engine_running": True,
            "hub_port_7777": True,
            "invent_hard_disabled": True,
        },
        risks={"high": 0, "risks": []},
        ready={"ok": True, "blockers": []},
        logistics={"needs_attention": False},
        resources_history={"summary": {"verdict": "headroom"}},
        ports={"ports": {"7777": {"ok": True}, "7775": {"ok": True}}},
        overview={"down_ports": []},
        agent_mcp=_MCP_NONE,
    )
    assert env["severity"] == "green"
    assert env["alerts"] == []
    assert env["domains"]["agent_mcp"]["ok"] is None


def test_probe_agent_mcp_unconfigured_and_fail(monkeypatch):
    from _ops_probe import probe_agent_mcp
    import _ops_probe as op

    empty = probe_agent_mcp(entries=[])
    assert empty["mcp_probed"] is True
    assert empty["ok"] is None
    assert empty["servers"] == []

    monkeypatch.setattr(
        op,
        "_probe_mcp_url",
        lambda url, timeout=1.5: (False, "refused"),
    )
    bad = probe_agent_mcp(
        entries=[
            {
                "name": "dead-remote",
                "source": "test",
                "type": "remote",
                "url": "http://127.0.0.1:9/mcp",
                "enabled": True,
            }
        ]
    )
    assert bad["mcp_probed"] is True
    assert bad["ok"] is False
    assert "dead-remote" in bad["failed"]
    assert bad["list"] == ["dead-remote"]


def test_workspace_summaries_board_counts(tmp_path: Path):
    from _ops_probe import workspace_summaries

    ws = tmp_path / "demo"
    board = ws / ".ccc" / "board"
    for col in ("planned", "in_progress", "testing", "abnormal", "backlog"):
        (board / col).mkdir(parents=True)
    (board / "planned" / "w1.jsonl").write_text(
        json.dumps({"id": "w1", "card_kind": "work", "title": "a"}) + "\n",
        encoding="utf-8",
    )
    (board / "abnormal" / "w2.jsonl").write_text(
        json.dumps({"id": "w2", "card_kind": "work", "title": "b", "note": "hang"})
        + "\n",
        encoding="utf-8",
    )
    (board / "backlog" / "e-done.jsonl").write_text(
        json.dumps(
            {
                "id": "e-done",
                "card_kind": "epic",
                "split_status": "done",
                "title": "done epic",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    # git init so dirty/branch probes don't explode
    import subprocess

    subprocess.run(["git", "init"], cwd=ws, check=True, capture_output=True)
    rows = workspace_summaries({"demo": str(ws)})
    assert len(rows) == 1
    row = rows[0]
    assert row["workspace"] == "demo"
    assert row["planned"] == 1
    assert row["abnormal"] == 1
    assert row["backlog"] == 0  # done epic filtered
