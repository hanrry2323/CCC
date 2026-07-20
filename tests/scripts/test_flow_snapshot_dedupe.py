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


def test_snapshot_failed_stage_from_abnormal_and_split():
    """Phase9：abnormal work 或 epic split_status=failed → user_stage=failed。"""
    board_abn = {
        "backlog": [
            {
                "id": "epic-f",
                "title": "Epic Fail",
                "card_kind": "epic",
                "split_status": "running",
                "child_ids": ["w-bad"],
            }
        ],
        "abnormal": [
            {
                "id": "w-bad",
                "title": "Bad Work",
                "parent_id": "epic-f",
                "executor": "opencode",
                "note": "hang",
            }
        ],
    }
    snap = snapshot_from_board(board_abn, epic_id="epic-f", project_id="hp")
    assert snap.get("user_stage") == "failed"
    assert "卡住" in (snap.get("headline") or "")
    assert snap["epic"]["user_stage"] == "failed"

    board_split = {
        "backlog": [
            {
                "id": "epic-s",
                "title": "Epic Split Failed",
                "card_kind": "epic",
                "split_status": "failed",
                "child_ids": [],
            }
        ],
    }
    snap2 = snapshot_from_board(board_split, epic_id="epic-s", project_id="hp")
    assert snap2.get("user_stage") == "failed"
    assert "止损" in (snap2.get("headline") or "")
