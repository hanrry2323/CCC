"""Gate rule fitness: card-kind review, prose ban, hollow path-aware."""

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
    (ws / ".ccc" / "board" / "testing").mkdir(parents=True)
    (ws / ".ccc" / "plans").mkdir(parents=True)
    (ws / ".ccc" / "reports").mkdir(parents=True)
    (ws / ".ccc" / "verdicts").mkdir(parents=True)
    (ws / "scripts").mkdir()
    return ws


def test_acceptance_prose_forbidden_for_business(ws_git: Path):
    from _acceptance_gate import check_acceptance

    tid = "biz-w1"
    (ws_git / ".ccc" / "board" / "testing" / f"{tid}.jsonl").write_text(
        json.dumps(
            {
                "id": tid,
                "title": "feature",
                "pipeline": "dev",
                "card_kind": "work",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (ws_git / ".ccc" / "plans" / f"{tid}.plan.md").write_text(
        "## 验收\n- 写好说明文档即可\n", encoding="utf-8"
    )
    (ws_git / "scripts" / "x.py").write_text("x=1\n", encoding="utf-8")
    subprocess.run(["git", "add", "scripts/x.py"], cwd=ws_git, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", f"feat({tid}): x"],
        cwd=ws_git,
        check=True,
        capture_output=True,
    )
    head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ws_git, text=True
    ).strip()
    r = check_acceptance(ws_git, tid, commit=head)
    assert r["ok"] is False
    assert r["reason"] == "acceptance_prose_forbidden_for_business"


def test_acceptance_prose_ok_for_ops(ws_git: Path):
    from _acceptance_gate import check_acceptance

    tid = "ops-w1"
    (ws_git / ".ccc" / "board" / "testing" / f"{tid}.jsonl").write_text(
        json.dumps(
            {
                "id": tid,
                "title": "看板卫生",
                "pipeline": "ops",
                "card_kind": "work",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (ws_git / ".ccc" / "plans" / f"{tid}.plan.md").write_text(
        "## 验收\n- 板面干净即可\n", encoding="utf-8"
    )
    (ws_git / "scripts" / "y.py").write_text("y=1\n", encoding="utf-8")
    subprocess.run(["git", "add", "scripts/y.py"], cwd=ws_git, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", f"chore({tid}): y"],
        cwd=ws_git,
        check=True,
        capture_output=True,
    )
    head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ws_git, text=True
    ).strip()
    r = check_acceptance(ws_git, tid, commit=head)
    assert r["ok"] is True
    assert r["reason"] == "acceptance_prose_with_commit"


def test_hollow_skips_script_seed_path():
    from _opencode_quality_gate import detect_hollow_opencode_run

    raw = (
        '{"path":"script_seed","ok":true,'
        '"stdout":"permission requested: external_directory; auto-rejecting"}'
    )
    assert detect_hollow_opencode_run(raw, path="script_seed") is None
    assert detect_hollow_opencode_run(raw) is None  # path in JSON


def test_hollow_prefers_stdout_not_stale_report():
    from _opencode_quality_gate import detect_hollow_opencode_run

    result = '{"exit_code":0,"stdout":"wrote docs/NOTE.md\\n"}'
    stale = (
        "permission requested: external_directory (/Users/fan/.ccc/*); "
        "auto-rejecting\nALL SELF-CHECKS PASSED\n"
    )
    # clean current stdout → should not inherit stale report hollow
    assert detect_hollow_opencode_run(result, stale) is None


def test_detect_review_kind_script_seed(ws_git: Path, monkeypatch):
    from board.context import set_workspace
    from board.roles import reviewer as rev

    set_workspace(ws_git)
    tid = "seed-w1"
    (ws_git / ".ccc" / "reports" / f"{tid}.result.json").write_text(
        json.dumps({"path": "script_seed", "ok": True}) + "\n",
        encoding="utf-8",
    )
    task = {"id": tid, "title": "paper", "executor": "python"}
    kind = rev._detect_review_kind(ws_git, task, "", "")
    assert kind == "script_seed"


def test_tester_requires_pass_verdict(ws_git: Path):
    from board.roles.tester import _tester_verdict_allows_verified
    from board.context import set_workspace

    set_workspace(ws_git)
    tid = "t1"
    assert _tester_verdict_allows_verified(tid) is False
    (ws_git / ".ccc" / "verdicts" / f"{tid}.verdict.md").write_text(
        "# t\n\n**Verdict:** FAIL\n", encoding="utf-8"
    )
    assert _tester_verdict_allows_verified(tid) is False
    (ws_git / ".ccc" / "verdicts" / f"{tid}.verdict.md").write_text(
        "# t\n\n**Verdict:** PASS\n", encoding="utf-8"
    )
    assert _tester_verdict_allows_verified(tid) is True
