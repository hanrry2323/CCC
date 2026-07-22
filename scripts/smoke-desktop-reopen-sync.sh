#!/usr/bin/env bash
# Desktop 关再开 · 后台同步烟测（不启 GUI）：磁盘契约 + sidecar flush
# Hub 不可达时仍验收本地契约与 sidecar outbox_flush 能力；可达则完整投递。
# 用法：
#   bash scripts/smoke-desktop-reopen-sync.sh
#   CCC_SERVER=http://127.0.0.1:17777 bash scripts/smoke-desktop-reopen-sync.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

SERVER="${CCC_SERVER:-http://127.0.0.1:17777}"
AGENT="${CCC_AGENT:-http://127.0.0.1:7788}"
USER="${CCC_CHAT_USER:-ccc}"
PASS="${CCC_CHAT_PASS:-ccc}"
AUTH=(-u "${USER}:${PASS}")
PROJECT="${CCC_DESKTOP_SMOKE_PROJECT:-ccc-demo}"
OUTBOX_DIR="${HOME}/Library/Application Support/CCCDesktop"
OUTBOX="${OUTBOX_DIR}/transfer-outbox.json"
FAILED="${OUTBOX_DIR}/transfer-failed.json"
export OUTBOX FAILED PROJECT HOME
TS=$(date +%s)
CRID="reopen-sync-${TS}-$$"
TID="${PROJECT}::reopen-sync"
export CRID TID

TOKEN_FILE="${HOME}/.ccc/agent-token"
[[ -f "${TOKEN_FILE}" ]] || TOKEN_FILE="${HOME}/.ccc/agent-sidecar.token"
TOKEN=""
if [[ -f "${TOKEN_FILE}" ]]; then
  TOKEN=$(tr -d '[:space:]' < "${TOKEN_FILE}")
fi

echo "== desktop reopen/sync smoke server=${SERVER} agent=${AGENT} =="

# 0) sidecar 必达
curl -sf --connect-timeout 5 --max-time 10 "${AGENT}/health" \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d.get("ok") and d.get("outbox_flush") is True; print("sidecar outbox_flush ok")'

HUB_OK=0
if curl -sf --connect-timeout 8 --max-time 20 "${AUTH[@]}" "${SERVER}/api/desktop/projects" >/dev/null; then
  HUB_OK=1
  echo "Hub reachable"
else
  echo "WARN: Hub unreachable — continue local+sidecar contract"
fi

# 1) 磁盘契约：board-cache + transfer-failed
mkdir -p "${OUTBOX_DIR}"
python3 - <<'PY'
import json, os
from pathlib import Path
from datetime import datetime, timezone
root = Path.home() / "Library/Application Support/CCCDesktop"
proj = os.environ["PROJECT"]
cache = root / f"board-cache-{proj}.json"
cache.write_text(json.dumps({
  "project_id": proj,
  "workspace": proj,
  "columns": {
    "backlog": [], "planned": [], "in_progress": [],
    "testing": [], "verified": [], "released": [], "abnormal": [],
  },
  "saved_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
}, ensure_ascii=False, indent=2), encoding="utf-8")
loaded = json.loads(cache.read_text(encoding="utf-8"))
assert loaded["project_id"] == proj and "columns" in loaded
failed = root / "transfer-failed.json"
if not failed.is_file():
  failed.write_text("[]\n", encoding="utf-8")
assert isinstance(json.loads(failed.read_text(encoding="utf-8")), list)
print("board-cache + transfer-failed schema ok")
PY

