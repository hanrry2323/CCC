#!/usr/bin/env bash
# post-exec.sh — CCC default post-execution hook (v0.11 Phase a1)
#
# Triggered by ccc-exec-launcher.sh after a phase completes successfully.
# Responsibilities:
#   1. cd into the target workspace (passed as $1)
#   2. git add -A all changes
#   3. git commit -m "phase X done" (auto-increment from $CCC_PHASE_INDEX)
#   4. If nothing to commit, write a .ccc/pending-commit marker (red-line 8 fallback)
#
# Usage: post-exec.sh <workspace> [phase_index]
# Env:   CCC_PHASE_INDEX, CCC_PLAN_NAME, CCC_DRY_RUN
set -euo pipefail

WORKSPACE="${1:-${CCC_WORKSPACE:-$PWD}}"
PHASE_INDEX="${2:-${CCC_PHASE_INDEX:-?}}"
PLAN_NAME="${CCC_PLAN_NAME:-unknown}"
DRY_RUN="${CCC_DRY_RUN:-0}"

if [[ ! -d "$WORKSPACE/.git" ]]; then
  echo "[post-exec] ERROR: $WORKSPACE is not a git repo" >&2
  exit 2
fi

cd "$WORKSPACE"

if [[ "$DRY_RUN" == "1" ]]; then
  echo "[post-exec] DRY_RUN=1, would run: git add -A && git commit -m 'phase $PHASE_INDEX done'"
  exit 0
fi

git add -A

# Detect empty stage; if nothing changed, mark pending instead of failing the hook
if git diff --cached --quiet; then
  mkdir -p "$WORKSPACE/.ccc"
  printf "phase=%s\nplan=%s\nreason=no-changes\n" "$PHASE_INDEX" "$PLAN_NAME" \
    >> "$WORKSPACE/.ccc/pending-commit"
  echo "[post-exec] no staged changes; appended to .ccc/pending-commit"
  exit 0
fi

COMMIT_MSG="phase $PHASE_INDEX done (plan: $PLAN_NAME)"
git commit -m "$COMMIT_MSG" >/dev/null
echo "[post-exec] committed: $COMMIT_MSG"
