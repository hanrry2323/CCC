"""Stage A: epic/work schema + store guards."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _board_store import (  # noqa: E402
    FileBoardStore,
    fill_task_defaults,
    normalize_task_view,
    validate_task_jsonl,
)


def _ts():
    return "2026-07-17T12:00:00+08:00"


def test_fill_defaults_backlog_is_epic():
    d = fill_task_defaults(
        {
            "id": "e1",
            "title": "Epic",
            "status": "backlog",
            "created_at": _ts(),
            "updated_at": _ts(),
        },
        column="backlog",
    )
    assert d["card_kind"] == "epic"
    assert d["split_status"] == "pending"
    assert d["ui_hidden"] is False


def test_fill_defaults_planned_is_work():
    d = fill_task_defaults(
        {
            "id": "w1",
            "title": "Work",
            "status": "planned",
            "created_at": _ts(),
            "updated_at": _ts(),
        },
        column="planned",
    )
    assert d["card_kind"] == "work"


def test_epic_cannot_validate_outside_backlog():
    ok, errs = validate_task_jsonl(
        {
            "id": "e1",
            "title": "E",
            "status": "planned",
            "created_at": _ts(),
            "updated_at": _ts(),
            "card_kind": "epic",
            "split_status": "pending",
        }
    )
    assert not ok
    assert any("epic" in e for e in errs)


def test_create_epic_and_reject_move(tmp_path):
    store = FileBoardStore(tmp_path)
    assert store.create_task(
        {"id": "big-epic", "title": "Big", "description": "do things"},
        column="backlog",
    )
    tasks = store.list_tasks("backlog")
    assert len(tasks) == 1
    assert tasks[0]["card_kind"] == "epic"
    assert store.move_task("big-epic", "backlog", "planned") is False
    assert (tmp_path / ".ccc/board/backlog/big-epic.jsonl").is_file()
    assert not (tmp_path / ".ccc/board/planned/big-epic.jsonl").exists()


def test_create_work_child_in_planned(tmp_path):
    store = FileBoardStore(tmp_path)
    assert store.create_task(
        {"id": "parent-e", "title": "Parent"}, column="backlog"
    )
    assert store.create_task(
        {
            "id": "parent-e-w1",
            "title": "Child",
            "card_kind": "work",
            "parent_id": "parent-e",
            "color_group": "A",
            "color_depth": 1,
        },
        column="planned",
    )
    kids = store.list_tasks("planned")
    assert len(kids) == 1
    assert kids[0]["parent_id"] == "parent-e"


def test_backlog_sort_done_sinks(tmp_path):
    store = FileBoardStore(tmp_path)
    store.create_task({"id": "old-done", "title": "Done"}, column="backlog")
    store.patch_task(
        "old-done",
        {"split_status": "done", "color_group": "A", "updated_at": "2026-07-01T00:00:00+08:00"},
    )
    store.create_task({"id": "new-pending", "title": "New"}, column="backlog")
    ids = [t["id"] for t in store.list_tasks("backlog")]
    assert ids[0] == "new-pending"
    assert ids[-1] == "old-done"


def test_ui_hidden_filtered(tmp_path):
    store = FileBoardStore(tmp_path)
    store.create_task({"id": "vis", "title": "V"}, column="backlog")
    store.create_task({"id": "hid", "title": "H"}, column="backlog")
    store.patch_task("hid", {"ui_hidden": True, "split_status": "done"})
    assert [t["id"] for t in store.list_tasks("backlog")] == ["vis"]
    assert len(store.list_tasks("backlog", include_hidden=True)) == 2


def test_patch_epic_fields(tmp_path):
    store = FileBoardStore(tmp_path)
    store.create_task({"id": "e", "title": "E"}, column="backlog")
    assert store.patch_task(
        "e",
        {
            "split_status": "active",
            "color_group": "B",
            "child_ids": ["e-1", "e-2"],
        },
    )
    _, t = store.find_task("e")
    # 写盘时 fill_task_defaults 将 active → running
    assert t["split_status"] == "running"
    assert t["child_ids"] == ["e-1", "e-2"]
    assert t["color_group"] == "B"