# 2) 写 outbox（模拟转任务后立刻杀 App）
python3 - <<'PY'
import json, os
from pathlib import Path
from datetime import datetime, timezone
p = Path(os.environ["OUTBOX"])
item = {
  "client_request_id": os.environ["CRID"],
  "project_id": os.environ["PROJECT"],
  "thread_id": os.environ["TID"],
  "title": "Reopen sync smoke",
  "goal": "sidecar flush without Desktop",
  "acceptance": ["epic 存在"],
  "pipeline": "dev",
  "feasibility": "ok",
  "feasibility_reason": None,
  "executor_intent": "python",
  "plan_md": "# Plan\n\n## 目标\nreopen\n\n## 验收\n- epic\n",
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
print("outbox queued", len(q))
PY

if [[ -z "${TOKEN}" ]]; then
  echo "ERROR: missing agent token for /api/outbox/flush" >&2
  exit 1
fi

# 3) sidecar flush
if [[ "${HUB_OK}" = "1" ]]; then
  DELIVERED=0
  for _ in 1 2 3 4 5 6 7 8 9 10 11 12; do
    RESP=$(curl -sf --connect-timeout 5 --max-time 30 \
      -H "Authorization: Bearer ${TOKEN}" \
      -X POST "${AGENT}/api/outbox/flush" || true)
    if echo "${RESP}" | CRID="${CRID}" python3 -c '
import json,sys,os
d=json.load(sys.stdin)
crid=os.environ["CRID"]
details=d.get("details") or []
hit=any(x.get("client_request_id")==crid and x.get("status")=="delivered" for x in details)
sys.exit(0 if hit or int(d.get("delivered") or 0)>=1 else 1)
' 2>/dev/null; then
      DELIVERED=1
      echo "sidecar flush delivered: ${RESP}"
      break
    fi
    sleep 1
  done
  if [[ "${DELIVERED}" != "1" ]]; then
    python3 - <<'PY'
import json, os, sys
from pathlib import Path
p=Path(os.environ["OUTBOX"])
crid=os.environ["CRID"]
q=json.loads(p.read_text(encoding="utf-8")) if p.is_file() else []
left=[x for x in q if x.get("client_request_id")==crid]
if left:
    print("ERROR: still in outbox", left, file=sys.stderr)
    sys.exit(1)
print("outbox already clear (background loop)")
PY
  fi

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
print("outbox dequeued ok; remaining", len(q))
PY

  BODY=$(python3 - <<'PY'
import json, os
print(json.dumps({
  "project_id": os.environ["PROJECT"],
  "thread_id": os.environ["TID"],
  "client_request_id": os.environ["CRID"],
  "title": "Reopen sync smoke",
  "goal": "sidecar flush without Desktop",
  "acceptance": ["epic 存在"],
  "pipeline": "dev",
  "feasibility": "ok",
  "executor_intent": "python",
  "complexity": "small",
  "plan_md": "# Plan\n\n## 目标\nreopen\n\n## 验收\n- epic\n",
}))
PY
)
  curl -sf --connect-timeout 10 --max-time 45 "${AUTH[@]}" \
    -H 'Content-Type: application/json' -d "${BODY}" \
    "${SERVER}/api/desktop/transfer" | tee /tmp/ccc-reopen-sync-transfer.json | python3 -c '
import json,sys
d=json.load(sys.stdin)
assert d.get("ok") and d.get("epic_id"), d
print("idempotent ok", d["epic_id"], "replay", d.get("idempotent_replay"))
open("/tmp/ccc-reopen-sync-epic.txt","w").write(d["epic_id"])
'
  EPIC=$(cat /tmp/ccc-reopen-sync-epic.txt)
  curl -sf --connect-timeout 10 --max-time 20 "${AUTH[@]}" \
    "${SERVER}/api/desktop/flow/snapshot?project_id=${PROJECT}&epic_id=${EPIC}" \
    | python3 -c '
import json,sys
d=json.load(sys.stdin)
assert d.get("ok") and d.get("epic_id")
print("snapshot ok", d["epic_id"])
'
  echo "== desktop reopen/sync PASS epic=${EPIC} =="
else
  # Hub down：只验证 flush API 可调用，并从 outbox 清掉本条以免污染（不投递）
  RESP=$(curl -sf --connect-timeout 5 --max-time 20 \
    -H "Authorization: Bearer ${TOKEN}" \
    -X POST "${AGENT}/api/outbox/flush" || true)
  echo "flush while Hub down: ${RESP:-(empty)}"
  python3 - <<'PY'
import json, os
from pathlib import Path
p=Path(os.environ["OUTBOX"])
crid=os.environ["CRID"]
q=json.loads(p.read_text(encoding="utf-8")) if p.is_file() else []
# 允许仍在 outbox（retry）或已失败；不得静默丢 schema
assert isinstance(q, list)
left=[x for x in q if x.get("client_request_id")==crid]
# 清理本条，避免污染用户 outbox
q=[x for x in q if x.get("client_request_id")!=crid]
p.write_text(json.dumps(q, ensure_ascii=False, indent=2), encoding="utf-8")
print("local contract ok; cleaned smoke outbox item; was_pending=", bool(left))
PY
  echo "== desktop reopen/sync PASS (local+sidecar; Hub down) =="
fi
