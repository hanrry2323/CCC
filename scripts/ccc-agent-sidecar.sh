#!/usr/bin/env bash
# Start local Desktop Agent Sidecar (loop-code hot path on 127.0.0.1)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

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
export ANTHROPIC_BASE_URL="${ANTHROPIC_BASE_URL:-${CCC_AGENT_ROUTER:-http://192.168.3.116:4000}}"

# Prefer arch-matching vendor cli
if [[ ! -x "${ROOT}/vendor/loop-code/cli" ]]; then
  echo "WARN: missing vendor/loop-code/cli — install via scripts/install-executor-loop-code.sh"
fi

exec "$PY" "${ROOT}/scripts/ccc-agent-sidecar.py"
