"""L1 planned → transfer payload / dry-run promote."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from chat_server.services import intent_promote as ip


@pytest.fixture()
def mind_root(tmp_path: Path) -> Path:
    root = tmp_path / "ws"
    (root / ".ccc" / "agent-mind").mkdir(parents=True)
    for col in ("backlog", "planned", "in_progress"):
        (root / ".ccc" / "board" / col).mkdir(parents=True)
    decided = {
        "schema_version": "1",
        "goals": [
            {
                "id": "g-ok",
                "text": "抽 src/utils/cost.py 共享 round_trip_cost",
                "title": "净 edge CLOSE",
                "status": "planned",
                "exit_condition": (
                    ".venv/bin/python -m pytest -q tests/unit/test_momentum_fees.py"
                ),
            },
            {
                "id": "g-weak",
                "text": "stamp only",
                "status": "planned",
                "exit_condition": "test -f README.md",
            },
            {
                "id": "g-prose",
                "text": "VIP paper later",
                "status": "planned",
                "exit_condition": "探针脚本 exit0 + 报告落盘 docs/reports/",
            },
            {
                "id": "g-done",
                "text": "already dispatched",
                "status": "dispatched",
                "exit_condition": (
                    ".venv/bin/python -m pytest -q tests/unit/test_x.py"
                ),
            },
        ],
    }
    (root / ".ccc" / "agent-mind" / "decided.json").write_text(
        json.dumps(decided), encoding="utf-8"
    )
    return root


def test_list_promotable_skips_dispatched(mind_root: Path) -> None:
    rows = ip.list_promotable_planned(mind_root)
    ids = {str(g.get("id")) for g in rows}
    assert "g-ok" in ids
    assert "g-weak" in ids
    assert "g-done" not in ids


def test_build_payload_from_goal_extracts_scope(mind_root: Path) -> None:
    g = ip.list_promotable_planned(mind_root, goal_ids=["g-ok"])[0]
    body = ip.build_transfer_payload_from_goal("qb", g, thread_id="qb::main")
    assert body is not None
    assert "src/utils/cost.py" in body["plan_md"]
    assert body["client_request_id"].startswith("promote-")
    assert not ip._is_thin_boilerplate_plan(body["plan_md"])


def test_dry_run_rejects_weak_and_prose(mind_root: Path) -> None:
    rows = ip.dry_run_promote_payloads("qb", mind_root, thread_id="qb::main")
    by_id = {str(r.get("goal_id")): r for r in rows}
    assert by_id["g-ok"]["ok"] is True
    assert by_id["g-ok"]["payload"] is not None
    assert by_id["g-weak"]["ok"] is False
    assert by_id["g-prose"]["ok"] is False


def test_dry_run_idempotent_inflight(mind_root: Path) -> None:
    # write raw jsonl with l1_goal_id (FileBoardStore may strip unknown keys)
    p = mind_root / ".ccc" / "board" / "backlog" / "epic-cost.jsonl"
    p.write_text(
        json.dumps(
            {
                "id": "epic-cost",
                "title": "净 edge CLOSE",
                "l1_goal_id": "g-ok",
                "card_kind": "epic",
                "status": "backlog",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    rows = ip.dry_run_promote_payloads(
        "qb", mind_root, thread_id="qb::main", goal_ids=["g-ok"]
    )
    assert len(rows) == 1
    assert rows[0].get("idempotent") is True
    assert rows[0].get("epic_id") == "epic-cost"
    assert rows[0].get("payload") is None
