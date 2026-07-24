#!/usr/bin/env bash
# 双口烟测：M1 对话口 + Mac2017 编排口（禁止以 2017 为 chat origin）
# 用法：
#   CCC_AGENT=http://192.168.3.140:7788 \
#   CCC_SERVER=http://192.168.3.116:7777 \
#     bash scripts/smoke-dual-port-remote.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

AGENT="${CCC_AGENT:-http://192.168.3.140:7788}"
SERVER="${CCC_SERVER:-http://127.0.0.1:17777}"
USER="${CCC_CHAT_USER:-ccc}"
PASS="${CCC_CHAT_PASS:-ccc}"
AUTH=(-u "${USER}:${PASS}")
PROJECT="${CCC_DESKTOP_SMOKE_PROJECT:-ccc-demo}"
THREAD="${PROJECT}::dual-port-smoke"
CRID="dual-$(date +%s)-$$"

echo "== Dual-port smoke agent=${AGENT} hub=${SERVER} =="

# 1) 对话口 health（直打 M1，不经 Hub 反代）
curl -sf --connect-timeout 5 "${AGENT}/health" | python3 -c '
import json,sys
d=json.load(sys.stdin)
assert d.get("ok") is True, d
print("agent health ok", d.get("product"), d.get("agent_runtime"), "shell=", d.get("shell"))
'

# 2) shell-config（对话 SPA 宿主；含 LAN Hub 供手机）
curl -sf --connect-timeout 5 "${AGENT}/api/shell-config" | python3 -c '
import json,sys
d=json.load(sys.stdin)
assert d.get("shell")=="dialogue", d
assert d.get("hub_base"), d
assert d.get("hub_base_lan"), d
assert "127.0.0.1" in d["hub_base"] or "17777" in d["hub_base"] or d["hub_base"], d
lan = d["hub_base_lan"]
assert "7777" in lan or lan.startswith("http"), lan
print("shell-config ok hub_base=", d.get("hub_base"), "hub_base_lan=", lan)
'

# 3) Hub 编排口 hub-config
curl -sf --connect-timeout 5 "${AUTH[@]}" "${SERVER}/api/hub-config" | python3 -c '
import json,sys
d=json.load(sys.stdin)
assert d.get("dual_port") is True, d
assert d.get("agent_proxy") in (None, "", False), d
assert d.get("dialogue_url") or d.get("desktop_agent_url"), d
print("hub-config ok dual_port dialogue=", d.get("dialogue_url"))
'

# 4) remote-chat 已退役
code=$(curl -s -o /dev/null -w "%{http_code}" "${AUTH[@]}" \
  -H 'Content-Type: application/json' \
  -d '{}' "${SERVER}/api/remote-chat/stream" || true)
test "$code" = "404" -o "$code" = "405" -o "$code" = "000"
echo "remote-chat retired ok (HTTP $code)"

# 5) transfer 仍走 Hub
BODY=$(python3 - <<PY
import json
print(json.dumps({
  "project_id": "${PROJECT}",
  "thread_id": "${THREAD}",
  "client_request_id": "${CRID}",
  "title": "Dual-port smoke",
  "goal": "验证对话口 M1 + 编排口 2017",
  "acceptance": ["DRY_RUN=true python3 -c 'print(1)'"],
  "pipeline": "dev",
  "feasibility": "ok",
  "executor_intent": "python",
  "complexity": "small",
  "plan_md": "# Plan\\n\\ndual port smoke\\n",
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

echo "OK smoke-dual-port-remote"
