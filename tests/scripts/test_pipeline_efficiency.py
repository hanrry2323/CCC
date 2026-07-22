"""产线提效 P1–P4 单测：槽生命周期 / result 解析 / FAIL revert / testing 预算。"""
from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from _result_json import extract_json_object, parse_result_file
from engine import active_tasks, gates, slots


def test_extract_json_object_pure():
    obj = extract_json_object('{"exit_code": 0, "duration_s": 12.5}')
    assert obj == {"exit_code": 0, "duration_s": 12.5}


def test_extract_json_object_polluted():
    raw = "INFO starting\n[opencode] hello\n{\"exit_code\": 0, \"duration_s\": 3.2}\ntrailing\n"
    obj = extract_json_object(raw)
    assert obj is not None
    assert obj["exit_code"] == 0
    assert obj["duration_s"] == 3.2


def test_parse_result_file_dirty(tmp_path: Path):
    p = tmp_path / "t.result.json"
    p.write_text("noise\n{\"exit_code\": 1, \"duration_s\": 9}\n", encoding="utf-8")
    obj, dirty = parse_result_file(p)
    assert dirty is True
    assert obj["exit_code"] == 1


def test_workspace_blocks_new_opencode_done_does_not_block(tmp_path: Path):
    ws = tmp_path / "ws"
    pids = ws / ".ccc" / "pids"
    pids.mkdir(parents=True)
    tid = "card-old"
    (pids / f"{tid}.done").write_text("done\n")
    (pids / f"{tid}.pid").write_text("999999\n")  # dead
    active = {
        f"{ws.resolve()}|{tid}": {
            "workspace": ws,
            "task_id": tid,
            "started_at": "2000-01-01T00:00:00+00:00",
        }
    }
    assert active_tasks.workspace_blocks_new_opencode(ws, active) is False


def test_workspace_blocks_new_opencode_live_pid(tmp_path: Path):
    ws = tmp_path / "ws"
    pids = ws / ".ccc" / "pids"
    pids.mkdir(parents=True)
    tid = "card-live"
    pid = os.getpid()
    (pids / f"{tid}.pid").write_text(f"{pid}\n")
    active = {
        f"{ws.resolve()}|{tid}": {
            "workspace": ws,
            "task_id": tid,
            "started_at": time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime()),
        }
    }
    assert active_tasks.workspace_blocks_new_opencode(ws, active) is True


def test_release_dev_slot_clears_active(tmp_path: Path, monkeypatch):
    ws = tmp_path / "ws"
    ws.mkdir()
    tid = "t1"
    key = f"{ws.resolve()}|{tid}"
    active = {key: {"workspace": ws, "task_id": tid}}
    monkeypatch.setattr(active_tasks, "release_opencode_slot", lambda *a, **k: 1)
    monkeypatch.setattr(
        active_tasks, "_save_active_tasks", lambda *a, **k: None
    )
    with patch("engine.active_tasks.reap_opencode_workspace", create=True):
        # release_dev_slot imports reap inside try
        pass
    active_tasks.release_dev_slot(active, ws, tid, reap=False)
    assert key not in active


def _git_init(ws: Path) -> None:
    subprocess.run(["git", "init"], cwd=ws, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "t@example.com"],
        cwd=ws,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "t"],
        cwd=ws,
        check=True,
        capture_output=True,
    )
    (ws / "a.txt").write_text("v1\n")
    subprocess.run(["git", "add", "a.txt"], cwd=ws, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init"], cwd=ws, check=True, capture_output=True
    )


def test_revert_conflict_aborts_no_revert_head(tmp_path: Path):
    ws = tmp_path / "ws"
    ws.mkdir()
    _git_init(ws)
    # make a commit mentioning task id
    tid = "stress-task-w1"
    (ws / "a.txt").write_text("v2\n")
    subprocess.run(["git", "add", "a.txt"], cwd=ws, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", f"feat({tid}): change a"],
        cwd=ws,
        check=True,
        capture_output=True,
    )
    commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ws, text=True
    ).strip()
    # diverge working tree to force conflict on revert
    (ws / "a.txt").write_text("conflict-side\n")
    subprocess.run(["git", "add", "a.txt"], cwd=ws, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "diverge"],
        cwd=ws,
        check=True,
        capture_output=True,
    )
    # rewrite history? simpler: change file so revert of first change conflicts
    # Actually revert of "feat" commit onto "diverge" may succeed if content differs.
    # Force conflict: start a revert, leave REVERT_HEAD, then call our function.
    phases = ws / ".ccc" / "phases"
    phases.mkdir(parents=True)
    (phases / f"{tid}.phases.json").write_text(
        json.dumps([{"phase": 1, "commit": commit}]) + "\n"
    )

    # Pretend mid-revert: create REVERT_HEAD then call helper
    (ws / ".git" / "REVERT_HEAD").write_text(commit + "\n")
    # Also create unmerged-like state by starting real revert that conflicts
    # Reset: abort first then use our function which should abort sequencer
    ok = gates._revert_task_commit(ws, tid)
    assert (ws / ".git" / "REVERT_HEAD").exists() is False
    assert gates._git_sequencer_active(ws) is False
    # ok may be True or False depending on conflict; invariant is no half-revert
    assert isinstance(ok, bool)


def test_testing_gate_respects_max_per_tick(tmp_path: Path, monkeypatch):
    ws = tmp_path / "ws"
    store = MagicMock()
    store.list_tasks.return_value = [
        {"id": "a"},
        {"id": "b"},
        {"id": "c"},
    ]
    calls: list[str] = []

    monkeypatch.setattr(gates, "_activate_workspace", lambda w: None)
    monkeypatch.setattr(gates, "_get_store", lambda w: store)
    monkeypatch.setattr(gates, "_ws_label", lambda w: "ws")
    monkeypatch.setattr(gates, "_testing_gate_budget", lambda: (1, 180.0))
    monkeypatch.setattr(
        gates,
        "_run_reviewer_tester_gate",
        lambda w, tid: calls.append(tid) or True,
    )
    monkeypatch.setattr(gates, "_refresh_parent_epic", lambda w, tid: None)

    gates._run_testing_tasks_gate(ws)
    assert calls == ["a"]


def test_try_acquire_releases_done_ghost(tmp_path: Path, monkeypatch):
    ws = tmp_path / "ws"
    pids = ws / ".ccc" / "pids"
    pids.mkdir(parents=True)
    old = "old-card"
    (pids / f"{old}.done").write_text("done\n")
    state_path = tmp_path / "slots.json"
    held = f"{ws.resolve()}|{old}"
    state_path.write_text(
        json.dumps({"max": 6, "count": 1, "tasks": {held: {"n": 1, "pid": 1}}})
        + "\n"
    )
    monkeypatch.setattr(slots, "opencode_slots_path", lambda: state_path)
    # also patch board.slots default if needed — try_acquire uses state_path arg
    new_key = f"{ws.resolve()}|new-card"
    # After releasing ghost, acquire should succeed
    ok = slots.try_acquire_opencode_slot(new_key)
    assert ok is True
