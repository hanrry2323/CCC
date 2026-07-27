"""test_reviewer_verdict_failsafe.py — Phase C: reviewer no-verdict → FAIL verdict first.

Covers:
- _write_fail_verdict_before_quarantine creates verdict file with FAIL
- Existing verdict file is NOT overwritten
- All three quarantine sites in gates.py produce a FAIL verdict
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def ws(tmp_path: Path) -> Path:
    w = tmp_path / "ws"
    (w / ".ccc" / "verdicts").mkdir(parents=True)
    return w


@pytest.fixture(scope="module")
def _gates():
    """Load gates module once per module."""
    import importlib.util

    repo = Path(__file__).resolve().parents[2]
    gate_path = repo / "scripts" / "engine" / "gates.py"
    spec = importlib.util.spec_from_file_location(
        "engine.gates_test", gate_path
    )
    assert spec and spec.loader, f"cannot load {gate_path}"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── _write_fail_verdict_before_quarantine ─────────────────────────────────


def test_write_fail_verdict_creates_file(ws: Path, _gates):
    """Calling _write_fail_verdict_before_quarantine creates a verdict file with FAIL."""
    tid = "stress-mx-20260728-kpi-r1-w1"
    reason = "reviewer produced no verdict"
    _gates._write_fail_verdict_before_quarantine(ws, tid, reason)

    vf = ws / ".ccc" / "verdicts" / f"{tid}.verdict.md"
    assert vf.is_file(), f"verdict file not created at {vf}"
    content = vf.read_text(encoding="utf-8")
    assert "FAIL" in content, f"expected FAIL in verdict, got: {content}"
    assert reason in content, f"expected reason '{reason}' in verdict, got: {content}"


def test_write_fail_verdict_does_not_overwrite_existing(ws: Path, _gates):
    """If a verdict file already exists, do NOT overwrite it."""
    tid = "stress-mx-20260728-kpi-r1-w2"
    vf = ws / ".ccc" / "verdicts" / f"{tid}.verdict.md"
    vf.write_text(
        f"# {tid} Verdict\n\n**Verdict:** PASS\n\n**Reason:** all good\n",
        encoding="utf-8",
    )
    orig = vf.read_text(encoding="utf-8")

    # Call helper — should NOT overwrite the existing PASS verdict
    _gates._write_fail_verdict_before_quarantine(
        ws, tid, "reviewer produced no verdict"
    )
    assert vf.read_text(encoding="utf-8") == orig, "existing verdict was overwritten"


def test_write_fail_verdict_no_verdict_dir_creates_it(tmp_path: Path, _gates):
    """Even if verdicts/ directory does not exist, the helper creates it."""
    ws = tmp_path / "ws_no_verdict_dir"
    tid = "no-dir-test"
    _gates._write_fail_verdict_before_quarantine(
        ws, tid, "verdict directory missing"
    )
    vf = ws / ".ccc" / "verdicts" / f"{tid}.verdict.md"
    assert vf.is_file()
    assert "FAIL" in vf.read_text(encoding="utf-8")


def test_three_reasons_distinct(ws: Path, _gates):
    """All three quarantine reasons produce distinct verdict bodies."""
    reasons_and_tids = [
        ("stress-a", "retry budget exceeded (reviewer)"),
        ("stress-b", "reviewer timeout retries exhausted"),
        ("stress-c", "reviewer produced no verdict"),
    ]
    for tid, reason in reasons_and_tids:
        _gates._write_fail_verdict_before_quarantine(ws, tid, reason)
        vf = ws / ".ccc" / "verdicts" / f"{tid}.verdict.md"
        assert vf.is_file(), f"file for {tid} not created"
        content = vf.read_text(encoding="utf-8")
        assert "FAIL" in content, f"{tid}: expected FAIL"
        assert reason in content, f"{tid}: expected reason '{reason}'"
