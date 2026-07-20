#!/usr/bin/env bash
# Hub-Shell 分层回归门禁（真机 Hub；full 档需 Engine）。
# 用法：
#   CCC_SERVER=http://192.168.3.116:7777 bash scripts/smoke-hub-shell-gate.sh
#   CCC_HUB_SHELL_TIER=fast|full bash scripts/smoke-hub-shell-gate.sh
#   CCC_SKIP_OUTAGE=1 …  # full 时跳过 Hub unload 烟测
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

TIER="${CCC_HUB_SHELL_TIER:-fast}"
export CCC_SERVER="${CCC_SERVER:-http://192.168.3.116:7777}"
export CCC_CHAT_USER="${CCC_CHAT_USER:-ccc}"
export CCC_CHAT_PASS="${CCC_CHAT_PASS:-ccc}"
export CCC_DESKTOP_SMOKE_PROJECT="${CCC_DESKTOP_SMOKE_PROJECT:-ccc-demo}"
# loopback Hub → remote checks via ssh 127.0.0.1（可在 Mac2017 本机跑 full）
case "${CCC_SERVER}" in
  *127.0.0.1*|*localhost*) export CCC_REMOTE_HOST="${CCC_REMOTE_HOST:-127.0.0.1}" ;;
esac
# 本机无 sidecar 时默认跳过 outage（sidecar 在 M1）
if [[ "${CCC_SERVER}" == *127.0.0.1* || "${CCC_SERVER}" == *localhost* ]]; then
  export CCC_SKIP_OUTAGE="${CCC_SKIP_OUTAGE:-1}"
fi

run() {
  echo ""
  echo ">>> $*"
  bash "$ROOT/scripts/$1"
}

echo "== hub-shell-gate tier=${TIER} server=${CCC_SERVER} =="

# Prefer Hub venv when present (Mac2017); fall back to python3
if [[ -n "${CCC_PYTHON:-}" ]]; then
  PY="$CCC_PYTHON"
elif [[ -x "$ROOT/.venv-hub/bin/python" ]]; then
  PY="$ROOT/.venv-hub/bin/python"
else
  PY="python3"
fi

run_pytest() {
  if ! "$PY" -c 'import pytest' 2>/dev/null; then
    echo "WARN: pytest not installed for ${PY} — skip offline unit checks"
    return 0
  fi
  "$PY" -m pytest "$@"
}

# Offline Phase9 contract (always when pytest available)
run_pytest "$ROOT/tests/scripts/test_flow_snapshot_dedupe.py" \
  -q -k test_snapshot_failed_stage_from_abnormal_and_split --tb=short
if [[ -f "$ROOT/tests/scripts/test_phase9_stoploss_client_contract.py" ]]; then
  run_pytest "$ROOT/tests/scripts/test_phase9_stoploss_client_contract.py" -q --tb=short
fi

case "$TIER" in
  fast)
    run smoke-hub-api-v1.sh
    run smoke-inbox-adopt.sh
    run smoke-hub-empty-transfer-retry.sh
    ;;
  full)
    run smoke-hub-api-v1.sh
    run smoke-inbox-adopt.sh
    run smoke-hub-empty-transfer-retry.sh
    run smoke-ccc-demo-soak.sh
    run smoke-ccc-demo-released.sh
    run smoke-hub-shell-phase9.sh
    if [[ "${CCC_SKIP_OUTAGE:-0}" != "1" ]]; then
      run smoke-hub-outage-outbox.sh
    else
      echo ">>> skip smoke-hub-outage-outbox (CCC_SKIP_OUTAGE=1)"
    fi
    ;;
  *)
    echo "Unknown CCC_HUB_SHELL_TIER=${TIER} (use fast|full)" >&2
    exit 2
    ;;
esac

echo "== hub-shell-gate PASS tier=${TIER} =="
