"""Transfer lessons (L1) for Agent epic-craft training."""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

from chat_server.services import agent_mind  # noqa: E402
from chat_server.services import project_brain  # noqa: E402
from chat_server.services.board_repair import (  # noqa: E402
    _optimize_hint_for,
    failure_pack,
)
from _board_store import FileBoardStore  # noqa: E402


def test_append_transfer_lesson_roundtrip(tmp_path: Path):
    mind = tmp_path / ".ccc" / "agent-mind"
    mind.mkdir(parents=True)
    agent_mind.append_transfer_lesson(
        tmp_path,
        epic_id="epic-a",
        bucket="hang",
        title_snip="过宽卡",
        hint="缩小到 1 phase",
        bad_pattern="Step1-6",
        good_fix="单卡单 phase",
        source="test",
    )
    d = agent_mind.load_decided(tmp_path)
    assert d["transfer_lessons"]
    assert d["transfer_lessons"][0]["bucket"] == "hang"
    text = agent_mind.format_digest(
        project_id="qb",
        observed={"as_of": "t", "board_counts": {}},
        decided=d,
    )
    assert "近期定卡教训" in text
    assert "hang" in text


def test_brain_includes_qb_playbook(tmp_path: Path):
    (tmp_path / "CLAUDE.md").write_text("# qb\n", encoding="utf-8")
    (tmp_path / ".ccc").mkdir()
    out = project_brain.compile_brain(tmp_path, project_id="qb")
    assert "定卡反模式" in out["brain"] or "hang" in out["brain"].lower()


def test_optimize_hint_and_failure_pack(tmp_path: Path):
    assert "hang" in _optimize_hint_for("hang").lower() or "phase" in _optimize_hint_for(
        "hang"
    ).lower()
    board = tmp_path / ".ccc" / "board"
    for col in ("abnormal", "backlog", "planned", "testing", "verified", "released"):
        (board / col).mkdir(parents=True)
    store = FileBoardStore(tmp_path)
    store.create_task(
        {
            "id": "epic-x-w1",
            "title": "fail work",
            "card_kind": "work",
            "parent_id": "epic-x",
            "note": "hang_detected: hang auto-restart 耗尽",
            "status": "abnormal",
        },
        column="abnormal",
    )
    pack = failure_pack(tmp_path, epic_id="epic-x")
    assert pack["ok"]
    rows = pack.get("exhausted") or []
    if rows:
        assert rows[0].get("optimize_hint")
        assert "optimize_hints" in pack
    d = agent_mind.load_decided(tmp_path)
    # failure_pack should have attempted lesson write
    assert isinstance(d.get("transfer_lessons"), list)
