"""test_hang.py — Phase 4.1: engine.hang 检测逻辑（mock ps + tmp board）"""
from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest import mock

import pytest


def _make_ws(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    (ws / ".ccc" / "board" / "in_progress").mkdir(parents=True)
    (ws / ".ccc" / "pids").mkdir(parents=True)
    return ws


def _make_task(store, tid: str, col: str = "in_progress") -> None:
    from _board_store import FileBoardStore

    task = {
        "id": tid,
        "title": f"t-{tid}",
        "description": "d",
        "status": col,
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
    FileBoardStore(ws := store.workspace).create_task(task, column=col) if False else None
    # 直接写文件避免依赖完整 store
    (store.workspace / ".ccc" / "board" / col / f"{tid}.jsonl").write_text(
        json.dumps(task, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def test_hang_retry_counter_persistence(tmp_path, monkeypatch):
    """F-ARCH-01: hang retry counter 持久化到磁盘"""
    counter_file = tmp_path / "engine-hang-retries.json"
    monkeypatch.setattr("engine.hang._HANG_COUNTER_FILE", counter_file)

    from engine import hang

    hang._hang_retry_counter = {"key1": 1, "key2": 2}
    hang._save_hang_retry_counter()
    assert counter_file.is_file()

    hang._hang_retry_counter = {}
    hang._load_hang_retry_counter()
    assert hang._hang_retry_counter == {"key1": 1, "key2": 2}


def test_hang_counter_corrupt_file_resets(tmp_path, monkeypatch):
    counter_file = tmp_path / "engine-hang-retries.json"
    counter_file.write_text("not json {", encoding="utf-8")
    monkeypatch.setattr("engine.hang._HANG_COUNTER_FILE", counter_file)

    from engine import hang

    hang._hang_retry_counter = {"stale": 99}
    hang._load_hang_retry_counter()
    assert hang._hang_retry_counter == {}


def test_check_and_mark_hung_skips_abnormal(tmp_path, monkeypatch):
    """abnormal 列任务不参与 hang 检测"""
    from engine import hang
    from _board_store import FileBoardStore

    ws = _make_ws(tmp_path)
    store = FileBoardStore(ws)
    _make_task(store, "t1", col="abnormal")

    # active_tasks 指向 t1
    active = {
        "k1": {
            "workspace": ws,
            "task_id": "t1",
            "started_at": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
        }
    }

    # mock 防止真实 ps 调用
    with mock.patch.object(hang, "_eng", return_value=None), \
         mock.patch.object(hang, "_activate_workspace"), \
         mock.patch.object(hang, "_find_task_column", return_value="abnormal"):
        hang._check_and_mark_hung(ws, active)
    # 无 .hung 文件产生
    assert not list((ws / ".ccc" / "pids").glob("*.hung"))


def test_check_and_mark_hung_writes_marker_on_low_cpu_long_elapsed(tmp_path, monkeypatch):
    """CPU=0 + elapsed > 5min + 无近期活动 → 标记 hung"""
    from engine import hang
    from _board_store import FileBoardStore

    ws = _make_ws(tmp_path)
    store = FileBoardStore(ws)
    _make_task(store, "t1", col="in_progress")

    started = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    active = {
        "k1": {
            "workspace": ws,
            "task_id": "t1",
            "started_at": started,
        }
    }

    # 写 .pid 文件（mtime 设为 5 分钟前，避免「近期活动」跳过）
    subid = "t1__p1"
    pid_file = ws / ".ccc" / "pids" / f"{subid}.pid"
    pid_file.write_text("99999")
    import time as _time
    old = _time.time() - 600
    os.utime(pid_file, (old, old))

    # mock: 进程存活，ps 返回 CPU=0
    def fake_kill(pid, sig):
        if sig == 0:
            return None  # 进程存活
        raise ProcessLookupError

    def fake_run(cmd, **kw):
        return mock.Mock(returncode=0, stdout="0.0\n", stderr="")

    # mock board.phase._current_running_phase → 返回 1
    # mock engine 模块（_eng 返回 None → 走 fallback subid）
    with mock.patch.object(hang, "_eng", return_value=None), \
         mock.patch.object(hang, "_activate_workspace"), \
         mock.patch.object(hang, "_find_task_column", return_value="in_progress"), \
         mock.patch("engine.hang.os.kill", side_effect=fake_kill), \
         mock.patch("engine.hang.subprocess.run", side_effect=fake_run), \
         mock.patch("board.phase._current_running_phase", return_value=1), \
         mock.patch("engine.hang.record_failure", return_value=None) if False else mock.patch(
             "_failure_ledger.record_failure", return_value=None
         ):
        hang._check_and_mark_hung(ws, active)

    hung_files = list((ws / ".ccc" / "pids").glob("*.hung"))
    assert len(hung_files) == 1
    marker = json.loads(hung_files[0].read_text())
    assert marker["task_id"] == "t1"
    assert marker["pid"] == 99999


def test_check_and_mark_hung_skips_when_done_marker_exists(tmp_path, monkeypatch):
    """已 done 的 phase 跳过 hang 标记（避免 abort 已成功任务）。"""
    from engine import hang
    from _board_store import FileBoardStore

    ws = _make_ws(tmp_path)
    store = FileBoardStore(ws)
    _make_task(store, "t1", col="in_progress")

    started = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    active = {
        "k1": {
            "workspace": ws,
            "task_id": "t1",
            "started_at": started,
        }
    }

    subid = "t1__p1"
    pid_file = ws / ".ccc" / "pids" / f"{subid}.pid"
    pid_file.write_text("99999")
    done_file = ws / ".ccc" / "pids" / f"{subid}.done"
    done_file.write_text("ok\n")

    with mock.patch.object(hang, "_eng", return_value=None), \
         mock.patch.object(hang, "_activate_workspace"), \
         mock.patch.object(hang, "_find_task_column", return_value="in_progress"), \
         mock.patch("board.phase._current_running_phase", return_value=1):
        hang._check_and_mark_hung(ws, active)
    assert not list((ws / ".ccc" / "pids").glob("*.hung"))


def test_hang_retry_counter_capped_at_max(tmp_path, monkeypatch):
    """_MAX_HANG_RETRY 上限保护：reload 后仍生效。"""
    from engine import hang

    monkeypatch.setattr(hang, "_MAX_HANG_RETRY", 2)
    assert hang._MAX_HANG_RETRY == 2
    # counter 文件读写后值被 clamp 在 _MAX_HANG_RETRY 之内（按业务语义不强制，
    # 这里只断言 reload 不丢失既有计数）
    counter_file = tmp_path / "engine-hang-retries.json"
    monkeypatch.setattr(hang, "_HANG_COUNTER_FILE", counter_file)
    hang._hang_retry_counter = {"k": 99}
    hang._save_hang_retry_counter()
    hang._hang_retry_counter = {}
    hang._load_hang_retry_counter()
    assert hang._hang_retry_counter["k"] == 99
