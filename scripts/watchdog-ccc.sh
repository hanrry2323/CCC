#!/usr/bin/env bash
# ── scripts/watchdog-ccc.sh ──
# CCC 看门狗守护脚本（P5 灭：服务防死锁与 <60s 快速自愈）
#
# 用法：
#   ./scripts/watchdog-ccc.sh
#
# 机制：
#   1. 检查 com.ccc.engine (server.engine.main) 进程是否存在
#   2. 检查 com.ccc.web-server 进程是否存在
#   3. 检查日志 ~/.ccc/logs/engine.stderr.log 的最近心跳修改时间 (mtime < 120s)
#   4. 如果任何一项异常，只重启对应服务（不连带重启其他服务）
#
# 2026-08-21 修复：分离服务健康检查，避免 engine 故障时连带重启 web-server

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="${HOME}/.ccc/logs"
mkdir -p "${LOG_DIR}"

HEARTBEAT_LOG="${LOG_DIR}/engine.stderr.log"
# 槽位心跳（run_once 每轮写 engine-metrics.jsonl）——真实心跳源，优先于 stderr.log
SLOT_METRICS="${LOG_DIR}/exec/engine-metrics.jsonl"
WATCHDOG_LOG="${LOG_DIR}/watchdog.log"

ENGINE_PNAME="server.engine.main"
WEB_PNAME="server.web.server"

# 心跳宽限（秒）：engine 心跳默认 60s，但 run_once 偶发阻塞（子进程/SSH）可达 10-40min，
# 固定 120s 会误杀。默认 300s，可经 CCC_WATCHDOG_HEARTBEAT_GRACE 覆盖。
HEARTBEAT_GRACE="${CCC_WATCHDOG_HEARTBEAT_GRACE:-300}"

log_watchdog() {
  local msg="$1"
  local ts
  ts="$(date '+%Y-%m-%d %H:%M:%S')"
  echo "[${ts}] ${msg}" >> "${WATCHDOG_LOG}"
}

# 1. 检查 engine 进程是否存在
is_engine_alive() {
  pgrep -f "${ENGINE_PNAME}" >/dev/null 2>&1
}

# 2. 检查 web-server 进程是否存在
is_web_alive() {
  pgrep -f "${WEB_PNAME}" >/dev/null 2>&1
}

# 3. 检查 engine 心跳新鲜度：优先 slot 心跳 engine-metrics.jsonl（run_once 每轮写），
#    缺失/不可读回退 stderr.log。宽限 HEARTBEAT_GRACE（默认 300s，2026-08-22 硬化）。
is_engine_heartbeat_healthy() {
  local source=""
  local last_mod=""

  if [[ -f "${SLOT_METRICS}" ]]; then
    source="${SLOT_METRICS}"
  elif [[ -f "${HEARTBEAT_LOG}" ]]; then
    source="${HEARTBEAT_LOG}"
  else
    return 1
  fi

  if [[ "$OSTYPE" == "darwin"* ]]; then
    last_mod=$(stat -f "%m" "${source}")
  else
    last_mod=$(stat -c "%Y" "${source}")
  fi

  local now
  now=$(date +%s)
  local diff=$((now - last_mod))

  if [[ $diff -lt ${HEARTBEAT_GRACE} ]]; then
    return 0
  else
    return 1
  fi
}

# 4. 检查 web-server HTTP 健康
is_web_http_healthy() {
  local http_code
  http_code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 3 http://localhost:7788/health 2>/dev/null || echo "000")
  if [[ "$http_code" == "200" ]]; then
    return 0
  else
    return 1
  fi
}

# 检查各服务状态
ENGINE_ISSUES=()
WEB_ISSUES=()

# Engine 检查
if ! is_engine_alive; then
  ENGINE_ISSUES+=("进程不存在")
elif ! is_engine_heartbeat_healthy; then
  ENGINE_ISSUES+=("日志心跳超时")
fi

# Web Server 检查
if ! is_web_alive; then
  WEB_ISSUES+=("进程不存在")
elif ! is_web_http_healthy; then
  WEB_ISSUES+=("HTTP 健康检查失败")
fi

# 如果都没问题，退出
if [[ ${#ENGINE_ISSUES[@]} -eq 0 ]] && [[ ${#WEB_ISSUES[@]} -eq 0 ]]; then
  echo "健康"
  exit 0
fi

# 只重启有问题的服务，不连带重启
FAILED=0

if [[ ${#ENGINE_ISSUES[@]} -gt 0 ]]; then
  REASON="Engine: ${ENGINE_ISSUES[*]}"
  log_watchdog "发现故障 [${REASON}] -> 正在触发 kickstart --engine-only"
  echo "[WARN] 发现故障: ${REASON}，启动针对性自愈..." >&2
  
  if "${SCRIPT_DIR}/kickstart-ccc.sh" --engine-only >/dev/null 2>&1; then
    log_watchdog "自愈成功：engine 重启完毕"
    echo "Engine 已拉起"
  else
    log_watchdog "ERROR：engine 自愈失败"
    echo "Engine 重启失败"
    FAILED=$((FAILED + 1))
  fi
fi

if [[ ${#WEB_ISSUES[@]} -gt 0 ]]; then
  REASON="Web Server: ${WEB_ISSUES[*]}"
  log_watchdog "发现故障 [${REASON}] -> 正在触发 kickstart --web-only"
  echo "[WARN] 发现故障: ${REASON}，启动针对性自愈..." >&2
  
  if "${SCRIPT_DIR}/kickstart-ccc.sh" --web-only >/dev/null 2>&1; then
    log_watchdog "自愈成功：web-server 重启完毕"
    echo "Web Server 已拉起"
  else
    log_watchdog "ERROR：web-server 自愈失败"
    echo "Web Server 重启失败"
    FAILED=$((FAILED + 1))
  fi
fi

if [[ $FAILED -gt 0 ]]; then
  exit 1
fi

exit 0
