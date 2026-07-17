"""Workspace isolation: opencode --dir/--pure + cross-repo audit."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

_EXEC = SCRIPTS / "opencode-exec.py"
_spec = importlib.util.spec_from_file_location("_ccc_opencode_exec", _EXEC)
_mod = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(_mod)
build_opencode_run_cmd = _mod.build_opencode_run_cmd

from _workspace_isolation import (  # noqa: E402
    audit_isolation_after,
    capture_isolation_baseline,
    require_cwd,
)


def test_build_cmd_includes_dir_and_pure(tmp_path):
    cmd = build_opencode_run_cmd(
        "opencode",
        "loop/code",
        message="do it",
        cwd=tmp_path,
    )
    assert "--dir" in cmd
    assert str(tmp_path.resolve()) in cmd
    assert "--pure" in cmd
    assert cmd[cmd.index("--dir") + 1] == str(tmp_path.resolve())


def test_build_cmd_requires_cwd():
    with pytest.raises(ValueError, match="cwd required"):
        build_opencode_run_cmd("opencode", "loop/code", message="x", cwd=None)


def test_build_cmd_with_prompt_file_keeps_dir(tmp_path):
    cmd = build_opencode_run_cmd(
        "opencode",
        "loop/code",
        message="Read attached file",
        prompt_file="/tmp/p.md",
        cwd=tmp_path,
    )
    assert "--dir" in cmd
    assert "--file" in cmd


def test_require_cwd_rejects_empty():
    with pytest.raises(ValueError):
        require_cwd("")


def test_isolation_detects_foreign_task_commit(tmp_path):
    """目标仓 A；在仓 B 留下含 task_id 的 commit → audit 失败。"""
    a = tmp_path / "target"
    b = tmp_path / "foreign"
    for d in (a, b):
        d.mkdir()
        subprocess.run(["git", "init"], cwd=d, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "t@t.com"],
            cwd=d,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "t"],
            cwd=d,
            check=True,
            capture_output=True,
        )
        (d / "f.txt").write_text("x")
        subprocess.run(["git", "add", "f.txt"], cwd=d, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "init"], cwd=d, check=True, capture_output=True
        )

    import _workspace_isolation as iso

    orig_load = iso.load_registered_workspaces
    orig_orch = iso.CCC_ORCH_HOME
    iso.load_registered_workspaces = lambda: [a.resolve(), b.resolve()]
    iso.CCC_ORCH_HOME = b.resolve()
    try:
        capture_isolation_baseline(a, "task-pollute-1")
        (b / "g.txt").write_text("pollute")
        subprocess.run(["git", "add", "g.txt"], cwd=b, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "feat: task-pollute-1 oops"],
            cwd=b,
            check=True,
            capture_output=True,
        )
        ok, errs = audit_isolation_after(a, "task-pollute-1")
        assert not ok
        assert any("CROSS-REPO POLLUTION" in e for e in errs)
    finally:
        iso.load_registered_workspaces = orig_load
        iso.CCC_ORCH_HOME = orig_orch
