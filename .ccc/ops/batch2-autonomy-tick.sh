#!/usr/bin/env bash
# Durable Batch2 / clawmed autonomy tick — launchd Hourly, NOT Cursor-session dependent.
set -euo pipefail
CCC_HOME="${CCC_HOME:-/Users/apple/program/CCC}"
CLA="${CLA:-/Users/apple/program/clawmed-ccc}"
LOG_DIR="${HOME}/.ccc/logs"
mkdir -p "$LOG_DIR" "$CCC_HOME/.ccc/ops"
STAMP=$(date '+%Y-%m-%dT%H:%M:%S%z')
OUT="$LOG_DIR/batch2-autonomy-tick.log"
CHECK="$CCC_HOME/.ccc/ops/batch2-check.py"

{
  echo "==== TICK $STAMP ===="
  # heal engine if crash-looping
  if ! pgrep -f 'scripts/ccc-engine.py' >/dev/null 2>&1; then
    echo "engine dead → kickstart"
    launchctl kickstart -k "gui/$(id -u)/com.ccc.engine" 2>/dev/null || true
    sleep 2
  fi
  # heal board :7775
  if ! curl -sf -m 2 'http://127.0.0.1:7775/api/board?workspace=clawmed-ccc' >/dev/null; then
    echo "board api bad → kickstart com.ccc.board"
    launchctl kickstart -k "gui/$(id -u)/com.ccc.board" 2>/dev/null || true
    sleep 2
  fi
  if [ -f "$CHECK" ]; then
    python3 "$CHECK" || true
  fi
  # wake engine if planned backlog exists
  if ls "$CLA/.ccc/board/planned"/*.jsonl >/dev/null 2>&1 || ls "$CLA/.ccc/board/backlog"/*.jsonl >/dev/null 2>&1; then
    printf '%s\n' '{"reason":"autonomy_hourly","workspace":"clawmed-ccc"}' > "$HOME/.ccc/engine.wake"
    echo "wrote engine.wake"
  fi
} >>"$OUT" 2>&1
