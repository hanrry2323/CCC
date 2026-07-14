"""test_engine.py — ccc-engine.py 可测纯逻辑 + phase 依赖链（mock 文件系统）"""

from __future__ import annotations

import importlib.util
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch


SCRIPTS = Path(__file__).resolve().parent.parent.parent / "scripts"

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
_check_phase_failures = ccc_board._check_phase_failures

_spec_engine = importlib.util.spec_from_file_location(
    "ccc_engine_test", str(SCRIPTS / "ccc-engine.py")
)
ccc_engine = importlib.util.module_from_spec(_spec_engine)
sys.modules["ccc_engine_test"] = ccc_engine
_spec_engine.loader.exec_module(ccc_engine)


class TestEnginePhaseDependencyChain:
    def test_chain_all_executable_when_no_deps(self):
        phases = [
            {"phase": 1, "status": "pending", "depends_on": []},
            {"phase": 2, "status": "pending", "depends_on": [1]},
        ]
        phases[0]["status"] = "done"
        exe, blocked, skipped = _resolve_phase_dependencies(phases)
        assert 2 in exe
        assert not skipped

    def test_phase_fail_skip_dependent(self):
        """phase 1 failed → phase 2 (depends_on phase1) 被标 skipped。"""
        phases = [
            {"phase": 1, "status": "failed", "depends_on": []},
            {"phase": 2, "status": "pending", "depends_on": [1]},
        ]
        exe, blocked, skipped = _resolve_phase_dependencies(phases)
        assert 1 not in exe
        assert 2 in skipped
        assert 2 not in exe
        assert 2 not in blocked

    def test_phase_fail_jump_executable(self):
        """phase 1 failed → 无依赖的 phase 3 仍可执行。"""
        phases = [
            {"phase": 1, "status": "failed", "depends_on": []},
            {"phase": 2, "status": "pending", "depends_on": [1]},
            {"phase": 3, "status": "pending", "depends_on": []},
        ]
        exe, blocked, skipped = _resolve_phase_dependencies(phases)
        assert 3 in exe
        assert 1 not in exe
        assert 2 in skipped
        assert 3 not in skipped
        assert 3 not in blocked

    def test_phase_all_terminal(self):
        """全部 phase 失败或完成时，_check_phase_failures 返回 all_terminal=True。"""
        phases = [
            {"phase": 1, "status": "done", "depends_on": []},
            {"phase": 2, "status": "failed", "depends_on": []},
            {"phase": 3, "status": "skipped", "depends_on": [2]},
        ]
        with (
            patch.object(ccc_board, "_load_phases", return_value=phases),
            patch.object(ccc_board, "_apply_phase_status_updates", return_value=None),
            patch.object(ccc_board, "_read_engine_iter", return_value=0),
            patch.object(ccc_board, "_write_engine_iter", return_value=None),
        ):
            result = _check_phase_failures("dummy-task")
        assert result["all_terminal"] is True
        assert result["all_failed_or_skipped"] is False
        assert 3 in result["skipped"]
        assert result["executable"] == []
