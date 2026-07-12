"""test_engine.py — ccc-engine.py 可测纯逻辑 + phase 依赖链（mock 文件系统）"""
from __future__ import annotations

import importlib.util
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent.parent / "scripts"

# ccc-board: phase 依赖（Engine 调度所依赖）
_spec_board = importlib.util.spec_from_file_location(
    "ccc_board_engine_test", str(SCRIPTS / "ccc-board.py")
)
ccc_board = importlib.util.module_from_spec(_spec_board)
sys.modules["ccc_board_engine_test"] = ccc_board
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
_spec_board.loader.exec_module(ccc_board)

_resolve_phase_dependencies = ccc_board._resolve_phase_dependencies
_detect_phase_cycle = ccc_board._detect_phase_cycle

# ccc-engine: 辅助函数（不跑 engine_loop）
_spec_engine = importlib.util.spec_from_file_location(
    "ccc_engine_test", str(SCRIPTS / "ccc-engine.py")
)
ccc_engine = importlib.util.module_from_spec(_spec_engine)
sys.modules["ccc_engine_test"] = ccc_engine
_spec_engine.loader.exec_module(ccc_engine)


class TestEnginePhaseDependencyChain:
    """Engine 依赖 _resolve_phase_dependencies — 纯逻辑，mock phases 列表。"""

    def test_chain_all_executable_when_no_deps(self):
        phases = [
            {"phase": 1, "status": "pending", "depends_on": []},
            {"phase": 2, "status": "pending", "depends_on": [1]},
        ]
        phases[0]["status"] = "done"
        exe, blocked, skipped = _resolve_phase_dependencies(phases)
        assert 2 in exe
        assert not skipped

    def test_cycle_marks_skipped(self):
        phases = [
            {"phase": 1, "status": "pending", "depends_on": [2]},
            {"phase": 2, "status": "pending", "depends_on": [1]},
        ]
        cycles = _detect_phase_cycle(phases)
        assert len(cycles) >= 1
        _, _, skipped = _resolve_phase_dependencies(phases)
        assert 1 in skipped and 2 in skipped

    def test_failed_upstream_skips_downstream(self):
        phases = [
            {"phase": 1, "status": "failed", "depends_on": []},
            {"phase": 2, "status": "pending", "depends_on": [1]},
        ]
        exe, blocked, skipped = _resolve_phase_dependencies(phases)
        assert 2 in skipped
        assert 2 not in exe


class TestEngineHelpers:
    def test_wait_tick_sleeps_remaining(self):
        start = time.time() - 5
        with patch("time.sleep") as sleep:
            ccc_engine._wait_tick(start)
        sleep.assert_called_once()
        assert sleep.call_args[0][0] > 0

    def test_audit_should_run_when_no_last_run(self, tmp_path, monkeypatch):
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        assert ccc_engine._audit_should_run(str(tmp_path / "ws"), interval_hours=2)

    def test_audit_should_run_respects_interval(self, tmp_path, monkeypatch):
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        audit_dir = tmp_path / ".ccc"
        audit_dir.mkdir(parents=True)
        slug_file = audit_dir / "audit-last-run.ws.json"
        recent = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
        slug_file.write_text(json.dumps({"last_run": recent}))
        assert ccc_engine._audit_should_run(str(tmp_path / "ws"), interval_hours=24) is False

    def test_get_store_cached(self, tmp_path, monkeypatch):
        board = tmp_path / ".ccc" / "board"
        board.mkdir(parents=True)
        for col in ccc_board.COLUMNS if hasattr(ccc_board, "COLUMNS") else []:
            (board / col).mkdir(exist_ok=True)
        ccc_engine._store_instance = None
        s1 = ccc_engine._get_store(tmp_path)
        s2 = ccc_engine._get_store(tmp_path)
        assert s1 is s2
