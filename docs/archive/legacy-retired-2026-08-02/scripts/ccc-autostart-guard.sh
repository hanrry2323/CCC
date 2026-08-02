#!/bin/bash
# ccc-autostart-guard.sh — CCC 控制面 CLI（v0.61.0 阶段 B 瘦身版）
#
# SSOT: ~/.ccc/control.json
#
#   disabled → 禁止一切常驻
#   ui       → 仅 Hub + Board（无 Engine）
#   enabled  → Engine 只消费队列（禁止自造）
#   invent   → Engine + 允许 audit/evolve/abnormal 回灌
#
# 启停统一委托 ccc-fleet.sh(本脚本不再维护 launchd 列表 / 探活 / 进程名)。
# 自身只管 control.json 状态切换 + status 输出。
#
# 用法:
#   bash scripts/ccc-autostart-guard.sh disable
#   bash scripts/ccc-autostart-guard.sh ui [--start]
#   bash scripts/ccc-autostart-guard.sh enable [--start]
#   bash scripts/ccc-autostart-guard.sh invent [--start]
#   bash scripts/ccc-autostart-guard.sh status
#   bash scripts/ccc-autostart-guard.sh status-fleet  # 委派 ccc-fleet.sh status

set -uo pipefail

CCC_HOME="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="${CCC_HOME}/scripts${PYTHONPATH:+:$PYTHONPATH}"

_disable() {
  python3 "${CCC_HOME}/scripts/_ccc_control.py" disable "guard disable"
  bash "${CCC_HOME}/scripts/ccc-fleet.sh" stop all
  if crontab -l 2>/dev/null | grep -q 'ccc-loop-monitor'; then
    crontab -l 2>/dev/null | grep -v 'ccc-loop-monitor' | crontab -
    echo "removed ccc-loop-monitor from crontab"
  fi
  echo "CCC control=disabled"
  status
}

_ui() {
  local do_start=0
  [[ "${1:-}" == "--start" ]] && do_start=1
  python3 "${CCC_HOME}/scripts/_ccc_control.py" ui "guard ui"
  if [[ "$do_start" == "1" ]]; then
    bash "${CCC_HOME}/scripts/ccc-fleet.sh" start ui-tier
  else
    echo "control=ui; Hub/Board NOT started. Use: $0 ui --start"
    echo "或前台开发: bash ${CCC_HOME}/scripts/ccc-hub-dev.sh"
  fi
  status
}

_enable() {
  local do_start=0
  [[ "${1:-}" == "--start" ]] && do_start=1
  python3 "${CCC_HOME}/scripts/_ccc_control.py" enable "guard enable"
  if [[ "$do_start" == "1" ]]; then
    bash "${CCC_HOME}/scripts/ccc-fleet.sh" start all
  else
    echo "control=enabled (queue consumer); Engine NOT started. Use: $0 enable --start"
  fi
  status
}

_invent() {
  local do_start=0
  [[ "${1:-}" == "--start" ]] && do_start=1
  python3 "${CCC_HOME}/scripts/_ccc_control.py" invent "guard invent"
  echo "WARN: invent allows audit→backlog / evolve / abnormal retry"
  if [[ "$do_start" == "1" ]]; then
    bash "${CCC_HOME}/scripts/ccc-fleet.sh" start all
  else
    echo "control=invent; Engine NOT started. Use: $0 invent --start"
  fi
  status
}

status() {
  python3 "${CCC_HOME}/scripts/_ccc_control.py" status
  echo "---"
  bash "${CCC_HOME}/scripts/ccc-fleet.sh" status 2>/dev/null || true
}

status_fleet() {
  bash "${CCC_HOME}/scripts/ccc-fleet.sh" status "$@"
}

case "${1:-status}" in
  disable) _disable ;;
  ui)      shift; _ui "$@" ;;
  enable)  shift; _enable "$@" ;;
  invent)  shift; _invent "$@" ;;
  status)  status ;;
  status-fleet) shift; status_fleet "$@" ;;
  *) echo "usage: $0 {disable|ui [--start]|enable [--start]|invent [--start]|status|status-fleet}"; exit 1 ;;
esac
