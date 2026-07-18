#!/usr/bin/env bash
# Desktop UI 键入/发送无人值守自检（不依赖辅助功能权限）
# 用法：
#   CCC_SERVER=http://192.168.3.116:7777 bash desktop/scripts/smoke-ui-chat.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT/desktop"

SERVER="${CCC_SERVER:-http://192.168.3.116:7777}"
OUT="${CCC_DESKTOP_UI_SMOKE_OUT:-/tmp/ccc-desktop-ui-smoke.json}"
TIMEOUT_SEC="${CCC_DESKTOP_UI_SMOKE_TIMEOUT:-180}"
rm -f "$OUT"

echo "== Desktop UI smoke against ${SERVER} =="
swift build -q

# 先确认 Hub
curl -sf -u "${CCC_CHAT_USER:-ccc}:${CCC_CHAT_PASS:-ccc}" --connect-timeout 5 \
  "${SERVER%/}/api/desktop/config" >/dev/null

export CCC_SERVER="$SERVER"
export CCC_DESKTOP_UI_SMOKE=1
export CCC_DESKTOP_UI_SMOKE_OUT="$OUT"

# 限时跑 App；App 内跑完会写 OUT 并 exit
set +e
CODE=0
if command -v gtimeout >/dev/null 2>&1; then
  gtimeout "$TIMEOUT_SEC" swift run CCCDesktop
  CODE=$?
elif command -v timeout >/dev/null 2>&1; then
  timeout "$TIMEOUT_SEC" swift run CCCDesktop
  CODE=$?
else
  # macOS 无 GNU timeout：后台 + 轮询
  swift run CCCDesktop &
  PID=$!
  SECS=0
  while kill -0 "$PID" 2>/dev/null; do
    if [[ -f "$OUT" ]]; then
      sleep 1
      kill "$PID" 2>/dev/null || true
      wait "$PID" 2>/dev/null || true
      break
    fi
    sleep 1
    SECS=$((SECS + 1))
    if [[ "$SECS" -ge "$TIMEOUT_SEC" ]]; then
      kill "$PID" 2>/dev/null || true
      wait "$PID" 2>/dev/null || true
      CODE=124
      break
    fi
  done
  wait "$PID" 2>/dev/null
  CODE=${CODE:-$?}
fi
set -e

if [[ ! -f "$OUT" ]]; then
  echo "FAIL: missing smoke result $OUT (exit=$CODE)"
  exit 1
fi
python3 - <<PY
import json,sys
d=json.load(open("$OUT"))
print("ui_smoke", d)
assert d.get("ok") is True, d
assert d.get("assistant"), d
print("== Desktop UI smoke PASS ==")
PY
exit 0
