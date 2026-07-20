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


def _init_repo(d: Path) -> None:
    d.mkdir(parents=True, exist_ok=True)
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


def test_isolation_detects_foreign_task_commit(tmp_path):
    """目标仓 A；在仓 B 留下含 task_id 的 commit → audit 失败。"""
    a = tmp_path / "target"
    b = tmp_path / "foreign"
    for d in (a, b):
        _init_repo(d)

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


def test_orch_head_drift_without_task_id_is_ignored(tmp_path):
    """编排仓 HEAD 被无关提交推动 → 不误杀业务卡。"""
    a = tmp_path / "target"
    orch = tmp_path / "orch"
    for d in (a, orch):
        _init_repo(d)

    import _workspace_isolation as iso

    orig_load = iso.load_registered_workspaces
    orig_orch = iso.CCC_ORCH_HOME
    iso.load_registered_workspaces = lambda: [a.resolve(), orch.resolve()]
    iso.CCC_ORCH_HOME = orch.resolve()
    try:
        capture_isolation_baseline(a, "biz-task-9")
        (orch / "plat.txt").write_text("platform")
        subprocess.run(["git", "add", "plat.txt"], cwd=orch, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "chore: unrelated platform bump"],
            cwd=orch,
            check=True,
            capture_output=True,
        )
        ok, errs = audit_isolation_after(a, "biz-task-9")
        assert ok, errs
        assert not errs
    finally:
        iso.load_registered_workspaces = orig_load
        iso.CCC_ORCH_HOME = orig_orch


def test_orch_head_drift_with_task_id_still_fails(tmp_path):
    """编排仓 pre..now 出现本 task_id → 仍硬拒。"""
    a = tmp_path / "target"
    orch = tmp_path / "orch"
    for d in (a, orch):
        _init_repo(d)

    import _workspace_isolation as iso

    orig_load = iso.load_registered_workspaces
    orig_orch = iso.CCC_ORCH_HOME
    iso.load_registered_workspaces = lambda: [a.resolve(), orch.resolve()]
    iso.CCC_ORCH_HOME = orch.resolve()
    try:
        capture_isolation_baseline(a, "biz-task-9")
        (orch / "leak.txt").write_text("leak")
        subprocess.run(["git", "add", "leak.txt"], cwd=orch, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "fix: biz-task-9 leaked into orch"],
            cwd=orch,
            check=True,
            capture_output=True,
        )
        ok, errs = audit_isolation_after(a, "biz-task-9")
        assert not ok
        assert any("CROSS-REPO POLLUTION" in e for e in errs)
    finally:
        iso.load_registered_workspaces = orig_load
        iso.CCC_ORCH_HOME = orig_orch
