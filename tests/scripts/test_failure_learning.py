"""Failure learning R1/R2 — fail pack, phase align, repair, prompt inject."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))


@pytest.fixture()
def ws(tmp_path: Path):
    w = tmp_path / "app"
    (w / ".ccc" / "pids").mkdir(parents=True)
    (w / ".ccc" / "plans").mkdir(parents=True)
    (w / ".ccc" / "phases").mkdir(parents=True)
    (w / ".ccc" / "reports").mkdir(parents=True)
    (w / ".ccc" / "verdicts").mkdir(parents=True)
    return w


def test_write_and_read_review_fail_pack(ws: Path):
    from _failure_learning import read_review_fail_pack, write_review_fail_pack

    tid = "t-w1"
    (ws / ".ccc" / "verdicts" / f"{tid}.verdict.md").write_text(
        "# v\n\n**Verdict:** FAIL\n\nbad scope\n", encoding="utf-8"
    )
    (ws / ".ccc" / "reports" / f"{tid}.review.md").write_text(
        '# r\n\n```json\n{"verdict":"fail","findings":[{"issue":"wrong_scope"}]}\n```\n',
        encoding="utf-8",
    )
    p = write_review_fail_pack(ws, tid, status="FAIL")
    assert p.is_file()
    text = read_review_fail_pack(ws, tid)
    assert "category: wrong_scope" in text
    assert "FAIL" in text


def test_needs_plan_repair_triggers():
    from _failure_learning import needs_plan_repair

    assert needs_plan_repair(fail_loops=1, fail_pack_text="ok") is False
    assert needs_plan_repair(fail_loops=2, fail_pack_text="ok") is True
    assert needs_plan_repair(
        fail_loops=1, fail_pack_text="category: plan_gap\nwrong_acceptance"
    )


def test_align_phases_after_revert(ws: Path):
    from _failure_learning import align_phases_after_revert

    tid = "t-w1"
    pf = ws / ".ccc" / "phases" / f"{tid}.phases.json"
    pf.write_text(
        json.dumps({"engine_iter": 5, "engine_iter_phase": 1})
        + "\n"
        + json.dumps(
            {"phase": 1, "status": "done", "commit": "abc123", "title": "p1"}
        )
        + "\n",
        encoding="utf-8",
    )
    r = align_phases_after_revert(ws, tid)
    assert r["ok"] is True
    rows = [
        json.loads(ln)
        for ln in pf.read_text(encoding="utf-8").splitlines()
        if ln.strip()
    ]
    meta = next(x for x in rows if "engine_iter" in x and "phase" not in x)
    assert meta["engine_iter"] == 0
    ph = next(x for x in rows if x.get("phase") == 1)
    assert ph["status"] == "pending"
    assert ph.get("commit") in ("", None)
    assert ph.get("reverted_commit") == "abc123"


def test_heuristic_repair_and_repair_work_plan(ws: Path):
    from _failure_learning import (
        heuristic_repair_plan,
        repair_work_plan,
        write_review_fail_pack,
    )

    tid = "t-w1"
    write_review_fail_pack(
        ws,
        tid,
        status="FAIL",
        verdict_text="**Verdict:** FAIL\nplan_gap 验收写错\n",
    )
    (ws / ".ccc" / "plans" / f"{tid}.plan.md").write_text(
        "# Plan\n\n## 目标\n做 X\n", encoding="utf-8"
    )
    # board store needs board dir for patch — optional
    (ws / ".ccc" / "board" / "planned").mkdir(parents=True)
    (ws / ".ccc" / "board" / "planned" / f"{tid}.jsonl").write_text(
        json.dumps({"id": tid, "title": "t", "card_kind": "work"}) + "\n",
        encoding="utf-8",
    )
    r = repair_work_plan(ws, tid, fail_loops=2, use_llm=False)
    assert r["ok"] is True
    plan = (ws / ".ccc" / "plans" / f"{tid}.plan.md").read_text(encoding="utf-8")
    assert "repair_of" in plan
    assert "Repair notes" in plan
    assert "## 验收" in plan

    h = heuristic_repair_plan("# P\n", "fail", reason="t")
    assert "repair_of" in h


def test_prompt_injects_review_failure(tmp_path: Path):
    from board.prompt import build_dev_phase_prompt

    ws = tmp_path / "w"
    ws.mkdir()
    text = build_dev_phase_prompt(
        "t1",
        1,
        "# plan\n",
        workspace=ws,
        review_failure="category: wrong_scope\nbad",
        pytest_failure="",
    )
    assert "上次审查/验收失败" in text
    assert "wrong_scope" in text
    assert "R2" in text or "repair" in text.lower() or "修订" in text
