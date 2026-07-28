"""Hollow OpenCode / false SELF-CHECKS gate (v0.52)."""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from _opencode_quality_gate import (  # noqa: E402
    agent_declared_self_checks_passed,
    detect_hollow_opencode_run,
    detect_hollow_phase_scope,
    report_has_self_checks_passed,
    _scope_intersects_names,
)
from _task_commit import porcelain_product_paths  # noqa: E402
from _workspace_isolation import cwd_hardgate_block  # noqa: E402
from board.prompt import build_dev_phase_prompt  # noqa: E402


def test_detect_external_directory_auto_reject():
    raw = (
        "permission requested: external_directory (/Users/fan/.ccc/*); "
        "auto-rejecting\n"
        "Error: The user rejected permission to use this tool from "
        "/Users/fan/.ccc/state.md\n"
    )
    reason = detect_hollow_opencode_run(raw, "ALL SELF-CHECKS PASSED\n")
    assert reason is not None
    assert "external_directory" in reason


def test_detect_clean_run_ok():
    raw = "wrote README.md\ncommit ok\n"
    assert detect_hollow_opencode_run(raw, "ALL SELF-CHECKS PASSED") is None


def test_scope_intersects_names():
    assert _scope_intersects_names(
        ["tests/test_ccc_loop_r3_util.py"],
        ["tests/test_ccc_loop_r3_util.py"],
    )
    assert not _scope_intersects_names(
        ["tests/test_ccc_loop_r3_util.py"],
        ["scripts/ccc_loop_r3_util.py"],
    )


def test_hollow_phase_reused_commit_without_scope(tmp_path):
    """phase2 reusing phase1 commit that only touched scripts/ → hollow."""
    import subprocess

    ws = tmp_path / "app"
    ws.mkdir()
    subprocess.run(["git", "init"], cwd=ws, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "t@t"], cwd=ws, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "config", "user.name", "t"], cwd=ws, check=True, capture_output=True
    )
    (ws / "scripts").mkdir()
    (ws / "tests").mkdir()
    (ws / "scripts" / "ccc_loop_r3_util.py").write_text("def f():\n    return 1\n")
    (ws / "tests" / "test_ccc_loop_r3_util.py").write_text("def test_f():\n    assert True\n")
    subprocess.run(["git", "add", "-A"], cwd=ws, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init"], cwd=ws, check=True, capture_output=True
    )
    (ws / "scripts" / "ccc_loop_r3_util.py").write_text(
        "def f():\n    return 1\n\ndef loop_r5_stamp():\n    return 'ok'\n"
    )
    subprocess.run(["git", "add", "-A"], cwd=ws, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "task-r5-w1 phase=1"],
        cwd=ws,
        check=True,
        capture_output=True,
    )
    commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ws, text=True
    ).strip()
    phases = [
        {"phase": 1, "status": "done", "commit": commit, "scope": ["scripts/ccc_loop_r3_util.py"]},
        {
            "phase": 2,
            "status": "pending",
            "commit": commit,
            "scope": ["tests/test_ccc_loop_r3_util.py"],
        },
    ]
    reason = detect_hollow_phase_scope(
        ws,
        phase_num=2,
        scope=["tests/test_ccc_loop_r3_util.py"],
        task_commit=commit,
        phases=phases,
    )
    assert reason is not None
    assert "reused commit" in reason
    assert detect_hollow_phase_scope(
        ws,
        phase_num=1,
        scope=["scripts/ccc_loop_r3_util.py"],
        task_commit=commit,
        phases=phases,
    ) is None


def test_report_marker():
    assert report_has_self_checks_passed("x\nALL SELF-CHECKS PASSED\n")
    assert not report_has_self_checks_passed("almost passed")


def test_agent_declared_from_result_stdout():
    result = (
        '{"phase_id":"t-p1","exit_code":0,'
        '"stdout":"done\\nALL SELF-CHECKS PASSED\\n","stderr":""}'
    )
    assert agent_declared_self_checks_passed("", result)
    assert agent_declared_self_checks_passed("stub without marker", result)
    assert not agent_declared_self_checks_passed(
        "stub", '{"stdout":"no marker yet","exit_code":0}'
    )


def test_porcelain_ignores_ccc_meta():
    porcelain = (
        " M .ccc/state.md\n"
        " M .ccc/board/index.json\n"
        " M README.md\n"
        "?? .ccc/flow-smoke.md\n"
    )
    got = porcelain_product_paths(porcelain)
    assert got == ["README.md", ".ccc/flow-smoke.md"]


def test_porcelain_only_ccc_is_empty():
    assert porcelain_product_paths(" M .ccc/state.md\n") == []


def test_hardgate_forbids_home_ccc():
    ws = Path("/tmp/demo-app")
    text = cwd_hardgate_block(ws)
    assert "禁止" in text
    assert "/.ccc/" in text or ".ccc/" in text
    assert "external_directory" in text
    assert str(ws.resolve()) in text


def test_prompt_paths_and_no_invent_pass():
    ws = "/tmp/ccc-demo-ws"
    Path(ws).mkdir(parents=True, exist_ok=True)
    text = build_dev_phase_prompt("t1", 1, "## plan", workspace=ws)
    assert f"{Path(ws).resolve()}/.ccc/state.md" in text
    assert "禁止" in text and "~/.ccc/" in text
    assert "门禁不代写" in text
