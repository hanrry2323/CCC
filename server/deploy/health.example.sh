#!/usr/bin/env bash
# ── CCC Engine 健康检查脚本（模板） ──
# 复制为 health.sh，按环境修改后使用。
# 输出 JSON 供监控探活。
#
# 用法：./health.sh [--config /path/to/config.env]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG_ENV="${CCC_CONFIG_ENV:-${PROJECT_ROOT}/server/config/config.env}"

if [[ -f "$CONFIG_ENV" ]]; then
  set -a
  source "$CONFIG_ENV"
  set +a
fi

ENGINE_PORT="${ENGINE_PORT:-}"
ENGINE_HOST="${ENGINE_HOST:-127.0.0.1}"
PYTHON_BIN="${PYTHON_BIN:-}"

# ── 健康检查：探活 Engine HTTP 端点 ──
ENGINE_UP=false
ENGINE_LATENCY_MS=""

if [[ -n "$ENGINE_PORT" ]]; then
  if [[ -n "$PYTHON_BIN" ]]; then
    start_ms=$("$PYTHON_BIN" -c 'import time; print(int(time.time() * 1000))')
  fi
  if curl -sf "http://${ENGINE_HOST}:${ENGINE_PORT}/health" >/dev/null 2>&1; then
    ENGINE_UP=true
    if [[ -n "${start_ms:-}" ]]; then
      end_ms=$("$PYTHON_BIN" -c 'import time; print(int(time.time() * 1000))')
      ENGINE_LATENCY_MS=$(( end_ms - start_ms ))
    fi
  fi
fi

# ── 磁盘 / 日志目录检查 ──
LOG_DIR="${LOG_DIR:-}"
LOG_DIR_WRITABLE=false
if [[ -n "$LOG_DIR" && -d "$LOG_DIR" && -w "$LOG_DIR" ]]; then
  LOG_DIR_WRITABLE=true
fi

# ── 输出 JSON ──
cat <<EOF
{
  "service": "ccc-engine",
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "engine_up": $ENGINE_UP,
  "engine_host": "${ENGINE_HOST}",
  "engine_port": "${ENGINE_PORT}",
  "engine_latency_ms": ${ENGINE_LATENCY_MS:-null},
  "log_dir_writable": $LOG_DIR_WRITABLE,
  "config_file": "${CONFIG_ENV}"
}
EOF

# ── Web Server 健康检查示例（T19 壳迁移后探活 7788） ──
# 用法：bash health-web.sh [--config /path/to/config.env]
# 输出 JSON 供监控探活。
#
# WEB_HOST="${WEB_HOST:-127.0.0.1}"
# WEB_PORT="${WEB_PORT:-7788}"
# WEB_UP=false
# if curl -sf "http://${WEB_HOST}:${WEB_PORT}/health" >/dev/null 2>&1; then
#   WEB_UP=true
# fi
# cat <<EOF
# {
#   "service": "ccc-web-server",
#   "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
#   "web_up": $WEB_UP,
#   "web_host": "${WEB_HOST}",
#   "web_port": "${WEB_PORT}"
# }
# EOF