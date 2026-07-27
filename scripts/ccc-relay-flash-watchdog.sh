#!/usr/bin/env bash
# CCC Relay flash 探针看门狗（2017）
# 每轮 POST /v1/messages flash；连续失败达阈值 → kickstart com.ccc.relay.2017
#
# 用法：
#   bash scripts/ccc-relay-flash-watchdog.sh          # 单次探针
#   bash scripts/ccc-relay-flash-watchdog.sh --loop    # 每 60s（前台）
# launchd：见 scripts/install-relay-flash-watchdog-plist.sh

set -euo pipefail

RELAY_URL="${CCC_RELAY_URL:-http://127.0.0.1:4000}"
LABEL="${CCC_RELAY_LABEL:-com.ccc.relay.2017}"
FAIL_FILE="${CCC_RELAY_WD_STATE:-$HOME/.ccc/relay/flash-watchdog.fail}"
LOG_DIR="${CCC_RELAY_WD_LOG_DIR:-$HOME/.ccc/logs}"
MAX_FAIL="${CCC_RELAY_WD_MAX_FAIL:-3}"
TIMEOUT_S="${CCC_RELAY_WD_TIMEOUT:-25}"
INTERVAL_S="${CCC_RELAY_WD_INTERVAL:-60}"

mkdir -p "$(dirname "$FAIL_FILE")" "$LOG_DIR"
LOG="$LOG_DIR/ccc-relay-flash-watchdog.log"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }

probe_once() {
  local code
  code=$(curl -sS -m "$TIMEOUT_S" -o /tmp/ccc-relay-wd-body.json -w '%{http_code}' \
    "$RELAY_URL/v1/messages" \
    -H 'content-type: application/json' \
    -d '{"model":"flash","max_tokens":8,"messages":[{"role":"user","content":"wd"}]}' \
    2>/tmp/ccc-relay-wd-curl.err || echo "000")
  if [[ "$code" == "200" ]]; then
    echo 0 > "$FAIL_FILE"
    return 0
  fi
  local n=0
  [[ -f "$FAIL_FILE" ]] && n=$(cat "$FAIL_FILE" 2>/dev/null || echo 0)
  n=$((n + 1))
  echo "$n" > "$FAIL_FILE"
  log "FAIL http=$code streak=$n/$(cat "$FAIL_FILE") curl=$(tr '\n' ' ' </tmp/ccc-relay-wd-curl.err | head -c 120) body=$(head -c 160 /tmp/ccc-relay-wd-body.json 2>/dev/null || true)"
  if (( n >= MAX_FAIL )); then
    log "kickstart $LABEL after $n consecutive failures"
    launchctl kickstart -k "gui/$(id -u)/$LABEL" 2>>"$LOG" || log "kickstart failed"
    echo 0 > "$FAIL_FILE"
  fi
  return 1
}

if [[ "${1:-}" == "--loop" ]]; then
  while true; do
    probe_once || true
    sleep "$INTERVAL_S"
  done
else
  probe_once
fi
