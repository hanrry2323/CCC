#!/bin/bash
# ccc-engine.sh — CCC Engine 入口 (v0.29.3+)
# 由 launchd com.ccc.engine 守护
# 单进程多 workspace 引擎 — 自动发现所有 workspace

set -uo pipefail

CCC_HOME="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

LOG_DIR="${HOME}/.ccc/logs"
mkdir -p "$LOG_DIR"
LOG="${LOG_DIR}/engine-${$}.log"

# 修复 launchd 环境缺 PATH
export PATH="/Users/apple/.npm-global/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
export OPENCODE_MODEL="${OPENCODE_MODEL:-loop/code}"

exec python3 "$CCC_HOME/scripts/ccc-engine.py" >> "$LOG" 2>&1
