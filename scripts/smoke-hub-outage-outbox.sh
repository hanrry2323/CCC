#!/usr/bin/env bash
# Hub 断线韧性：sidecar 仍可探活；transfer 失败可排队；恢复后投递成功
# 用法：
#   CCC_SERVER=http://192.168.3.116:7777 CCC_AGENT=http://127.0.0.1:7788 \
#     bash scripts/smoke-hub-outage-outbox.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

SERVER="${CCC_SERVER:-http://192.168.3.116:7777}"
AGENT="${CCC_AGENT:-http://127.0.0.1:7788}"
USER="${CCC_CHAT_USER:-ccc}"
PASS="${CCC_CHAT_PASS:-ccc}"
AUTH=(-u "${USER}:${PASS}")
PROJECT="${CCC_DESKTOP_SMOKE_PROJECT:-ccc-demo}"
# shellcheck source=scripts/_smoke_remote.sh
source "$(dirname "$0")/_smoke_remote.sh"
REMOTE="${SMOKE_REMOTE_HOST}"
OUTBOX_DIR="${HOME}/Library/Application Support/CCCDesktop"
OUTBOX="${OUTBOX_DIR}/transfer-outbox.json"
export OUTBOX
TS=$(date +%s)
CRID="phase5b-outage-${TS}-$$"
EPIC_HINT="phase5b-outage-${TS}"
TID="${PROJECT}::phase5b-outage"
export CRID PROJECT TID EPIC_HINT
HUB_STOPPED=0

cleanup() {
  if [[ "${HUB_STOPPED}" = "1" ]]; then
    echo "trap: restoring Hub…"
    ssh -o ConnectTimeout=8 -o BatchMode=yes "${REMOTE}" \
      'launchctl load -w "$HOME/Library/LaunchAgents/com.ccc.chat-server.plist" 2>/dev/null || true; launchctl kickstart -k "gui/$(id -u)/com.ccc.chat-server" 2>/dev/null || true; sleep 2; curl -sf -m 5 -u ccc:ccc http://127.0.0.1:7777/api/desktop/projects >/dev/null' \
      || true
  fi
}
trap cleanup EXIT

echo "== hub outage/outbox smoke server=${SERVER} agent=${AGENT} =="

# 0) baseline
curl -sf --connect-timeout 8 --max-time 15 "${AUTH[@]}" "${SERVER}/api/desktop/projects" >/dev/null
curl -sf --connect-timeout 5 --max-time 10 "${AGENT}/health" \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d.get("ok"); print("sidecar ok", d.get("product"))'

# 1) stop Hub on 2017（unload；restore 用 load -w）
ssh -o ConnectTimeout=8 -o BatchMode=yes "${REMOTE}" \
  'launchctl unload "$HOME/Library/LaunchAgents/com.ccc.chat-server.plist" 2>/dev/null || launchctl bootout "gui/$(id -u)/com.ccc.chat-server" 2>/dev/null || true; sleep 2; ! curl -sf -m 2 -u ccc:ccc http://127.0.0.1:7777/api/desktop/projects >/dev/null'
HUB_STOPPED=1
echo "Hub stopped"

# 2) sidecar still healthy (dialogue path independent)
curl -sf --connect-timeout 5 --max-time 10 "${AGENT}/health" \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d.get("ok"); print("sidecar still ok while Hub down")'

# 3) transfer must fail
code=$(curl -s -o /tmp/ccc-phase5b-fail.json -w "%{http_code}" --connect-timeout 3 --max-time 8 \
  "${AUTH[@]}" -H 'Content-Type: application/json' \
  -d "{\"project_id\":\"${PROJECT}\",\"title\":\"x\"}" \
  "${SERVER}/api/desktop/transfer" || true)
if [[ "${code}" == "200" ]]; then
  echo "ERROR: transfer unexpectedly succeeded while Hub down (http=${code})" >&2
  exit 1
fi
echo "transfer fail while Hub down ok (http=${code:-000})"

# 4) simulate Desktop outbox enqueue (same schema as LocalSessionStore.TransferOutboxItem)
mkdir -p "${OUTBOX_DIR}"
python3 - <<'PY'
import json, os
from pathlib import Path
from datetime import datetime, timezone
p = Path(os.environ["OUTBOX"])
item = {
  "client_request_id": os.environ["CRID"],
  "project_id": os.environ["PROJECT"],
  "thread_id": os.environ["TID"],
  "title": "Phase5b outbox flush smoke",
  "goal": "Hub 恢复后从本机 outbox 投递成功",
  "acceptance": ["epic 存在于 backlog 或已扇出"],
  "pipeline": "dev",
  "feasibility": "ok",
  "feasibility_reason": None,
  "executor_intent": "python",
  "plan_md": "# Plan\n\n## 目标\nphase5b outbox\n\n## 验收\n- epic\n",
  "complexity": "small",
  "attempts": 0,
  "saved_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
}
q = []
if p.is_file():
  try:
    q = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(q, list):
      q = []
  except Exception:
    q = []
q = [x for x in q if x.get("client_request_id") != item["client_request_id"]]
q.append(item)
p.write_text(json.dumps(q, ensure_ascii=False, indent=2), encoding="utf-8")
print("outbox queued", p, "n=", len(q))
PY

