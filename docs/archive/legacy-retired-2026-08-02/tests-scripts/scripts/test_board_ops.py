"""board_ops short path."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))


def test_board_ops_moves_and_filters(tmp_path: Path):
    from board.roles.board_ops import run_board_ops, should_use_board_ops
    from chat_server.services import hub_lens

    ws = tmp_path / "app"
    ws.mkdir()
    subprocess.run(["git", "init"], cwd=ws, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "t@t.com"], cwd=ws, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "config", "user.name", "t"], cwd=ws, check=True, capture_output=True
    )
    for col in ("backlog", "released", "in_progress", "planned"):
        (ws / ".ccc" / "board" / col).mkdir(parents=True)
    (ws / ".ccc" / "phases").mkdir(parents=True)
    (ws / ".ccc" / "plans").mkdir(parents=True)
    (ws / ".ccc" / "reports").mkdir(parents=True)

    zombie = {
        "id": "old-epic",
        "title": "old",
        "card_kind": "epic",
        "split_status": "done",
        "ui_hidden": True,
        "schema_version": "1.2",
        "status": "backlog",
    }
    (ws / ".ccc" / "board" / "backlog" / "old-epic.jsonl").write_text(
        json.dumps(zombie) + "\n"
    )
    tid = "hygiene-w1"
    task = {
        "id": tid,
        "title": "retire",
        "card_kind": "work",
        "executor": "python",
        "schema_version": "1.2",
        "complexity": "medium",
        "ui_hidden": False,
        "status": "in_progress",
    }
    (ws / ".ccc" / "board" / "in_progress" / f"{tid}.jsonl").write_text(
        json.dumps(task) + "\n"
    )
    (ws / ".ccc" / "phases" / f"{tid}.phases.json").write_text(
        '{"schema_version":"1.1"}\n'
        + json.dumps(
            {
                "phase": 1,
                "status": "pending",
                "description": "move",
                "scope": [
                    ".ccc/board/backlog/old-epic.jsonl",
                    ".ccc/board/released/old-epic.jsonl",
                    ".ccc/board/index.json",
                ],
                "subtasks": {"1.1": "pending"},
                "timeout": 600,
            }
        )
        + "\n"
    )
    (ws / ".ccc" / "plans" / f"{tid}.plan.md").write_text(
        "## 验收\n- backlog/old-epic.jsonl 归 released\n", encoding="utf-8"
    )
    assert should_use_board_ops(ws, task) is True
    r = run_board_ops(ws, tid)
    assert r["ok"] is True
    assert "old-epic" in r["moved"]
    assert (ws / ".ccc" / "board" / "released" / "old-epic.jsonl").is_file()
    assert not (ws / ".ccc" / "board" / "backlog" / "old-epic.jsonl").is_file()
    board = hub_lens.collect_board(ws, project_id="app")
    assert board["counts"]["backlog"] == 0
