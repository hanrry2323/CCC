"""_task_commit.py — Dev DoD: ensure commit message contains task_id before gate."""

from __future__ import annotations

import subprocess
from pathlib import Path

from _config import get_logger

_log = get_logger("task.commit")


def find_task_commit(workspace: Path, task_id: str) -> str:
    try:
        r = subprocess.run(
            [
                "git",
                "log",
                "--all",
                "--grep",
                task_id,
                "--format=%H",
                "--max-count=1",
            ],
            cwd=str(workspace),
            capture_output=True,
            text=True,
            timeout=15,
        )
        if r.returncode == 0:
            lines = (r.stdout or "").strip().splitlines()
            if lines and len(lines[0]) >= 40:
                return lines[0][:40]
    except Exception as exc:
        _log.warning("find_task_commit failed: %s", exc)
    return ""


def ensure_task_commit(
    workspace: Path,
    task_id: str,
    *,
    phase_num: int | None = None,
    pre_head: str = "",
) -> tuple[bool, str, str]:
    """If no task_id commit exists but there are local changes, create one.

    Returns (ok, reason, commit_hash).
    Does NOT invent empty commits when the tree is clean — that means the
    agent produced no diffs and must fail the gate.
    """
    existing = find_task_commit(workspace, task_id)
    if existing and (not pre_head or existing != pre_head):
        return True, "already", existing

    try:
        st = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(workspace),
            capture_output=True,
            text=True,
            timeout=15,
        )
    except Exception as exc:
        return False, f"git status failed: {exc}", ""

    dirty = (st.stdout or "").strip()
    if not dirty:
        return (
            False,
            "no task_id commit and working tree clean — agent did not land changes",
            existing,
        )

    try:
        subprocess.run(
            ["git", "add", "-A"],
            cwd=str(workspace),
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        phase_bit = f" phase={phase_num}" if phase_num is not None else ""
        msg = f"{task_id}{phase_bit}: auto-commit by CCC DoD gate"
        r = subprocess.run(
            ["git", "commit", "-m", msg],
            cwd=str(workspace),
            capture_output=True,
            text=True,
            timeout=60,
        )
        if r.returncode != 0:
            err = ((r.stderr or "") + (r.stdout or "")).strip()[:400]
            return False, f"auto-commit failed: {err}", ""
    except Exception as exc:
        return False, f"auto-commit exception: {exc}", ""

    h = find_task_commit(workspace, task_id)
    if not h:
        # commit succeeded but grep miss — resolve HEAD
        try:
            r = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=str(workspace),
                capture_output=True,
                text=True,
                timeout=10,
            )
            h = (r.stdout or "").strip()[:40]
        except Exception:
            h = ""
    if not h:
        return False, "auto-commit produced no hash", ""
    _log.info("[DoD] %s auto-committed %s", task_id, h[:12])
    return True, "auto-committed", h
