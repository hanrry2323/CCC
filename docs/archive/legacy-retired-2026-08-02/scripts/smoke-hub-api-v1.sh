#!/usr/bin/env bash
# Hub API v1 烟测：projects / transfer 幂等 / snapshot
# 用法：
#   CCC_SERVER=http://192.168.3.116:7777 bash scripts/smoke-hub-api-v1.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

SERVER="${CCC_SERVER:-http://192.168.3.116:7777}"
USER="${CCC_CHAT_USER:-ccc}"
PASS="${CCC_CHAT_PASS:-ccc}"
AUTH=(-u "${USER}:${PASS}")
PROJECT="${CCC_DESKTOP_SMOKE_PROJECT:-ccc-demo}"
CRID="hub-api-v1-$(date +%s)-$$"

echo "== Hub API v1 smoke against ${SERVER} project=${PROJECT} =="

curl -sf --connect-timeout 5 "${AUTH[@]}" "${SERVER}/api/desktop/projects" \
  | python3 -c '
import json,sys
d=json.load(sys.stdin)
ps=d.get("projects") or []
assert ps, d
ids={p.get("id") for p in ps}
assert "'"${PROJECT}"'" in ids or any("demo" in str(i) for i in ids), ids
print("projects ok", len(ps))
'

# Gate reject
code=$(curl -s -o /tmp/ccc-hub-v1-gate.json -w "%{http_code}" "${AUTH[@]}" \
  -H 'Content-Type: application/json' \
  -d "{\"project_id\":\"${PROJECT}\",\"title\":\"x\"}" \
  "${SERVER}/api/desktop/transfer")
test "$code" = "400"
python3 -c 'import json; d=json.load(open("/tmp/ccc-hub-v1-gate.json")); assert d.get("ok") is False; print("gate reject ok")'

# First transfer
BODY=$(python3 - <<PY
import json
print(json.dumps({
  "project_id": "${PROJECT}",
  "thread_id": "${PROJECT}::hub-api-v1",
  "client_request_id": "${CRID}",
  "title": "Hub API v1 smoke small",
  "goal": "验证幂等 transfer 与 snapshot",
  "acceptance": ["epic 存在于 backlog 或已扇出"],
  "pipeline": "dev",
  "feasibility": "ok",
  "executor_intent": "python",
  "complexity": "small",
  "plan_md": "# Plan\\n\\n## 目标\\nv1 smoke\\n\\n## 验收\\n- epic 存在\\n",
}))
PY
)

curl -sf "${AUTH[@]}" -H 'Content-Type: application/json' -d "${BODY}" \
  "${SERVER}/api/desktop/transfer" | tee /tmp/ccc-hub-v1-t1.json | python3 -c '
import json,sys
d=json.load(sys.stdin)
assert d.get("ok") and d.get("epic_id"), d
assert d.get("idempotent_replay") in (False, None)
print("transfer1", d["epic_id"], "wake", d.get("engine_wake"))
open("/tmp/ccc-hub-v1-epic.txt","w").write(d["epic_id"])
'

EPIC=$(cat /tmp/ccc-hub-v1-epic.txt)

# Second transfer same client_request_id → idempotent
curl -sf "${AUTH[@]}" -H 'Content-Type: application/json' -d "${BODY}" \
  "${SERVER}/api/desktop/transfer" | tee /tmp/ccc-hub-v1-t2.json | python3 -c '
import json,sys
d=json.load(sys.stdin)
assert d.get("ok") and d.get("epic_id"), d
e1=open("/tmp/ccc-hub-v1-epic.txt").read().strip()
assert d["epic_id"]==e1, (d["epic_id"], e1)
assert d.get("idempotent_replay") is True, d
print("transfer2 idempotent ok", d["epic_id"])
'

curl -sf "${AUTH[@]}" \
  "${SERVER}/api/desktop/flow/snapshot?project_id=${PROJECT}&epic_id=${EPIC}" \
  | python3 -c '
import json,sys
d=json.load(sys.stdin)
assert d.get("ok"), d
assert d.get("epic_id"), d
print("snapshot ok", d.get("epic_id"), "works", len(d.get("works") or []))
'

echo "== Hub API v1 PASS epic=${EPIC} =="
