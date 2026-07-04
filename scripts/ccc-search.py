#!/usr/bin/env python3
"""ccc-search — cross-project .ccc/ keyword search.

Usage: ccc search <query>
Searches all ~/program/*/.ccc/{plans,phases,reports,verdicts,abnormal-reports}/*.md
for the given keyword and prints matches with one-line context.
"""

import os
import re
import sys
from pathlib import Path

HOME = Path.home()
SEARCH_DIRS = ["plans", "phases", "reports", "verdicts", "abnormal-reports"]


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print("Usage: ccc search <query>")
        sys.exit(0 if len(sys.argv) < 2 else 1)

    query = " ".join(sys.argv[1:])
    project_dirs = sorted(HOME.glob("program/*"))

    if not project_dirs:
        print("No projects found under ~/program/")
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
