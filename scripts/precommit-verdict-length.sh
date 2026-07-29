#!/usr/bin/env bash
# precommit-verdict-length.sh — pre-commit hook runner
# Red line 11 enforcement: verdict files must be >= 50 lines.
# Iterates over STAGED new verdict.md files (--diff-filter=A).
set -e

REPO_ROOT="$(git rev-parse --show-toplevel)"

fail=0
staged_verdicts=$(git diff --cached --name-only --diff-filter=A 2>/dev/null | grep -E '\.verdict\.md$' || true)

if [ -z "$staged_verdicts" ]; then
    echo "OK: no staged verdict files"
    exit 0
fi

for f in $staged_verdicts; do
    [ -f "$f" ] || continue
    lines=$(wc -l < "$f")
    if [ "$lines" -lt 50 ]; then
        echo "FAIL: $f only $lines lines (need >= 50, red line 11)"
        fail=1
    else
        echo "OK: $f = $lines lines"
    fi
done

exit "$fail"
