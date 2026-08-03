"""KPI R1 P0: short-path advance + ungradable diff → FAIL not quarantine."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))


@pytest.fixture()
def ws_git(tmp_path: Path):
    ws = tmp_path / "app"
    ws.mkdir()
    subprocess.run(["git", "init"], cwd=ws, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "t@t.com"], cwd=ws, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "config", "user.name", "t"], cwd=ws, check=True, capture_output=True
    )
    for col in ("testing", "planned", "abnormal", "in_progress"):
        (ws / ".ccc" / "board" / col).mkdir(parents=True)
    (ws / ".ccc" / "plans").mkdir(parents=True)
    (ws / ".ccc" / "reports").mkdir(parents=True)
    (ws / ".ccc" / "verdicts").mkdir(parents=True)
    return ws


def test_ungradable_diff_writes_fail_not_quarantine(ws_git: Path):
    from board.context import set_workspace
    from board.roles import reviewer as rev

    set_workspace(ws_git)
    tid = "ungradable-w1"
    task = {
        "id": tid,
        "title": "x",
        "card_kind": "work",
        "complexity": "medium",
        "schema_version": "1.2",
        "status": "testing",
    }
    (ws_git / ".ccc" / "board" / "testing" / f"{tid}.jsonl").write_text(
        json.dumps(task) + "\n"
    )
    (ws_git / ".ccc" / "plans" / f"{tid}.plan.md").write_text(
        "## 验收\n- test -f scripts/x.py\n", encoding="utf-8"
    )

    with patch.object(rev, "_get_git_diff", return_value=("weird\nno summary\n", "diff --git a/x b/x\n")):
        with patch.object(rev, "_detect_review_kind", return_value="opencode"):
            with patch.object(rev, "_quarantine") as q:
                ok = rev._review_one_task(tid)  # noqa: SLF001
    assert ok is False
    q.assert_not_called()
    v = (ws_git / ".ccc" / "verdicts" / f"{tid}.verdict.md").read_text()
    assert "**Verdict:** FAIL" in v
    assert "fixable" in v.lower() or "ungradable" in v.lower()
    # still in testing (gate will FAIL→planned); not abnormal
    assert (ws_git / ".ccc" / "board" / "testing" / f"{tid}.jsonl").is_file()
    assert not (ws_git / ".ccc" / "board" / "abnormal" / f"{tid}.jsonl").is_file()
