"""Hollow OpenCode / false SELF-CHECKS gate (v0.52)."""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from _opencode_quality_gate import (  # noqa: E402
    detect_hollow_opencode_run,
    report_has_self_checks_passed,
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


def test_report_marker():
    assert report_has_self_checks_passed("x\nALL SELF-CHECKS PASSED\n")
    assert not report_has_self_checks_passed("almost passed")


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
