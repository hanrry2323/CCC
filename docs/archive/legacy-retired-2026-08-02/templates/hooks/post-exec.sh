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

# v0.15b: launcher 传 <phase_id> <workspace> 2 个参数
# 之前 $1=phase_id 当 workspace 是错的; 现在 $1=phase_id $2=workspace
WORKSPACE="${2:-${CCC_WORKSPACE:-$PWD}}"
PHASE_INDEX="${1:-${CCC_PHASE_INDEX:-?}}"
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

# v0.15d: 自动 push 远端（如果配了 remote 且 fast-forward）
# 失败不阻断（可能没 remote / 远端无写权 / 网络问题）
CCC_PUSH="${CCC_PUSH:-1}"  # 默认开, 设 CCC_PUSH=0 关
if [[ "$CCC_PUSH" == "1" ]]; then
  REMOTE=$(git remote 2>/dev/null | head -1)
  BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)
  if [[ -n "$REMOTE" && -n "$BRANCH" ]]; then
    if git push "$REMOTE" "$BRANCH" 2>/dev/null; then
      echo "[post-exec] pushed to $REMOTE/$BRANCH"
    else
      echo "[post-exec] push failed (non-fatal): $REMOTE/$BRANCH"
    fi
  else
    echo "[post-exec] no remote/branch, skip push"
  fi
fi
