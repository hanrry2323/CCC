#!/usr/bin/env bash
# ccc-hub-token.sh — 打印 Hub Bearer 会话 token（scripts 侧 shell 调用方共用；窗口 G）。
#
# 用法：
#   TOKEN="$(bash scripts/ccc-hub-token.sh [SERVER] [USER] [PASS])"
#   AUTH=(-H "Authorization: Bearer $TOKEN")
#
# 成功 → stdout 打印 token，exit 0；失败 → stdout 空，exit 1（调用方回退 Basic）。
# 服务端开关（CCC_AUTH_REQUIRE_BEARER）off/on 两态下登录口均接受 Basic，故 token 换发始终可用。
set -euo pipefail

SERVER="${1:-${CCC_SERVER:-${CCC_HUB_URL:-http://127.0.0.1:17777}}}"
USER="${2:-${CCC_CHAT_USER:-ccc}}"
PASS="${3:-${CCC_CHAT_PASS:-ccc}}"

resp="$(curl -sS --connect-timeout 5 -m 8 -u "${USER}:${PASS}" \
  -X POST "${SERVER%/}/api/auth/token" 2>/dev/null || true)"
tok="$(printf '%s' "$resp" | python3 -c 'import sys, json
d = json.load(sys.stdin)
print(d.get("token") or "")' 2>/dev/null || true)"

if [[ -n "$tok" ]]; then
  printf '%s' "$tok"
  exit 0
fi
exit 1
