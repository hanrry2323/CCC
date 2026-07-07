#!/usr/bin/env python3
"""ccc-search — cross-project .ccc/ keyword search.

Usage: ccc search <query> [--workspace <path>]

Searches all ~/program/*/.ccc/{plans,phases,reports,verdicts,abnormal-reports,board}/*.md
for the given keyword and prints matches with one-line context.
With --workspace, only searches that specific project.
"""

import argparse
import os
import re
import sys
from pathlib import Path

HOME = Path.home()
SEARCH_DIRS = ["plans", "phases", "reports", "verdicts", "abnormal-reports", "board"]


def main():
    parser = argparse.ArgumentParser(description="Search .ccc/ files for keywords")
    parser.add_argument("query", nargs="?", help="Search keyword")
    parser.add_argument("--workspace", help="Scope search to specific project path")
    args = parser.parse_args()

    if not args.query:
        parser.print_help()
        sys.exit(0)

    query = args.query
    if args.workspace:
        project_dirs = [Path(args.workspace)]
    else:
        project_dirs = sorted(HOME.glob("program/*"))

    if not project_dirs:
        print("No projects found")
        return

    total_hits = 0

    for proj in project_dirs:
        ccc_dir = proj / ".ccc"
        if not ccc_dir.is_dir():
            continue

        for sub in SEARCH_DIRS:
            sub_dir = ccc_dir / sub
            if not sub_dir.is_dir():
                continue

            for fpath in sorted(sub_dir.glob("*.md")):
                try:
                    text = fpath.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    continue

                for lineno, line in enumerate(text.splitlines(), 1):
                    if query.lower() in line.lower():
                        match = line.strip()[:120]
                        print(f"[{proj.name}] {fpath.name}:{lineno}  {match}")
                        total_hits += 1

    if total_hits == 0:
        print(f"No matches for '{query}' in any project .ccc/ files.")
    else:
        print(f"\n--- {total_hits} match(es) ---")


if __name__ == "__main__":
    main()
