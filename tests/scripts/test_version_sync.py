"""Regression tests for version consistency gate."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_check_version_sync_passes():
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check-version-sync.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "VERSION sync OK" in proc.stdout
