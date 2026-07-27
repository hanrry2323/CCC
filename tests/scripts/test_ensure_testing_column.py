"""test_ensure_testing_column.py — verified→testing pullback in workspace.py.

Commit 43c0b7f: _ensure_task_in_testing pulls a task from verified back to testing
so reviewer/tester gates can process it. COLUMN_TRANSITIONS["testing"] now includes
"verified" to permit the move.

Tests:
  - Task in verified → moved to testing
  - Task already in testing → no-op
  - Task in in_progress / planned → no-op
  - Non-existent task → no crash
  - Move rejected (patched transitions) → warning logged, task stays in verified
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from _board_store import COLUMNS, COLUMN_TRANSITIONS, FileBoardStore, now_iso
from engine.workspace import _ensure_task_in_testing, _find_task_column


# ── helpers ──


def _make_ws(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    for col in COLUMNS:
        (ws / ".ccc" / "board" / col).mkdir(parents=True)
    (ws / ".ccc" / "board" / "events").mkdir(parents=True)
    (ws / ".ccc" / "plans").mkdir(parents=True)
    (ws / ".ccc" / "phases").mkdir(parents=True)
    return ws


def _task(**overrides: str) -> dict:
    defaults = {
        "id": "t-default",
        "title": "default",
        "status": "backlog",
        "card_kind": "work",
    }
    defaults.update(overrides)
    return defaults


# ── _ensure_task_in_testing ──


class TestEnsureTaskInTesting:
    """_ensure_task_in_testing: pullback verified→testing for reviewer/tester gate."""

    def test_pullback_verified_to_testing(self, tmp_path: Path):
        """Task in verified column → moved to testing."""
        ws = _make_ws(tmp_path)
        store = FileBoardStore(ws)
        store.create_task(
            _task(id="pullback-t1", title="Task in verified", status="verified"),
            column="verified",
        )
        assert _find_task_column(store, "pullback-t1") == "verified"

        _ensure_task_in_testing(store, "pullback-t1")

        assert _find_task_column(store, "pullback-t1") == "testing"
        # Source file should be gone from verified
        assert not (ws / ".ccc" / "board" / "verified" / "pullback-t1.jsonl").exists()

    def test_noop_when_already_in_testing(self, tmp_path: Path):
        """Task already in testing → no move."""
        ws = _make_ws(tmp_path)
        store = FileBoardStore(ws)
        store.create_task(
            _task(id="pullback-t2", title="Task in testing", status="testing"),
            column="testing",
        )
        assert _find_task_column(store, "pullback-t2") == "testing"

        _ensure_task_in_testing(store, "pullback-t2")

        assert _find_task_column(store, "pullback-t2") == "testing"

    def test_noop_when_in_in_progress(self, tmp_path: Path):
        """Task in in_progress → no move."""
        ws = _make_ws(tmp_path)
        store = FileBoardStore(ws)
        store.create_task(
            _task(id="pullback-t3", title="Task in progress", status="in_progress"),
            column="in_progress",
        )
        assert _find_task_column(store, "pullback-t3") == "in_progress"

        _ensure_task_in_testing(store, "pullback-t3")

        assert _find_task_column(store, "pullback-t3") == "in_progress"

    def test_noop_when_in_planned(self, tmp_path: Path):
        """Task in planned → no move."""
        ws = _make_ws(tmp_path)
        store = FileBoardStore(ws)
        store.create_task(
            _task(id="pullback-t4", title="Task in planned", status="planned"),
            column="planned",
        )
        assert _find_task_column(store, "pullback-t4") == "planned"

        _ensure_task_in_testing(store, "pullback-t4")

        assert _find_task_column(store, "pullback-t4") == "planned"

    def test_noop_when_in_released(self, tmp_path: Path):
        """Task already released → no move (no pullback from released)."""
        ws = _make_ws(tmp_path)
        store = FileBoardStore(ws)
        store.create_task(
            _task(id="pullback-t-rel", title="Released task", status="released"),
            column="released",
        )
        assert _find_task_column(store, "pullback-t-rel") == "released"

        _ensure_task_in_testing(store, "pullback-t-rel")

        assert _find_task_column(store, "pullback-t-rel") == "released"

    def test_noop_when_nonexistent(self, tmp_path: Path):
        """Non-existent task ID → no crash, silent no-op."""
        ws = _make_ws(tmp_path)
        store = FileBoardStore(ws)

        # Must not raise
        _ensure_task_in_testing(store, "no-such-task")

    def test_warning_logged_when_move_rejected(self, tmp_path: Path):
        """Move fails due to missing transition rule → warning logged, task stays in verified.

        Simulate by removing 'verified' from COLUMN_TRANSITIONS['testing'] so the
        move is rejected by the file-store gate.
        """
        ws = _make_ws(tmp_path)
        store = FileBoardStore(ws)
        store.create_task(
            _task(id="pullback-t6", title="Blocked pullback", status="verified"),
            column="verified",
        )
        assert _find_task_column(store, "pullback-t6") == "verified"

        # Patch transitions so verified→testing is not allowed
        patched = dict(COLUMN_TRANSITIONS)
        patched["testing"] = ["in_progress", "abnormal", "planned"]  # no "verified"

        import _board_store as bs

        with (
            patch.object(bs, "COLUMN_TRANSITIONS", patched),
            patch("engine.workspace._log") as mock_log,
        ):
            _ensure_task_in_testing(store, "pullback-t6")

        # Task should still be in verified (move was rejected)
        assert _find_task_column(store, "pullback-t6") == "verified"

        # Warning should be logged mentioning the task id (printf-style: %s → tid)
        mock_log.warning.assert_called_once()
        args, _ = mock_log.warning.call_args
        assert "pullback-t6" in str(args), f"Expected pullback-t6 in warning args: {args}"


# ── COLUMN_TRANSITIONS 门禁 ──


class TestColumnTransitionsTesting:
    """COLUMN_TRANSITIONS['testing'] must include 'verified' for pullback to work."""

    def test_verified_in_testing_transitions(self):
        """'verified' is listed in COLUMN_TRANSITIONS['testing']."""
        assert "verified" in COLUMN_TRANSITIONS["testing"], (
            "COLUMN_TRANSITIONS['testing'] must include 'verified' "
            "(commit 43c0b7f: reviewer pullback)"
        )

    def test_direct_move_verified_to_testing(self, tmp_path: Path):
        """FileBoardStore.move_task(tid, 'verified', 'testing') succeeds."""
        ws = _make_ws(tmp_path)
        store = FileBoardStore(ws)
        store.create_task(
            _task(id="direct-pullback", title="Direct move test", status="verified"),
            column="verified",
        )

        ok = store.move_task("direct-pullback", "verified", "testing")
        assert ok, "move_task verified→testing should succeed"
        assert _find_task_column(store, "direct-pullback") == "testing"

    def test_reverse_move_testing_to_verified(self, tmp_path: Path):
        """move_task(tid, 'testing', 'verified') still works (normal verified ingress)."""
        ws = _make_ws(tmp_path)
        store = FileBoardStore(ws)
        store.create_task(
            _task(id="reverse-pullback", title="Reverse move", status="testing"),
            column="testing",
        )

        ok = store.move_task("reverse-pullback", "testing", "verified")
        assert ok, "move_task testing→verified should succeed"
        assert _find_task_column(store, "reverse-pullback") == "verified"
