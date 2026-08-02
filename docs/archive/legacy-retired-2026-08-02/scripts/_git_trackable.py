"""Git trackability helpers — reject scope paths ignored by .gitignore.

Used by phase_lint / product fanout so deliverables that cannot land in git
(e.g. AGENTS.md when `/agents.md` is ignored on case-insensitive FS) fail early.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def is_path_git_trackable(workspace: Path, rel_path: str) -> bool:
    """Return True if *rel_path* can be committed under *workspace*.

    Rules:
    - Already tracked (`git ls-files --error-unmatch`) → True
    - Matched by gitignore (`git check-ignore -q`) → False
    - Not a git repo / git errors → True (do not block non-git workspaces)
    """
    path = (rel_path or "").strip().lstrip("./")
    if not path or path.lower() in {"all", "*"}:
        return True
    ws = Path(workspace)
    if not ws.is_dir():
        return True
    try:
        tracked = subprocess.run(
            ["git", "ls-files", "--error-unmatch", "--", path],
            cwd=str(ws),
            capture_output=True,
            text=True,
            timeout=10,
        )
        if tracked.returncode == 0:
            return True
        ignored = subprocess.run(
            ["git", "check-ignore", "-q", "--", path],
            cwd=str(ws),
            capture_output=True,
            text=True,
            timeout=10,
        )
        # exit 0 = ignored; 1 = not ignored; 128 = not a git repo / error
        if ignored.returncode == 0:
            return False
        return True
    except (OSError, subprocess.TimeoutExpired):
        return True


def untrackable_scope_paths(workspace: Path, scope: list) -> list[str]:
    """Return scope entries that are gitignored (and not already tracked)."""
    bad: list[str] = []
    for raw in scope or []:
        s = str(raw or "").strip()
        if not s:
            continue
        if not is_path_git_trackable(workspace, s):
            bad.append(s)
    return bad
