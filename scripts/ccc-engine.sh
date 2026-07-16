#!/bin/bash
# ccc-engine.sh — CCC Engine 入口 (v0.39 控制面)
# 唯一合法常驻入口：launchd com.ccc.engine
# 禁止：crontab / patrol Popen / 手动旁路常驻（调试可前台跑，仍受 control.json 约束）

set -uo pipefail

CCC_HOME="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p "${HOME}/.ccc/logs"

# v0.39: 控制面 — disabled 则空转（KeepAlive 下不退出，避免狂重启）
if ! python3 -c "import sys; sys.path.insert(0, r'''$CCC_HOME/scripts'''); from _ccc_control import is_enabled; raise SystemExit(0 if is_enabled() else 1)"; then
  echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] CCC control=disabled — idle hold" \
    >> "${HOME}/.ccc/logs/engine-disabled.log"
  while ! python3 -c "import sys; sys.path.insert(0, r'''$CCC_HOME/scripts'''); from _ccc_control import is_enabled; raise SystemExit(0 if is_enabled() else 1)"; do
    sleep 60
  done
fi

export PATH="/Users/apple/.npm-global/bin:/opt/homebrew/bin:/Users/apple/.local/bin:/usr/local/bin:/usr/bin:/bin"
export OPENCODE_MODEL="${OPENCODE_MODEL:-loop/code}"
export CCC_AUTO_REPLENISH="${CCC_AUTO_REPLENISH:-0}"
export CCC_EVOLVE_ON_IDLE="${CCC_EVOLVE_ON_IDLE:-0}"
export CCC_EVOLVE_ON_AUDIT="${CCC_EVOLVE_ON_AUDIT:-0}"
export CCC_MEM_WARN_MB="${CCC_MEM_WARN_MB:-400}"
export CCC_MEM_DEGRADED_MB="${CCC_MEM_DEGRADED_MB:-800}"
export CCC_MEM_KILL_MB="${CCC_MEM_KILL_MB:-1500}"
export CCC_PRODUCT_ASYNC_TIMEOUT="${CCC_PRODUCT_ASYNC_TIMEOUT:-600}"

exec python3 "$CCC_HOME/scripts/ccc-engine.py"
