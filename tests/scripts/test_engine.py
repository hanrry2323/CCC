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
_check_phase_failures = ccc_board._check_phase_failures

from board.phase import _detect_phase_cycle  # noqa: E402

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
        import board.phase as phase_mod

        phases = [
            {"phase": 1, "status": "done", "depends_on": []},
            {"phase": 2, "status": "failed", "depends_on": []},
            {"phase": 3, "status": "skipped", "depends_on": [2]},
        ]
        with (
            patch.object(phase_mod, "_load_phases", return_value=phases),
            patch.object(phase_mod, "_apply_phase_status_updates", return_value=None),
            patch.object(phase_mod, "_read_engine_iter", return_value=0),
            patch.object(phase_mod, "_write_engine_iter", return_value=None),
        ):
            result = _check_phase_failures("dummy-task")
        assert result["all_terminal"] is True
        assert result["all_failed_or_skipped"] is False
        assert 3 in result["skipped"]
        assert result["executable"] == []


def _mk_board_ws(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    for col in (
        "backlog",
        "planned",
        "in_progress",
        "testing",
        "verified",
        "released",
        "abnormal",
    ):
        (ws / ".ccc" / "board" / col).mkdir(parents=True)
    for sub in ("plans", "phases", "reports", "verdicts", "pids"):
        (ws / ".ccc" / sub).mkdir(parents=True)
    return ws


def _write_task(ws: Path, col: str, tid: str, **extra) -> None:
    now = "2026-07-17T00:00:00+08:00"
    payload = {
        "id": tid,
        "title": tid,
        "status": col,
        "created_at": now,
        "updated_at": now,
        **extra,
    }
    (ws / ".ccc" / "board" / col / f"{tid}.jsonl").write_text(
        json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8"
    )


class TestFailureRoutingKeepPhases:
    """commit-gate / epic 子卡不得删 phases 回 backlog 误跑 product。"""

    def test_commit_gate_failed_goes_abnormal_keeps_phases(self, tmp_path, monkeypatch):
        ws = _mk_board_ws(tmp_path)
        tid = "epic-child-w1"
        _write_task(
            ws,
            "in_progress",
            tid,
            card_kind="work",
            parent_id="epic-parent",
        )
        phases = ws / ".ccc" / "phases" / f"{tid}.phases.json"
        phases.write_text(
            json.dumps({"schema_version": "1.1", "engine_iter": 1})
            + "\n"
            + json.dumps(
                {
                    "phase": 1,
                    "title": "p1",
                    "status": "running",
                    "depends_on": [],
                    "files": ["a.py"],
                    "acceptance": ["ok"],
                }
            )
            + "\n",
            encoding="utf-8",
        )
        monkeypatch.setenv("CCC_WORKSPACE", str(ws))
        ccc_engine._stores.clear()
        with patch.object(ccc_engine, "engine_log"):
            removed = ccc_engine._handle_task_result(
                ws,
                tid,
                {
                    "status": "failed",
                    "error": "commit-gate: no git commit whose message contains task_id",
                    "retry": 0,
                },
            )
        assert removed is True
        assert phases.is_file(), "commit-gate 失败必须保留 phases.json"
        assert (ws / ".ccc" / "board" / "abnormal" / f"{tid}.jsonl").is_file()
        assert not (ws / ".ccc" / "board" / "in_progress" / f"{tid}.jsonl").exists()
        assert not (ws / ".ccc" / "board" / "backlog" / f"{tid}.jsonl").exists()

    def test_unresolvable_epic_child_keeps_phases(self, tmp_path, monkeypatch):
        ws = _mk_board_ws(tmp_path)
        tid = "epic-child-w2"
        _write_task(
            ws,
            "in_progress",
            tid,
            card_kind="work",
            parent_id="epic-parent",
        )
        phases = ws / ".ccc" / "phases" / f"{tid}.phases.json"
        phases.write_text(
            json.dumps({"schema_version": "1.1", "engine_iter": 5})
            + "\n"
            + json.dumps(
                {
                    "phase": 1,
                    "title": "p1",
                    "status": "running",
                    "depends_on": [],
                    "files": ["a.py"],
                    "acceptance": ["ok"],
                }
            )
            + "\n",
            encoding="utf-8",
        )
        monkeypatch.setenv("CCC_WORKSPACE", str(ws))
        ccc_engine._stores.clear()
        with (
            patch.object(ccc_engine, "engine_log"),
            patch.object(
                ccc_engine,
                "_check_phase_failures",
                return_value={"unresolvable": True},
            ),
        ):
            removed = ccc_engine._handle_task_result(
                ws, tid, {"status": "failed", "retry": 0, "error": ""}
            )
        assert removed is True
        assert phases.is_file()
        assert (ws / ".ccc" / "board" / "abnormal" / f"{tid}.jsonl").is_file()
        assert not (ws / ".ccc" / "board" / "backlog" / f"{tid}.jsonl").exists()

    def test_process_backlog_epic_child_missing_phases_to_abnormal(
        self, tmp_path, monkeypatch
    ):
        ws = _mk_board_ws(tmp_path)
        tid = "epic-child-w3"
        _write_task(
            ws,
            "backlog",
            tid,
            card_kind="work",
            parent_id="epic-parent",
        )
        (ws / ".ccc" / "plans" / f"{tid}.plan.md").write_text("# plan\n", encoding="utf-8")
        monkeypatch.setenv("CCC_WORKSPACE", str(ws))
        ccc_engine._stores.clear()
        ccc_engine._degraded_mode = False
        with (
            patch.object(ccc_engine, "engine_log"),
            patch.object(ccc_engine, "_refresh_epic_statuses"),
            patch.object(ccc_engine, "_is_upstream_healthy", return_value=True),
        ):
            did = ccc_engine._process_backlog(ws)
        assert did is True
        assert (ws / ".ccc" / "board" / "abnormal" / f"{tid}.jsonl").is_file()
        assert not (ws / ".ccc" / "board" / "backlog" / f"{tid}.jsonl").exists()
