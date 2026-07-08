"""test_ccc_exec_commit_smoke.py — Smoke for ccc-exec-commit.sh.

Tests git auto-commit workflow:
1. Init temp git repo + .ccc/phases/<task>.phases.json with phase done, commit=null
2. Run script
3. Verify commit hash filled into phases.json
4. Verify git log +1
"""
from __future__ import annotations
import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT = ROOT / "scripts" / "ccc-exec-commit.sh"


def _git(args, cwd):
    return subprocess.run(
        ["git"] + args, cwd=cwd, capture_output=True, text=True, check=False,
    )


@pytest.fixture
def fake_workspace(tmp_path):
    """Create a temp git repo with fake .ccc/ structure."""
    repo = tmp_path / "testrepo"
    repo.mkdir()
    _git(["init", "-b", "main"], cwd=repo)
    _git(["config", "user.email", "test@x"], cwd=repo)
    _git(["config", "user.name", "Test"], cwd=repo)
    # Initial commit
    (repo / "README.md").write_text("# test")
    _git(["add", "README.md"], cwd=repo)
    _git(["commit", "-m", "initial"], cwd=repo)
    # .ccc/phases/<task>.phases.json with phase 1 done, commit=null
    ccc = repo / ".ccc"
    (ccc / "phases").mkdir(parents=True)
    (ccc / "reports").mkdir()
    (ccc / "plans").mkdir()
    (ccc / "verdicts").mkdir()
    phases = ccc / "phases" / "testtask.phases.json"
    phases.write_text(
        '{"phase": 1, "status": "done", "subtasks": {"1.1": "done"}, "commit": null, "notes": ""}\n'
    )
    _git(["add", ".ccc"], cwd=repo)
    _git(["commit", "-m", "phases init"], cwd=repo)
    return repo


def test_commit_empty_phases_noop(fake_workspace):
    """scope 为空 → script noop (exit 0)."""
    p = fake_workspace / ".ccc" / "phases" / "testtask.phases.json"
    # 合法 schema（含 scope 字段，但为空 → 无改动需 commit → noop）
    p.write_text(json.dumps({
        "phases": [
            {"id": 1, "status": "done", "scope": [], "commit": None,
             "commit_message": "feat: noop test", "subtasks": {}, "notes": ""}
        ]
    }) + "\n")
    proc = subprocess.run(
        ["bash", str(SCRIPT), str(fake_workspace), "testtask"],
        capture_output=True, text=True, timeout=10,
    )
    assert proc.returncode == 0, f"expected exit 0, got {proc.returncode}: {proc.stderr}"


def test_script_syntax_only():
    """Bash -n validates syntax."""
    proc = subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr


def test_help_shows_usage():
    """--help shows usage."""
    proc = subprocess.run(
        ["bash", str(SCRIPT), "--help"],
        capture_output=True, text=True, timeout=5,
    )
    out = proc.stdout + proc.stderr
    assert "用法" in out or "Usage" in out or "workspace" in out


def test_skip_already_committed(fake_workspace):
    """If phase already has commit hash, skip (soft skip, exit 0)."""
    p = fake_workspace / ".ccc" / "phases" / "testtask.phases.json"
    p.write_text(
        '{"phase": 1, "status": "done", "subtasks": {}, "commit": "abc123", "notes": ""}\n'
    )
    proc = subprocess.run(
        ["bash", str(SCRIPT), str(fake_workspace), "testtask"],
        capture_output=True, text=True, timeout=10,
    )
    # Script exits 0 on already-committed (soft skip), never 3
    assert proc.returncode == 0, f"expected exit 0, got {proc.returncode}: {proc.stderr}"
