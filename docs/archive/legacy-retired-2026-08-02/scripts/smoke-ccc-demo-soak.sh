#!/usr/bin/env bash
# ccc-demo 可靠性浸泡：transfer → snapshot → orphan_delta=0（F2-1：默认 N=5）
# 用法：
#   CCC_SERVER=http://192.168.3.116:7777 bash scripts/smoke-ccc-demo-soak.sh
#   SOAK_N=5 bash scripts/smoke-ccc-demo-soak.sh
#   CCC_SOAK_N=5 bash scripts/smoke-ccc-demo-soak.sh   # 兼容旧名
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

SERVER="${CCC_SERVER:-http://192.168.3.116:7777}"
USER="${CCC_CHAT_USER:-ccc}"
PASS="${CCC_CHAT_PASS:-ccc}"
AUTH=(-u "${USER}:${PASS}")
PROJECT="${CCC_DESKTOP_SMOKE_PROJECT:-ccc-demo}"
# F2-1：优先 SOAK_N，其次 CCC_SOAK_N；默认 5
N="${SOAK_N:-${CCC_SOAK_N:-5}}"
WAIT_SEC="${CCC_SOAK_WAIT_SEC:-90}"
# product 扇出收尾：等 orphan 回到基线后再断言（避免把在飞 session 当泄漏）
SETTLE_SEC="${CCC_SOAK_SETTLE_SEC:-180}"
# F2-1 硬门：合计与每轮 orphan 净增必须为 0
MAX_ORPHAN_DELTA="${CCC_SOAK_MAX_ORPHAN_DELTA:-0}"
MAX_DEAD_PIDS="${CCC_SOAK_MAX_DEAD_PIDS:-8}"
MAX_LIVE_ORPHANS="${CCC_SOAK_MAX_LIVE_ORPHANS:-5}"

# shellcheck source=scripts/_smoke_remote.sh
source "$(dirname "$0")/_smoke_remote.sh"

echo "== ccc-demo soak N=${N} orphan_delta<=${MAX_ORPHAN_DELTA} against ${SERVER} remote=${SMOKE_REMOTE_HOST} =="

count_orphans() {
  smoke_remote \
    'pgrep -lf "opencode exec|ccc-product-session|claude " 2>/dev/null | grep -v ccc-engine | grep -v ccc-chat || true' \
    | wc -l | tr -d ' '
}

# 等到 orphan 数 ≤ target；超时非零退出
wait_orphans_at_most() {
  local target="$1" label="${2:-settle}" deadline=$((SECONDS + SETTLE_SEC)) cur
  while (( SECONDS < deadline )); do
    cur=$(count_orphans)
    if (( cur <= target )); then
      echo "${label}: orphans=${cur} <= ${target}"
      return 0
    fi
    echo "${label}: orphans=${cur} > ${target}, wait…"
    sleep 5
  done
  cur=$(count_orphans)
  echo "FAIL: ${label} timeout orphans=${cur} target<=${target}" >&2
  smoke_remote \
    'pgrep -lf "opencode exec|ccc-product-session|claude " 2>/dev/null | grep -v ccc-engine | grep -v ccc-chat || true' >&2 || true
  return 1
}

