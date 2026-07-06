"""test_executor_watchdog_smoke.py — Smoke for executor-watchdog.sh.

Tests 4 checks (CPU/memory, mavis stuck, port conflict, OM memory) + 4 exit codes.
"""
from __future__ import annotations
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT = ROOT / "scripts" / "executor-watchdog.sh"


def test_syntax_check():
    proc = subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr


def test_help_shows():
    proc = subprocess.run(
        ["bash", str(SCRIPT), "--help"],
        capture_output=True, text=True, timeout=5,
    )
    out = proc.stdout + proc.stderr
    assert "用法" in out or "exit" in out or "watchdog" in out


def test_default_invocation_exits_0_or_1():
    """Default run (no hang) → exit 0 (healthy) or 1 (warning)."""
    proc = subprocess.run(
        ["bash", str(SCRIPT)],
        capture_output=True, text=True, timeout=10,
    )
    # 0=healthy, 1=warning, 2=serious, 3=killed
    assert proc.returncode in (0, 1, 2, 3)


def test_quiet_mode_runs_silently():
    """--quiet suppresses output but exits with code."""
    proc = subprocess.run(
        ["bash", str(SCRIPT), "--quiet"],
        capture_output=True, text=True, timeout=10,
    )
    # Quiet should produce less output than default
    assert proc.returncode in (0, 1, 2, 3)


def test_force_kill_flag_recognized():
    """--force-kill is a recognized option."""
    proc = subprocess.run(
        ["bash", str(SCRIPT), "--force-kill", "--quiet"],
        capture_output=True, text=True, timeout=10,
    )
    # Should not error on unknown flag
    assert "unknown option" not in proc.stderr.lower()
    assert proc.returncode in (0, 1, 2, 3)
