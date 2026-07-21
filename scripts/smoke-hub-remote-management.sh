#!/usr/bin/env bash
# Hub 远程管理口烟测：分区校验 + history + transfer（hub:: thread）
# 用法：
#   CCC_SERVER=http://127.0.0.1:7777 bash scripts/smoke-hub-remote-management.sh
# 可选真聊：CCC_REMOTE_CHAT_LIVE=1 …
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

SERVER="${CCC_SERVER:-http://127.0.0.1:7777}"
USER="${CCC_CHAT_USER:-ccc}"
PASS="${CCC_CHAT_PASS:-ccc}"
AUTH=(-u "${USER}:${PASS}")
PROJECT="${CCC_DESKTOP_SMOKE_PROJECT:-ccc-demo}"
THREAD="hub::${PROJECT}::smoke-rm-$$"
CRID="hub-remote-smoke-$(date +%s)-$$"

echo "== Hub remote management smoke against ${SERVER} project=${PROJECT} =="

# 探活
curl -sf --connect-timeout 5 "${AUTH[@]}" "${SERVER}/api/desktop/projects" >/dev/null
echo "projects ok"

# 分区：拒绝 Desktop 形态 thread
code=$(curl -s -o /tmp/ccc-rm-bad.json -w "%{http_code}" "${AUTH[@]}" \
  -H 'Content-Type: application/json' \
  -d "{\"project\":\"${PROJECT}\",\"thread_id\":\"${PROJECT}::main\",\"message\":\"ping\"}" \
  "${SERVER}/api/remote-chat/stream")
test "$code" = "400"
python3 -c '
import json
d=json.load(open("/tmp/ccc-rm-bad.json"))
assert d.get("error")=="invalid_thread_id", d
print("partition reject ok")
'

# history 默认 hub:: thread
curl -sf "${AUTH[@]}" \
  "${SERVER}/api/remote-chat/history?project=${PROJECT}&thread_id=${THREAD}" \
  | python3 -c '
import json,sys
d=json.load(sys.stdin)
assert d.get("ok") and d.get("thread_id","").startswith("hub::"), d
assert isinstance(d.get("messages"), list)
print("history ok", d["thread_id"], "msgs", len(d["messages"]))
'

# transfer 带 hub:: thread_id（与 Desktop 分区，编排共用）
BODY=$(python3 - <<PY
import json
print(json.dumps({
  "project_id": "${PROJECT}",
  "thread_id": "${THREAD}",
  "client_request_id": "${CRID}",
  "title": "Hub remote smoke small",
  "goal": "验证远程管理口 transfer + hub:: 分区",
  "acceptance": ["epic 存在于看板"],
  "pipeline": "dev",
  "feasibility": "ok",
  "executor_intent": "python",
  "complexity": "small",
  "plan_md": "# Plan\\n\\n## 目标\\nremote smoke\\n\\n## 验收\\n- epic 存在\\n",
}))
PY
)

curl -sf "${AUTH[@]}" -H 'Content-Type: application/json' -d "${BODY}" \
  "${SERVER}/api/desktop/transfer" | tee /tmp/ccc-rm-t1.json | python3 -c '
import json,sys
d=json.load(sys.stdin)
assert d.get("ok") and d.get("epic_id"), d
print("transfer ok", d["epic_id"])
open("/tmp/ccc-rm-epic.txt","w").write(d["epic_id"])
'

# 幂等
curl -sf "${AUTH[@]}" -H 'Content-Type: application/json' -d "${BODY}" \
  "${SERVER}/api/desktop/transfer" | python3 -c '
import json,sys
d=json.load(sys.stdin)
e1=open("/tmp/ccc-rm-epic.txt").read().strip()
assert d.get("ok") and d.get("epic_id")==e1 and d.get("idempotent_replay") is True, d
print("transfer idempotent ok")
'

# 可选：真聊一轮（需 2017 上 Claude/loop-code 可用）
if [[ "${CCC_REMOTE_CHAT_LIVE:-0}" == "1" ]]; then
  echo "== live remote chat =="
  curl -sf -N --max-time 120 "${AUTH[@]}" \
    -H 'Content-Type: application/json' \
    -d "{\"project\":\"${PROJECT}\",\"thread_id\":\"${THREAD}\",\"tool_mode\":\"discuss\",\"message\":\"用一句话说明你是 Hub 远程管理口，不要改文件。\"}" \
    "${SERVER}/api/remote-chat/stream" | tee /tmp/ccc-rm-stream.txt | head -c 8000 || true
  grep -q '"type"' /tmp/ccc-rm-stream.txt
  echo "live stream saw events"
  curl -sf "${AUTH[@]}" \
    "${SERVER}/api/remote-chat/history?project=${PROJECT}&thread_id=${THREAD}" \
    | python3 -c '
import json,sys
d=json.load(sys.stdin)
assert any(m.get("role")=="user" for m in (d.get("messages") or [])), d
print("history after live ok", len(d["messages"]))
'
else
  echo "skip live chat (set CCC_REMOTE_CHAT_LIVE=1 to enable)"
fi

echo "OK hub-remote-management"
