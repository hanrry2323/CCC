#!/bin/bash
# ccc-autostart-guard.sh — CCC 总开关（防后台无限自启）
#
# ~/.ccc/DISABLED 存在时：
#   - engine / patrol / loop-monitor 不得拉起任何 CCC 进程
#   - launchd KeepAlive 若仍在，engine.sh 进入空转 sleep（不干活）
#
# 用法:
#   bash scripts/ccc-autostart-guard.sh disable   # 立即停机 + 写哨兵 + 卸 crontab
#   bash scripts/ccc-autostart-guard.sh enable    # 删哨兵（不自动 load plist）
#   bash scripts/ccc-autostart-guard.sh status

set -uo pipefail

SENTINEL="${HOME}/.ccc/DISABLED"
CCC_HOME="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

_status() {
  if [[ -f "$SENTINEL" ]]; then
    echo "CCC_AUTOSTART=OFF  ($SENTINEL)"
  else
    echo "CCC_AUTOSTART=ON   (no sentinel)"
  fi
  launchctl list 2>/dev/null | grep ccc || echo "(no ccc launchd agents)"
  crontab -l 2>/dev/null | grep -E 'ccc-loop-monitor|ccc-engine|flywheel' || echo "(no ccc crontab)"
  pgrep -fl 'ccc-engine|ccc-board-server|ccc-chat-server' || echo "(no ccc processes)"
}

_disable() {
  mkdir -p "${HOME}/.ccc"
  cat > "$SENTINEL" <<EOF
# CCC disabled $(date -u +%Y-%m-%dT%H:%M:%SZ)
# Remove this file (or: bash scripts/ccc-autostart-guard.sh enable) to allow Engine again.
EOF
  echo "wrote $SENTINEL"

  # 卸 launchd（含 opencode serve — CCC 执行器常驻，KeepAlive 会复活）
  uid=$(id -u)
  for label in com.ccc.engine com.ccc.board com.ccc.chat-server com.ccc.flywheel-scan com.ccc.loop-monitor com.opencode.serve; do
    launchctl bootout "gui/${uid}/${label}" 2>/dev/null || true
  done
  mkdir -p "${HOME}/Library/LaunchAgents/disabled-ccc"
  for f in "${HOME}/Library/LaunchAgents"/com.ccc.*.plist \
           "${HOME}/Library/LaunchAgents"/com.opencode.serve.plist; do
    [[ -f "$f" ]] || continue
    mv "$f" "${HOME}/Library/LaunchAgents/disabled-ccc/" 2>/dev/null || true
  done

  # 杀进程
  pkill -9 -f 'ccc-engine\.py' 2>/dev/null || true
  pkill -9 -f 'ccc-board-server\.py' 2>/dev/null || true
  pkill -9 -f 'ccc-chat-server\.py' 2>/dev/null || true
  pkill -9 -f 'opencode serve' 2>/dev/null || true
  pkill -9 -f 'claude -p' 2>/dev/null || true

  # 卸 crontab 中的 loop-monitor（根因：每 5 分钟强制拉起 engine）
  if crontab -l 2>/dev/null | grep -q 'ccc-loop-monitor'; then
    crontab -l 2>/dev/null | grep -v 'ccc-loop-monitor' | crontab -
    echo "removed ccc-loop-monitor from crontab"
  fi

  echo "CCC disabled."
  _status
}

_enable() {
  rm -f "$SENTINEL"
  echo "removed $SENTINEL (Engine will NOT auto-start until you load plists)"
  echo "To start: mv ~/Library/LaunchAgents/disabled-ccc/com.ccc.engine.plist ~/Library/LaunchAgents/ && launchctl bootstrap gui/\$(id -u) ~/Library/LaunchAgents/com.ccc.engine.plist"
  _status
}

case "${1:-status}" in
  disable) _disable ;;
  enable)  _enable ;;
  status)  _status ;;
  *) echo "usage: $0 {disable|enable|status}"; exit 1 ;;
esac
