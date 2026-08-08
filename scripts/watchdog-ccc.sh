#!/usr/bin/env bash
# ── scripts/watchdog-ccc.sh ──
# CCC 看门狗守护脚本（P5 灭：服务防死锁与 <60s 快速自愈）
#
# 用法：
#   ./scripts/watchdog-ccc.sh
#
# 机制：
#   1. 检查 com.ccc.engine (server.engine.main) 进程是否存在
#   2. 检查日志 ~/.ccc/logs/engine.stdout.log 的最近心跳修改时间 (mtime < 120s)
#   3. 如果以上任何一项异常，触发 kickstart-ccc.sh 并记录动作到 ~/.ccc/logs/watchdog.log
#
# 部署说明（如何挂载到 cron 或 launchd，实现 60 秒高频轮询）：
#   CRON 挂载 (每周一至周日, 每分钟执行一次):
#     * * * * * /Users/apple/program/CCC/scripts/watchdog-ccc.sh >/dev/null 2>&1
#
#   LAUNCHD 部署 (plist 示例，挂载到 ~/Library/LaunchAgents/com.ccc.watchdog.plist):
#     <?xml version="1.0" encoding="UTF-8"?>
#     <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
#     <plist version="1.0">
#     <dict>
#         <key>Label</key>
#         <string>com.ccc.watchdog</string>
#         <key>ProgramArguments</key>
#         <array>
#             <string>/Users/apple/program/CCC/scripts/watchdog-ccc.sh</string>
#         </array>
#         <key>StartInterval</key>
#         <integer>60</integer>
#         <key>RunAtLoad</key>
#         <true/>
#     </dict>
#     </plist>

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="${HOME}/.ccc/logs"
mkdir -p "${LOG_DIR}"

HEARTBEAT_LOG="${LOG_DIR}/engine.stdout.log"
WATCHDOG_LOG="${LOG_DIR}/watchdog.log"

ENGINE_PNAME="server.engine.main"

log_watchdog() {
  local msg="$1"
  local ts
  today="$(date '+%Y-%m-%d %H:%M:%S')"
  echo "[${today}] ${msg}" >> "${WATCHDOG_LOG}"
}

# 1. 检查常驻进程是否存在
is_alive() {
  pgrep -f "${ENGINE_PNAME}" >/dev/null 2>&1
}

# 2. 检查日志心跳 (mtime < 120s)
is_healthy_heartbeat() {
  if [[ ! -f "${HEARTBEAT_LOG}" ]]; then
    return 1
  fi

  local last_mod
  # mac/darwin vs linux compatibility
  if [[ "$OSTYPE" == "darwin"* ]]; then
    last_mod=$(stat -f "%m" "${HEARTBEAT_LOG}")
  else
    last_mod=$(stat -c "%Y" "${HEARTBEAT_LOG}")
  fi

  local now
  now=$(date +%s)
  local diff=$((now - last_mod))

  if [[ $diff -lt 120 ]]; then
    return 0 # 健康
  else
    return 1 # 心跳超时
  fi
}

HEALTHY=true
REASON=""

if ! is_alive; then
  HEALTHY=false
  REASON="Engine 进程不存在"
elif ! is_healthy_heartbeat; then
  HEALTHY=false
  REASON="Engine 日志心跳超时 (未在120s内刷新)"
fi

if [[ "$HEALTHY" == "true" ]]; then
  echo "健康"
  exit 0
fi

# 不健康，触发自愈热重启
log_watchdog "发现故障: ${REASON} -> 正在触发 kickstart 自愈重启机制"
echo "[WARN] 发现故障: ${REASON}，启动热重启自愈..." >&2

if "${SCRIPT_DIR}/kickstart-ccc.sh" >/dev/null 2>&1; then
  log_watchdog "自愈成功：kickstart 触发完毕"
  echo "已拉起"
  exit 0
else
  log_watchdog "ERROR：自愈失败，kickstart 重启异常"
  echo "失败"
  exit 1
fi
