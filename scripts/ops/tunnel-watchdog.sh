#!/usr/bin/env bash
set -euo pipefail

CCC_M1_HOST="${CCC_M1_HOST:-192.168.3.140}"
CCC_TUNNEL_LABEL="${CCC_TUNNEL_LABEL:-com.fan.m1-tunnel}"
CCC_TUNNEL_HEALTH_URL="${CCC_TUNNEL_HEALTH_URL:-http://127.0.0.1:3456/v1/models}"
CCC_WEB_HEALTH_URL="${CCC_WEB_HEALTH_URL:-http://192.168.3.116:7788/health}"
LOG_FILE="${CCC_TUNNEL_WATCHDOG_LOG:-${HOME}/.ccc/logs/tunnel-watchdog.log}"

mkdir -p "$(dirname "$LOG_FILE")"

log_line() {
  printf '%s action=%s result=%s\n' "$(date '+%Y-%m-%dT%H:%M:%S%z')" "$1" "$2" >> "$LOG_FILE"
}


# ── 日志轮转（copytruncate 式，>50M 截断，保留最近 3 份）──
rotate_log() {
  local f="$1" cap=$((50 * 1024 * 1024))
  [ -f "$f" ] || return 0
  local size
  size=$(stat -f %z "$f" 2>/dev/null || echo 0)
  [ "$size" -gt "$cap" ] || return 0
  local ts; ts=$(date +%Y%m%d%H%M%S)
  cp "$f" "${f}.${ts}" && : > "$f"
  ls -t "${f}".* 2>/dev/null | grep -v '\.log$' | tail -n +4 | xargs rm -f 2>/dev/null
  echo "$(date '+%Y-%m-%dT%H:%M:%S%z') action=log-rotate result=done file=$f size=$size" >> "$LOG_FILE"
}
rotate_log "${HOME}/.ccc/logs/engine.stderr.log"
rotate_log "${HOME}/.ccc/logs/web-server.stderr.log"

probe_tunnel() {
  [[ "$(curl -s -m 5 -o /dev/null -w '%{http_code}' "$CCC_TUNNEL_HEALTH_URL")" == "200" ]]
}

if probe_tunnel; then
  exit 0
fi

if nc -z -w 3 "$CCC_M1_HOST" 22 >/dev/null 2>&1; then
  launchctl kickstart -k "gui/$(id -u)/${CCC_TUNNEL_LABEL}"
  sleep 6
  if probe_tunnel; then
    log_line kickstart recovered
    if curl -s -m 5 -o /dev/null "$CCC_WEB_HEALTH_URL"; then
      log_line ccc-web-health reachable
    else
      log_line ccc-web-health unreachable
    fi
  else
    log_line kickstart failed
  fi
else
  log_line m1-connectivity unreachable
fi

exit 0
