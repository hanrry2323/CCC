from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "ccc-desktop-stability-report.py"
SPEC = importlib.util.spec_from_file_location("ccc_desktop_stability_report", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)
build_report = module.build_report


def test_build_report_matches_turn_ids_and_percentiles():
    desktop = [
        {"event": "ok", "turn_id": "t1", "duration_ms": 100, "first_delta_ms": 40},
        {"event": "fail", "turn_id": "t2", "duration_ms": 300, "code": "tool_stall"},
        {"event": "flow_disconnected", "projectId": "demo"},
        {"event": "hub_reachability", "reachable": False},
    ]
    sidecar = [
        {"event": "turn_end", "turn_id": "t1", "code": ""},
        {"event": "turn_end", "turn_id": "t2", "code": "tool_stall"},
    ]

    report = build_report(desktop, sidecar)

    assert "Success rate: **50.00%**" in report
    assert "Cross-layer matched `turn_id`: **2**" in report
    assert "Turn duration P50 / P95: **100 ms / 300 ms**" in report
    assert "`tool_stall`" in report
    assert "`flow_disconnected`" in report