# 5) restore Hub
HUB_STOPPED=0
ssh -o ConnectTimeout=8 -o BatchMode=yes "${REMOTE}" \
  'launchctl load -w "$HOME/Library/LaunchAgents/com.ccc.chat-server.plist" 2>/dev/null || true; launchctl kickstart -k "gui/$(id -u)/com.ccc.chat-server" 2>/dev/null || true'
echo "Hub restoring…"
for i in 1 2 3 4 5 6 7 8; do
  if curl -sf --connect-timeout 5 --max-time 12 "${AUTH[@]}" \
    "${SERVER}/api/desktop/projects" >/dev/null; then
    echo "Hub back"
    break
  fi
  sleep 2
done
curl -sf --connect-timeout 8 --max-time 15 "${AUTH[@]}" "${SERVER}/api/desktop/projects" >/dev/null

# 6) sidecar flush outbox → Hub（关 Desktop 也会走这条；不依赖 App 再开）
TOKEN_FILE="${HOME}/.ccc/agent-token"
[[ -f "${TOKEN_FILE}" ]] || TOKEN_FILE="${HOME}/.ccc/agent-sidecar.token"
TOKEN=""
if [[ -f "${TOKEN_FILE}" ]]; then
  TOKEN=$(tr -d '[:space:]' < "${TOKEN_FILE}")
fi
if [[ -z "${TOKEN}" ]]; then
  echo "ERROR: missing ${TOKEN_FILE} for sidecar outbox flush" >&2
  exit 1
fi

# 等 lifespan loop 或主动触发
for i in 1 2 3 4 5 6 7 8 9 10; do
  RESP=$(curl -sf --connect-timeout 5 --max-time 30 \
    -H "Authorization: Bearer ${TOKEN}" \
    -X POST "${AGENT}/api/outbox/flush" || true)
  if echo "${RESP}" | python3 -c '
import json,sys
d=json.load(sys.stdin)
sys.exit(0 if d.get("delivered",0)>=1 or d.get("pending",1)==0 else 1)
' 2>/dev/null; then
    echo "sidecar flush ok: ${RESP}"
    break
  fi
  sleep 1
done

# outbox 应已 dequeue 本条
python3 - <<'PY'
import json, os, sys
from pathlib import Path
p=Path(os.environ["OUTBOX"])
crid=os.environ["CRID"]
q=json.loads(p.read_text(encoding="utf-8")) if p.is_file() else []
left=[x for x in q if x.get("client_request_id")==crid]
if left:
    print("ERROR: outbox still has", crid, file=sys.stderr)
    sys.exit(1)
print("outbox dequeued; remaining", len(q))
PY

# 用 Hub 侧 idempotent 再 POST 一次拿 epic_id（或从 flush details；此处查 flow）
# 通过 projects/board 不够稳；用带同一 client_request_id 的 transfer 拿 idempotent replay
BODY=$(python3 - <<'PY'
import json, os
from pathlib import Path
# item 已从 outbox 删；重建最小 body 用同一 crid
print(json.dumps({
  "project_id": os.environ["PROJECT"],
  "thread_id": os.environ["TID"],
  "client_request_id": os.environ["CRID"],
  "title": "Phase5b outbox flush smoke",
  "goal": "Hub 恢复后从本机 outbox 投递成功",
  "acceptance": ["epic 存在于 backlog 或已扇出"],
  "pipeline": "dev",
  "feasibility": "ok",
  "executor_intent": "python",
  "complexity": "small",
  "plan_md": "# Plan\n\n## 目标\nphase5b outbox\n\n## 验收\n- epic\n",
  "epic_id": os.environ["EPIC_HINT"],
}))
PY
)

curl -sf --connect-timeout 10 --max-time 45 "${AUTH[@]}" \
  -H 'Content-Type: application/json' -d "${BODY}" \
  "${SERVER}/api/desktop/transfer" | tee /tmp/ccc-phase5b-transfer.json | python3 -c '
import json,sys
d=json.load(sys.stdin)
assert d.get("ok") and d.get("epic_id"), d
print("idempotent lookup ok", d["epic_id"], "replay", d.get("idempotent_replay"))
open("/tmp/ccc-phase5b-epic.txt","w").write(d["epic_id"])
'

EPIC=$(cat /tmp/ccc-phase5b-epic.txt)
curl -sf "${AUTH[@]}" \
  "${SERVER}/api/desktop/flow/snapshot?project_id=${PROJECT}&epic_id=${EPIC}" \
  | python3 -c '
import json,sys
d=json.load(sys.stdin)
assert d.get("ok") and d.get("epic_id")
print("snapshot ok", d["epic_id"])
'

# hide smoke epic
ssh -o ConnectTimeout=8 -o BatchMode=yes "${REMOTE}" \
  "cd ~/program/CCC && PYTHONPATH=scripts python3 - <<PY
from pathlib import Path
from _board_store import FileBoardStore
store = FileBoardStore(Path('/Users/fan/program/apps/ccc-demo'))
for tid in ['${EPIC}']:
    try:
        store.patch_task(tid, {'ui_hidden': True})
        print('hide', tid)
    except Exception as e:
        print('skip', tid, e)
PY
" || true

echo "== hub outage/outbox PASS epic=${EPIC} =="
