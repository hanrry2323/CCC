#!/usr/bin/env python3
"""Gated skill hygiene — dry-run by default; --apply to mutate.

Examples:
  python3 scripts/ccc-skill-cleanup.py --dry-run
  python3 scripts/ccc-skill-cleanup.py --apply --broken-links
  python3 scripts/ccc-skill-cleanup.py --apply --worktree-prune
  python3 scripts/ccc-skill-cleanup.py --apply --archive
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

HOME = Path.home()
CCC = Path(__file__).resolve().parents[1]


def find_broken_symlinks(roots: list[Path]) -> list[Path]:
    broken: list[Path] = []
    for root in roots:
        if not root.is_dir():
            continue
        for p in root.iterdir():
            if p.is_symlink() and not p.exists():
                broken.append(p)
    return broken


def list_archive_dirs() -> list[Path]:
    base = HOME / ".ccc" / "archive"
    if not base.is_dir():
        return []
    return sorted(
        p for p in base.iterdir() if p.is_dir() and "worktrees-archive" in p.name
    )


def ghost_worktrees() -> list[str]:
    try:
        out = subprocess.check_output(
            ["git", "-C", str(CCC), "worktree", "list", "--porcelain"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    ghosts: list[str] = []
    path = None
    for line in out.splitlines():
        if line.startswith("worktree "):
            path = line[len("worktree ") :].strip()
        elif line.startswith("detached") or line.startswith("branch ") or line == "":
            if path and path != str(CCC) and not Path(path).exists():
                ghosts.append(path)
            path = None
    if path and path != str(CCC) and not Path(path).exists():
        ghosts.append(path)
    return ghosts


def main() -> int:
    ap = argparse.ArgumentParser(description="CCC skill hygiene (gated)")
    ap.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Only print actions (default)",
    )
    ap.add_argument(
        "--apply",
        action="store_true",
        help="Actually delete/prune (requires a target flag)",
    )
    ap.add_argument(
        "--broken-links",
        action="store_true",
        help="Remove broken symlinks under OpenCode/Copilot skills",
    )
    ap.add_argument(
        "--worktree-prune",
        action="store_true",
        help="git worktree prune for CCC ghost worktrees",
    )
    ap.add_argument(
        "--archive",
        action="store_true",
        help="Remove ~/.ccc/archive/worktrees-archive-*",
    )
    args = ap.parse_args()
    apply = bool(args.apply)
    if apply:
        args.dry_run = False

    if not any([args.broken_links, args.worktree_prune, args.archive]):
        # Default preview: show everything
        args.broken_links = True
        args.worktree_prune = True
        args.archive = True
        apply = False
        print("== dry-run preview (pass --apply --broken-links|… to mutate) ==\n")

    changed = 0

    if args.broken_links:
        roots = [
            HOME / ".config" / "opencode" / "skills",
            HOME / ".copilot" / "skills",
        ]
        broken = find_broken_symlinks(roots)
        print(f"[broken-links] {len(broken)} symlink(s)")
        for p in broken:
            print(f"  {'DELETE' if apply else 'would delete'}: {p}")
            if apply:
                p.unlink(missing_ok=True)
                changed += 1

    if args.worktree_prune:
        ghosts = ghost_worktrees()
        print(f"[worktree-prune] {len(ghosts)} ghost(s)")
        for g in ghosts:
            print(f"  ghost: {g}")
        if apply:
            subprocess.check_call(["git", "-C", str(CCC), "worktree", "prune"])
            print("  ran: git worktree prune")
            changed += 1
        elif ghosts:
            print("  would run: git worktree prune")

    if args.archive:
        archives = list_archive_dirs()
        print(f"[archive] {len(archives)} dir(s)")
        for d in archives:
            size = sum(f.stat().st_size for f in d.rglob("*") if f.is_file())
            print(
                f"  {'DELETE' if apply else 'would delete'}: {d} (~{size // 1024}KB)"
            )
            if apply:
                shutil.rmtree(d)
                changed += 1

    if apply:
        print(f"\nDone. mutations={changed}")
    else:
        print("\nNo changes (dry-run).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
