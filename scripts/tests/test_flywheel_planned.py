"""Flywheel idle → materialize next L1 planned (no backlog)."""

from __future__ import annotations

import json
from pathlib import Path

from chat_server.services import agent_mind as am


def test_ensure_flywheel_planned_from_dev_plan(tmp_path: Path) -> None:
    root = tmp_path / "qb"
    (root / ".ccc" / "agent-mind").mkdir(parents=True)
    for col in ("backlog", "planned", "in_progress", "testing"):
        (root / ".ccc" / "board" / col).mkdir(parents=True)
    (root / "docs").mkdir(parents=True)
    (root / "docs" / "DEV_PLAN_v1.1.md").write_text(
        "# Plan\n\n## B4.2 实盘确认\n做实盘闸\n\n## B5 回测可视化\n做回测图\n",
        encoding="utf-8",
    )
    (root / "CLAUDE.md").write_text(
        "规划 SSOT = `docs/DEV_PLAN_v1.1.md`\n",
        encoding="utf-8",
    )
    (root / ".ccc" / "agent-mind" / "decided.json").write_text(
        json.dumps({"schema_version": "1.1", "goals": []}),
        encoding="utf-8",
    )

    card = am.ensure_flywheel_planned_intent(
        root, project_id="qb", pipeline_idle=True
    )
    assert card is not None
    assert str(card.get("status")) == "planned"
    assert "B4.2" in str(card.get("text") or "") or "实盘" in str(card.get("text") or "")

    # second call: already planned → no duplicate flood
    again = am.ensure_flywheel_planned_intent(
        root, project_id="qb", pipeline_idle=True
    )
    assert again is not None
    dec = am.load_decided(root)
    planned = [g for g in dec["goals"] if str(g.get("status")) == "planned"]
    assert len(planned) == 1


def test_ensure_flywheel_skips_when_busy(tmp_path: Path) -> None:
    root = tmp_path / "qb"
    (root / ".ccc" / "agent-mind").mkdir(parents=True)
    for col in ("backlog", "planned", "in_progress"):
        (root / ".ccc" / "board" / col).mkdir(parents=True)
    (root / ".ccc" / "board" / "in_progress" / "w1.jsonl").write_text(
        json.dumps({"id": "w1", "title": "busy", "card_kind": "work"}) + "\n",
        encoding="utf-8",
    )
    (root / ".ccc" / "agent-mind" / "decided.json").write_text(
        json.dumps({"goals": []}), encoding="utf-8"
    )
    assert (
        am.ensure_flywheel_planned_intent(root, project_id="qb", pipeline_idle=None)
        is None
    )
