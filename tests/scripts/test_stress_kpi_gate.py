"""Tests for stress KPI scorecard gate."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
GATE_PATH = REPO / "scripts" / "ccc-stress-kpi-gate.py"
SCORECARD = REPO / "references" / "stress-kpi-scorecard.json"


def _load_gate():
    spec = importlib.util.spec_from_file_location("ccc_stress_kpi_gate", GATE_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


GATE = _load_gate()


def _minimal_report(**over):
    base = {
        "run": "test-run",
        "generated_at": "2026-07-23T00:00:00+08:00",
        "work_columns": {"released": 10, "abnormal": 0, "in_progress": 0},
        "epic_split_status": {"done": 10, "failed": 0, "running": 0},
        "epics": [
            {"id": f"e{i}", "split_status": "done", "app": "ccc-demo", "col": "backlog"}
            for i in range(10)
        ]
        + [
            {"id": f"q{i}", "split_status": "done", "app": "qb", "col": "backlog"}
            for i in range(2)
        ],
        "works": [],
        "time_agg": {
            "queue_wait_s": {"p50": 50, "p95": 200, "n": 10},
            "queue_wait_indep_s": {"p50": 40, "p95": 180, "n": 8},
            "gate_wall_s": {"p50": 100, "p95": 400, "n": 10},
            "e2e_work_s": {"p50": 300, "p95": 900, "n": 10},
            "dev_wall_s": {"p50": 20, "p95": 100, "n": 10},
        },
        "opencode_timings": {"duration_s_fill_rate": 0.95},
        "dev_path": {"dirty_result_n": 0},
        "bottlenecks_hint": [],
    }
    base.update(over)
    return base


def test_scorecard_file_valid():
    sc = json.loads(SCORECARD.read_text(encoding="utf-8"))
    assert sc["profile"] == "efficiency_six"
    assert sc["rounds"]["max"] == 5
    assert any(g["id"] == "dirty_result_n" for g in sc["gates"])


def test_gate_pass():
    sc = GATE.load_scorecard()
    result = GATE.evaluate(_minimal_report(), sc)
    assert result["verdict"] == "PASS"
    assert result["all_ok"] is True


def test_gate_fail_abnormal():
    sc = GATE.load_scorecard()
    result = GATE.evaluate(
        _minimal_report(work_columns={"released": 8, "abnormal": 3, "in_progress": 0}),
        sc,
    )
    assert result["verdict"] == "FAIL"
    assert "work_abnormal_n" in result["primary_fail"]


def test_gate_invalid_duration():
    sc = GATE.load_scorecard()
    # only duration fails → INVALID
    rep = _minimal_report()
    rep["opencode_timings"] = {"duration_s_fill_rate": 0.0}
    result = GATE.evaluate(rep, sc)
    assert result["verdict"] == "INVALID"


def test_gate_hard_red_dirty():
    sc = GATE.load_scorecard()
    rep = _minimal_report()
    rep["dev_path"] = {"dirty_result_n": 2}
    result = GATE.evaluate(rep, sc)
    assert result["verdict"] == "FAIL"
    assert any(g["id"] == "dirty_result_n" and not g["ok"] for g in result["gates"])


def test_ghost_heuristic():
    sc = GATE.load_scorecard()
    rep = _minimal_report(
        work_columns={"released": 10, "abnormal": 0, "in_progress": 1},
        works=[
            {
                "id": "x-w1",
                "col": "in_progress",
                "title": "Phase 1 — `.ccc/board`",
                "t_testing": None,
                "dev_wall_s": None,
                "gate_wall_s": None,
            }
        ],
    )
    # also need epic rate etc still pass — 12 done already
    result = GATE.evaluate(rep, sc)
    assert result["computed"]["ghost_in_progress_n"] == 1
    assert result["verdict"] == "FAIL"
    assert "ghost_in_progress_n" in result["primary_fail"]


def test_epic_done_inferred_from_dispatch():
    rep = _minimal_report(
        dispatch={"ok": 12, "n": 12, "rows": [{}] * 12},
    )
    rep["epics"] = [
        {"id": "a", "split_status": "failed", "app": "x", "col": "backlog"},
        {"id": "b", "split_status": "failed", "app": "x", "col": "backlog"},
        {"id": "c", "split_status": "running", "app": "x", "col": "backlog"},
        {"id": "d", "split_status": "running", "app": "x", "col": "backlog"},
    ]
    rep["epic_split_status"] = {"failed": 2, "running": 2}
    enriched = GATE.enrich_computed(rep)
    assert enriched["computed"]["epic_done_n"] == 8
    assert enriched["computed"]["epic_done_rate"] == 0.6667


def test_cli_exit_codes(tmp_path: Path):
    good = tmp_path / "good-efficiency.json"
    good.write_text(json.dumps(_minimal_report(run="good")), encoding="utf-8")
    assert GATE.main(["--efficiency", str(good), "--out", str(tmp_path)]) == 0

    bad = tmp_path / "bad-efficiency.json"
    bad.write_text(
        json.dumps(
            _minimal_report(
                run="bad",
                work_columns={"released": 5, "abnormal": 5, "in_progress": 0},
            )
        ),
        encoding="utf-8",
    )
    assert GATE.main(["--efficiency", str(bad), "--out", str(tmp_path)]) == 1
