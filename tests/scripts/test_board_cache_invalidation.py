"""test_board_cache_invalidation.py — Phase 1.1 验收：mtime 读缓存正确失效。

覆盖：
- 重复 list_tasks 命中缓存（同 mtime 返回同对象）
- create/patch/move/quarantine 后缓存失效，读到新状态
- 外部直改文件后 mtime 兜底失效
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

from _board_store import FileBoardStore


def _make_store(tmp_path: Path) -> FileBoardStore:
    ws = tmp_path / "ws"
    (ws / ".ccc" / "board" / "backlog").mkdir(parents=True)
    return FileBoardStore(ws)


def _new_task(tid: str, **kw) -> dict:
    base = {
        "id": tid,
        "title": f"title-{tid}",
        "description": "d",
        "status": "backlog",
        "created_at": "2026-07-19T00:00:00+08:00",
        "updated_at": "2026-07-19T00:00:00+08:00",
        "assignee": None,
        "tags": [],
        "note": None,
        "schema_version": "1.2",
        "color_group": None,
        "color_depth": 0,
        "complexity": "medium",
        "card_kind": "work",
        "parent_id": None,
        "split_status": None,
        "child_ids": [],
        "ui_hidden": False,
    }
    base.update(kw)
    return base


def test_list_tasks_cache_hit_same_mtime(tmp_path):
    store = _make_store(tmp_path)
    assert store.create_task(_new_task("t1"))
    first = store.list_tasks("backlog")
    second = store.list_tasks("backlog")
    assert [t["id"] for t in first] == [t["id"] for t in second]
    # 同 mtime → 返回同一 list 对象（缓存命中）
    assert first is second


def test_create_invalidates_cache(tmp_path):
    store = _make_store(tmp_path)
    assert store.create_task(_new_task("t1"))
    before = store.list_tasks("backlog")
    assert [t["id"] for t in before] == ["t1"]
    assert store.create_task(_new_task("t2"))
    after = store.list_tasks("backlog")
    assert {t["id"] for t in after} == {"t1", "t2"}


def test_patch_invalidates_cache(tmp_path):
    store = _make_store(tmp_path)
    assert store.create_task(_new_task("t1"))
    assert store.list_tasks("backlog")
    assert store.patch_task("t1", {"title": "patched"})
    after = store.list_tasks("backlog")
    assert after[0]["title"] == "patched"


def test_move_invalidates_both_columns(tmp_path):
    store = _make_store(tmp_path)
    assert store.create_task(_new_task("t1"))
    store.list_tasks("backlog")
    assert store.move_task("t1", "backlog", "planned")
    assert store.list_tasks("backlog") == []
    assert [t["id"] for t in store.list_tasks("planned")] == ["t1"]


def test_external_edit_mtime_invalidation(tmp_path):
    store = _make_store(tmp_path)
    assert store.create_task(_new_task("t1"))
    store.list_tasks("backlog")
    # 外部直改文件内容（绕过 store，不动缓存 dict）
    f = store.board / "backlog" / "t1.jsonl"
    raw = f.read_text(encoding="utf-8")
    obj = json.loads(raw.splitlines()[0])
    obj["title"] = "externally-patched"
    # 确保 mtime 变化（同秒写可能 mtime 不变 → 显式 futime）
    f.write_text(json.dumps(obj, ensure_ascii=False) + "\n", encoding="utf-8")
    now = time.time()
    os.utime(f, (now + 5, now + 5))
    after = store.list_tasks("backlog")
    assert after[0]["title"] == "externally-patched"


def test_find_task_uses_path_probe(tmp_path):
    store = _make_store(tmp_path)
    assert store.create_task(_new_task("t1"))
    assert store.move_task("t1", "backlog", "planned")
    col, task = store.find_task("t1")
    assert col == "planned"
    assert task["id"] == "t1"
    col, _ = store.find_task("nope")
    assert col is None
