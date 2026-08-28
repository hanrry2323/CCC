#!/usr/bin/env bash
# ── scripts/kickstart-ccc.sh ──
# 幂等重启 com.ccc.engine 与 com.ccc.web-server 两服务（ccc-plan-052 卡C：服务集对齐两服务；board-scheduler/watchdog 维持停用，巡检已内嵌 engine）
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

# 服务配置（ccc-plan-052 卡C：恰两服务）
ENGINE_SERVICE="gui/${UID_VAL}/com.ccc.engine"
WEB_SERVICE="gui/${UID_VAL}/com.ccc.web-server"

ENGINE_PNAME="server.engine.main"
WEB_PNAME="server.web.server"

# ── ccc083 防旋（2026-08-25）：同服务最小重启间隔 + DRY-RUN 演练 ──
# 背景：2026-08-24 机审会话连环触发本脚本（47 次 kickstart），在飞执行体被连带击杀
# （exit 137）→ 引擎回待分派重派 → 自持风暴。本闸为最内层防线：任何调用方
# （watchdog/deploy/人工）对同一服务的重启间隔不得小于 CCC_KICKSTART_MIN_INTERVAL 秒。
#   CCC_KICKSTART_MIN_INTERVAL  默认 60；设 0 关闭冷却
#   CCC_KICKSTART_FORCE=1       跳过冷却强制重启（人工确认场景）
#   CCC_KICKSTART_DRY_RUN=1     只记录意图不执行 launchctl/pkill（测试/演练）
KICK_MIN_INTERVAL="${CCC_KICKSTART_MIN_INTERVAL:-60}"
KICK_FORCE="${CCC_KICKSTART_FORCE:-0}"
KICK_DRY_RUN="${CCC_KICKSTART_DRY_RUN:-0}"
KICK_STATE_DIR="${CCC_KICKSTART_STATE_DIR:-${LOG_DIR}/kickstart-state}"

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
  local state_file="${KICK_STATE_DIR}/${name}.last"
  local now last delta

  # 冷却检查：距上次真实重启不足间隔则跳过（幂等安全侧）
  now="$(date +%s)"
  last="$(cat "${state_file}" 2>/dev/null | tr -cd '0-9')"
  last="${last:-0}"
  delta=$((now - last))
  if [[ "${KICK_FORCE}" != "1" ]] && [[ "${KICK_DRY_RUN}" != "1" ]] \
     && (( KICK_MIN_INTERVAL > 0 )) && (( delta < KICK_MIN_INTERVAL )); then
    echo "[INFO] 服务 ${name} 距上次重启 ${delta}s < ${KICK_MIN_INTERVAL}s，冷却跳过（FORCE=1 可强制）" >&2
    log_kickstart "冷却跳过: ${name}（${delta}s < ${KICK_MIN_INTERVAL}s）"
    return 0
  fi

  # 未挂载的服务跳过（如 com.ccc.engine 待 052 卡B 装回）：WARN 不算失败，
  # 部署链不因「服务尚未装回」而整体失败；已挂载服务的重启失败仍为 ERROR。
  if ! launchctl print "${service}" >/dev/null 2>&1; then
    echo "[WARN] 服务 ${name} 未挂载（launchctl print 失败），跳过重启" >&2
    log_kickstart "跳过未挂载服务: ${name}"
    return 0
  fi

  if [[ "${KICK_DRY_RUN}" == "1" ]]; then
    echo "[DRY-RUN] 将热重启 ${service}（未执行 launchctl/pkill）" >&2
    log_kickstart "[DRY-RUN] 热重启意图: ${name}"
    mkdir -p "${KICK_STATE_DIR}" 2>/dev/null || true
    echo "${now}" > "${state_file}" 2>/dev/null || true
    return 0
  fi

  echo "[INFO] 正在尝试热重启常驻服务: ${service}..." >&2

  if launchctl kickstart -k "${service}" 2>/dev/null; then
    echo "[OK] 服务 ${name} 热重启成功。" >&2
    log_kickstart "热重启成功: ${name}"
    mkdir -p "${KICK_STATE_DIR}" 2>/dev/null || true
    echo "${now}" > "${state_file}" 2>/dev/null || true
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

if [[ "${FAILED}" -gt 0 ]]; then
  echo "[ERROR] 重启过程中发现有服务启动失败！" >&2
  exit 1
fi

echo "[OK] CCC 服务幂等热重启成功。"
exit 0
