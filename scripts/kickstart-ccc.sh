#!/usr/bin/env bash
# ── scripts/kickstart-ccc.sh ──
# 幂等重启 com.ccc.engine、com.ccc.web-server 与 com.ccc.board-scheduler（P5 灭：防部署悬挂与热自愈）
#
# 用法：
#   ./scripts/kickstart-ccc.sh
#
# 机制：
#   优先使用 launchctl kickstart -k 热重启常驻服务，不中断外部通道；
#   如果 kickstart 失败（或系统不兼容），则优雅退回到 killall 强杀进程并通过 launchctl start 唤醒启动。

set -euo pipefail

UID_VAL="$(id -u)"
SERVICE_TARGETS=(
  "gui/${UID_VAL}/com.ccc.engine"
  "gui/${UID_VAL}/com.ccc.web-server"
  "gui/${UID_VAL}/com.ccc.board-scheduler"
)

# 备用进程名
PROCESS_NAMES=("server.engine.main" "server.web.server" "server.board.scheduler")

kickstart_service() {
  local service="$1"
  local name="${service##*/}"
  echo "[INFO] 正在尝试热重启常驻服务: ${service}..." >&2

  if launchctl kickstart -k "${service}" 2>/dev/null; then
    echo "[OK] 服务 ${name} 热重启成功。" >&2
    return 0
  fi

  echo "[WARN] launchctl kickstart 失败，尝试优雅退回到进程强杀与重新拉起..." >&2

  # 寻找对应的进程名并强杀
  local matched_pname=""
  if [[ "${name}" == *"engine"* ]]; then
    matched_pname="server.engine.main"
  elif [[ "${name}" == *"board-scheduler"* ]]; then
    matched_pname="server.board.scheduler"
  else
    matched_pname="server.web.server"
  fi

  # 使用 pkill/killall 杀掉进程以触发 KeepAlive
  if pkill -f "${matched_pname}" 2>/dev/null || killall -f "${matched_pname}" 2>/dev/null; then
    echo "[INFO] 已杀掉进程 ${matched_pname}，等待 launchd KeepAlive 唤醒机制..." >&2
  fi

  # launchctl start 确保服务状态处于启动中
  if launchctl start "${service}" 2>/dev/null; then
    echo "[OK] 服务 ${name} 进程已拉起并激活。" >&2
    return 0
  fi

  echo "[ERROR] 服务 ${name} 重启失败！" >&2
  return 1
}

# 依次处理两个核心服务
FAILED=0
for svc in "${SERVICE_TARGETS[@]}"; do
  if ! kickstart_service "${svc}"; then
    FAILED=$((FAILED + 1))
  fi
done

if [[ "$FAILED" -gt 0 ]]; then
  echo "[ERROR] 重启过程中发现有服务启动失败！" >&2
  exit 1
fi

echo "[OK] CCC 全套服务幂等热重启成功。"
exit 0
