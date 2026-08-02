#!/usr/bin/env bash
# ccc-demo 无人值守到 released：transfer(small flow-smoke) → 等 user_stage=done
# 用法：
#   CCC_SERVER=http://192.168.3.116:7777 bash scripts/smoke-ccc-demo-released.sh
# 环境：CCC_RELEASED_WAIT_SEC（默认 1200）、CCC_DESKTOP_SMOKE_PROJECT
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

SERVER="${CCC_SERVER:-http://192.168.3.116:7777}"
USER="${CCC_CHAT_USER:-ccc}"
PASS="${CCC_CHAT_PASS:-ccc}"
AUTH=(-u "${USER}:${PASS}")
PROJECT="${CCC_DESKTOP_SMOKE_PROJECT:-ccc-demo}"
WAIT_SEC="${CCC_RELEASED_WAIT_SEC:-1200}"
POLL="${CCC_RELEASED_POLL_SEC:-15}"
TS=$(date +%s)
SUFFIX=$(printf '%x' "$$")
EPIC_ID="phase5a-released-${TS}-${SUFFIX}"
CRID="phase5a-${TS}-${SUFFIX}"
STAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)
export STAMP EPIC_ID PROJECT CRID

echo "== ccc-demo released smoke against ${SERVER} epic=${EPIC_ID} wait=${WAIT_SEC}s =="

# Hub + Engine 探活（带重试）
hub_ok=0
for _ in 1 2 3 4 5; do
  if curl -sf --connect-timeout 8 --max-time 20 "${AUTH[@]}" \
    "${SERVER}/api/desktop/projects" >/dev/null; then
    hub_ok=1
    break
  fi
  echo "Hub probe retry…"
  sleep 3
done
test "$hub_ok" = "1" || { echo "ERROR: Hub unreachable ${SERVER}" >&2; exit 1; }
# shellcheck source=scripts/_smoke_remote.sh
source "$(dirname "$0")/_smoke_remote.sh"
smoke_remote \
  'pgrep -f "ccc-engine.py" >/dev/null' || {
  echo "ERROR: Engine not running on ${SMOKE_REMOTE_HOST}" >&2
  exit 1
}

BODY=$(python3 - <<'PY'
import json
import os
stamp = os.environ["STAMP"]
epic = os.environ["EPIC_ID"]
project = os.environ["PROJECT"]
crid = os.environ["CRID"]
print(json.dumps({
  "project_id": project,
  "epic_id": epic,
  "thread_id": f"{project}::phase5a-released",
  "client_request_id": crid,
  "title": "流水线烟测：写入并提交 .ccc/flow-smoke.md",
  "goal": f"Phase5a 无人值守绿通：写入 .ccc/flow-smoke.md 含 stamp={stamp} 并 git commit（含任务 id）",
  "acceptance": [
    ".ccc/flow-smoke.md 存在且含本轮 stamp",
    "git log 含本任务或 epic id 的 commit",
    "work 进入 released，epic split_status=done",
  ],
  "pipeline": "dev",
  "feasibility": "ok",
  "executor_intent": "opencode",
  "complexity": "small",
  "plan_md": (
    f"# Plan — {epic}\n\n"
    f"## 目标\n写入并提交 `.ccc/flow-smoke.md`（stamp={stamp}）。\n\n"
    f"## 范围\n- **只改文件**: `.ccc/flow-smoke.md`\n\n"
    f"## 步骤\n1. 写入文件内容含 stamp 与 epic id\n"
    f"2. git add + commit，message 含任务 id\n"
    f"3. report 注明 ALL SELF-CHECKS PASSED\n\n"
    f"## 验收\n- 文件存在\n- commit 可查\n"
  ),
}))
PY
)

