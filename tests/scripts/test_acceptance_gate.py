"""Acceptance gate + hollow refuse for salvage."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

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
    (ws / ".ccc" / "board" / "in_progress").mkdir(parents=True)
    (ws / ".ccc" / "plans").mkdir(parents=True)
    (ws / ".ccc" / "reports").mkdir(parents=True)
    (ws / "src").mkdir()
    (ws / "src" / "a.py").write_text("x=1\n", encoding="utf-8")
    subprocess.run(["git", "add", "src/a.py"], cwd=ws, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "chore: tid-w1 touch src/a.py"],
        cwd=ws,
        check=True,
        capture_output=True,
    )
    return ws


def test_acceptance_missing_rejects(ws_git: Path):
    from _acceptance_gate import check_acceptance

    r = check_acceptance(ws_git, "tid-w1", commit="HEAD")
    assert r["ok"] is False
    assert r["reason"] == "missing_acceptance"


def test_acceptance_path_in_commit(ws_git: Path):
    from _acceptance_gate import check_acceptance

    tid = "tid-w1"
    (ws_git / ".ccc" / "plans" / f"{tid}.plan.md").write_text(
        "## 验收\n- `src/a.py` 已修改\n", encoding="utf-8"
    )
    head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ws_git, text=True
    ).strip()
    r = check_acceptance(ws_git, tid, commit=head)
    assert r["ok"] is True


def test_acceptance_cmds_refuse_uncommitted_vs_commit(ws_git: Path):
    """WT probe green + old task commit still PENDING → refuse (no OpenCode commit 假绿).

    用业务路径（非 docs/reports harness 噪声）覆盖 uncommitted_vs_commit。
    """
    from _acceptance_gate import check_acceptance

    tid = "tid-w1"
    stamp = ws_git / "src" / "stamp_marker.py"
    stamp.parent.mkdir(parents=True, exist_ok=True)
    stamp.write_text("PENDING\n", encoding="utf-8")
    subprocess.run(["git", "add", "src/stamp_marker.py"], cwd=ws_git, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", f"feat({tid}): seed PENDING"],
        cwd=ws_git,
        check=True,
        capture_output=True,
    )
    head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ws_git, text=True
    ).strip()
    stamp.write_text("GOLDEN_PATH_OK_V2\n", encoding="utf-8")
    (ws_git / ".ccc" / "plans" / f"{tid}.plan.md").write_text(
        "## 验收\n"
        "- test -f src/stamp_marker.py && "
        "grep -q GOLDEN_PATH_OK_V2 src/stamp_marker.py\n",
        encoding="utf-8",
    )
    r = check_acceptance(ws_git, tid, commit=head)
    assert r["ok"] is False
    assert r["reason"] == "acceptance_uncommitted_vs_commit"


def test_ensure_recommit_when_scope_dirty_after_prior_task_commit(ws_git: Path):
    from _task_commit import ensure_task_commit, find_task_commit

    tid = "tid-w1"
    stamp = ws_git / "docs" / "reports" / "stamp.md"
    stamp.parent.mkdir(parents=True)
    stamp.write_text("PENDING\n", encoding="utf-8")
    subprocess.run(["git", "add", "docs/reports/stamp.md"], cwd=ws_git, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", f"feat({tid}): seed PENDING"],
        cwd=ws_git,
        check=True,
        capture_output=True,
    )
    prior = find_task_commit(ws_git, tid)
    assert prior
    (ws_git / ".ccc" / "plans" / f"{tid}.plan.md").write_text(
        "## 范围\n- docs/reports/stamp.md\n",
        encoding="utf-8",
    )
    stamp.write_text("GOLDEN_PATH_OK_V2\n", encoding="utf-8")
    ok, why, h = ensure_task_commit(ws_git, tid)
    assert ok is True
    assert h != prior
    assert "GOLDEN_PATH_OK_V2" in subprocess.check_output(
        ["git", "show", f"{h}:docs/reports/stamp.md"], cwd=ws_git, text=True
    )


def test_salvage_refuses_without_acceptance(ws_git: Path, monkeypatch):
    from board.context import set_workspace
    from board.roles import dev as dev_mod

    set_workspace(ws_git)
    tid = "tid-w1"
    task = {
        "id": tid,
        "title": "x",
        "description": "y",
        "status": "in_progress",
        "created_at": "2026-07-20T00:00:00+08:00",
        "updated_at": "2026-07-20T00:00:00+08:00",
        "card_kind": "work",
        "complexity": "medium",
        "schema_version": "1.2",
        "ui_hidden": False,
        "child_ids": [],
        "parent_id": None,
        "split_status": None,
        "color_group": "A",
        "color_depth": 1,
        "tags": [],
        "assignee": None,
        "note": None,
    }
    (ws_git / ".ccc" / "board" / "in_progress" / f"{tid}.jsonl").write_text(
        json.dumps(task) + "\n"
    )
    (ws_git / ".ccc" / "reports" / f"{tid}.result.json").write_text(
        json.dumps({"stdout": "ALL SELF-CHECKS PASSED\n"})
    )
    monkeypatch.setenv("CCC_SKIP_COMMIT_GATE", "1")
    assert dev_mod.try_complete_if_gates_satisfied(tid) is None


def test_hub_lens_filters_hidden_done(tmp_path: Path):
    from chat_server.services import hub_lens

    board = tmp_path / ".ccc" / "board" / "backlog"
    board.mkdir(parents=True)
    (board / "zombie.jsonl").write_text(
        json.dumps(
            {
                "id": "zombie",
                "title": "done epic",
                "card_kind": "epic",
                "split_status": "done",
                "ui_hidden": True,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (board / "live.jsonl").write_text(
        json.dumps(
            {
                "id": "live",
                "title": "pending epic",
                "card_kind": "epic",
                "split_status": "pending",
                "ui_hidden": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    data = hub_lens.collect_board(tmp_path, project_id="demo")
    assert data["counts"]["backlog"] == 1
    assert data["counts_raw"]["backlog"] == 2
