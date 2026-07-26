"""test_role_tool.py — _role_tool.py 前置校验函数测试。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from _board_store import COLUMNS, FileBoardStore, now_iso
from _role_tool import _find_running_phase, _read_phases_json, prepare_role_call


def _make_valid_task(task_id: str, status: str = "planned") -> dict:
    ts = now_iso()
    kind = "work" if status != "backlog" else "epic"
    return {
        "id": task_id,
        "title": f"Test {task_id}",
        "status": status,
        "created_at": ts,
        "updated_at": ts,
        "card_kind": kind,
    }


@pytest.fixture
def ws(tmp_path: Path) -> Path:
    ws = tmp_path / "workspace"
    ws.mkdir(parents=True)
    board = ws / ".ccc" / "board"
    for col in COLUMNS:
        (board / col).mkdir(parents=True)
    (board / "events").mkdir(parents=True)
    return ws


@pytest.fixture
def store(ws: Path) -> FileBoardStore:
    return FileBoardStore(ws)


def _write_phases(ws: Path, task_id: str, phases: list[dict]) -> None:
    d = ws / ".ccc" / "phases"
    d.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps({"schema_version": "1.1"})]
    for p in phases:
        lines.append(json.dumps(p, ensure_ascii=False))
    (d / f"{task_id}.phases.json").write_text("\n".join(lines))


class TestReadPhasesJson:
    def test_returns_none_for_missing(self, ws: Path):
        assert _read_phases_json(ws, "nope") is None

    def test_parses_valid_phases(self, ws: Path):
        phases = [
            {"phase": 1, "status": "pending", "scope": ["file1.py"]},
            {"phase": 2, "status": "pending", "scope": ["file2.py"]},
        ]
        _write_phases(ws, "t1", phases)
        got = _read_phases_json(ws, "t1")
        assert got is not None
        assert len(got) == 2
        assert got[0]["phase"] == 1


class TestFindRunningPhase:
    def test_in_progress_first(self):
        phases = [
            {"phase": 1, "status": "done"},
            {"phase": 2, "status": "in_progress"},
            {"phase": 3, "status": "pending"},
        ]
        assert _find_running_phase(phases) == 2

    def test_fallback_to_pending(self):
        phases = [
            {"phase": 1, "status": "done"},
            {"phase": 2, "status": "pending"},
        ]
        assert _find_running_phase(phases) == 2

    def test_fallback_to_blocked(self):
        phases = [
            {"phase": 1, "status": "done"},
            {"phase": 2, "status": "blocked"},
        ]
        assert _find_running_phase(phases) == 2

    def test_all_done_returns_none(self):
        phases = [{"phase": 1, "status": "done"}, {"phase": 2, "status": "done"}]
        assert _find_running_phase(phases) is None


class TestPrepareRoleCall:
    def test_task_not_found_returns_false(self, ws: Path):
        ok, reason = prepare_role_call("nope", ws)
        assert not ok
        assert "not found" in reason

    def test_missing_phases_json_returns_false(self, ws: Path, store: FileBoardStore):
        store.create_task(_make_valid_task("t1"), column="planned")
        ok, reason = prepare_role_call("t1", ws, store=store)
        assert not ok
        assert "phases.json" in reason

    def test_missing_scope_file_returns_false(self, ws: Path, store: FileBoardStore):
        store.create_task(_make_valid_task("t2"), column="planned")
        _write_phases(
            ws, "t2",
            [{"phase": 1, "status": "pending", "scope": ["missing_file.py"]}],
        )
        ok, reason = prepare_role_call("t2", ws, store=store)
        assert not ok
        assert "scope" in reason.lower()

    def test_all_checks_pass(self, ws: Path, store: FileBoardStore):
        store.create_task(_make_valid_task("t3"), column="planned")
        _write_phases(
            ws, "t3",
            [{"phase": 1, "status": "pending", "scope": []}],
        )
        # pids_dir + reports_dir auto-created
        ok, reason = prepare_role_call("t3", ws, store=store)
        assert ok, f"expected pass, got reason: {reason}"
        assert reason == ""

    def test_all_phase_done_returns_false(self, ws: Path, store: FileBoardStore):
        store.create_task(_make_valid_task("t4"), column="planned")
        _write_phases(
            ws, "t4",
            [{"phase": 1, "status": "done"}, {"phase": 2, "status": "done"}],
        )
        ok, reason = prepare_role_call("t4", ws, store=store)
        assert not ok
        assert "无待执行" in reason or "phase" in reason.lower()