transfer() {
  local tries=0
  while (( tries < 5 )); do
    if curl -sf --connect-timeout 8 --max-time 45 "${AUTH[@]}" \
      -H 'Content-Type: application/json' -d "${BODY}" \
      "${SERVER}/api/desktop/transfer" | tee /tmp/ccc-phase5a-transfer.json \
      | python3 -c '
import json,sys
d=json.load(sys.stdin)
assert d.get("ok") and d.get("epic_id"), d
print("transfer ok", d["epic_id"], "wake", d.get("engine_wake"))
open("/tmp/ccc-phase5a-epic.txt","w").write(d["epic_id"])
'; then
      return 0
    fi
    tries=$((tries + 1))
    echo "transfer retry ${tries}…"
    sleep 4
  done
  echo "transfer failed" >&2
  cat /tmp/ccc-phase5a-transfer.json 2>/dev/null || true
  return 1
}

transfer
EPIC=$(cat /tmp/ccc-phase5a-epic.txt)

deadline=$((SECONDS + WAIT_SEC))
last_stage=""
while (( SECONDS < deadline )); do
  if curl -sf --connect-timeout 8 "${AUTH[@]}" \
    "${SERVER}/api/desktop/flow/snapshot?project_id=${PROJECT}&epic_id=${EPIC}" \
    >/tmp/ccc-phase5a-snap.json 2>/dev/null; then
    eval "$(python3 - <<'PY'
import json
d=json.load(open("/tmp/ccc-phase5a-snap.json"))
stage=d.get("user_stage") or ""
works=d.get("works") or []
statuses=",".join(sorted({str(w.get("status") or "?") for w in works})) or "-"
n=len(works)
print(f'stage="{stage}"')
print(f'n_works={n}')
print(f'statuses="{statuses}"')
released=sum(1 for w in works if w.get("status")=="released")
verified=sum(1 for w in works if w.get("status") in ("verified","released"))
print(f'released={released}')
print(f'verified_or_released={verified}')
abn=sum(1 for w in works if w.get("status")=="abnormal")
print(f'abnormal={abn}')
PY
)"
    if [[ "${stage}" != "${last_stage}" || -n "${statuses}" ]]; then
      echo "t+$((SECONDS))s stage=${stage} works=${n_works} statuses=${statuses}"
      last_stage="${stage}"
    fi
    if [[ "${stage}" == "failed" || "${abnormal}" -gt 0 ]]; then
      echo "FAIL: pipeline failed stage=${stage} abnormal=${abnormal}" >&2
      python3 -c 'import json;print(json.dumps(json.load(open("/tmp/ccc-phase5a-snap.json")),ensure_ascii=False,indent=2)[:2000])' >&2 || true
      exit 1
    fi
    if [[ "${stage}" == "done" ]]; then
      # prefer at least one released work when works exist
      if [[ "${n_works}" -eq 0 || "${released}" -gt 0 || "${verified_or_released}" -eq "${n_works}" ]]; then
        echo "== ccc-demo released PASS epic=${EPIC} stage=done works=${n_works} =="
        # hide on board (ui_hidden) so Desktop stays clean
        smoke_remote \
          "cd ~/program/CCC && PYTHONPATH=scripts python3 - <<PY
from pathlib import Path
from _board_store import FileBoardStore
ws = Path('/Users/fan/program/apps/ccc-demo')
store = FileBoardStore(ws)
for tid in ['${EPIC}'] + [t.get('id') for col in ('released','verified','planned','in_progress','testing','backlog') for t in store.list_tasks(col) if str(t.get('id') or '').startswith('${EPIC}')]:
    try:
        store.patch_task(tid, {'ui_hidden': True})
        print('hide', tid)
    except Exception as e:
        print('skip', tid, e)
PY
" || true
        exit 0
      fi
    fi
  else
    echo "t+$((SECONDS))s snapshot retry…"
  fi
  sleep "${POLL}"
done

echo "FAIL: timeout ${WAIT_SEC}s waiting for released/done epic=${EPIC}" >&2
cat /tmp/ccc-phase5a-snap.json 2>/dev/null | head -c 2000 >&2 || true
echo >&2
exit 1
