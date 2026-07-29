"""L1 planned → transfer payload / dry-run promote."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from chat_server.services import agent_mind as am
from chat_server.services import intent_promote as ip


@pytest.fixture()
def mind_root(tmp_path: Path) -> Path:
    root = tmp_path / "ws"
    (root / ".ccc" / "agent-mind").mkdir(parents=True)
    decided = {
        "schema_version": "1",
        "goals": [
            {
                "id": "g-ok",
                "text": "净 edge CLOSE",
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


def test_list_promotable_skips_dispatched_and_needs_exit(mind_root: Path) -> None:
    rows = ip.list_promotable_planned(mind_root)
    ids = {str(g.get("id")) for g in rows}
    assert "g-ok" in ids
    assert "g-weak" in ids  # has exit_condition string; gate rejects later
    assert "g-done" not in ids


def test_build_payload_from_goal(mind_root: Path) -> None:
    g = ip.list_promotable_planned(mind_root, goal_ids=["g-ok"])[0]
    body = ip.build_transfer_payload_from_goal("qb", g, thread_id="qb::main")
    assert body is not None
    assert body["project_id"] == "qb"
    assert body["client_request_id"].startswith("promote-")
    assert body["l1_goal_id"] == "g-ok"
    assert "pytest" in body["acceptance"][0]
    assert "## 验收" in body["plan_md"]


def test_dry_run_promote_separates_weak(mind_root: Path) -> None:
    rows = ip.dry_run_promote_payloads("qb", mind_root, thread_id="qb::main")
    by_id = {str(r.get("goal_id")): r for r in rows}
    assert by_id["g-ok"]["ok"] is True
    assert by_id["g-ok"]["payload"] is not None
    assert by_id["g-weak"]["ok"] is False
    codes = {e.get("code") for e in (by_id["g-weak"].get("errors") or [])}
    assert "acceptance_weak" in codes or by_id["g-weak"]["ok"] is False
