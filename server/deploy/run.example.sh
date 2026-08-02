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