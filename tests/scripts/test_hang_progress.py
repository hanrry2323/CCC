"""Wave A: no-progress hang + gate salvage."""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

import pytest


def _make_ws(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    (ws / ".ccc" / "board" / "in_progress").mkdir(parents=True)
    (ws / ".ccc" / "pids").mkdir(parents=True)
    (ws / ".ccc" / "reports").mkdir(parents=True)
    (ws / ".ccc" / "phases").mkdir(parents=True)
    return ws


def test_no_progress_marks_hung_with_task_pid(tmp_path, monkeypatch):
    from engine import hang

    monkeypatch.setenv("CCC_PHASE_NO_PROGRESS_SEC", "120")
    # reload threshold
    hang._NO_PROGRESS_SEC = 120

    ws = _make_ws(tmp_path)
    tid = "flow-green-x-w1"
    task = {
        "id": tid,
        "title": "t",
        "description": "d",
        "status": "in_progress",
        "created_at": "2026-07-20T00:00:00+08:00",
        "updated_at": "2026-07-20T00:00:00+08:00",
        "card_kind": "work",
        "complexity": "small",
        "schema_version": "1.2",
        "ui_hidden": False,
        "child_ids": [],
        "parent_id": None,
        "split_status": None,
        "color_group": None,
        "color_depth": 0,
        "tags": [],
        "assignee": None,
        "note": None,
    }
    (ws / ".ccc" / "board" / "in_progress" / f"{tid}.jsonl").write_text(
        json.dumps(task) + "\n", encoding="utf-8"
    )
    # task-level pid (opencode-runner style)
    pid_file = ws / ".ccc" / "pids" / f"{tid}.pid"
    pid_file.write_text("424242")
    old = time.time() - 700
    os.utime(pid_file, (old, old))

    started = (datetime.now(timezone.utc) - timedelta(seconds=700)).isoformat()
    active = {"k1": {"workspace": ws, "task_id": tid, "started_at": started}}

    def fake_kill(pid, sig):
        return None

    with mock.patch.object(hang, "_eng", return_value=None), mock.patch.object(
        hang, "_activate_workspace"
    ), mock.patch.object(
        hang, "_find_task_column", return_value="in_progress"
    ), mock.patch(
        "engine.hang.os.kill", side_effect=fake_kill
    ), mock.patch(
        "board.phase._current_running_phase", return_value=1
    ), mock.patch(
        "_failure_ledger.record_failure", return_value=None
    ):
        hang._check_and_mark_hung(ws, active)

    hung = list((ws / ".ccc" / "pids").glob("*.hung"))
    assert len(hung) == 1
    marker = json.loads(hung[0].read_text())
    assert marker["reason"] == "no_progress"
    assert marker["pid"] == 424242


def test_is_no_progress_helper(tmp_path, monkeypatch):
    from engine import hang

    hang._NO_PROGRESS_SEC = 600
    ws = _make_ws(tmp_path)
    tid = "t1"
    now = time.time()
    started = now - 700
    # fresh activity → not stale
    act = ws / ".ccc" / "reports" / f"{tid}.result.json"
    act.write_text("{}")
    stale, idle, _ = hang._is_no_progress(
        ws=ws, tid=tid, started_ts=started, now_ts=now
    )
    assert stale is False
    # old activity
    os.utime(act, (now - 700, now - 700))
    stale, idle, reason = hang._is_no_progress(
        ws=ws, tid=tid, started_ts=started, now_ts=now
    )
    assert stale is True
    assert "no-progress" in reason
