#!/bin/bash
# ccc-engine.sh — CCC Engine 入口 (v0.20.1)
# 由 launchd com.ccc.engine 守护
# 包装 ccc-engine.py，串行驱动 task backlog→released

set -uo pipefail

CCC_HOME="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export CCC_WORKSPACE="${CCC_WORKSPACE:-$CCC_HOME}"

LOG_DIR="${HOME}/.ccc/logs"
mkdir -p "$LOG_DIR"
# 用 PID + workspace 末段做 LOG 后缀，避免 5 个 engine 同秒启动写到同一个文件
WS_SLUG=$(basename "${CCC_WORKSPACE}")
LOG="${LOG_DIR}/engine-${WS_SLUG}-${$}.log"

# 修复 launchd 环境缺 PATH
export PATH="/Users/apple/.npm-global/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
export OPENCODE_MODEL="${OPENCODE_MODEL:-code}"

exec python3 "$CCC_HOME/scripts/ccc-engine.py" --workspace "$CCC_WORKSPACE" >> "$LOG" 2>&1
