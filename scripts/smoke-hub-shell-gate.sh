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

run() {
  echo ""
  echo ">>> $*"
  bash "$ROOT/scripts/$1"
}

echo "== hub-shell-gate tier=${TIER} server=${CCC_SERVER} =="

# Offline Phase9 contract (always)
python3 -m pytest "$ROOT/tests/scripts/test_flow_snapshot_dedupe.py" \
  -q -k test_snapshot_failed_stage_from_abnormal_and_split --tb=short
if [[ -f "$ROOT/tests/scripts/test_phase9_stoploss_client_contract.py" ]]; then
  python3 -m pytest "$ROOT/tests/scripts/test_phase9_stoploss_client_contract.py" -q --tb=short
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
