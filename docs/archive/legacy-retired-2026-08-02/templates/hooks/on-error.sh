#!/usr/bin/env bash
# on-error.sh — CCC default on-error hook (v0.11 Phase a1)
#
# Triggered by ccc-exec-launcher.sh when a phase exits non-zero.
# Responsibilities:
#   1. Emit L2 macOS desktop notification (escalation chain L1 -> L2 -> L3)
#   2. Append a structured report to .ccc/abnormal-reports/
#
# Usage: on-error.sh <workspace> <phase_index> <exit_code> <stderr_log>
# Env:   CCC_PLAN_NAME, CCC_NOTIFY_BIN, CCC_DRY_RUN
set -euo pipefail

WORKSPACE="${1:-${CCC_WORKSPACE:-$PWD}}"
PHASE_INDEX="${2:-${CCC_PHASE_INDEX:-?}}"
EXIT_CODE="${3:-1}"
STDERR_LOG="${4:-}"
PLAN_NAME="${CCC_PLAN_NAME:-unknown}"
DRY_RUN="${CCC_DRY_RUN:-0}"
NOTIFY_BIN="${CCC_NOTIFY_BIN:-$(command -v ccc-notify.sh 2>/dev/null || true)}"

REPORT_DIR="$WORKSPACE/.ccc/abnormal-reports"
mkdir -p "$REPORT_DIR"

TS="$(date +%Y%m%d-%H%M%S)"
REPORT_FILE="$REPORT_DIR/${PLAN_NAME}.phase${PHASE_INDEX}.${TS}.md"

{
  echo "# Abnormal Report"
  echo
  echo "- plan: \`$PLAN_NAME\`"
  echo "- phase: \`$PHASE_INDEX\`"
  echo "- exit_code: \`$EXIT_CODE\`"
  echo "- timestamp: \`$TS\`"
  echo "- workspace: \`$WORKSPACE\`"
  if [[ -n "$STDERR_LOG" && -f "$STDERR_LOG" ]]; then
    echo
    echo "## stderr tail"
    echo
    echo '```'
    tail -n 80 "$STDERR_LOG" || true
    echo '```'
  fi
} > "$REPORT_FILE"

echo "[on-error] wrote $REPORT_FILE"

if [[ "$DRY_RUN" == "1" ]]; then
  echo "[on-error] DRY_RUN=1, skipping L2 notification"
  exit 0
fi

if [[ -x "$NOTIFY_BIN" ]]; then
  # ccc-notify.sh 用 positional 参数：<level> <title> <message>
  "$NOTIFY_BIN" L2 "CCC phase failed: $PHASE_INDEX" "plan=$PLAN_NAME phase=$PHASE_INDEX exit=$EXIT_CODE" \
    || echo "[on-error] notify returned non-zero (continuing)"
else
  echo "[on-error] WARN: ccc-notify.sh not found; skipping L2 notification" >&2
fi
