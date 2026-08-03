"""docs-only / doc_only stamps must skip forced full-repo pytest."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))


def test_docs_only_scope_skips_forced_pytest(tmp_path: Path):
    from _ccc_hygiene import scopes_are_docs_only, task_skips_forced_pytest

    assert scopes_are_docs_only(["docs/reports/stamp.md"]) is True
    assert scopes_are_docs_only(["scripts/x.py"]) is False

    ws = tmp_path / "app"
    tid = "doc-w1"
    (ws / ".ccc" / "phases").mkdir(parents=True)
    (ws / ".ccc" / "reports").mkdir(parents=True)
    (ws / ".ccc" / "phases" / f"{tid}.phases.json").write_text(
        json.dumps({"phase": 1, "scope": ["docs/reports/ccc-layer1-golden-path-v3.md"]})
        + "\n",
        encoding="utf-8",
    )
    task = {
        "id": tid,
        "title": "Layer1 文档戳记报告 v3",
        "tags": ["exec:opencode"],
    }
    assert task_skips_forced_pytest(ws, tid, task) is True

    # path=doc_only also skips even with empty scopes
    tid2 = "doc-w2"
    (ws / ".ccc" / "phases" / f"{tid2}.phases.json").write_text(
        json.dumps({"phase": 1, "scope": []}) + "\n", encoding="utf-8"
    )
    (ws / ".ccc" / "reports" / f"{tid2}.result.json").write_text(
        json.dumps({"path": "doc_only"}) + "\n", encoding="utf-8"
    )
    assert task_skips_forced_pytest(ws, tid2, {"id": tid2, "title": "x"}) is True


def test_doc_only_acceptance_does_not_append_cov_suite(tmp_path: Path):
    """Layer2 stamp cards: acceptance probe only — no forced cov pytest."""
    from board.roles.tester import build_tester_verify_commands

    ws = tmp_path / "qb"
    tid = "layer2-stamp-w1"
    (ws / ".ccc" / "reports").mkdir(parents=True)
    (ws / ".ccc" / "phases").mkdir(parents=True)
    (ws / "pyproject.toml").write_text("[project]\nname='qb'\n", encoding="utf-8")
    (ws / ".ccc" / "reports" / f"{tid}.result.json").write_text(
        json.dumps({"path": "doc_only", "ok": True}) + "\n", encoding="utf-8"
    )
    (ws / ".ccc" / "phases" / f"{tid}.phases.json").write_text(
        json.dumps({"phase": 1, "scope": ["docs/reports/layer2-open-lpsn-evidence.md"]})
        + "\n",
        encoding="utf-8",
    )
    plan_cmds = [
        "DRY_RUN=true .venv/bin/python scripts/paper_intent_probe.py --env paper",
    ]
    cmds, skip = build_tester_verify_commands(
        ws, tid, plan_commands=plan_cmds, task_meta={"id": tid, "title": "stamp"}
    )
    assert skip is True
    assert cmds == plan_cmds
    assert not any("cov-fail-under" in c for c in cmds)


def test_empty_plan_falls_back_to_scripts_pytest_not_cov(tmp_path: Path):
    """No plan probes → scripts/ tests fallback; cov only when that path lacks pytest."""
    from board.roles.tester import build_tester_verify_commands

    ws = tmp_path / "app"
    tid = "feat-w1"
    (ws / ".ccc" / "reports").mkdir(parents=True)
    (ws / ".ccc" / "phases").mkdir(parents=True)
    (ws / "pyproject.toml").write_text("[project]\nname='app'\n", encoding="utf-8")
    (ws / ".ccc" / "phases" / f"{tid}.phases.json").write_text(
        json.dumps({"phase": 1, "scope": ["src/main.py"]}) + "\n", encoding="utf-8"
    )
    cmds, skip = build_tester_verify_commands(
        ws, tid, plan_commands=[], task_meta={"id": tid, "title": "feature"}
    )
    assert skip is False
    assert any("pytest" in c for c in cmds)
    # scripts fallback already contains pytest → cov suite is not piled on
    assert not any("cov-fail-under" in c for c in cmds)


def test_plan_probes_do_not_append_cov_suite(tmp_path: Path):
    """Open-intent / script_seed: plan python3 -c assert must not force qb cov."""
    from board.roles.tester import build_tester_verify_commands

    ws = tmp_path / "qb"
    tid = "open-intent-r7-w1"
    (ws / ".ccc" / "reports").mkdir(parents=True)
    (ws / ".ccc" / "phases").mkdir(parents=True)
    (ws / "pyproject.toml").write_text("[project]\nname='qb'\n", encoding="utf-8")
    (ws / ".ccc" / "phases" / f"{tid}.phases.json").write_text(
        json.dumps({"phase": 1, "scope": ["scripts/ccc_open_intent_r7_probe.py"]})
        + "\n",
        encoding="utf-8",
    )
    plan_cmds = [
        "test -f scripts/ccc_open_intent_r7_probe.py",
        "python3 -m py_compile scripts/ccc_open_intent_r7_probe.py",
        "python3 -c \"from scripts.ccc_open_intent_r7_probe import open_intent_r7_ok; "
        "assert open_intent_r7_ok() == 'CCC_OPEN_INTENT_R7_OK v0.63'\"",
    ]
    cmds, skip = build_tester_verify_commands(
        ws, tid, plan_commands=plan_cmds, task_meta={"id": tid, "title": "R7"}
    )
    assert skip is False
    assert cmds == plan_cmds
    assert not any("cov-fail-under" in c for c in cmds)
