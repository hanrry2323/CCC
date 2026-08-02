#!/usr/bin/env bash
# ── CCC Engine 启动脚本（模板） ──
# 复制为 run.sh，按环境修改 CONFIG_ENV 路径后执行。
# 用法：./run.sh [--config /path/to/config.env]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# ── 默认配置路径 ──
CONFIG_ENV="${CCC_CONFIG_ENV:-${PROJECT_ROOT}/server/config/config.env}"

# 解析 --config 参数
if [[ $# -ge 2 && "$1" == "--config" ]]; then
  CONFIG_ENV="$2"
fi

if [[ ! -f "$CONFIG_ENV" ]]; then
  echo "[FATAL] config file not found: $CONFIG_ENV" >&2
  echo "  Copy server/config/config.example.env to $CONFIG_ENV and fill in values." >&2
  exit 1
fi

# ── 加载配置（仅导出，loader.py 会二次校验） ──
set -a
source "$CONFIG_ENV"
set +a

# ── 必要变量检查 ──
: "${ENGINE_PORT:?}"
: "${PYTHON_BIN:?}"

# ── 启动 Engine ──
echo "[INFO] Starting CCC Engine ..."
echo "[INFO] Config: $CONFIG_ENV"
echo "[INFO] Engine port: $ENGINE_PORT"

exec "$PYTHON_BIN" -m server.engine.main \
  --config "$CONFIG_ENV"

# ── Web Server 启动示例（T19 壳迁移后接管 7788 对话口） ──
# 用法：bash run-web.sh [--config /path/to/config.env]
# 占位变量：$PYTHON_BIN / $WEB_HOST / $WEB_PORT / $CONFIG_ENV
#
# set -euo pipefail
# SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
# CONFIG_ENV="${CCC_CONFIG_ENV:-${PROJECT_ROOT}/server/config/config.env}"
# if [[ $# -ge 2 && "$1" == "--config" ]]; then CONFIG_ENV="$2"; fi
# if [[ ! -f "$CONFIG_ENV" ]]; then echo "[FATAL] config not found: $CONFIG_ENV" >&2; exit 1; fi
# set -a; source "$CONFIG_ENV"; set +a
# : "${PYTHON_BIN:?}"; : "${WEB_HOST:?}"; : "${WEB_PORT:?}"
# exec "$PYTHON_BIN" -m server.web.server --host "$WEB_HOST" --port "$WEB_PORT"