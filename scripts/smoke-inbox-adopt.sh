#!/usr/bin/env bash
# Inbox 采纳旁路烟测：未采纳不进板；采纳 → transfer
# 用法：CCC_SERVER=http://192.168.3.116:7777 bash scripts/smoke-inbox-adopt.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

SERVER="${CCC_SERVER:-http://192.168.3.116:7777}"
USER="${CCC_CHAT_USER:-ccc}"
PASS="${CCC_CHAT_PASS:-ccc}"
AUTH=(-u "${USER}:${PASS}")
SAMPLE="phase4-smoke-sample"
REMOTE_HOST="${CCC_REMOTE_HOST:-mac2017}"

# ensure local sample pending
mkdir -p inbox/adopted
if [[ ! -f "inbox/${SAMPLE}.md" ]]; then
  if [[ -f "inbox/adopted/${SAMPLE}.md" ]]; then
    mv "inbox/adopted/${SAMPLE}.md" "inbox/${SAMPLE}.md"
  else
    echo "missing inbox/${SAMPLE}.md" >&2
    exit 1
  fi
fi
python3 - <<PY
from pathlib import Path
p = Path("inbox/${SAMPLE}.md")
t = p.read_text(encoding="utf-8")
t = t.replace("status: adopted", "status: pending")
p.write_text(t, encoding="utf-8")
print("sample ready", p)
PY

# Hub 读的是服务端仓 inbox/；远端时先同步样例并清掉 adopted 残留
if [[ "${SERVER}" == *"192.168."* ]] || [[ "${SERVER}" == *"mac2017"* ]] || [[ -n "${CCC_SYNC_INBOX:-}" ]]; then
  ssh "${REMOTE_HOST}" "mkdir -p ~/program/CCC/inbox/adopted; rm -f ~/program/CCC/inbox/adopted/${SAMPLE}.md"
  rsync -az "inbox/${SAMPLE}.md" "${REMOTE_HOST}:~/program/CCC/inbox/${SAMPLE}.md"
fi

echo "== inbox adopt smoke against ${SERVER} =="

# list must include sample before adopt
curl -sf --connect-timeout 8 "${AUTH[@]}" "${SERVER}/api/desktop/proposals" \
  | python3 -c '
import json,sys
d=json.load(sys.stdin)
assert d.get("ok")
ids={p["id"] for p in d.get("proposals") or []}
assert "'"${SAMPLE}"'" in ids, ids
print("list ok", sorted(ids))
'

# adopt
curl -sf --connect-timeout 15 -X POST "${AUTH[@]}" \
  "${SERVER}/api/desktop/proposals/${SAMPLE}/adopt" \
  | tee /tmp/ccc-inbox-adopt.json | python3 -c '
import json,sys
d=json.load(sys.stdin)
assert d.get("ok") and d.get("epic_id") and d.get("adopted"), d
print("adopted epic", d["epic_id"])
open("/tmp/ccc-inbox-epic.txt","w").write(d["epic_id"])
'

EPIC=$(cat /tmp/ccc-inbox-epic.txt)

# 远端 Hub 采纳会移动 2017 上 inbox/；以 list API 为准
curl -sf "${AUTH[@]}" "${SERVER}/api/desktop/proposals" \
  | python3 -c '
import json,sys
d=json.load(sys.stdin)
ids={p["id"] for p in d.get("proposals") or []}
assert "'"${SAMPLE}"'" not in ids, ids
print("pending list cleared ok")
'

curl -sf "${AUTH[@]}" \
  "${SERVER}/api/desktop/flow/snapshot?project_id=ccc-demo&epic_id=${EPIC}" \
  | python3 -c '
import json,sys
d=json.load(sys.stdin)
assert d.get("ok") and d.get("epic_id")
print("snapshot ok", d["epic_id"])
'

# restore pending sample on remote+local for next run / repo
python3 - <<PY
from pathlib import Path
p = Path("inbox/${SAMPLE}.md")
t = p.read_text(encoding="utf-8").replace("status: adopted", "status: pending")
p.write_text(t, encoding="utf-8")
print("local sample restored pending")
PY
if [[ "${SERVER}" == *"192.168."* ]] || [[ "${SERVER}" == *"mac2017"* ]] || [[ -n "${CCC_SYNC_INBOX:-}" ]]; then
  ssh "${REMOTE_HOST}" "rm -f ~/program/CCC/inbox/adopted/${SAMPLE}.md"
  rsync -az "inbox/${SAMPLE}.md" "${REMOTE_HOST}:~/program/CCC/inbox/${SAMPLE}.md"
fi

echo "== inbox adopt PASS epic=${EPIC} =="
