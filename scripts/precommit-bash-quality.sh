#!/usr/bin/env bash
# precommit-bash-quality.sh — pre-commit hook runner
# Two checks:
#   1. bash -n for every scripts/*.sh + tools/*.sh (syntax)
#   2. v3 portability: ban `bash -c '\$VAR'` nested pattern (red line 20)
set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SH_FILES=$(find "$REPO_ROOT/scripts" "$REPO_ROOT/tools" -name "*.sh" 2>/dev/null || true)

# 1. syntax check
for f in $SH_FILES; do
    bash -n "$f" || {
        echo "FAIL: bash syntax error in $f"
        exit 1
    }
done

# 2. v3 portability: ban bash -c '...$VAR...' nested pattern
# Pattern: bash -c with single-quoted string containing $VAR (with backslash or not)
BANNED=$(grep -rPn "bash -c '[^']*\\\\\\$[A-Z_]+|^[^#]*bash -c '[^']*\\$[A-Z_]+" "$REPO_ROOT/scripts" "$REPO_ROOT/tools" 2>/dev/null || true)
if [ -n "$BANNED" ]; then
    echo "FAIL: bash v3 portability violation (red line 20)"
    echo "$BANNED"
    exit 1
fi

echo "OK: bash -n + v3 portability $(echo "$SH_FILES" | wc -l | tr -d ' ') script(s)"
exit 0
