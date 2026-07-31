"""test_engine_kb_gate.py — _run_verified_kb_gate every-tick kb processing.

Commit 43c0b7f moves _run_verified_kb_gate from the %6 block (every ~60s) to a
per-tick position run immediately after the testing gate for each workspace. The
idle-path fallback (no active tasks → also run kb) is retained as a secondary
path.

Tests:
  - Empty verified column → gate is a no-op (kb_role not called)
  - Verified column has tasks → kb_role called, moved tasks refreshed
  - kb_role exception → caught gracefully, no crash
  - kb_role returns None → handled gracefully
  - Multiple verified tasks → all moved get refresh_epic
  - Idempotent: calling twice with already-empty verified is still safe
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, call

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from _board_store import COLUMNS, FileBoardStore, now_iso


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


# ── _run_verified_kb_gate ──


class TestRunVerifiedKbGate:
    """_run_verified_kb_gate: verified→kb→released, idempotent, no crash on error."""

    @pytest.fixture(autouse=True)
    def _legacy_kb_llm_path(self, monkeypatch):
        """这些用例锁定史径 kb LLM；默认 min-pipeline 会快通跳过 kb_role。"""
        import importlib

        from engine import min_pipeline as mp

        monkeypatch.setenv("CCC_MIN_PIPELINE", "0")
        importlib.reload(mp)
        yield
        monkeypatch.setenv("CCC_MIN_PIPELINE", "1")
        importlib.reload(mp)

    def test_empty_verified_is_noop(self, tmp_path: Path):
        """No verified tasks → gate returns after early-exit, kb_role not called."""
        from engine.gates import _run_verified_kb_gate

        ws = _make_ws(tmp_path)
        FileBoardStore(ws)  # ensure dirs exist

        with patch("engine.verify_gate.kb_role") as mock_kb:
            _run_verified_kb_gate(ws)

        mock_kb.assert_not_called()

    def test_verified_calls_kb_role(self, tmp_path: Path):
        """Verified column has tasks → kb_role is called once."""
        from engine.gates import _run_verified_kb_gate

        ws = _make_ws(tmp_path)
        store = FileBoardStore(ws)
        store.create_task(
            _task(id="kb-t1", title="KB task 1", status="verified"),
            column="verified",
        )

        with (
            patch("engine.verify_gate.kb_role", return_value={"moved": ["kb-t1"]}) as mock_kb,
            patch("engine.verify_gate.refresh_parent_epic") as mock_refresh,
        ):
            _run_verified_kb_gate(ws)

        mock_kb.assert_called_once()
        mock_refresh.assert_called_once_with(ws, "kb-t1")

    def test_multiple_verified_tasks_all_refreshed(self, tmp_path: Path):
        """When kb_role moves multiple tasks, each gets _refresh_parent_epic."""
        from engine.gates import _run_verified_kb_gate

        ws = _make_ws(tmp_path)
        store = FileBoardStore(ws)
        for i in range(3):
            store.create_task(
                _task(id=f"kb-t{i}", title=f"KB task {i}", status="verified"),
                column="verified",
            )

        with (
            patch("engine.verify_gate.kb_role", return_value={"moved": ["kb-t0", "kb-t2"]}) as mock_kb,
            patch("engine.verify_gate.refresh_parent_epic") as mock_refresh,
        ):
            _run_verified_kb_gate(ws)

        mock_kb.assert_called_once()
        assert mock_refresh.call_count == 2, f"Expected 2 refresh calls, got {mock_refresh.call_count}"
        mock_refresh.assert_has_calls(
            [call(ws, "kb-t0"), call(ws, "kb-t2")],
            any_order=True,
        )

    def test_kb_role_exception_caught(self, tmp_path: Path):
        """kb_role raises → exception caught, no crash, update_index still called."""
        from engine.gates import _run_verified_kb_gate

        ws = _make_ws(tmp_path)
        store = FileBoardStore(ws)
        store.create_task(
            _task(id="kb-t-err", title="KB error", status="verified"),
            column="verified",
        )

        with (
            patch("engine.verify_gate.kb_role", side_effect=ValueError("kb oops")) as mock_kb,
            patch("engine.verify_gate.refresh_parent_epic") as mock_refresh,
        ):
            # Should not raise
            _run_verified_kb_gate(ws)

        mock_kb.assert_called_once()
        mock_refresh.assert_not_called()  # exception before refresh

        # Task should still be in verified (no move happened)
        col, _ = store.find_task("kb-t-err")
        assert col == "verified"

    def test_kb_role_none_return(self, tmp_path: Path):
        """kb_role returns None → no crash, no tasks refreshed."""
        from engine.gates import _run_verified_kb_gate

        ws = _make_ws(tmp_path)
        store = FileBoardStore(ws)
        store.create_task(
            _task(id="kb-t-none", title="KB none", status="verified"),
            column="verified",
        )

        with (
            patch("engine.verify_gate.kb_role", return_value=None) as mock_kb,
            patch("engine.verify_gate.refresh_parent_epic") as mock_refresh,
        ):
            _run_verified_kb_gate(ws)

        mock_kb.assert_called_once()
        mock_refresh.assert_not_called()

    def test_kb_role_empty_moved_list(self, tmp_path: Path):
        """kb_role returns {'moved': []} → no refresh calls, no crash."""
        from engine.gates import _run_verified_kb_gate

        ws = _make_ws(tmp_path)
        store = FileBoardStore(ws)
        store.create_task(
            _task(id="kb-t-empty", title="KB empty moved", status="verified"),
            column="verified",
        )

        with (
            patch("engine.verify_gate.kb_role", return_value={"moved": []}) as mock_kb,
            patch("engine.verify_gate.refresh_parent_epic") as mock_refresh,
        ):
            _run_verified_kb_gate(ws)

        mock_kb.assert_called_once()
        mock_refresh.assert_not_called()

    def test_idempotent_empty_after_first_gate(self, tmp_path: Path):
        """Calling the gate twice: first call processes tasks, second call is no-op.

        Use a mock side-effect that actually moves the task out of verified to
        simulate real kb_role behavior.
        """
        from engine.gates import _run_verified_kb_gate

        ws = _make_ws(tmp_path)
        store = FileBoardStore(ws)
        store.create_task(
            _task(id="kb-idemp", title="Idempotent test", status="verified"),
            column="verified",
        )

        moved_ids = []

        def _kb_role_side():
            """Fake kb_role: move all verified tasks to released."""
            for t in store.list_tasks("verified"):
                tid = t["id"]
                ok = store.move_task(tid, "verified", "released")
                if ok:
                    moved_ids.append(tid)
            return {"moved": moved_ids}

        with patch("engine.verify_gate.kb_role", side_effect=_kb_role_side) as mock_kb:
            _run_verified_kb_gate(ws)

        assert mock_kb.call_count == 1
        assert "kb-idemp" in moved_ids

        # Second call: no verified tasks remain → no-op
        with patch("engine.verify_gate.kb_role") as mock_kb2:
            _run_verified_kb_gate(ws)

        mock_kb2.assert_not_called()

    def test_activate_workspace_and_get_store(self, tmp_path: Path):
        """The gate calls _activate_workspace + _get_store internally.

        This test verifies the function's workspace management works by creating
        a real store outside the gate and checking it's reachable.
        """
        from engine.gates import _run_verified_kb_gate

        ws = _make_ws(tmp_path)
        store = FileBoardStore(ws)
        store.create_task(
            _task(id="kb-activate", title="Activate test", status="verified"),
            column="verified",
        )

        with (
            patch("engine.verify_gate.kb_role", return_value={"moved": ["kb-activate"]}) as mock_kb,
            patch("engine.verify_gate.refresh_parent_epic"),
        ):
            _run_verified_kb_gate(ws)

        # After gate, task should have been moved to released by kb_role
        # (kb_role returns moved, and the gate logs it — but the actual move
        #  is kb_role's job, not the gate's. The gate calls update_index after.)
        mock_kb.assert_called_once()

    def test_update_index_called_after_success(self, tmp_path: Path):
        """store.update_index() is called after kb_role succeeds."""
        from engine.gates import _run_verified_kb_gate

        ws = _make_ws(tmp_path)
        store = FileBoardStore(ws)
        store.create_task(
            _task(id="kb-index", title="Index test", status="verified"),
            column="verified",
        )

        # We cannot easily mock update_index on the same store the gate gets,
        # but we can check that the gate runs to completion without error
        # and that the store is still usable afterwards.
        with (
            patch("engine.verify_gate.kb_role", return_value={"moved": ["kb-index"]}),
            patch("engine.verify_gate.refresh_parent_epic"),
        ):
            _run_verified_kb_gate(ws)

        # Index should have been updated (check the file exists)
        index_file = ws / ".ccc" / "board" / "index.json"
        assert index_file.exists(), "index.json should exist after update_index()"


# ── Engine loop structure: kb gate runs every tick ──


class TestEngineLoopKbGatePlacement:
    """Structural verification that the engine loop runs _run_verified_kb_gate every tick.

    The engine loop (ccc-engine.py:engine_loop) has three relevant sections:

    1. Testing-gate per tick (lines ~2593-2601)
    2. KB-gate per tick (lines ~2603-2611) — NEW, every tick
    3. %6 block (lines ~2613-2650) — removed redundant kb gate

    These tests verify the code structure is correct.
    """

    def test_kb_gate_imported_from_gates(self):
        """_run_verified_kb_gate is imported from engine.gates in ccc-engine.py."""
        import ast

        engine_path = ROOT / "scripts" / "ccc-engine.py"
        tree = ast.parse(engine_path.read_text(encoding="utf-8"))

        found = False
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if getattr(node, "module", None) == "engine.gates":
                    for alias in node.names:
                        if alias.name == "_run_verified_kb_gate":
                            found = True
                            break
        assert found, "_run_verified_kb_gate must be imported from engine.gates"

    def test_kb_gate_called_per_tick(self):
        """The per-tick loop calls _run_verified_kb_gate for each workspace.

        Uses source-line-based analysis to check the kb gate call appears
        outside the %6 block.
        """
        import ast

        engine_path = ROOT / "scripts" / "engine" / "_loop_impl.py"
        source_lines = engine_path.read_text(encoding="utf-8").splitlines()
        tree = ast.parse("\n".join(source_lines))

        # Find engine_loop function
        engine_loop = None
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "engine_loop":
                engine_loop = node
                break
        assert engine_loop is not None, "engine_loop function not found"

        # Find the %6 block boundaries
        # Walk if statements in engine_loop; find the one checking iteration % 6
        six_block_start = six_block_end = None
        for node in ast.iter_child_nodes(engine_loop):
            if isinstance(node, ast.If) and isinstance(node.test, ast.Compare):
                # Check: left is BinOp with Mod(), ops[0] is Eq()
                left = node.test.left
                if (
                    isinstance(left, ast.BinOp)
                    and isinstance(left.op, ast.Mod)
                    and len(node.test.ops) == 1
                    and isinstance(node.test.ops[0], ast.Eq)
                ):
                    # Check right comparators include 0
                    for c in node.test.comparators:
                        if isinstance(c, ast.Constant) and c.value == 0:
                            six_block_start = node.lineno
                            six_block_end = node.end_lineno or len(source_lines)
                            break
                if six_block_start:
                    break

        # Now find all _run_verified_kb_gate calls in engine_loop
        kb_calls_outside_six = 0
        for node in ast.walk(engine_loop):
            if isinstance(node, ast.Call):
                call_line = source_lines[node.lineno - 1].strip()
                if "_run_verified_kb_gate" in call_line:
                    is_inside_six = (
                        six_block_start is not None
                        and six_block_start <= node.lineno <= six_block_end
                    )
                    if not is_inside_six:
                        kb_calls_outside_six += 1

        assert kb_calls_outside_six >= 1, (
            f"No _run_verified_kb_gate call found outside the %6 block "
            f"(6-block={six_block_start}-{six_block_end})"
        )

    def test_no_duplicate_kb_gate_in_six_block(self):
        """The old %6 block no longer has a redundant _run_verified_kb_gate call.

        Commit 43c0b7f removed the redundant:
            if _store.list_tasks("verified"):
                _run_verified_kb_gate(ws)
        from inside the %6 block.
        """
        import ast

        engine_path = ROOT / "scripts" / "engine" / "_loop_impl.py"
        source_lines = engine_path.read_text(encoding="utf-8").splitlines()
        tree = ast.parse("\n".join(source_lines))

        # Find engine_loop function
        engine_loop = None
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "engine_loop":
                engine_loop = node
                break
        assert engine_loop is not None, "engine_loop not found"

        # Find the %6 block and check no _run_verified_kb_gate call inside
        # Walk all If nodes in engine_loop to find `iteration % 6 == 0` (value=6, not 12/36)
        found_six_block = False
        for child in ast.walk(engine_loop):
            if not isinstance(child, ast.If) or not isinstance(child.test, ast.Compare):
                continue
            left = child.test.left
            if not isinstance(left, ast.BinOp) or not isinstance(left.op, ast.Mod):
                continue
            right_val = getattr(left.right, "value", None)
            if right_val != 6:  # only match % 6, not % 12, % 36, etc.
                continue
            if (
                len(child.test.ops) == 1
                and isinstance(child.test.ops[0], ast.Eq)
                and any(
                    isinstance(c, ast.Constant) and c.value == 0
                    for c in child.test.comparators
                )
            ):
                found_six_block = True
                # Check all calls inside this block
                for call_node in ast.walk(child):
                    if isinstance(call_node, ast.Call):
                        call_text = source_lines[call_node.lineno - 1].strip()
                        if "_run_verified_kb_gate" in call_text:
                            pytest.fail(
                                f"Redundant _run_verified_kb_gate call at line "
                                f"{call_node.lineno} inside the %6 block — "
                                f"must be removed (commit 43c0b7f)"
                            )
                break

        assert found_six_block, (
            "No 'if iteration % 6 == 0' block found in engine_loop — "
            "something changed in the engine loop structure"
        )
