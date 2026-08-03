"""Acceptance strength: block existence-only false greens."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))


def test_classify_existence_and_behavioral():
    from _acceptance_strength import classify_cmd, cmds_are_existence_only, is_strong_enough

    assert classify_cmd("test -f scripts/x.py") == "existence_only"
    assert classify_cmd("python3 -m py_compile scripts/x.py") == "compile_only"
    assert (
        classify_cmd(
            "python3 -c \"from scripts.x import f; assert f()=='OK'\""
        )
        == "behavioral"
    )
    assert classify_cmd("python3 -m pytest -q tests/test_x.py") == "behavioral"
    assert classify_cmd("grep -qx 'OK' docs/a.md") == "behavioral"

    weak = ["test -f scripts/x.py", "test -d .ccc/board"]
    assert cmds_are_existence_only(weak) is True
    ok, reason = is_strong_enough(weak, require_strong=True)
    assert ok is False
    assert reason == "acceptance_weak_existence_only"

    strong = [
        "test -f scripts/x.py",
        "python3 -c \"assert True\"",
    ]
    ok, reason = is_strong_enough(strong, require_strong=True)
    assert ok is True


def test_phase_lint_rejects_existence_only():
    from phase_lint import validate_plan_acceptance

    plan = "## 验收\n- test -f scripts/foo.py\n"
    ok, errs = validate_plan_acceptance(plan, require_probe=True)
    assert ok is False
    assert any("weak" in e or "existence" in e for e in errs)


def test_phase_lint_accepts_python_assert():
    from phase_lint import validate_plan_acceptance

    plan = (
        "## 验收\n"
        "- python3 -c \"from scripts.ccc_open_intent_r7_probe import open_intent_r7_ok; "
        "assert open_intent_r7_ok()=='CCC_OPEN_INTENT_R7_OK v0.63'\"\n"
    )
    ok, errs = validate_plan_acceptance(plan, require_probe=True)
    assert ok is True, errs


def test_check_acceptance_blocks_existence_only(tmp_path: Path):
    from _acceptance_gate import check_acceptance

    ws = tmp_path / "app"
    tid = "weak-w1"
    (ws / ".ccc" / "plans").mkdir(parents=True)
    (ws / ".ccc" / "board" / "testing").mkdir(parents=True)
    (ws / "scripts").mkdir(parents=True)
    (ws / "scripts" / "foo.py").write_text("x=1\n", encoding="utf-8")
    (ws / ".ccc" / "board" / "testing" / f"{tid}.jsonl").write_text(
        json.dumps({"id": tid, "title": "feature", "pipeline": "dev"}) + "\n",
        encoding="utf-8",
    )
    (ws / ".ccc" / "plans" / f"{tid}.plan.md").write_text(
        "## 验收\n- test -f scripts/foo.py\n", encoding="utf-8"
    )
    r = check_acceptance(ws, tid, commit="")
    assert r["ok"] is False
    assert r["reason"] == "acceptance_weak_existence_only"


def test_strengthen_existence_bullets():
    from _acceptance_strength import strengthen_existence_bullets

    out = strengthen_existence_bullets(
        ["test -f scripts/foo.py"], ["scripts/foo.py"]
    )
    assert any("py_compile" in c for c in out)


def test_ops_plan_exempt_from_strength():
    from phase_lint import validate_plan_acceptance

    plan = "## 验收\n- test -d .ccc/board\n\npipeline: ops\n"
    ok, errs = validate_plan_acceptance(plan, require_probe=True)
    # hygiene/ops marker in plan → exempt strength (still needs some probe)
    assert ok is True, errs
