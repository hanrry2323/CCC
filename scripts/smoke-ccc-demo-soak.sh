#!/usr/bin/env bash
# ccc-demo 可靠性浸泡 N=3：transfer → 确认 epic → 无孤儿进程
# 用法：CCC_SERVER=http://192.168.3.116:7777 bash scripts/smoke-ccc-demo-soak.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

SERVER="${CCC_SERVER:-http://192.168.3.116:7777}"
USER="${CCC_CHAT_USER:-ccc}"
PASS="${CCC_CHAT_PASS:-ccc}"
AUTH=(-u "${USER}:${PASS}")
PROJECT="${CCC_DESKTOP_SMOKE_PROJECT:-ccc-demo}"
N="${CCC_SOAK_N:-3}"
WAIT_SEC="${CCC_SOAK_WAIT_SEC:-90}"

echo "== ccc-demo soak N=${N} against ${SERVER} =="

count_orphans() {
  ssh -o ConnectTimeout=8 -o BatchMode=yes mac2017 \
    'pgrep -lf "opencode exec|ccc-product-session|claude " 2>/dev/null | grep -v ccc-engine | grep -v ccc-chat || true' \
    | wc -l | tr -d ' '
}

count_dead_pid_files() {
  ssh -o ConnectTimeout=8 -o BatchMode=yes mac2017 'python3 - <<"PY"
from pathlib import Path
import os
p = Path.home() / ".ccc" / "opencode-pids"
n = 0
if p.is_dir():
    for f in p.glob("*.pid"):
        try:
            pid = int(f.read_text().strip().split()[0])
        except Exception:
            n += 1
            continue
        try:
            os.kill(pid, 0)
        except OSError:
            n += 1
print(n)
PY'
}

transfer_once() {
  local body="$1" out="$2" tries=0
  while (( tries < 4 )); do
    if curl -sf --connect-timeout 8 --max-time 30 "${AUTH[@]}" \
      -H 'Content-Type: application/json' -d "${body}" \
      "${SERVER}/api/desktop/transfer" >"${out}" 2>/tmp/ccc-soak-curl.err; then
      python3 -c '
import json,sys
d=json.load(open(sys.argv[1]))
assert d.get("ok") and d.get("epic_id"), d
print("transfer", d["epic_id"])
open("/tmp/ccc-soak-last-epic.txt","w").write(d["epic_id"])
' "${out}"
      return 0
    fi
    tries=$((tries + 1))
    echo "transfer retry ${tries}…"
    sleep 3
  done
  echo "transfer failed:" >&2
  cat /tmp/ccc-soak-curl.err >&2 || true
  cat "${out}" >&2 || true
  return 1
}

BEFORE_ORPHANS=$(count_orphans)
echo "orphans before: ${BEFORE_ORPHANS}"

for i in $(seq 1 "$N"); do
  CRID="soak-${i}-$(date +%s)-$$"
  echo "-- round ${i}/${N} crid=${CRID} --"
  BODY=$(python3 - <<PY
import json
print(json.dumps({
  "project_id": "${PROJECT}",
  "thread_id": "${PROJECT}::soak-${i}",
  "client_request_id": "${CRID}",
  "title": "Soak round ${i} small",
  "goal": "浸泡烟测第 ${i} 轮，仅验证投递与无泄漏",
  "acceptance": ["epic 存在"],
  "pipeline": "dev",
  "feasibility": "ok",
  "executor_intent": "python",
  "complexity": "small",
  "plan_md": "# Plan\\n\\n## 目标\\nsoak ${i}\\n\\n## 验收\\n- epic\\n",
}))
PY
)
  transfer_once "${BODY}" "/tmp/ccc-soak-${i}.json"
  EPIC=$(cat /tmp/ccc-soak-last-epic.txt)
  # wait until snapshot ok
  deadline=$((SECONDS + WAIT_SEC))
  ok_snap=0
  while (( SECONDS < deadline )); do
    if curl -sf --connect-timeout 5 "${AUTH[@]}" \
      "${SERVER}/api/desktop/flow/snapshot?project_id=${PROJECT}&epic_id=${EPIC}" \
      | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d.get("ok") and d.get("epic_id"); print("snap", d["epic_id"])' \
      >/tmp/ccc-soak-snap.txt 2>/dev/null; then
      ok_snap=1
      break
    fi
    sleep 3
  done
  test "$ok_snap" = "1"
  echo "round ${i} snapshot ok epic=${EPIC}"
  sleep 5
done

AFTER_ORPHANS=$(count_orphans)
DEAD_PIDS=$(count_dead_pid_files)
echo "orphans after: ${AFTER_ORPHANS} (before ${BEFORE_ORPHANS})"
echo "dead opencode-pid files: ${DEAD_PIDS}"

# 允许短暂 product session；禁止浸泡后孤儿净增过多（阈值 5）
python3 - <<PY
before=int("${BEFORE_ORPHANS}")
after=int("${AFTER_ORPHANS}")
dead=int("${DEAD_PIDS}")
delta=after-before
print(f"orphan_delta={delta}")
assert delta <= 5, f"too many new orphans: {delta}"
assert dead <= 8, f"too many dead pid files left: {dead}"
print("soak leak checks ok")
PY

# hide soak / hub-api-v1 smoke epics on 2017 board
ssh -o ConnectTimeout=8 -o BatchMode=yes mac2017 \
  "cd ~/program/CCC && PYTHONPATH=scripts python3 - <<'PY'
from pathlib import Path
from _board_store import FileBoardStore
ws = Path('/Users/fan/program/apps/ccc-demo')
store = FileBoardStore(ws)
n = 0
for col in ('backlog','planned','in_progress','testing','verified','abnormal'):
    for t in list(store.list_tasks(col)):
        title = str(t.get('title') or '')
        tid = str(t.get('id') or '')
        if t.get('ui_hidden'):
            continue
        if title.startswith('Soak round') or title.startswith('Hub API v1 smoke') or tid.startswith('hub-api-v1-smoke'):
            store.patch_task(tid, {'ui_hidden': True})
            n += 1
            print('hide', col, tid)
print('hidden', n)
PY"

echo "== ccc-demo soak PASS N=${N} =="
