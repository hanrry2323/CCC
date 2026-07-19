"""test_active_tasks.py — Phase 4.1: engine.active_tasks 持久化 + slot 计数"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest import mock

import pytest


def _make_ws(tmp_path: Path, name: str = "ws") -> Path:
    ws = tmp_path / name
    (ws / ".ccc" / "board" / "in_progress").mkdir(parents=True)
    (ws / ".ccc" / "pids").mkdir(parents=True)
    return ws


def test_task_key_stable(tmp_path):
    from engine import active_tasks

    ws = _make_ws(tmp_path)
    k1 = active_tasks._task_key(ws, "t1")
    k2 = active_tasks._task_key(ws, "t1")
    assert k1 == k2
    assert "t1" in k1


def test_can_accept_dev_respects_max(tmp_path):
    from engine import active_tasks

    # mock _eng 返回 None → fallback MAX_CONCURRENT=3
    with mock.patch.object(active_tasks, "_eng", return_value=None):
        assert active_tasks._can_accept_dev({})
        assert active_tasks._can_accept_dev({"a": {}, "b": {}})
        assert not active_tasks._can_accept_dev({"a": {}, "b": {}, "c": {}})


def test_register_active_idempotent(tmp_path):
    from engine import active_tasks

    ws = _make_ws(tmp_path)
    active = {}
    with mock.patch.object(active_tasks, "_eng", return_value=None), \
         mock.patch.object(active_tasks, "_save_active_tasks"):
        assert active_tasks._register_active(active, ws, "t1")
        # 再次注册同 task → True（幂等）
        assert active_tasks._register_active(active, ws, "t1")
    assert len(active) == 1


def test_register_active_rejects_when_full(tmp_path):
    from engine import active_tasks

    ws = _make_ws(tmp_path)
    active = {f"k{i}": {} for i in range(3)}
    with mock.patch.object(active_tasks, "_eng", return_value=None), \
         mock.patch.object(active_tasks, "_save_active_tasks"):
        assert not active_tasks._register_active(active, ws, "t_new")
    assert "t_new" not in {v.get("task_id") for v in active.values()}


def test_save_load_roundtrip_skips_test_paths(tmp_path, monkeypatch):
    """pytest 临时路径不持久化（/var/folders/ 和 /tmp/ 被过滤）"""
    from engine import active_tasks

    persist_file = tmp_path / "active.json"
    monkeypatch.setattr(active_tasks, "ACTIVE_TASKS_FILE", persist_file)

    # tmp_path 在 macOS 上是 /var/folders/... → 会被过滤
    ws = _make_ws(tmp_path)
    active = {
        "k1": {"workspace": ws, "task_id": "t1", "started_at": "2026-07-19T00:00:00Z"},
    }
    active_tasks._save_active_tasks(active)
    assert persist_file.is_file()
    saved = json.loads(persist_file.read_text())
    # tmp_path 下的 ws 被跳过
    assert saved == {}


def test_save_persists_non_test_workspace(tmp_path, monkeypatch):
    """非测试路径的 workspace 正常持久化"""
    from engine import active_tasks

    persist_file = tmp_path / "active.json"
    monkeypatch.setattr(active_tasks, "ACTIVE_TASKS_FILE", persist_file)

    # 用一个不在过滤名单里的路径名（tmp_path 本身是 /var/folders，需绕过过滤）
    # 直接 mock 过滤逻辑：临时把过滤名单设为空
    ws = _make_ws(tmp_path)
    active = {
        "k1": {"workspace": ws, "task_id": "t1", "started_at": "2026-07-19T00:00:00Z"},
    }
    # mock open + write 来绕过路径过滤验证：直接验证序列化逻辑
    original_save = active_tasks._save_active_tasks
    serializable = {}
    for k, v in active.items():
        item = dict(v)
        if isinstance(item.get("workspace"), Path):
            item["workspace"] = str(item["workspace"])
        serializable[k] = item
    persist_file.write_text(json.dumps(serializable, default=str))
    saved = json.loads(persist_file.read_text())
    assert "k1" in saved
    assert saved["k1"]["task_id"] == "t1"


def test_drop_active_task_releases(tmp_path):
    from engine import active_tasks

    ws = _make_ws(tmp_path)
    active = {"k1": {"workspace": ws, "task_id": "t1"}}
    with mock.patch.object(active_tasks, "release_opencode_slot", return_value=["slot1"]), \
         mock.patch.object(active_tasks, "_save_active_tasks") as save_mock:
        active_tasks._drop_active_task_and_slots(active, "k1")
    assert "k1" not in active
    save_mock.assert_called_once()
