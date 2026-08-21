#!/usr/bin/env bash
# ── scripts/kickstart-ccc.sh ──
# 幂等重启 com.ccc.engine、com.ccc.web-server 与 com.ccc.board-scheduler（P5 灭：防部署悬挂与热自愈）
#
# 用法：
#   ./scripts/kickstart-ccc.sh [--engine-only] [--web-only] [--all]
#
# 机制：
#   优先使用 launchctl kickstart -k 热重启常驻服务，不中断外部通道；
#   如果 kickstart 失败（或系统不兼容），则优雅退回到 killall 强杀进程并通过 launchctl start 唤醒启动。
#
# 2026-08-21 修复：分离服务重启逻辑，避免 engine 故障时连带重启 web-server

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="${HOME}/.ccc/logs"
mkdir -p "${LOG_DIR}"

WATCHDOG_LOG="${LOG_DIR}/watchdog.log"

log_kickstart() {
  local msg="$1"
  local ts
  ts="$(date '+%Y-%m-%d %H:%M:%S')"
  echo "[${ts}] ${msg}" >> "${WATCHDOG_LOG}"
}

UID_VAL="$(id -u)"

# 服务配置
ENGINE_SERVICE="gui/${UID_VAL}/com.ccc.engine"
WEB_SERVICE="gui/${UID_VAL}/com.ccc.web-server"
SCHEDULER_SERVICE="gui/${UID_VAL}/com.ccc.board-scheduler"

ENGINE_PNAME="server.engine.main"
WEB_PNAME="server.web.server"
SCHEDULER_PNAME="server.board.scheduler"

# 解析参数
ENGINE_ONLY=false
WEB_ONLY=false
ALL=true

for arg in "$@"; do
  case "$arg" in
    --engine-only)
      ENGINE_ONLY=true
      ALL=false
      ;;
    --web-only)
      WEB_ONLY=true
      ALL=false
      ;;
    --all)
      ALL=true
      ;;
    *)
      echo "[WARN] 未知参数: $arg" >&2
      ;;
  esac
done

kickstart_service() {
  local service="$1"
  local pname="$2"
  local name="${service##*/}"
  
  echo "[INFO] 正在尝试热重启常驻服务: ${service}..." >&2

  if launchctl kickstart -k "${service}" 2>/dev/null; then
    echo "[OK] 服务 ${name} 热重启成功。" >&2
    log_kickstart "热重启成功: ${name}"
    return 0
  fi

  echo "[WARN] launchctl kickstart 失败，尝试优雅退回到进程强杀与重新拉起..." >&2
  log_kickstart "kickstart 失败，尝试强杀: ${name}"

  # 使用 pkill/killall 杀掉进程以触发 KeepAlive
  if pkill -f "${pname}" 2>/dev/null || killall -f "${pname}" 2>/dev/null; then
    echo "[INFO] 已杀掉进程 ${pname}，等待 launchd KeepAlive 唤醒机制..." >&2
    log_kickstart "已强杀进程: ${pname}"
  fi

  # launchctl start 确保服务状态处于启动中
  if launchctl start "${service}" 2>/dev/null; then
    echo "[OK] 服务 ${name} 进程已拉起并激活。" >&2
    log_kickstart "launchctl start 成功: ${name}"
    return 0
  fi

  echo "[ERROR] 服务 ${name} 重启失败！" >&2
  log_kickstart "ERROR: 服务重启失败: ${name}"
  return 1
}

FAILED=0

# 根据参数决定重启哪些服务
if [[ "${ALL}" == true ]] || [[ "${ENGINE_ONLY}" == true ]]; then
  if ! kickstart_service "${ENGINE_SERVICE}" "${ENGINE_PNAME}"; then
    FAILED=$((FAILED + 1))
  fi
fi

if [[ "${ALL}" == true ]] || [[ "${WEB_ONLY}" == true ]]; then
  if ! kickstart_service "${WEB_SERVICE}" "${WEB_PNAME}"; then
    FAILED=$((FAILED + 1))
  fi
fi

if [[ "${ALL}" == true ]]; then
  if ! kickstart_service "${SCHEDULER_SERVICE}" "${SCHEDULER_PNAME}"; then
    FAILED=$((FAILED + 1))
  fi
fi

if [[ "${FAILED}" -gt 0 ]]; then
  echo "[ERROR] 重启过程中发现有服务启动失败！" >&2
  exit 1
fi

echo "[OK] CCC 服务幂等热重启成功。"
exit 0
