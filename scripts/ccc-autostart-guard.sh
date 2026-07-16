#!/bin/bash
# ccc-autostart-guard.sh — CCC 控制面 CLI（v0.39.2）
#
# SSOT: ~/.ccc/control.json
#
#   disabled → 禁止一切常驻
#   ui       → 仅 Hub + Board（无 Engine）
#   enabled  → Engine 只消费队列（禁止自造）
#   invent   → Engine + 允许 audit/evolve/abnormal 回灌
#
# 前端日常开发（推荐，不改 control、不装 KeepAlive）:
#   bash scripts/ccc-hub-dev.sh
#
# 用法:
#   bash scripts/ccc-autostart-guard.sh disable
#   bash scripts/ccc-autostart-guard.sh ui [--start]
#   bash scripts/ccc-autostart-guard.sh enable [--start]   # 队列消费者
#   bash scripts/ccc-autostart-guard.sh invent [--start]   # 允许自造
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

_bootout_all() {
  local uid
  uid=$(id -u)
  for label in com.ccc.engine com.ccc.board com.ccc.chat-server \
               com.ccc.flywheel-scan com.ccc.loop-monitor com.opencode.serve \
               com.ccc.ccc-exec-launcher; do
    launchctl bootout "gui/${uid}/${label}" 2>/dev/null || true
    launchctl disable "gui/${uid}/${label}" 2>/dev/null || true
  done
  mkdir -p "${HOME}/Library/LaunchAgents/disabled-ccc"
  set +o nomatch 2>/dev/null || true
  for f in "${HOME}/Library/LaunchAgents"/com.ccc.*.plist \
           "${HOME}/Library/LaunchAgents"/com.opencode.serve.plist; do
    [[ -f "$f" ]] || continue
    mv -f "$f" "${HOME}/Library/LaunchAgents/disabled-ccc/" 2>/dev/null || true
  done
}

_kill_procs() {
  pkill -9 -f 'ccc-engine\.py' 2>/dev/null || true
  pkill -9 -f 'ccc-engine\.sh' 2>/dev/null || true
  pkill -9 -f 'ccc-board-server\.py' 2>/dev/null || true
  pkill -9 -f 'ccc-chat-server\.py' 2>/dev/null || true
  pkill -9 -f 'opencode serve' 2>/dev/null || true
  pkill -9 -f 'claude -p' 2>/dev/null || true
}

_disable() {
  python3 "${CCC_HOME}/scripts/_ccc_control.py" disable "guard disable"
  _bootout_all
  _kill_procs

  if crontab -l 2>/dev/null | grep -q 'ccc-loop-monitor'; then
    crontab -l 2>/dev/null | grep -v 'ccc-loop-monitor' | crontab -
    echo "removed ccc-loop-monitor from crontab"
  fi

  echo "CCC control=disabled"
  _status
}

_restore_plist() {
  local name="$1"
  local src="${HOME}/Library/LaunchAgents/disabled-ccc/${name}"
  local dst="${HOME}/Library/LaunchAgents/${name}"
  if [[ -f "$src" && ! -f "$dst" ]]; then
    mv "$src" "$dst"
    echo "restored $dst"
  fi
  [[ -f "$dst" ]]
}

_start_ui_agents() {
  local uid
  uid=$(id -u)
  for name in com.ccc.board.plist com.ccc.chat-server.plist; do
    _restore_plist "$name" || true
    local active="${HOME}/Library/LaunchAgents/${name}"
    if [[ -f "$active" ]]; then
      local label="${name%.plist}"
      launchctl enable "gui/${uid}/${label}" 2>/dev/null || true
      launchctl bootstrap "gui/${uid}" "$active" 2>/dev/null \
        || launchctl load -w "$active" 2>/dev/null \
        || true
      echo "requested start $label"
    else
      echo "WARN: missing $active — run: bash scripts/install-board-plist.sh && bash scripts/install-hub-plist.sh"
    fi
  done
}

_ui() {
  local do_start=0
  [[ "${1:-}" == "--start" ]] && do_start=1

  python3 "${CCC_HOME}/scripts/_ccc_control.py" ui "guard ui"

  # 确保 Engine 不在跑
  local uid
  uid=$(id -u)
  launchctl bootout "gui/${uid}/com.ccc.engine" 2>/dev/null || true
  launchctl disable "gui/${uid}/com.ccc.engine" 2>/dev/null || true
  pkill -9 -f 'ccc-engine\.py' 2>/dev/null || true
  pkill -9 -f 'ccc-engine\.sh' 2>/dev/null || true
  if [[ -f "${HOME}/Library/LaunchAgents/com.ccc.engine.plist" ]]; then
    mkdir -p "${HOME}/Library/LaunchAgents/disabled-ccc"
    mv -f "${HOME}/Library/LaunchAgents/com.ccc.engine.plist" \
      "${HOME}/Library/LaunchAgents/disabled-ccc/" 2>/dev/null || true
  fi

  if [[ "$do_start" == "1" ]]; then
    _start_ui_agents
  else
    echo "control=ui; Hub/Board NOT started. Use: $0 ui --start"
    echo "或前台开发: bash ${CCC_HOME}/scripts/ccc-hub-dev.sh"
  fi
  _status
}

_start_engine() {
  uid=$(id -u)
  launchctl enable "gui/${uid}/com.ccc.engine" 2>/dev/null || true
  local src="${HOME}/Library/LaunchAgents/disabled-ccc/com.ccc.engine.plist"
  local dst="${HOME}/Library/LaunchAgents/com.ccc.engine.plist"
  if [[ -f "$src" && ! -f "$dst" ]]; then
    mv "$src" "$dst"
    echo "restored $dst"
  fi
  if [[ -f "$dst" ]]; then
    launchctl bootstrap "gui/$(id -u)" "$dst" 2>/dev/null \
      || launchctl load -w "$dst" 2>/dev/null \
      || true
    echo "requested launchd start for com.ccc.engine"
  else
    echo "WARN: no engine plist — run: bash scripts/install-ccc-roles.sh"
  fi
}

_enable() {
  local do_start=0
  [[ "${1:-}" == "--start" ]] && do_start=1
  python3 "${CCC_HOME}/scripts/_ccc_control.py" enable "guard enable"
  if [[ "$do_start" == "1" ]]; then
    _start_engine
  else
    echo "control=enabled (queue consumer); Engine NOT started. Use: $0 enable --start"
  fi
  _status
}

_invent() {
  local do_start=0
  [[ "${1:-}" == "--start" ]] && do_start=1
  python3 "${CCC_HOME}/scripts/_ccc_control.py" invent "guard invent"
  echo "WARN: invent allows audit→backlog / evolve / abnormal retry"
  if [[ "$do_start" == "1" ]]; then
    _start_engine
  else
    echo "control=invent; Engine NOT started. Use: $0 invent --start"
  fi
  _status
}

case "${1:-status}" in
  disable) _disable ;;
  ui)      shift; _ui "$@" ;;
  enable)  shift; _enable "$@" ;;
  invent)  shift; _invent "$@" ;;
  status)  _status ;;
  *) echo "usage: $0 {disable|ui [--start]|enable [--start]|invent [--start]|status}"; exit 1 ;;
esac
