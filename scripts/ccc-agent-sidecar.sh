#!/usr/bin/env bash
# CCC Desktop 本机 Agent Sidecar
# 前台运行（供手工调试）；日常请用 launchd：
#   bash scripts/install-agent-sidecar-plist.sh --start
#
# 用法：
#   bash scripts/ccc-agent-sidecar.sh              # 前台跑
#   bash scripts/ccc-agent-sidecar.sh start|stop|status|restart
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
INSTALL="${ROOT}/scripts/install-agent-sidecar-plist.sh"

cmd="${1:-}"
case "$cmd" in
  start|--start)
    exec bash "$INSTALL" --start
    ;;
  stop|--stop)
    exec bash "$INSTALL" --stop
    ;;
  status|--status)
    exec bash "$INSTALL" --status
    ;;
  restart|--restart)
    bash "$INSTALL" --stop || true
    exec bash "$INSTALL" --start
    ;;
  ""|run|foreground)
    ;;
  *)
    echo "usage: $0 [start|stop|status|restart|run]"
    exit 2
    ;;
esac

PY="${ROOT}/.venv-hub/bin/python"
if [[ ! -x "$PY" ]]; then
  echo "Need .venv-hub with claude-agent-sdk:"
  echo "  python3 -m venv .venv-hub && .venv-hub/bin/pip install -r requirements-hub.txt"
  exit 1
fi

export CCC_EXECUTOR="${CCC_EXECUTOR:-loop-code}"
export CCC_AGENT_HOST="${CCC_AGENT_HOST:-127.0.0.1}"
export CCC_AGENT_PORT="${CCC_AGENT_PORT:-7788}"
export CCC_AGENT_CWD="${CCC_AGENT_CWD:-$ROOT}"
export ANTHROPIC_BASE_URL="${ANTHROPIC_BASE_URL:-${CCC_AGENT_ROUTER:-https://api.minimaxi.com/anthropic}}"
export ANTHROPIC_MODEL="${ANTHROPIC_MODEL:-MiniMax-M3}"

if [[ ! -x "${ROOT}/vendor/loop-code/cli" ]]; then
  echo "WARN: missing vendor/loop-code/cli — install via scripts/install-executor-loop-code.sh"
fi

exec "$PY" "${ROOT}/scripts/ccc-agent-sidecar.py"
