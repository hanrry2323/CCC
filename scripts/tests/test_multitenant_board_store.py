"""Multi-workspace board.store must follow get_workspace()."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))


def test_common_list_tasks_uses_active_workspace(tmp_path):
    from board.context import set_workspace
    from board.roles import common

    a = tmp_path / "alpha"
    b = tmp_path / "beta"
    for root, tid in ((a, "task-a"), (b, "task-b")):
        (root / ".ccc" / "board" / "backlog").mkdir(parents=True)
        (root / ".ccc" / "board" / "backlog" / f"{tid}.jsonl").write_text(
            json.dumps(
                {
                    "id": tid,
                    "title": tid,
                    "card_kind": "epic",
                    "split_status": "pending",
                    "schema_version": "1.2",
                }
            )
            + "\n"
        )

    common._reset_lazy()
    set_workspace(a)
    ids_a = [t["id"] for t in common.list_tasks("backlog")]
    assert ids_a == ["task-a"]

    common._reset_lazy()
    set_workspace(b)
    ids_b = [t["id"] for t in common.list_tasks("backlog")]
    assert ids_b == ["task-b"]


def test_refresh_epic_keeps_failed_without_kids(tmp_path):
    from _board_store import FileBoardStore
    from _product_fanout import refresh_epic_lifecycle

    root = tmp_path / "ws"
    (root / ".ccc" / "board" / "backlog").mkdir(parents=True)
    store = FileBoardStore(root)
    store.create_task(
        {
            "id": "epic-x",
            "title": "x",
            "card_kind": "epic",
            "split_status": "failed",
            "child_ids": [],
        },
        column="backlog",
    )
    assert refresh_epic_lifecycle(store, "epic-x") == "failed"
    col, t = store.find_task("epic-x")
    assert col == "backlog"
    assert t.get("split_status") == "failed"


def test_fanout_from_seeded_epic(tmp_path):
    from _board_store import FileBoardStore
    from _product_fanout import fanout_from_seeded_epic

    root = tmp_path / "ws"
    for col in ("backlog", "planned"):
        (root / ".ccc" / "board" / col).mkdir(parents=True)
    (root / ".ccc" / "plans").mkdir(parents=True)
    (root / ".ccc" / "phases").mkdir(parents=True)
    store = FileBoardStore(root)
    epic_id = "task-seed"
    store.create_task(
        {
            "id": epic_id,
            "title": "seeded",
            "description": "d",
            "card_kind": "epic",
            "split_status": "pending",
            "child_ids": [],
        },
        column="backlog",
    )
    plan = (
        "# Plan\n\n## 目标\n- do x\n\n"
        "## Phase 1: cleanup\n"
        "clean dirt\n\n## 验收\n- `echo ok` 输出 ok\n\n"
        "## Phase 2: feature\n"
        "build crawler\n\n## 验收\n- `test -f README.md` 成功\n"
    )
    (root / ".ccc" / "plans" / f"{epic_id}.plan.md").write_text(plan)
    phases = (
        json.dumps({"schema_version": "1.1"})
        + "\n"
        + json.dumps(
            {
                "phase": 1,
                "status": "pending",
                "description": "提交脏树 + 删 util",
                "scope": ["README.md"],
                "subtasks": {"1.1": "touch"},
                "timeout": 60,
                "depends_on": [],
            }
        )
        + "\n"
        + json.dumps(
            {
                "phase": 2,
                "status": "pending",
                "description": "实现省级药采爬虫",
                "scope": ["src/crawlers/"],
                "subtasks": {"2.1": "impl"},
                "timeout": 120,
                "depends_on": [1],
            }
        )
        + "\n"
    )
    (root / ".ccc" / "phases" / f"{epic_id}.phases.json").write_text(phases)
    r = fanout_from_seeded_epic(store, store.list_tasks("backlog")[0])
    assert r.get("ok"), r
    kids = r.get("child_ids") or []
    assert kids == ["task-seed-w1", "task-seed-w2"], kids
    _, epic = store.find_task(epic_id)
    assert epic.get("split_status") == "planned"
    assert store.find_task("task-seed-w1")[0] == "planned"
    assert store.find_task("task-seed-w2")[0] == "planned"
    w2 = store.find_task("task-seed-w2")[1]
    assert w2.get("depends_on_tasks") == ["task-seed-w1"]
    # each work has single phase renumbered to 1
    import json as _json
    from pathlib import Path as _P

    p2 = (_P(root) / ".ccc" / "phases" / "task-seed-w2.phases.json").read_text()
    phs = [
        _json.loads(l)
        for l in p2.splitlines()
        if l.strip().startswith("{") and '"phase"' in l
    ]
    assert len(phs) == 1 and phs[0]["phase"] == 1
    assert phs[0].get("depends_on") == []
