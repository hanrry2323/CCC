#!/bin/bash
# ccc-engine.sh — CCC Engine 入口 (v0.39 控制面)
# 唯一合法常驻入口：launchd com.ccc.engine
# 禁止：crontab / patrol Popen / 手动旁路常驻（调试可前台跑，仍受 control.json 约束）

set -uo pipefail

CCC_HOME="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p "${HOME}/.ccc/logs"

# v0.39/v0.42.1: 控制面 — disabled/ui 则空转（KeepAlive 下不退出，避免狂重启）
# invent 与 enabled 均可跑 Engine（may_start_engine）；仅 is_enabled 会把 invent 卡死
if ! python3 -c "import sys; sys.path.insert(0, r'''$CCC_HOME/scripts'''); from _ccc_control import may_start_engine; raise SystemExit(0 if may_start_engine() else 1)"; then
  echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] CCC control blocked Engine — idle hold" \
    >> "${HOME}/.ccc/logs/engine-disabled.log"
  while ! python3 -c "import sys; sys.path.insert(0, r'''$CCC_HOME/scripts'''); from _ccc_control import may_start_engine; raise SystemExit(0 if may_start_engine() else 1)"; do
    sleep 60
  done
fi

export PATH="/Users/apple/.npm-global/bin:/opt/homebrew/bin:/Users/apple/.local/bin:/usr/local/bin:/usr/bin:/bin"
export OPENCODE_MODEL="${OPENCODE_MODEL:-loop/code}"
export CCC_AUTO_REPLENISH=0
export CCC_EVOLVE_ON_IDLE=0
export CCC_EVOLVE_ON_AUDIT=0
# v0.42.4: invent/自动投入硬禁，禁止环境变量重新打开
export CCC_MEM_WARN_MB="${CCC_MEM_WARN_MB:-400}"
export CCC_MEM_DEGRADED_MB="${CCC_MEM_DEGRADED_MB:-800}"
export CCC_MEM_KILL_MB="${CCC_MEM_KILL_MB:-1500}"
export CCC_PRODUCT_ASYNC_TIMEOUT="${CCC_PRODUCT_ASYNC_TIMEOUT:-600}"

exec python3 "$CCC_HOME/scripts/ccc-engine.py"
