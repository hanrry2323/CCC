"""Tests: failure buckets + repair_queue epic_optimize + failure_pack."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))


def test_classify_failure_buckets():
    from _failure_buckets import classify_failure_bucket, is_exhaust_reason

    assert classify_failure_bucket("hang_detected: hang auto-restart 耗尽（1 次）") == "hang"
    assert is_exhaust_reason("hang_detected: hang auto-restart 耗尽（1 次）")
    assert (
        classify_failure_bucket("short_path_fail_budget path=script_seed n=3: acceptance:acceptance_cmd_failed")
        == "acceptance_fail"
    )
    assert is_exhaust_reason("short_path_fail_budget path=script_seed n=3: acceptance:acceptance_cmd_failed")
    assert (
        classify_failure_bucket("phase graph unresolvable（epic 子卡，禁止 product regen）")
        == "phase_unresolvable"
    )
    assert classify_failure_bucket("reviewer_fail_loop_exhausted (3)") == "fail_loop_exhausted"
    assert not is_exhaust_reason("connection timeout retry later")


def test_optimize_sop_prompt_contains_buckets():
    from chat_server.services import repair_queue as rq

    p = rq.optimize_sop_prompt(
        project_id="qb",
        epic_id="epic-1",
        hint="hang_detected",
        buckets="hang,acceptance_fail",
    )
    assert "耗尽改大卡" in p
    assert "post-exhaust-epic-optimize-sop" in p
    assert "hang,acceptance_fail" in p
    assert "禁止只藏卡结束" in p


def test_enqueue_epic_optimize_dedupe(tmp_path, monkeypatch):
    from chat_server.services import repair_queue as rq

    q = tmp_path / "repair-queue.jsonl"
    monkeypatch.setenv("CCC_REPAIR_QUEUE", str(q))
    r1 = rq.enqueue_epic_optimize(
        project_id="qb",
        epic_id="e1",
        hint="hang_detected 耗尽",
        buckets="hang",
    )
    assert r1["ok"] and not r1.get("deduped")
    r2 = rq.enqueue_epic_optimize(
        project_id="qb",
        epic_id="e1",
        hint="hang again",
        buckets="hang",
    )
    assert r2.get("deduped") is True
    pending = rq.load_pending()
    assert len(pending) == 1
    assert pending[0].get("kind") == "epic_optimize"
    assert "耗尽改大卡" in (pending[0].get("prompt") or "")


def test_failure_pack_and_exhausted(ws_board):
    from _board_store import FileBoardStore
    from chat_server.services import board_repair as br

    ws = ws_board
    store = FileBoardStore(ws)
    assert store.create_task(
        {
            "id": "epic-f1",
            "title": "Failed epic",
            "card_kind": "epic",
            "split_status": "failed",
            "status": "backlog",
            "goal": "g",
            "acceptance": ["a"],
            "pipeline": "dev",
        },
        column="backlog",
    )
    assert store.create_task(
        {
            "id": "epic-f1-w1",
            "title": "[ABNORMAL] hang",
            "card_kind": "work",
            "status": "abnormal",
            "parent_id": "epic-f1",
            "note": "hang_detected: hang auto-restart 耗尽（1 次）— epic-f1-w1",
            "goal": "g",
            "acceptance": ["a"],
            "pipeline": "dev",
        },
        column="abnormal",
    )
    blockers = br.list_blockers(ws)
    assert blockers.get("exhausted_count", 0) >= 1
    assert any(x["id"] == "epic-f1-w1" for x in blockers.get("exhausted") or [])
    pack = br.failure_pack(ws, epic_id="epic-f1")
    assert pack["ok"] is True
    assert "hang" in (pack.get("buckets") or [])
    assert any(x["id"] == "epic-f1-w1" for x in pack.get("exhausted") or [])

    out = br.run_repair(
        action="failure_pack",
        workspace=ws,
        project_id="demo",
        epic_id="epic-f1",
    )
    assert out.get("ok") is True
    assert out.get("action") == "failure_pack"
    reflowed = out.get("intent_cards_reflowed") or []
    assert isinstance(reflowed, list)
    assert len(reflowed) >= 1
    from chat_server.services import agent_mind as am

    decided = am.load_decided(ws)
    planned = [
        g
        for g in (decided.get("goals") or [])
        if isinstance(g, dict) and g.get("status") == "planned"
    ]
    assert planned, "failure_pack should seed planned intent card"


@pytest.fixture()
def ws_board(tmp_path):
    root = tmp_path / "app"
    for col in (
        "backlog",
        "abnormal",
        "planned",
        "in_progress",
        "testing",
        "verified",
        "released",
    ):
        (root / ".ccc" / "board" / col).mkdir(parents=True)
    return root
