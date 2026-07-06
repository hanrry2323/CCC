"""test_flywheel_scan_smoke.py — Smoke for flywheel-scan.py (v0.7).

Tests:
1. Reads .ccc/reports/*.md + .ccc/verdicts/*.md
2. Extracts 6 failure pattern categories
3. Dedupe by sha256
4. Writes ONLY to abnormal-reports/ (NEVER docs/lessons.md) — RED LINE 14

Note: subprocess doesn't inherit pytest monkeypatch.chdir. Each test creates
its own subdir under tmp_path and uses cwd= on run().
"""
from __future__ import annotations
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT = ROOT / "scripts" / "flywheel-scan.py"


def test_syntax_check():
    proc = subprocess.run(
        [sys.executable, "-m", "py_compile", str(SCRIPT)],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr


def test_no_ccc_dir_exits_zero_with_no_findings(tmp_path):
    """If .ccc/ doesn't exist, flywheel creates it + reports 'no findings' (graceful)."""
    workspace = tmp_path / "no-ccc"
    workspace.mkdir()
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=workspace,
        capture_output=True, text=True, timeout=5,
    )
    # Graceful exit 0 (no findings) — flywheel auto-creates .ccc/ structure
    assert proc.returncode == 0
    assert "no findings" in proc.stdout.lower()


def test_empty_reports_succeeds_silently(tmp_path):
    """Empty .ccc/reports + .ccc/verdicts → flywheel reports 'no findings'."""
    workspace = tmp_path / "no-findings"
    workspace.mkdir()
    (workspace / ".ccc" / "reports").mkdir(parents=True)
    (workspace / ".ccc" / "verdicts").mkdir(parents=True)
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=workspace,
        capture_output=True, text=True, timeout=5,
    )
    assert proc.returncode == 0
    out = proc.stdout.lower()
    assert "no findings" in out or "nothing to propose" in out
    # No candidate should be written
    candidates = list((workspace / ".ccc" / "abnormal-reports").glob("flywheel-candidate-*.md"))
    assert candidates == [], f"unexpected candidates: {candidates}"


def test_extracts_failure_patterns(tmp_path):
    """Reports containing failure words produce a candidate."""
    workspace = tmp_path / "extracts"
    workspace.mkdir()
    (workspace / ".ccc" / "reports").mkdir(parents=True)
    (workspace / ".ccc" / "verdicts").mkdir(parents=True)
    (workspace / ".ccc" / "abnormal-reports").mkdir(parents=True)
    (workspace / ".ccc" / "reports" / "task1.report.md").write_text(
        "## Task Failed\nFound circular import at line 42. Critical timeout occurred.\n"
    )
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=workspace,
        capture_output=True, text=True, timeout=5,
    )
    assert proc.returncode == 0
    assert "[flywheel]" in proc.stdout
    assert "wrote candidate" in proc.stdout.lower()
    candidates = list((workspace / ".ccc" / "abnormal-reports").glob("flywheel-candidate-*.md"))
    assert len(candidates) == 1, f"expected 1 candidate, got {len(candidates)}"
    content = candidates[0].read_text()
    assert "circular" in content.lower() or "circular_import" in content


def test_red_line_14_no_write_outside_abnormal_reports(tmp_path):
    """RED LINE 14: flywheel NEVER writes to docs/lessons.md."""
    workspace = tmp_path / "red-line-14"
    workspace.mkdir()
    (workspace / ".ccc" / "reports").mkdir(parents=True)
    (workspace / ".ccc" / "verdicts").mkdir(parents=True)
    (workspace / ".ccc" / "abnormal-reports").mkdir(parents=True)
    (workspace / "docs").mkdir()
    (workspace / ".ccc" / "reports" / "t.report.md").write_text("ERROR timeout found\n")
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=workspace,
        capture_output=True, text=True, timeout=5,
    )
    assert proc.returncode == 0
    # docs/ must NOT be touched (no .md files created by flywheel)
    docs_md = list((workspace / "docs").glob("*.md"))
    assert docs_md == [], f"flywheel touched docs/: {docs_md}"
