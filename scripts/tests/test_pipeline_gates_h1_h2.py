"""H1 commit gate + H2 reviewer FALLBACK≠PASS unit tests."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))


def _load_board():
    spec = importlib.util.spec_from_file_location(
        "ccc_board_gates", SCRIPTS / "ccc-board.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def board(tmp_path, monkeypatch):
    mod = _load_board()
    ws = tmp_path / "ws"
    for sub in (
        "board/backlog",
        "board/planned",
        "board/in_progress",
        "board/testing",
        "board/verified",
        "board/abnormal",
        "plans",
        "phases",
        "reports",
        "verdicts",
        "pids",
    ):
        (ws / ".ccc" / sub).mkdir(parents=True)
    monkeypatch.chdir(ws)
    monkeypatch.setenv("CCC_WORKSPACE", str(ws))
    mod.set_workspace(ws)
    mod._reset_lazy()
    yield mod, ws
    mod.clear_workspace()
    mod._reset_lazy()


def test_fallback_default_is_quarantine(monkeypatch):
    mod = _load_board()
    monkeypatch.delenv("CCC_REVIEWER_FALLBACK", raising=False)
    assert mod._reviewer_fallback_mode() == "quarantine"


def test_fallback_static_aliased_to_stay(monkeypatch):
    mod = _load_board()
    monkeypatch.setenv("CCC_REVIEWER_FALLBACK", "static")
    assert mod._reviewer_fallback_mode() == "stay"


def test_fallback_never_writes_pass_or_moves_verified(board, monkeypatch):
    mod, ws = board
    monkeypatch.setenv("CCC_REVIEWER_FALLBACK", "stay")
    tid = "gate-fb-stay"
    testing = ws / ".ccc" / "board" / "testing"
    testing.mkdir(parents=True, exist_ok=True)
    (testing / f"{tid}.jsonl").write_text(
        json.dumps(
            {
                "id": tid,
                "title": "t",
                "status": "testing",
                "created_at": "2026-07-17T00:00:00+08:00",
                "updated_at": "2026-07-17T00:00:00+08:00",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    verdict = ws / ".ccc" / "verdicts" / f"{tid}.verdict.md"
    review = ws / ".ccc" / "reports" / f"{tid}.review.md"
    moved = mod._apply_reviewer_llm_fallback(
        tid,
        "medium",
        "mock unavailable",
        verdict_path=verdict,
        review_md=review,
    )
    assert moved is False
    body = verdict.read_text(encoding="utf-8")
    assert "**Verdict:** FALLBACK" in body
    assert "**Verdict:** PASS" not in body
    assert list((ws / ".ccc" / "board" / "verified").glob("*.jsonl")) == []
    assert (testing / f"{tid}.jsonl").is_file()


def test_fallback_quarantine_moves_abnormal(board, monkeypatch):
    mod, ws = board
    monkeypatch.setenv("CCC_REVIEWER_FALLBACK", "quarantine")
    tid = "gate-fb-q"
    testing = ws / ".ccc" / "board" / "testing"
    (testing / f"{tid}.jsonl").write_text(
        json.dumps(
            {
                "id": tid,
                "title": "t",
                "status": "testing",
                "created_at": "2026-07-17T00:00:00+08:00",
                "updated_at": "2026-07-17T00:00:00+08:00",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    verdict = ws / ".ccc" / "verdicts" / f"{tid}.verdict.md"
    moved = mod._apply_reviewer_llm_fallback(
        tid,
        "large",
        "claude rc=1",
        verdict_path=verdict,
    )
    assert moved is False
    assert "**Verdict:** FALLBACK" in verdict.read_text(encoding="utf-8")
    assert list(testing.glob("*.jsonl")) == []
    assert (ws / ".ccc" / "board" / "abnormal" / f"{tid}.jsonl").is_file()


def _git_init(ws: Path):
    subprocess.run(["git", "init"], cwd=ws, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "t@example.com"],
        cwd=ws,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "T"],
        cwd=ws,
        check=True,
        capture_output=True,
    )
    (ws / "README.md").write_text("x\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=ws, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=ws,
        check=True,
        capture_output=True,
    )


def test_commit_gate_rejects_without_task_commit(board, monkeypatch):
    mod, ws = board
    monkeypatch.delenv("CCC_SKIP_COMMIT_GATE", raising=False)
    _git_init(ws)
    tid = "gate-no-commit"
    mod._capture_task_pre_head(tid)
    ok, why, h = mod._require_task_commit_for_testing(tid)
    assert ok is False
    assert "no git commit" in why
    assert h == ""


def test_commit_gate_accepts_new_task_commit(board, monkeypatch):
    mod, ws = board
    monkeypatch.delenv("CCC_SKIP_COMMIT_GATE", raising=False)
    _git_init(ws)
    tid = "gate-yes-commit"
    mod._capture_task_pre_head(tid)
    (ws / "f.txt").write_text("1\n", encoding="utf-8")
    subprocess.run(["git", "add", "f.txt"], cwd=ws, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", f"feat {tid} phase=1"],
        cwd=ws,
        check=True,
        capture_output=True,
    )
    ok, why, h = mod._require_task_commit_for_testing(tid)
    assert ok is True, why
    assert len(h) == 40


def test_find_task_commit_no_head_fallback(board, monkeypatch):
    mod, ws = board
    _git_init(ws)
    assert mod._find_task_commit_hash("never-matched-id-xyz") == ""
