"""agent_mind — L1 观察脑编译 + 决策脑合并 + digest。"""

from __future__ import annotations

import json
from pathlib import Path

from chat_server.services import agent_mind


def _seed_board(ws: Path) -> None:
    board = ws / ".ccc" / "board"
    for col in ("backlog", "planned", "in_progress", "released"):
        (board / col).mkdir(parents=True, exist_ok=True)
    (board / "planned" / "epic-demo.jsonl").write_text(
        json.dumps(
            {
                "id": "epic-demo",
                "title": "Demo epic",
                "card_kind": "epic",
                "status": "planned",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    (board / "released" / "old-work.jsonl").write_text(
        json.dumps({"id": "old-work", "title": "Old", "status": "released"}) + "\n",
        encoding="utf-8",
    )
    reports = ws / ".ccc" / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "daily-review-2099-01-01.md").write_text(
        "# Daily\n\nHeadline: 清理完成\n", encoding="utf-8"
    )
    (reports / "weekly-2099-01-07.md").write_text(
        "# Weekly\n\n本周稳态\n", encoding="utf-8"
    )


def test_compile_observed_and_digest(tmp_path: Path):
    ws = tmp_path / "app"
    ws.mkdir()
    (ws / ".git").mkdir()
    _seed_board(ws)

    observed = agent_mind.compile_observed(ws, project_id="demo")
    assert observed["board_counts"]["planned"] >= 1
    assert observed["daily_review_headline"]
    assert "daily-review" in observed["daily_review_headline"]
    assert observed["weekly_review_headline"]
    assert (ws / ".ccc" / "agent-mind" / "observed.json").is_file()

    dig = agent_mind.build_digest(ws, project_id="demo", use_cache=False)
    assert dig["ok"]
    assert "项目心智 L1" in dig["digest"]
    assert "planned" in dig["digest"] or "看板" in dig["digest"]
    assert len(dig["digest"]) <= agent_mind.DIGEST_MAX_CHARS + 5


def test_merge_decided_and_forbidden(tmp_path: Path):
    ws = tmp_path / "app2"
    ws.mkdir()
    _seed_board(ws)

    out = agent_mind.merge_decided(
        ws,
        {"constraints": ["不做第二树"], "goals": ["先对齐"]},
        updated_by="desktop-agent",
    )
    assert out["constraints"] == ["不做第二树"]
    assert out["updated_by"] == "desktop-agent"

    dig = agent_mind.build_digest(ws, project_id="demo2", use_cache=False)
    assert "不做第二树" in dig["digest"]

    try:
        agent_mind.merge_decided(ws, {"constraints": ["请 enable Engine"]})
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "forbidden" in str(exc).lower() or "enable" in str(exc).lower()


def test_digest_cache(tmp_path: Path):
    ws = tmp_path / "app3"
    ws.mkdir()
    _seed_board(ws)
    agent_mind.clear_digest_cache()
    a = agent_mind.build_digest(ws, project_id="c", use_cache=True)
    b = agent_mind.build_digest(ws, project_id="c", use_cache=True)
    assert a["digest"] == b["digest"]
