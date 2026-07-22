"""ops / .ccc-only 卫生卡跳过强制 pytest。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _ccc_hygiene import scopes_are_ccc_only, task_skips_forced_pytest


def test_scopes_are_ccc_only():
    assert scopes_are_ccc_only([".ccc/state.md", ".ccc/plans/a.plan.md"])
    assert not scopes_are_ccc_only([".ccc/state.md", "src/a.py"])
    assert not scopes_are_ccc_only([])


def test_skips_by_pipeline_note(tmp_path: Path):
    tid = "h1"
    task = {
        "id": tid,
        "title": "卫生",
        "note": json.dumps(
            {"transfer_gate": {"pipeline": "ops", "executor_intent": "python"}},
            ensure_ascii=False,
        ),
    }
    assert task_skips_forced_pytest(tmp_path, tid, task) is True


def test_skips_by_phase_scope(tmp_path: Path):
    tid = "h2"
    phases = tmp_path / ".ccc" / "phases"
    phases.mkdir(parents=True)
    (phases / f"{tid}.phases.json").write_text(
        '{"schema_version":"1.1"}\n'
        + json.dumps(
            {
                "phase": 1,
                "status": "pending",
                "description": "commit",
                "scope": [".ccc/state.md", ".ccc/lessons/a.json"],
                "subtasks": {"1.1": "pending"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    assert task_skips_forced_pytest(tmp_path, tid, {"id": tid, "title": "x"}) is True


def test_business_scope_not_skipped(tmp_path: Path):
    tid = "biz"
    phases = tmp_path / ".ccc" / "phases"
    phases.mkdir(parents=True)
    (phases / f"{tid}.phases.json").write_text(
        '{"schema_version":"1.1"}\n'
        + json.dumps(
            {
                "phase": 1,
                "status": "pending",
                "description": "code",
                "scope": ["src/core/x.py"],
                "subtasks": {"1.1": "pending"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    assert (
        task_skips_forced_pytest(
            tmp_path, tid, {"id": tid, "title": "feature", "note": "{}"}
        )
        is False
    )
