#!/usr/bin/env bash
# 验收：Hub 只读透镜 — 扇出后「在飞」可读；Hub 断不瞎编契约
# 用法：
#   bash tests/e2e/test_hub_lens_inflight.sh [project_id]
# 环境：
#   CCC_HUB_URL   默认 http://127.0.0.1:7777（本机 Hub）或 2017 LAN
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
HUB="${CCC_HUB_URL:-http://127.0.0.1:7777}"
PID="${1:-ccc-demo}"
LENS="$ROOT/scripts/ccc-hub-lens.py"

echo "== hub-lens board ($PID @ $HUB) =="
export CCC_HUB_URL="$HUB"
hub_up=0
if out="$(python3 "$LENS" board "$PID" 2>&1)"; then
  hub_up=1
  echo "$out" | head -n 5
  if ! echo "$out" | grep -Eq 'inflight=|in_progress=|planned='; then
    echo "FAIL: board summary missing counts"
    exit 1
  fi
  if echo "$out" | grep -q '"inflight_total": [1-9]'; then
    if ! echo "$out" | grep -q '"id":'; then
      echo "FAIL: inflight_total>0 but no id fields"
      exit 1
    fi
    echo "PASS: live inflight present"
  else
    echo "NOTE: inflight empty (ok if board idle); summary still live"
    echo "PASS: live board readable (empty inflight)"
  fi
  echo "== hub-lens git =="
  python3 "$LENS" git "$PID" >/dev/null
else
  echo "$out"
  if echo "$out" | grep -q "HUB_LENS_ERROR"; then
    echo "NOTE: Hub unreachable at $HUB — skip live board asserts"
  else
    echo "FAIL: board call failed without HUB_LENS_ERROR"
    exit 1
  fi
fi

echo "== simulate Hub down =="
down_out="$(CCC_HUB_URL="http://127.0.0.1:1" python3 "$LENS" board "$PID" 2>&1 || true)"
if echo "$down_out" | grep -q "HUB_LENS_ERROR"; then
  echo "PASS: Hub down → HUB_LENS_ERROR (no silent invent)"
else
  echo "FAIL: Hub down did not emit HUB_LENS_ERROR"
  echo "$down_out" | head -n 5
  exit 1
fi

if [[ "$hub_up" -eq 1 ]]; then
  echo "ALL PASS (live + down)"
else
  echo "ALL PASS (down-path only; start Hub to assert live inflight)"
fi

