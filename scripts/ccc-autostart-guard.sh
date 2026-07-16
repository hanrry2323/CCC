#!/bin/bash
# ccc-autostart-guard.sh — CCC 控制面 CLI（v0.39）
#
# SSOT: ~/.ccc/control.json（见 scripts/_ccc_control.py）
#
#   disabled → 禁止一切拉起；停进程；卸 crontab 自启；挪走 KeepAlive plist
#   enabled  → 允许经 launchd 单点启动（本脚本 enable 可 bootstrap engine）
#
# 用法:
#   bash scripts/ccc-autostart-guard.sh disable
#   bash scripts/ccc-autostart-guard.sh enable [--start]
#   bash scripts/ccc-autostart-guard.sh status

set -uo pipefail

CCC_HOME="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="${CCC_HOME}/scripts${PYTHONPATH:+:$PYTHONPATH}"

_status() {
  python3 "${CCC_HOME}/scripts/_ccc_control.py" status
  echo "---"
  launchctl list 2>/dev/null | grep -E 'ccc|opencode.serve' || echo "(no ccc/opencode launchd agents)"
  crontab -l 2>/dev/null | grep -E 'ccc-loop-monitor|ccc-engine|flywheel' || echo "(no ccc crontab)"
  pgrep -fl 'ccc-engine\.py|ccc-board-server|ccc-chat-server|opencode serve' || echo "(no ccc processes)"
}

_disable() {
  python3 "${CCC_HOME}/scripts/_ccc_control.py" disable "guard disable"

  uid=$(id -u)
  for label in com.ccc.engine com.ccc.board com.ccc.chat-server \
               com.ccc.flywheel-scan com.ccc.loop-monitor com.opencode.serve; do
    launchctl bootout "gui/${uid}/${label}" 2>/dev/null || true
  done
  mkdir -p "${HOME}/Library/LaunchAgents/disabled-ccc"
  for f in "${HOME}/Library/LaunchAgents"/com.ccc.*.plist \
           "${HOME}/Library/LaunchAgents"/com.opencode.serve.plist; do
    [[ -f "$f" ]] || continue
    mv "$f" "${HOME}/Library/LaunchAgents/disabled-ccc/" 2>/dev/null || true
  done

  pkill -9 -f 'ccc-engine\.py' 2>/dev/null || true
  pkill -9 -f 'ccc-board-server\.py' 2>/dev/null || true
  pkill -9 -f 'ccc-chat-server\.py' 2>/dev/null || true
  pkill -9 -f 'opencode serve' 2>/dev/null || true
  pkill -9 -f 'claude -p' 2>/dev/null || true

  if crontab -l 2>/dev/null | grep -q 'ccc-loop-monitor'; then
    crontab -l 2>/dev/null | grep -v 'ccc-loop-monitor' | crontab -
    echo "removed ccc-loop-monitor from crontab"
  fi

  echo "CCC control=disabled"
  _status
}

_enable() {
  local do_start=0
  [[ "${1:-}" == "--start" ]] && do_start=1

  python3 "${CCC_HOME}/scripts/_ccc_control.py" enable "guard enable"

  # 恢复 engine plist（若在 disabled-ccc）
  local src="${HOME}/Library/LaunchAgents/disabled-ccc/com.ccc.engine.plist"
  local dst="${HOME}/Library/LaunchAgents/com.ccc.engine.plist"
  if [[ -f "$src" && ! -f "$dst" ]]; then
    mv "$src" "$dst"
    echo "restored $dst"
  fi

  if [[ "$do_start" == "1" ]]; then
    if [[ -f "$dst" ]]; then
      launchctl bootstrap "gui/$(id -u)" "$dst" 2>/dev/null \
        || launchctl load -w "$dst" 2>/dev/null \
        || true
      echo "requested launchd start for com.ccc.engine"
    else
      echo "WARN: no engine plist — run: bash scripts/install-ccc-roles.sh"
    fi
  else
    echo "control=enabled; Engine NOT started. Use: $0 enable --start"
  fi
  _status
}

case "${1:-status}" in
  disable) _disable ;;
  enable)  shift; _enable "$@" ;;
  status)  _status ;;
  *) echo "usage: $0 {disable|enable [--start]|status}"; exit 1 ;;
esac
