"""Desktop transfer gate + executor registry + flow snapshot."""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

from chat_server.services import transfer_gate  # noqa: E402
from chat_server.services import flow_events  # noqa: E402
from executors.registry import normalize_executor, run_executor  # noqa: E402
from _board_store import FileBoardStore  # noqa: E402
from _product_fanout import apply_fanout  # noqa: E402


def test_gate_rejects_incomplete():
    ok, errors = transfer_gate.validate_transfer_payload(
        {"title": "x", "project_id": "demo"}
    )
    assert not ok
    codes = {e["code"] for e in errors}
    assert "missing_goal" in codes
    assert "missing_acceptance" in codes
    assert "missing_pipeline" in codes


def test_gate_rejects_feasibility_blocked():
    ok, errors = transfer_gate.validate_transfer_payload(
        {
            "title": "加一行 README",
            "goal": "加标记",
            "acceptance": ["grep DEMO"],
            "pipeline": "dev",
            "feasibility": "blocked",
            "feasibility_reason": "范围不清",
            "project_id": "ccc-demo",
            "executor_intent": "opencode",
        }
    )
    assert not ok
    assert any(e["code"] == "feasibility_blocked" for e in errors)


def test_gate_accepts_complete():
    body = {
        "title": "加一行 README",
        "goal": "在 README 加 DEMO 标记",
        "acceptance": ["grep DEMO README.md"],
        "pipeline": "dev",
        "feasibility": "ok",
        "project_id": "ccc-demo",
        "executor_intent": "python",
        "plan_md": "# Plan\n\n## 目标\nx\n",
    }
    ok, errors = transfer_gate.validate_transfer_payload(body)
    assert ok, errors
    assert transfer_gate.resolve_executor_intent(body) == "python"
    desc = transfer_gate.build_epic_description(body)
    assert "Transfer Gate" in desc
    assert "python" in desc
    plan = transfer_gate.build_plan_md(body)
    assert "## 验收" in plan


def test_executor_python_stub(tmp_path):
    r = run_executor(
        {
            "executor": "python",
            "cwd": str(tmp_path),
            "work_id": "w1",
            "executor_spec": {},
        }
    )
    assert r.ok
    assert r.executor == "python"
    assert (tmp_path / ".ccc" / "executor-python.ok").is_file()


def test_normalize_auto():
    assert normalize_executor("auto", pipeline="python-script") == "python"
    assert normalize_executor("auto", pipeline="dev") == "opencode"


def test_fanout_writes_executor(tmp_path):
    store = FileBoardStore(tmp_path)
    assert store.create_task(
        {
            "id": "epic-x",
            "title": "Epic",
            "tags": ["exec:python"],
            "description": "big",
        },
        column="backlog",
    )
    epic = store.list_tasks("backlog")[0]
    child = {
        "id": "epic-x-w1",
        "title": "W1",
        "description": "d",
        "plan_md": "# t\n\n## 验收\n- x\n",
        "phases": [
            {
                "phase": 1,
                "status": "pending",
                "description": "d",
                "scope": ["a.py"],
                "subtasks": {"1.1": "pending"},
                "timeout": 60,
                "commit": None,
                "notes": "",
            }
        ],
        "executor": "python",
    }
    r = apply_fanout(store, epic, children_raw=[child])
    assert r["ok"]
    _, work = store.find_task("epic-x-w1")
    assert work["executor"] == "python"


def test_flow_snapshot_from_board():
    board = {
        "backlog": [
            {
                "id": "e1",
                "title": "E",
                "card_kind": "epic",
                "split_status": "planned",
                "description": "## 目标\n做一件事\n\n## 验收\n- x\n",
            }
        ],
        "planned": [
            {
                "id": "e1-w1",
                "title": "W",
                "parent_id": "e1",
                "executor": "opencode",
                "depends_on_tasks": [],
            }
        ],
    }
    snap = flow_events.snapshot_from_board(board, epic_id="e1", project_id="demo")
    assert snap["epic"]["id"] == "e1"
    assert snap["works"][0]["executor"] == "opencode"
    assert snap["works"][0]["user_status"] == "排队"
    assert snap["works"][0]["executor_label"] == "写码"
    assert "goal_summary" in snap["epic"]
    assert snap.get("headline")
