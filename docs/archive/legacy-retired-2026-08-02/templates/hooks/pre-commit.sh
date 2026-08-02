#!/usr/bin/env bash
# pre-commit.sh — CCC default pre-commit guard (v0.11 Phase a1)
#
# Triggered by ccc-exec-commit.sh (or git pre-commit hook) before a phase commit.
# Soft lint: scan staged diff for TODO / FIXME / debug print() residue.
# Does NOT block commit; only emits warnings (per red-line 2: must be executable
# acceptance, but the lint is informational, not a gate).
#
# Usage: pre-commit.sh [workspace]
# Env:   CCC_DRY_RUN, CCC_LINT_STRICT (1 = exit 1 on any warning)
set -euo pipefail

WORKSPACE="${1:-${CCC_WORKSPACE:-$PWD}}"
STRICT="${CCC_LINT_STRICT:-0}"
WARN_COUNT=0

cd "$WORKSPACE"

# Gather staged additions/modifications only (ignore deletes)
STAGED_FILES=$(git diff --cached --name-only --diff-filter=ACMR || true)
if [[ -z "$STAGED_FILES" ]]; then
  exit 0
fi

warn() {
  echo "[pre-commit] WARN: $1" >&2
  WARN_COUNT=$((WARN_COUNT + 1))
}

# Heuristic 1: TODO / FIXME / XXX in added lines
if git diff --cached -U0 | grep -nE '^\+.*\b(TODO|FIXME|XXX)\b' >/dev/null 2>&1; then
  warn "staged diff contains TODO/FIXME/XXX markers"
fi

# Heuristic 2: leftover debug print() in Python/JS/TS staged files
PRINT_HITS=$(echo "$STAGED_FILES" \
  | grep -E '\.(py|js|ts|jsx|tsx|mjs|cjs)$' || true)
if [[ -n "$PRINT_HITS" ]]; then
  if echo "$PRINT_HITS" | xargs -I{} sh -c \
      'git diff --cached -U0 -- "{}" | grep -nE "^\+.*\bprint\s*\(" >/dev/null 2>&1 && echo "{}"' \
      2>/dev/null | grep -q .; then
    warn "staged diff contains debug print() calls"
  fi
fi

# Heuristic 3: pdb / breakpoint / console.log residue
RESIDUE=$(git diff --cached -U0 | grep -nE '^\+.*(\bpdb\.set_trace|breakpoint\(\)|console\.log\()' || true)
if [[ -n "$RESIDUE" ]]; then
  warn "staged diff contains debugger residue (pdb/breakpoint/console.log)"
fi

if [[ "$WARN_COUNT" -gt 0 ]]; then
  echo "[pre-commit] $WARN_COUNT warning(s) emitted"
fi

if [[ "$STRICT" == "1" && "$WARN_COUNT" -gt 0 ]]; then
  echo "[pre-commit] CCC_LINT_STRICT=1, refusing commit" >&2
  exit 1
fi

exit 0
