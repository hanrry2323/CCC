#!/usr/bin/env python3
"""DoD hygiene scope guard: ensure auto-commit never sweeps .ccc board dirt
into business repos for non-board_ops cards."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


# ---------------------------------------------------------------------------
# helpers: temp git repo fixture
# ---------------------------------------------------------------------------

def _git(repo: Path, *args: str) -> str:
    """Run a git command in *repo*, return stdout."""
    import subprocess
    r = subprocess.run(
        ["git", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        timeout=15,
    )
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {r.stderr.strip()}")
    return r.stdout.strip()


@pytest.fixture
def git_repo():
    """Fresh temp git repo with initial commit + minimal .ccc/ structure."""
    with tempfile.TemporaryDirectory() as td:
        repo = Path(td)
        _git(repo, "init")
        _git(repo, "config", "user.email", "test@ccc")
        _git(repo, "config", "user.name", "test")
        # initial commit
        (repo / "README.md").write_text("# test\n")
        _git(repo, "add", ".")
        _git(repo, "commit", "-m", "init")
        # .ccc/ structure (simulate board dirt)
        _ccc = repo / ".ccc"
        for sub in ("board", "plans", "phases", "reports", "pids", "stats"):
            (_ccc / sub).mkdir(parents=True, exist_ok=True)
        yield repo


def _write_and_dirty(repo: Path, path: str, content: str = "dirty"):
    """Write a file to disk without staging (simulates OpenCode leaving dirt).
    The file is created but not git-added — ensure_task_commit is responsible
    for staging only scope-relevant paths.
    Always ends with a newline for JSONL compatibility."""
    fp = repo / path
    fp.parent.mkdir(parents=True, exist_ok=True)
    data = str(content)
    if data and not data.endswith("\n"):
        data += "\n"
    fp.write_text(data)


# ---------------------------------------------------------------------------
# Test: doc_only card must NOT sweep .ccc board dirt
# ---------------------------------------------------------------------------

def test_doc_only_ignores_ccc_board_dirt(git_repo):
    """doc_only card: scope=docs/reports/stamp.md dirty + .ccc/board/* dirty
    → auto-commit must only commit the stamp file, not .ccc board entries."""
    from _task_commit import ensure_task_commit

    repo = git_repo
    tid = "doc-only-001"

    # Write plan scope file (the stamp)
    _write_and_dirty(repo, "docs/reports/stamp.md", "# Stamp 2026-07-27\n")
    # Create .ccc/board dirt (simulate the bug — unrelated board entries dirty)
    _write_and_dirty(repo, ".ccc/board/planned/some_other_task.jsonl", '{"id":"other"}')
    _write_and_dirty(repo, ".ccc/board/in_progress/doc-only-001.jsonl", '{"id":"doc-only-001"}')
    _write_and_dirty(repo, ".ccc/board/backlog/unrelated.jsonl", '{"id":"unrelated"}')

    # DoD auto-commit with no board_ops metadata (default no hygiene)
    ok, reason, commit = ensure_task_commit(repo, tid)

    assert ok, f"expected auto-committed, got: {reason}"
    assert commit, "expected a commit hash"

    # Inspect what was committed
    files = _git(repo, "show", "--name-only", "--format=", commit).splitlines()
    files = [f.strip() for f in files if f.strip()]

    assert "docs/reports/stamp.md" in files, \
        "scope file must be in the commit"
    assert ".ccc/board/planned/some_other_task.jsonl" not in files, \
        "board dirt from other tasks must NOT leak into doc_only commit"
    assert ".ccc/board/backlog/unrelated.jsonl" not in files, \
        "backlog board dirt must NOT leak into doc_only commit"


# ---------------------------------------------------------------------------
# Test: only .ccc dirty, scope clean → no commit / skipped
# ---------------------------------------------------------------------------

def test_only_ccc_dirty_no_scope_skipped(git_repo):
    """Only .ccc dirties, no plan scope changes → no commit produced.

    Simulates a scenario where the agent only churned board files but
    produced no actual product change.
    """
    from _task_commit import ensure_task_commit

    repo = git_repo
    tid = "ccc-only-002"

    # Only .ccc files dirty, no scope file
    _write_and_dirty(repo, ".ccc/board/planned/task-002.jsonl", '{"id":"task-002"}')

    ok, reason, commit = ensure_task_commit(repo, tid)

    # Must NOT auto-commit — no product changes
    assert not ok, f"expected no commit for only-ccc dirt, got: {reason}"
    assert "no task_id commit" in reason


# ---------------------------------------------------------------------------
# Test: board_ops card still commits .ccc meta (regression)
# ---------------------------------------------------------------------------

def test_board_ops_stages_ccc_meta(git_repo):
    """Board_ops card with .ccc board changes → auto-commit may include
    .ccc meta but only for its own task (not full board sweep)."""
    from _task_commit import ensure_task_commit

    repo = git_repo
    tid = "board-ops-003"
    # phases.json with .ccc scope → triggers scopes_are_ccc_only fallback
    # NOTE: do NOT commit phases — ensure_task_commit must find no prior commit
    # to proceed with auto-commit.
    phases = repo / ".ccc" / "phases" / f"{tid}.phases.json"
    phases.parent.mkdir(parents=True, exist_ok=True)
    phases.write_text(
        '{"schema_version": "1.1", "commit": ""}\n'
        f'{{"phase": 1, "scope": [".ccc/board/{tid}/"], "status": "pending"}}\n'
    )

    # Seed .ccc/board directory with a committed file so new board entries
    # show as file-level dirties in git porcelain (not directory-level ??).
    for subd in ("board/planned", "board/backlog", "board/released"):
        (repo / ".ccc" / subd).mkdir(parents=True, exist_ok=True)
        (repo / ".ccc" / subd / ".gitkeep").write_text("")
    _git(repo, "add", ".ccc/board/planned/.gitkeep", ".ccc/board/backlog/.gitkeep",
         ".ccc/board/released/.gitkeep", str(phases))
    _git(repo, "commit", "-m", "seed board dirs + phases")

    # Modify existing files (not untracked — tracked file changes)
    _write_and_dirty(repo, f".ccc/board/planned/{tid}.jsonl", '{"id":"board-ops-003"}')
    _write_and_dirty(repo, ".ccc/board/backlog/other.jsonl", '{"id":"other"}')
    _write_and_dirty(repo, ".ccc/board/released/done.jsonl", '{"id":"done"}')

    ok, reason, commit = ensure_task_commit(repo, tid)

    assert ok, f"expected auto-committed for board_ops, got: {reason}"
    assert commit, "expected a commit hash"

    files = _git(repo, "show", "--name-only", "--format=", commit).splitlines()
    files = [f.strip() for f in files if f.strip()]

    assert f".ccc/board/planned/{tid}.jsonl" in files, \
        "board_ops task's own board entry must be in commit"
    assert ".ccc/board/backlog/other.jsonl" not in files, \
        "backlog board for other tasks must NOT leak"
    assert ".ccc/board/released/done.jsonl" not in files, \
        "released board for other tasks must NOT leak"


# ---------------------------------------------------------------------------
# Test: regression — multi-file scope still commits together
# ---------------------------------------------------------------------------

def test_multi_file_scope_commits_together(git_repo):
    """Regression: multiple scope files dirty → all committed in one commit."""
    from _task_commit import ensure_task_commit

    repo = git_repo
    tid = "multi-file-004"

    # Multiple scope files
    _write_and_dirty(repo, "docs/reports/stamp.md", "# Stamp\n")
    _write_and_dirty(repo, "scripts/foo.py", "def foo(): pass\n")
    _write_and_dirty(repo, "tests/test_foo.py", "def test_foo(): pass\n")

    ok, reason, commit = ensure_task_commit(repo, tid)

    assert ok, f"expected auto-committed, got: {reason}"
    assert commit, "expected a commit hash"

    files = _git(repo, "show", "--name-only", "--format=", commit).splitlines()
    files = [f.strip() for f in files if f.strip()]

    assert "docs/reports/stamp.md" in files, "stamp must be in commit"
    assert "scripts/foo.py" in files, "scripts/foo.py must be in commit"
    assert "tests/test_foo.py" in files, "tests/test_foo.py must be in commit"


# ---------------------------------------------------------------------------
# Test: hygiene card (tag=hygiene) stages its own task-specific .ccc meta
# ---------------------------------------------------------------------------

def test_hygiene_card_stages_task_specific_ccc(git_repo):
    """Hygiene card with tag 'hygiene' → only task-specific .ccc paths
    are staged, not unrelated board/backlog or quarantines."""
    from _task_commit import ensure_task_commit

    repo = git_repo
    tid = "hygiene-task-005"

    # Seed board entry for hygiene task (tracked → modifications show as M)
    board_planned = repo / ".ccc" / "board" / "planned"
    board_planned.mkdir(parents=True, exist_ok=True)
    (board_planned / f"{tid}.jsonl").write_text(
        '{"id":"hygiene-task-005","title":"hygiene sweep","tags":["hygiene"]}\n'
    )
    # Seed .ccc subdirs so new files show as file-level dirt in porcelain
    for sub in (".ccc/reports", ".ccc/pids", ".ccc/board/backlog", ".ccc/quarantines"):
        (repo / sub).mkdir(parents=True, exist_ok=True)
        (repo / sub / ".gitkeep").write_text("")
    # Create the quarantine subdir for "some-task"
    (repo / ".ccc/quarantines/some-task").mkdir(parents=True, exist_ok=True)
    (repo / ".ccc/quarantines/some-task/.gitkeep").write_text("")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "seed hygiene task + .ccc dirs")

    # Hygiene-only dirties
    _write_and_dirty(repo, f".ccc/board/planned/{tid}.jsonl",
                     '{"id":"hygiene-task-005","tags":["hygiene"]}')
    _write_and_dirty(repo, f".ccc/reports/{tid}.report.md", "# Hygiene report\n")
    _write_and_dirty(repo, f".ccc/pids/{tid}.pid", "12345")
    # Unrelated board dirt
    _write_and_dirty(repo, ".ccc/board/backlog/other.jsonl", '{"id":"other"}')
    _write_and_dirty(repo, ".ccc/quarantines/some-task/reason.txt", "failed")

    ok, reason, commit = ensure_task_commit(repo, tid)

    assert ok, f"expected auto-committed, got: {reason}"
    assert commit, "expected a commit hash"

    files = _git(repo, "show", "--name-only", "--format=", commit).splitlines()
    files = [f.strip() for f in files if f.strip()]

    assert f".ccc/board/planned/{tid}.jsonl" in files, \
        "hygiene task's own board entry must be in commit"
    assert f".ccc/reports/{tid}.report.md" in files, \
        "hygiene task's own report must be in commit"
    assert ".ccc/board/backlog/other.jsonl" not in files, \
        "backlog for other tasks must NOT leak in hygiene commit"
    assert ".ccc/quarantines/some-task/reason.txt" not in files, \
        "quarantines for other tasks must NOT leak"


def test_lessons_noise_does_not_dirty_block_clean_scope(git_repo):
    """Verify-only: scope already clean + docs/lessons.md dirty must not dirty_block."""
    from _task_commit import ensure_task_commit

    repo = git_repo
    tid = "verify-only-040"
    # tracked scope files
    cfg = repo / "config" / "paper_strategy.json"
    cfg.parent.mkdir(parents=True)
    cfg.write_text('{"strategy":"unified_arb"}\n')
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "seed config")

    phases = repo / ".ccc" / "phases" / f"{tid}.phases.json"
    phases.write_text(
        '{"schema_version":"1.1"}\n'
        '{"phase":1,"status":"pending","scope":["config/paper_strategy.json"],'
        '"description":"verify only"}\n'
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", f"seed phases {tid}")

    # harness noise only
    _write_and_dirty(repo, "docs/lessons.md", "# lesson\n")
    _write_and_dirty(repo, f".ccc/lessons/{tid}.json", '{"x":1}')
    _write_and_dirty(repo, ".ccc/.product-fail-counter/foo.json", "{}")

    ok, reason, commit = ensure_task_commit(repo, tid)
    assert ok, f"expected pass on noise-only dirty, got: {reason}"
    assert "dirty_block" not in reason
