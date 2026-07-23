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

export PATH="${HOME}/.npm-global/bin:/opt/homebrew/bin:${HOME}/.local/bin:/usr/local/bin:/usr/bin:/bin"
# OpenCode 直连讯飞（见 ~/.opencode/opencode.json provider xfyun）
export OPENCODE_MODEL="${OPENCODE_MODEL:-xfyun/code}"
# product/reviewer Claude：默认直连 MiniMax（逻辑 flash → MiniMax-M3）
if [[ -z "${ANTHROPIC_BASE_URL:-}" ]]; then
  if [[ -f "${HOME}/.ccc/minimax-api-key" ]]; then
    export ANTHROPIC_BASE_URL="https://api.minimaxi.com/anthropic"
    export ANTHROPIC_AUTH_TOKEN="$(tr -d '[:space:]' < "${HOME}/.ccc/minimax-api-key")"
    export ANTHROPIC_MODEL="${ANTHROPIC_MODEL:-MiniMax-M3}"
  fi
fi
# Phase3：Engine 私有配置家（与个人 ~/.claude 切割；仍用 x86 原版 claude）
export CLAUDE_CONFIG_DIR="${CLAUDE_CONFIG_DIR:-${HOME}/.ccc/engine-claude}"
python3 -c "import sys; sys.path.insert(0, r'''${CCC_HOME}/scripts'''); from _claude_cli import ensure_engine_claude_config_dir; ensure_engine_claude_config_dir()" \
  || mkdir -p "${CLAUDE_CONFIG_DIR}"
# 健康检查与 get_relay_url 对齐：勿残留 AGENT_PLANNER→:4000
if [[ -z "${AGENT_PLANNER_BASE_URL:-}" && -n "${ANTHROPIC_BASE_URL:-}" ]]; then
  export AGENT_PLANNER_BASE_URL="${ANTHROPIC_BASE_URL}"
fi
# v0.51.0 P2-1: CCC_AUTO_REPLENISH / CCC_EVOLVE_ON_IDLE / CCC_EVOLVE_ON_AUDIT 已在 _config.py 强制 False，
# 这些环境变量 export 已无效（被 _config.__post_init__ 忽略）；不再 export 避免误导。
# v0.42.4: invent/自动投入硬禁，禁止环境变量重新打开
export CCC_MEM_WARN_MB="${CCC_MEM_WARN_MB:-400}"
export CCC_MEM_DEGRADED_MB="${CCC_MEM_DEGRADED_MB:-800}"
export CCC_MEM_KILL_MB="${CCC_MEM_KILL_MB:-1500}"
# 与 _config.product_async_timeout 默认对齐；600 会在扇出未完成时误杀 claude product
export CCC_PRODUCT_ASYNC_TIMEOUT="${CCC_PRODUCT_ASYNC_TIMEOUT:-1200}"
# 跨仓并发（同仓 OpenCode 仍 1）；Mac2017 有余量时可抬到 5–8
export CCC_MAX_CONCURRENT="${CCC_MAX_CONCURRENT:-6}"

exec python3 "$CCC_HOME/scripts/ccc-engine.py"
