"""Wave A2: try_complete_if_gates_satisfied."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest


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
    (ws / ".ccc" / "reports").mkdir(parents=True)
    (ws / ".ccc" / "phases").mkdir(parents=True)
    (ws / ".ccc" / "pids").mkdir(parents=True)
    smoke = ws / ".ccc" / "flow-smoke.md"
    smoke.parent.mkdir(parents=True, exist_ok=True)
    smoke.write_text("flow-green marker\n")
    subprocess.run(["git", "add", ".ccc/flow-smoke.md"], cwd=ws, check=True, capture_output=True)
    subprocess.run(
        [
            "git",
            "commit",
            "-m",
            "chore: flow-green-abc-w1 write flow-smoke",
        ],
        cwd=ws,
        check=True,
        capture_output=True,
    )
    return ws


def test_salvage_with_self_checks_in_result(ws_git: Path, monkeypatch):
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
    from board.context import set_workspace
    from board.roles import dev as dev_mod

    set_workspace(ws_git)
    tid = "flow-green-abc-w1"
    task = {
        "id": tid,
        "title": "写入并提交",
        "description": "smoke",
        "status": "in_progress",
        "created_at": "2026-07-20T00:00:00+08:00",
        "updated_at": "2026-07-20T00:00:00+08:00",
        "card_kind": "work",
        "complexity": "small",
        "schema_version": "1.2",
        "ui_hidden": False,
        "child_ids": [],
        "parent_id": "flow-green-abc",
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
    (ws_git / ".ccc" / "phases" / f"{tid}.phases.json").write_text(
        '{"schema_version":"1.1"}\n'
        + json.dumps(
            {
                "phase": 1,
                "status": "pending",
                "description": "write",
                "scope": [".ccc/flow-smoke.md"],
                "subtasks": {"1.1": "pending"},
                "timeout": 1800,
                "commit": None,
                "notes": "",
            }
        )
        + "\n"
    )
    (ws_git / ".ccc" / "reports" / f"{tid}.result.json").write_text(
        json.dumps(
            {
                "exit_code": 0,
                "stdout": "done\nALL SELF-CHECKS PASSED\n",
            }
        )
    )
    # stub report without marker
    (ws_git / ".ccc" / "reports" / f"{tid}.report.md").write_text(
        f"# {tid}\n\n门禁: missing SELF-CHECKS\n"
    )

    monkeypatch.setenv("CCC_SKIP_COMMIT_GATE", "1")
    out = dev_mod.try_complete_if_gates_satisfied(tid)
    assert out is not None
    assert out["status"] == "success"
    assert out.get("salvaged") is True
    assert (ws_git / ".ccc" / "board" / "testing" / f"{tid}.jsonl").is_file()
    report = (ws_git / ".ccc" / "reports" / f"{tid}.report.md").read_text()
    assert "ALL SELF-CHECKS PASSED" in report


def test_detect_oversplit_small_epic():
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
    from _product_fanout import detect_write_commit_oversplit

    kids = [
        {"title": "写入 flow-smoke", "description": "写文件", "plan_md": "x"},
        {"title": "提交 git commit 含任务 id", "description": "仅提交", "plan_md": "y"},
    ]
    err = detect_write_commit_oversplit(
        kids, epic={"complexity": "small", "title": "流水线烟测"}
    )
    assert err and "oversplit" in err


def test_detect_oversplit_small_rejects_three_children():
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
    from _product_fanout import detect_write_commit_oversplit, build_fanout_prompt
    from pathlib import Path as P

    kids = [
        {"title": "a 写入并提交", "description": "a", "plan_md": "## 验收\n- x"},
        {"title": "b 写入并提交", "description": "b", "plan_md": "## 验收\n- y"},
        {"title": "c 写入并提交", "description": "c", "plan_md": "## 验收\n- z"},
    ]
    err = detect_write_commit_oversplit(
        kids, epic={"complexity": "small", "title": "small epic"}
    )
    assert err and "exactly 1" in err
    prompt = build_fanout_prompt(
        epic={"id": "e1", "title": "t", "complexity": "small", "description": "d"},
        workspace=P("."),
        profile="p",
        code_ctx="",
        template_plan="# plan",
        ref_plans="",
        max_phases=3,
    )
    assert "complexity: small" in prompt
    assert "反过拆" in prompt
