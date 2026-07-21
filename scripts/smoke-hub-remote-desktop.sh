#!/usr/bin/env bash
# Hub Remote Desktop Shell 烟测：Agent 反代 + transfer（不跑 2017 独立聊天）
# 用法：
#   CCC_SERVER=http://192.168.3.116:7777 bash scripts/smoke-hub-remote-desktop.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

SERVER="${CCC_SERVER:-http://192.168.3.116:7777}"
USER="${CCC_CHAT_USER:-ccc}"
PASS="${CCC_CHAT_PASS:-ccc}"
AUTH=(-u "${USER}:${PASS}")
PROJECT="${CCC_DESKTOP_SMOKE_PROJECT:-ccc-demo}"
THREAD="${PROJECT}::remote-desktop-smoke"
CRID="hub-rd-$(date +%s)-$$"

echo "== Remote Desktop smoke against ${SERVER} =="

curl -sf --connect-timeout 5 "${AUTH[@]}" "${SERVER}/api/hub-config" \
  | python3 -c '
import json,sys
d=json.load(sys.stdin)
assert d.get("desktop_remote") is True, d
assert d.get("agent_proxy")=="/api/agent", d
print("hub-config ok", "agent", d.get("desktop_agent_url"))
'

# Agent health via Hub proxy（M1 sidecar 须可达）
code=$(curl -s -o /tmp/ccc-rd-health.json -w "%{http_code}" --connect-timeout 5 \
  "${AUTH[@]}" "${SERVER}/api/agent/health" || true)
if [[ "$code" == "200" ]]; then
  python3 -c '
import json
d=json.load(open("/tmp/ccc-rd-health.json"))
assert d.get("ok") is True, d
print("agent proxy health ok", d.get("product"), d.get("agent_runtime"))
'
else
  echo "WARN: /api/agent/health HTTP $code（M1 sidecar 未对 2017 开放或 token 未配）"
  cat /tmp/ccc-rd-health.json 2>/dev/null | head -c 300 || true
  echo
fi

# 禁止再出现 hub:: 分区 API
code=$(curl -s -o /dev/null -w "%{http_code}" "${AUTH[@]}" \
  -H 'Content-Type: application/json' \
  -d '{}' "${SERVER}/api/remote-chat/stream" || true)
test "$code" = "404" -o "$code" = "405" -o "$code" = "000"
echo "remote-chat retired ok (HTTP $code)"

# transfer 仍走 Hub（与 Desktop 同）
BODY=$(python3 - <<PY
import json
print(json.dumps({
  "project_id": "${PROJECT}",
  "thread_id": "${THREAD}",
  "client_request_id": "${CRID}",
  "title": "Remote Desktop smoke",
  "goal": "验证 HTTP 壳与 Desktop 同 transfer 契约",
  "acceptance": ["epic 存在"],
  "pipeline": "dev",
  "feasibility": "ok",
  "executor_intent": "python",
  "complexity": "small",
  "plan_md": "# Plan\\n\\nremote desktop smoke\\n",
}))
PY
)
curl -sf "${AUTH[@]}" -H 'Content-Type: application/json' -d "${BODY}" \
  "${SERVER}/api/desktop/transfer" | python3 -c '
import json,sys
d=json.load(sys.stdin)
assert d.get("ok") and d.get("epic_id"), d
print("transfer ok", d["epic_id"])
'

echo "OK smoke-hub-remote-desktop"
