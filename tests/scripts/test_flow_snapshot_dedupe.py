"""Flow snapshot 对同 id 多列副本去重。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from chat_server.services.flow_events import snapshot_from_board  # noqa: E402


def test_snapshot_dedupes_work_by_farthest_column():
    board = {
        "backlog": [
            {
                "id": "epic-1",
                "title": "Epic",
                "card_kind": "epic",
                "split_status": "running",
                "child_ids": ["w1"],
            }
        ],
        "in_progress": [
            {
                "id": "w1",
                "title": "Work",
                "parent_id": "epic-1",
                "executor": "opencode",
            }
        ],
        "released": [
            {
                "id": "w1",
                "title": "Work",
                "parent_id": "epic-1",
                "executor": "opencode",
            }
        ],
    }
    snap = snapshot_from_board(board, epic_id="epic-1", project_id="ccc-demo")
    works = snap.get("works") or []
    assert len(works) == 1
    assert works[0]["id"] == "w1"
    assert works[0]["status"] == "released"
    assert snap.get("user_stage") == "done"
    assert snap.get("headline") == "已完成"
