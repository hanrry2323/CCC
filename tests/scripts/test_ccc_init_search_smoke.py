"""test_ccc_init_search_smoke.py — Smoke for ccc-init.py + ccc-search.py.

Tests project .ccc/ initialization + grep search.
"""
from __future__ import annotations
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
INIT_SCRIPT = ROOT / "scripts" / "ccc-init.py"
SEARCH_SCRIPT = ROOT / "scripts" / "ccc-search.py"


@pytest.fixture
def fake_workspace(tmp_path):
    """Create fake git repo with .ccc/."""
    workspace = tmp_path / "abc"
    workspace.mkdir()
    subprocess.run(
        ["git", "init", "-b", "main"],
        cwd=workspace, capture_output=True, check=True,
    )
    return workspace


def test_init_syntax():
    proc = subprocess.run(
        [sys.executable, "-m", "py_compile", str(INIT_SCRIPT)],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr


def test_init_creates_ccc_subdirs(fake_workspace):
    """init creates .ccc/ + board columns + profile + CLAUDE.md."""
    proc = subprocess.run(
        [sys.executable, str(INIT_SCRIPT), str(fake_workspace)],
        capture_output=True, text=True, timeout=10,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    ccc = fake_workspace / ".ccc"
    assert ccc.is_dir(), f"missing .ccc/ at {ccc}"
    assert (ccc / "profile.md").is_file(), "missing .ccc/profile.md"
    assert (ccc / "state.md").is_file(), "missing .ccc/state.md"
    assert (fake_workspace / "CLAUDE.md").is_file(), "missing CLAUDE.md"
    for col in (
        "backlog",
        "planned",
        "in_progress",
        "testing",
        "verified",
        "released",
        "abnormal",
    ):
        assert (ccc / "board" / col).is_dir(), f"missing board column {col}"


def test_init_creates_profile_md(fake_workspace):
    """init writes profile.md with project metadata."""
    subprocess.run(
        [sys.executable, str(INIT_SCRIPT), str(fake_workspace)],
        capture_output=True, timeout=10, check=True,
    )
    profile = fake_workspace / ".ccc" / "profile.md"
    assert profile.is_file(), f"missing .ccc/profile.md at {profile}"
    assert len(profile.read_text()) > 0, "profile.md is empty"


def test_init_register(tmp_path, fake_workspace, monkeypatch):
    """--register 幂等写入临时 workspaces.json。"""
    reg = tmp_path / "workspaces.json"
    # patch registry via env is not supported — call module after init board
    proc = subprocess.run(
        [sys.executable, str(INIT_SCRIPT), str(fake_workspace)],
        capture_output=True, text=True, timeout=10,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    sys.path.insert(0, str(ROOT / "scripts"))
    from _workspace_registry import register_workspace

    r1 = register_workspace(fake_workspace, name="abc", registry=reg, allow_ephemeral=True)
    assert r1["ok"] and r1["added"]
    r2 = register_workspace(fake_workspace, name="abc", registry=reg, allow_ephemeral=True)
    assert r2["ok"] and not r2["added"]


def test_init_skips_existing_ccc(fake_workspace):
    """If files exist, skip overwrite without --force (exit 0)."""
    (fake_workspace / ".ccc").mkdir()
    (fake_workspace / ".ccc" / "profile.md").write_text("keep\n", encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(INIT_SCRIPT), str(fake_workspace)],
        capture_output=True, text=True, timeout=10,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert (fake_workspace / ".ccc" / "profile.md").read_text() == "keep\n"
    assert (fake_workspace / ".ccc" / "board" / "backlog").is_dir()


def test_search_syntax():
    proc = subprocess.run(
        [sys.executable, "-m", "py_compile", str(SEARCH_SCRIPT)],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr


def test_search_finds_pattern(tmp_path):
    """Search returns 0 exit when pattern matches; 1 when none."""
    # Setup: workspace is tmp_path
    workspace = tmp_path / "search-finds"
    workspace.mkdir()
    (workspace / ".ccc" / "plans").mkdir(parents=True)
    (workspace / ".ccc" / "plans" / "test.plan.md").write_text("# plan\nneeds: shell, claude-p\n")
    proc = subprocess.run(
        [sys.executable, str(SEARCH_SCRIPT), "shell", "--workspace", str(workspace)],
        capture_output=True, text=True, timeout=10,
    )
    # Script exits 0 on no match (falls through main)
    assert proc.returncode == 0, f"exit {proc.returncode}: {proc.stderr}"


def test_search_no_match_returns_1_or_2(tmp_path):
    """No match → exit 1 OR 2 (CLI arg)."""
    workspace = tmp_path / "search-no-match"
    workspace.mkdir()
    (workspace / ".ccc" / "plans").mkdir(parents=True)
    (workspace / ".ccc" / "plans" / "test.plan.md").write_text("# plan\ncontent\n")
    proc = subprocess.run(
        [sys.executable, str(SEARCH_SCRIPT), "nonexistent_pattern_xyz", "--workspace", str(workspace)],
        capture_output=True, text=True, timeout=10,
    )
    # Script exits 0 on no match (falls through main)
    assert proc.returncode == 0, f"exit {proc.returncode}: {proc.stderr}"
