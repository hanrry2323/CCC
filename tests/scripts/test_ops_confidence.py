"""Ops confidence pack — probe helpers (ready_to_dispatch, board counts)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))


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
    )
    assert green["severity"] == "green"
    assert green["alerts"] == []
    assert "可以放心" in green["human_line"]

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
    )
    assert amber["severity"] == "amber"
    assert amber["alerts"] == []
    assert amber["amber_notes"]

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