count_dead_pid_files() {
  smoke_remote 'python3 - <<"PY"
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

# 槽位探针：active_tasks 非测试条目数（回收应对齐，不净增失控）
count_active_slots() {
  smoke_remote 'python3 - <<"PY"
import json
from pathlib import Path
p = Path.home() / ".ccc" / "engine-active-tasks.json"
if not p.is_file():
    print(0); raise SystemExit
try:
    d = json.loads(p.read_text() or "{}")
except Exception:
    print(0); raise SystemExit
if not isinstance(d, dict):
    print(0); raise SystemExit
n = 0
for v in d.values():
    if not isinstance(v, dict):
        continue
    ws = str(v.get("workspace") or "")
    if any(seg in ws for seg in ("/pytest-", "/var/folders/", "/tmp/")):
        continue
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

# 开工前先把残留 product/claude 收干净，基线固定为 0
echo "pre-soak settle → orphans<=0 (timeout ${SETTLE_SEC}s)"
wait_orphans_at_most 0 "pre-soak"
BEFORE_ORPHANS=$(count_orphans)
BEFORE_SLOTS=$(count_active_slots)
echo "orphans before: ${BEFORE_ORPHANS}"
echo "active_slots before: ${BEFORE_SLOTS}"

BASELINE_ORPHANS="${BEFORE_ORPHANS}"
PREV_ORPHANS="${BEFORE_ORPHANS}"
PREV_SLOTS="${BEFORE_SLOTS}"

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

  # 等本轮 product/claude 收尾回到基线，再采 orphan / slot
  wait_orphans_at_most "${BASELINE_ORPHANS}" "round-${i}-settle"

  ROUND_ORPHANS=$(count_orphans)
  ROUND_SLOTS=$(count_active_slots)
  python3 - <<PY
round_i=int("${i}")
prev=int("${PREV_ORPHANS}")
cur=int("${ROUND_ORPHANS}")
baseline=int("${BASELINE_ORPHANS}")
delta_round=cur-prev
delta_base=cur-baseline
max_delta=int("${MAX_ORPHAN_DELTA}")
max_live=int("${MAX_LIVE_ORPHANS}")
prev_slots=int("${PREV_SLOTS}")
cur_slots=int("${ROUND_SLOTS}")
slot_growth=cur_slots-prev_slots
print(
    f"round {round_i}: orphans={cur} orphan_delta_round={delta_round} "
    f"orphan_delta_from_baseline={delta_base} "
    f"slots={cur_slots} slot_delta_round={slot_growth}"
)
assert delta_round <= max_delta, (
    f"round {round_i}: orphan_delta_round={delta_round} > {max_delta}"
)
assert delta_base <= max_delta, (
    f"round {round_i}: orphan_delta_from_baseline={delta_base} > {max_delta}"
)
assert cur <= max_live, f"round {round_i}: live orphans {cur} > cap {max_live}"
# 收尾后槽位应对齐基线（允许 ±0；短暂占用已在 settle 消化）
assert slot_growth <= 0, (
    f"round {round_i}: slot growth {slot_growth} after settle "
    f"(prev={prev_slots} cur={cur_slots})"
)
print(f"round {round_i} leak checks ok")
PY
  PREV_ORPHANS="${ROUND_ORPHANS}"
  PREV_SLOTS="${ROUND_SLOTS}"
done

wait_orphans_at_most "${BASELINE_ORPHANS}" "post-soak"
AFTER_ORPHANS=$(count_orphans)
AFTER_SLOTS=$(count_active_slots)
DEAD_PIDS=$(count_dead_pid_files)
echo "orphans after: ${AFTER_ORPHANS} (before ${BEFORE_ORPHANS})"
echo "active_slots after: ${AFTER_SLOTS} (before ${BEFORE_SLOTS})"
echo "dead opencode-pid files: ${DEAD_PIDS}"

python3 - <<PY
before=int("${BEFORE_ORPHANS}")
after=int("${AFTER_ORPHANS}")
dead=int("${DEAD_PIDS}")
slots_before=int("${BEFORE_SLOTS}")
slots_after=int("${AFTER_SLOTS}")
max_delta=int("${MAX_ORPHAN_DELTA}")
max_dead=int("${MAX_DEAD_PIDS}")
max_live=int("${MAX_LIVE_ORPHANS}")
delta=after-before
slot_delta=slots_after-slots_before
print(f"orphan_delta={delta}")
print(f"slot_delta={slot_delta}")
assert delta <= max_delta, f"too many new orphans: {delta} (want <= {max_delta})"
assert after <= max_live, f"live orphans after soak {after} > cap {max_live}"
assert dead <= max_dead, f"too many dead pid files left: {dead}"
assert slot_delta <= 0, f"slot leak: delta={slot_delta} (before={slots_before} after={slots_after})"
print("soak leak checks ok")
PY

# hide soak / hub-api-v1 smoke epics on board
smoke_remote \
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

echo "== ccc-demo soak PASS N=${N} orphan_delta<=${MAX_ORPHAN_DELTA} =="
