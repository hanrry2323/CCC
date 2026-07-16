#!/bin/bash
# ccc-engine.sh — CCC Engine 入口 (v0.29.3+ / v0.38.1)
# 由 launchd com.ccc.engine 守护
# 单进程多 workspace 引擎 — 自动发现所有 workspace

set -uo pipefail

CCC_HOME="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SENTINEL="${HOME}/.ccc/DISABLED"

# 日志目录确保存在（Python 端 ccc-engine.py 也会 mkdir，这里保留兜底）
mkdir -p "${HOME}/.ccc/logs"

# v0.38.1: 总开关 — 存在则绝不进入工作循环（防 crontab/patrol/KeepAlive 复活干活）
if [[ -f "$SENTINEL" ]]; then
  echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] CCC DISABLED ($SENTINEL) — idle hold" \
    >> "${HOME}/.ccc/logs/engine-disabled.log"
  # KeepAlive 下退出会被立刻拉起；改为长睡并周期性检查哨兵是否移除
  while [[ -f "$SENTINEL" ]]; do
    sleep 60
  done
  # 哨兵已删 → 继续正常启动
fi

# 修复 launchd 环境缺 PATH（含 .local/bin 供 claude CLI）
export PATH="/Users/apple/.npm-global/bin:/opt/homebrew/bin:/Users/apple/.local/bin:/usr/local/bin:/usr/bin:/bin"
export OPENCODE_MODEL="${OPENCODE_MODEL:-loop/code}"

# v0.37 生产力默认：空看板不自造任务；内存阈值收紧
# 需要旧行为时：export CCC_AUTO_REPLENISH=1 CCC_EVOLVE_ON_IDLE=1 CCC_EVOLVE_ON_AUDIT=1
export CCC_AUTO_REPLENISH="${CCC_AUTO_REPLENISH:-0}"
export CCC_EVOLVE_ON_IDLE="${CCC_EVOLVE_ON_IDLE:-0}"
export CCC_EVOLVE_ON_AUDIT="${CCC_EVOLVE_ON_AUDIT:-0}"
export CCC_MEM_WARN_MB="${CCC_MEM_WARN_MB:-400}"
export CCC_MEM_DEGRADED_MB="${CCC_MEM_DEGRADED_MB:-800}"
export CCC_MEM_KILL_MB="${CCC_MEM_KILL_MB:-1500}"
export CCC_PRODUCT_ASYNC_TIMEOUT="${CCC_PRODUCT_ASYNC_TIMEOUT:-600}"

# 日志改由 Python 端 TimedRotatingFileHandler 接管（参见 add_file_handler）
# 不再写 engine-${$}.log，避免每个 restart 累积一个 PID 文件
exec python3 "$CCC_HOME/scripts/ccc-engine.py"
