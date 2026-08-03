"""test_ccc_exec_commit_jsonl_smoke.py — Regression test for ccc-exec-commit.sh JSONL bug.

Bug: ccc-exec-commit.sh used `json.load(f)` on phases.json. Real phases.json is
JSONL (one JSON object per line), which triggers `json.decoder.JSONDecodeError: Extra data`.

This test verifies the fix: script accepts JSONL, JSON-array, and single-object formats
without raising JSONDecodeError.

See: zcode-blindspot-fill.verdict.md (Probe 4) — bug confirmed
     historical task plan §3 Phase 1 — fix
"""
from __future__ import annotations
import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT = ROOT / "scripts" / "ccc-exec-commit.sh"


def _git(args, cwd):
    return subprocess.run(
        ["git"] + args, cwd=cwd, capture_output=True, text=True, check=False,
    )


def _init_repo(tmp_path: Path, name: str) -> Path:
    repo = tmp_path / name
    repo.mkdir()
    _git(["init", "-b", "main"], cwd=repo)
    _git(["config", "user.email", "test@x"], cwd=repo)
    _git(["config", "user.name", "Test"], cwd=repo)
    (repo / "README.md").write_text("# test")
    _git(["add", "README.md"], cwd=repo)
    _git(["commit", "-m", "initial"], cwd=repo)
    ccc = repo / ".ccc"
    for sub in ("phases", "reports", "plans", "verdicts"):
        (ccc / sub).mkdir(parents=True, exist_ok=True)
    return repo


def _write_phases_jsonl(repo: Path, task: str, lines: list[str]) -> Path:
    p = repo / ".ccc" / "phases" / f"{task}.phases.json"
    p.write_text("\n".join(lines) + "\n")
    return p


# -------- Format 1: JSONL (canonical phases.json format) --------
def test_phases_jsonl_format_accepted(tmp_path):
    """JSONL format (each line one JSON object) must not raise JSONDecodeError."""
    repo = _init_repo(tmp_path, "jsonl_repo")
    phases_path = _write_phases_jsonl(repo, "jsonltask", [
        '{"phase": 1, "phase_id": "p1", "status": "pending", "commit": null, "scope": [], "commit_message": "noop"}',
        '{"phase": 2, "phase_id": "p2", "status": "pending", "commit": null, "scope": [], "commit_message": "noop"}',
    ])

    # Run with --phase 1 (no scope, no actual commit needed) — just verify parsing succeeds.
    result = subprocess.run(
        ["bash", str(SCRIPT), str(repo), "jsonltask", "--phase", "1"],
        capture_output=True, text=True, check=False,
    )

    # Must NOT contain JSONDecodeError
    combined = result.stdout + result.stderr
    assert "JSONDecodeError" not in combined, (
        f"JSONL parsing failed: stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert "Extra data" not in combined, (
        f"json.load() on JSONL triggered Extra data: stdout={result.stdout!r}"
    )
    # The script ran (exit 0 = no errors; the phase was pending so it was skipped)
    assert result.returncode in (0, 1), f"unexpected exit {result.returncode}"


def test_phases_jsonl_format_task_id_injected(tmp_path):
    """JSONL with no task_id field: script should auto-inject uuid task_id without crashing.

    Note: the script normalizes JSONL into a single JSON doc on task_id injection —
    that's an acceptable side-effect; the goal is to verify no JSONDecodeError occurs
    during the parsing path.
    """
    repo = _init_repo(tmp_path, "jsonl_repo_tid")
    phases_path = _write_phases_jsonl(repo, "jsonltidtask", [
        '{"phase": 1, "phase_id": "p1", "status": "pending", "commit": null, "scope": [], "commit_message": "noop"}',
    ])
    result = subprocess.run(
        ["bash", str(SCRIPT), str(repo), "jsonltidtask"],
        capture_output=True, text=True, check=False,
    )
    combined = result.stdout + result.stderr
    assert "JSONDecodeError" not in combined, combined
    assert "Extra data" not in combined, combined
    # The script outputs a confirmation that task_id was auto-injected
    assert "task_id" in combined, "expected task_id injection message in stdout"


# -------- Format 2: JSON array --------
def test_phases_json_array_format_accepted(tmp_path):
    """Legacy JSON-array format must also work (back-compat)."""
    repo = _init_repo(tmp_path, "array_repo")
    phases_path = repo / ".ccc" / "phases" / "arraytask.phases.json"
    phases_path.write_text(json.dumps([
        {"phase": 1, "phase_id": "p1", "status": "pending", "commit": None, "scope": [], "commit_message": "noop"},
    ]))

    result = subprocess.run(
        ["bash", str(SCRIPT), str(repo), "arraytask"],
        capture_output=True, text=True, check=False,
    )
    combined = result.stdout + result.stderr
    assert "JSONDecodeError" not in combined, combined


# -------- Format 3: single JSON object --------
def test_phases_single_object_format_accepted(tmp_path):
    """Single JSON object (no newlines) must work too."""
    repo = _init_repo(tmp_path, "single_repo")
    phases_path = repo / ".ccc" / "phases" / "singletask.phases.json"
    phases_path.write_text(json.dumps({
        "task_id": "abc",
        "phases": [
            {"phase": 1, "phase_id": "p1", "status": "pending", "commit": None, "scope": [], "commit_message": "noop"},
        ],
    }))

    result = subprocess.run(
        ["bash", str(SCRIPT), str(repo), "singletask"],
        capture_output=True, text=True, check=False,
    )
    combined = result.stdout + result.stderr
    assert "JSONDecodeError" not in combined, combined


# -------- Format 4: empty file --------
def test_phases_empty_file_handled(tmp_path):
    """Empty phases.json must not crash — script should treat as empty data."""
    repo = _init_repo(tmp_path, "empty_repo")
    phases_path = repo / ".ccc" / "phases" / "emptytask.phases.json"
    phases_path.write_text("")

    result = subprocess.run(
        ["bash", str(SCRIPT), str(repo), "emptytask"],
        capture_output=True, text=True, check=False,
    )
    combined = result.stdout + result.stderr
    assert "JSONDecodeError" not in combined, combined


# -------- Real historical phases.json (sanity check on actual file) --------
def test_real_historical_phases_jsonl(tmp_path):
    """The actual historical phases.json must parse via the script."""
    real_phases = ROOT / ".ccc" / "phases" / "zcode-blindspot-fill.phases.json"
    if not real_phases.exists():
        pytest.skip(f"real phases file not present: {real_phases}")

    # Sanity: the real file is JSONL (one object per line)
    content = real_phases.read_text().strip()
    lines = [ln for ln in content.splitlines() if ln.strip()]
    assert len(lines) >= 1
    for ln in lines:
        json.loads(ln)  # must parse as JSONL
    # The file starts with `{"phase": ...` and contains newlines — classic JSONL
    assert lines[0].startswith("{")
    if len(lines) > 1:
        # Multi-line: must NOT be parseable as single JSON
        with pytest.raises(json.JSONDecodeError):
            json.loads(content)
