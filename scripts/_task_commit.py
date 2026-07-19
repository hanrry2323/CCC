"""_task_commit.py — Dev DoD: ensure commit message contains task_id before gate."""

from __future__ import annotations

import subprocess
from pathlib import Path

from _config import get_logger

_log = get_logger("task.commit")


def porcelain_product_paths(porcelain: str) -> list[str]:
    """Parse ``git status --porcelain``; drop ``.ccc/`` meta noise.

    Board/state/report churn must not satisfy DoD — only product-file
    dirty lines count as agent landing changes.
    """
    out: list[str] = []
    for raw in (porcelain or "").splitlines():
        line = raw.rstrip("\n")
        if not line.strip():
            continue
        # status is 2 chars + space; path may be quoted or ``a -> b``
        path = line[3:] if len(line) >= 4 else line
        path = path.strip()
        if path.startswith('"') and path.endswith('"'):
            path = path[1:-1]
        if " -> " in path:
            path = path.split(" -> ", 1)[-1].strip().strip('"')
        if path == ".ccc" or path.startswith(".ccc/"):
            continue
        out.append(path)
    return out


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
    product = porcelain_product_paths(dirty)
    if not product:
        if dirty:
            return (
                False,
                "no task_id commit and only .ccc/ meta dirty — "
                "agent did not land product changes",
                existing,
            )
        return (
            False,
            "no task_id commit and working tree clean — agent did not land changes",
            existing,
        )

    try:
        # Stage product paths only — never auto-commit board/state noise as DoD.
        add_cmd = ["git", "add", "--", *product]
        subprocess.run(
            add_cmd,
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
