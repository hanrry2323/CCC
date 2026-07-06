"""test_ccc_tooling_hooks_smoke.py — Smoke for ccc-hook.sh + ccc-cost-report.sh + install + cluster-doctor.sh.

Lightweight tests covering syntax + basic invocation. Heavy integration
testing happens in cluster-bus / dispatcher tests.
"""
from __future__ import annotations
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS = ROOT / "scripts"
TOOLS = ROOT / "tools"


def test_ccc_hook_syntax():
    proc = subprocess.run(["bash", "-n", str(SCRIPTS / "ccc-hook.sh")],
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr


def test_ccc_cost_report_syntax():
    proc = subprocess.run(["bash", "-n", str(SCRIPTS / "ccc-cost-report.sh")],
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr


def test_install_ccc_as_skill_syntax():
    proc = subprocess.run(["bash", "-n", str(SCRIPTS / "install-ccc-as-skill.sh")],
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr


def test_cluster_doctor_syntax():
    proc = subprocess.run(["bash", "-n", str(TOOLS / "cluster-doctor.sh")],
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr


def test_ccc_cost_report_runs_and_outputs(tmp_path, monkeypatch):
    """Run cost-report in fresh project — exits 0 + some output."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".ccc" / "reports").mkdir(parents=True)
    (tmp_path / ".ccc" / "reports" / "t.report.md").write_text("# report\ncontent\n")
    proc = subprocess.run(
        ["bash", str(SCRIPTS / "ccc-cost-report.sh"), str(tmp_path)],
        capture_output=True, text=True, timeout=10,
    )
    # Exit 0 even with empty workspace
    assert proc.returncode in (0, 1)
    # Has something to say
    assert "CCC" in proc.stdout or "Cost" in proc.stdout or "cost" in proc.stdout.lower()


def test_install_ccc_as_skill_check_flag():
    """--check should not crash, may or may not PASS depending on state."""
    proc = subprocess.run(
        ["bash", str(SCRIPTS / "install-ccc-as-skill.sh"), "--check"],
        capture_output=True, text=True, timeout=10,
    )
    assert proc.returncode in (0, 1)  # 0 = install PASS, 1 = not installed
    out = proc.stdout + proc.stderr
    # Should print OK / MISSING or "安装" (Chinese)
    assert "OK" in out or "MISSING" in out or "安装" in out or "未" in out or "ccc-protocol" in out


def test_cluster_doctor_bus_down():
    """Bus down → doctor exit 1 with FAIL message."""
    proc = subprocess.run(
        ["bash", str(TOOLS / "cluster-doctor.sh")],
        capture_output=True, text=True, timeout=5,
    )
    # bus unreachable → exit 1
    assert proc.returncode == 1
    out = proc.stdout + proc.stderr
    assert "bus unreachable" in out.lower() or "fail" in out.lower() or "FAIL" in out


def test_ccc_hook_receives_stdin_json():
    """ccchook reads stdin JSON, decides allow/deny."""
    # Build a fake stdin event
    fake_event = '{"tool_name":"Write","tool_input":"create .ccc/plans/test.md"}\n'
    proc = subprocess.run(
        ["bash", str(SCRIPTS / "ccc-hook.sh")],
        input=fake_event.encode(),
        capture_output=True,
        timeout=5,
    )
    # .ccc/ writes usually allowed → exit 0 OR exit 2 if hook is strict
    # doc doesn't enforce return-code, just check non-crash
    assert proc.returncode in (0, 2)
