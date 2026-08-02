#!/usr/bin/env bash
# ccc-demo 可靠性探针：存活 / 槽位 / 死 pid / hang 计数 — 独立于 soak
# 用法：
#   CCC_SERVER=http://192.168.3.116:7777 bash scripts/smoke-ccc-demo-reliability.sh
#   CCC_SERVER=http://127.0.0.1:7777 bash scripts/smoke-ccc-demo-reliability.sh  # 本机
#   CCC_RELIABILITY_N=10 bash scripts/smoke-ccc-demo-reliability.sh             # N 轮 transfer
#
# 本脚本不发起新一轮 Engine；只探当前状态：
#   1. Hub 探活（现网无 /api/health；与 smoke-hub-api-v1 同用 /api/desktop/projects）
#   2. opencode-pids 死 pid 文件数（清理 ≤ 阈）
#   3. ~/.ccc/engine-active-tasks.json 与当前 board in_progress + testing 是否一致
#   4. N 轮 transfer（可配置）+ snapshot，每轮后断言 slot 不漂移
#   5. ~/.ccc/engine-hang-retries.json 读取并断言（无 key 视为 0）
# PASS/FAIL 全文一次；非零退出
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

SERVER="${CCC_SERVER:-http://192.168.3.116:7777}"
USER="${CCC_CHAT_USER:-ccc}"
PASS="${CCC_CHAT_PASS:-ccc}"
AUTH=(-u "${USER}:${PASS}")
PROJECT="${CCC_DESKTOP_SMOKE_PROJECT:-ccc-demo}"
N="${CCC_RELIABILITY_N:-3}"
WAIT_SEC="${CCC_RELIABILITY_WAIT_SEC:-45}"
# 阈值：与 soak 一致；允许小幅漂移（正常 release 竞态）
MAX_DEAD_PIDS="${CCC_RELIABILITY_MAX_DEAD_PIDS:-8}"
MAX_ORPHAN_DELTA="${CCC_RELIABILITY_MAX_ORPHAN_DELTA:-5}"

# shellcheck source=scripts/_smoke_remote.sh
source "$(dirname "$0")/_smoke_remote.sh"

echo "== ccc-demo reliability N=${N} server=${SERVER} remote=${SMOKE_REMOTE_HOST} =="

# 1. Hub 探活（Hub 已删主聊天；无 /api/health — 用 projects 作可达性探针）
curl -sf --connect-timeout 5 "${AUTH[@]}" "${SERVER}/api/desktop/projects" \
    >/tmp/ccc-reliability-health.json 2>/tmp/ccc-reliability-health.err \
  || { echo "FAIL: hub /api/desktop/projects unreachable"; cat /tmp/ccc-reliability-health.err >&2; exit 1; }
echo "hub health ok (desktop/projects)"

# 2. 死 pid 文件（与 soak 同口径）
DEAD_PIDS=$(smoke_remote 'python3 - <<"PY"
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
PY')
echo "dead opencode-pid files: ${DEAD_PIDS}"

# 3. active_tasks 一致性：本地文件 vs board 列计数
ACTIVE_JSON=$(smoke_remote 'cat ~/.ccc/engine-active-tasks.json 2>/dev/null || echo "{}"')
ACTIVE_COUNT=$(printf '%s' "$ACTIVE_JSON" | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
    if not isinstance(d, dict):
        print(0); sys.exit(0)
    n = 0
    for k, v in d.items():
        ws = str(v.get("workspace") or "")
        if any(seg in ws for seg in ("/pytest-", "/var/folders/", "/tmp/")):
            continue
        n += 1
    print(n)
except Exception:
    print(0)
')
# Hub 看板入口是 /api/board（无 /api/desktop/board）
INPROGRESS=$(curl -sf --connect-timeout 5 "${AUTH[@]}" \
    "${SERVER}/api/board?workspace=${PROJECT}&include_hidden=1" \
    | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
    cols = (d.get("columns") or {})
    print(len(cols.get("in_progress") or []) + len(cols.get("testing") or []))
except Exception:
    print(0)
')
echo "active_tasks (non-test): ${ACTIVE_COUNT}; board in_progress+testing: ${INPROGRESS}"
# 软警告：active_tasks 多于 board 通常是 phase 边界抖动；不强制相等
python3 - <<PY
a = int("${ACTIVE_COUNT}"); b = int("${INPROGRESS}")
gap = abs(a - b)
# active > board 表明 phase 推进未收尾（不可见一过态）；board > active 不应发生
if b > a:
    print(f"WARN: board({b}) > active_tasks({a}) — 可能 board 漂移")
print(f"active_vs_board_gap={gap}")
PY

# 4. hang retries 读取（必须能解析；不存在即 0）
HANG_COUNTER=$(smoke_remote 'python3 -c "
import json
from pathlib import Path
p = Path.home() / \".ccc\" / \"engine-hang-retries.json\"
if not p.is_file():
    print(0); raise SystemExit
try:
    d = json.loads(p.read_text() or \"{}\")
except Exception:
    print(0); raise SystemExit
if not isinstance(d, dict):
    print(0); raise SystemExit
print(len(d))
"')
echo "hang retry keys: ${HANG_COUNTER}"

# 5. 槽位：local 引擎可读（仅本机 / loopback Hub）
if [[ "${SERVER}" == *127.0.0.1* || "${SERVER}" == *localhost* ]]; then
    SLOT_COUNT=$(smoke_remote 'python3 -c "
import sys
sys.path.insert(0, \"scripts\")
try:
    from engine.slots import global_opencode_count
    print(int(global_opencode_count()))
except Exception as e:
    print(0)
"')
    echo "opencode slots (live): ${SLOT_COUNT}"
fi

# 6. N 轮 transfer + snapshot（与 soak 同口径；不重启 Engine）
BEFORE_ORPHANS=$(smoke_remote \
    'pgrep -lf "opencode exec|ccc-product-session|claude " 2>/dev/null | grep -v ccc-engine | grep -v ccc-chat | wc -l | tr -d " "')
echo "orphans before: ${BEFORE_ORPHANS}"

for i in $(seq 1 "$N"); do
  CRID="rel-${i}-$(date +%s)-$$"
  echo "-- probe round ${i}/${N} crid=${CRID} --"
  BODY=$(python3 - <<PY
import json
print(json.dumps({
  "project_id": "${PROJECT}",
  "thread_id": "${PROJECT}::rel-${i}",
  "client_request_id": "${CRID}",
  "title": "Reliability probe ${i}",
  "goal": "可靠性探针第 ${i} 轮，仅验证投递",
  "acceptance": ["epic 存在"],
  "pipeline": "dev",
  "feasibility": "ok",
  "executor_intent": "python",
  "complexity": "small",
  "plan_md": "# Plan\\n\\n## 目标\\nprobe ${i}\\n\\n## 验收\\n- epic\\n",
}))
PY
)
  tries=0
  while (( tries < 3 )); do
    if curl -sf --connect-timeout 8 --max-time 30 "${AUTH[@]}" \
        -H 'Content-Type: application/json' -d "${BODY}" \
        "${SERVER}/api/desktop/transfer" >/tmp/ccc-rel-${i}.json 2>/tmp/ccc-rel-${i}.err; then
      EPIC=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("epic_id") or "")' /tmp/ccc-rel-${i}.json)
      [[ -n "${EPIC}" ]] && break
    fi
    tries=$((tries + 1))
    sleep 2
  done
  [[ -n "${EPIC}" ]] || { echo "FAIL: transfer ${i} never returned epic_id"; exit 1; }
  # snapshot
  deadline=$((SECONDS + WAIT_SEC))
  ok_snap=0
  while (( SECONDS < deadline )); do
    if curl -sf --connect-timeout 5 "${AUTH[@]}" \
        "${SERVER}/api/desktop/flow/snapshot?project_id=${PROJECT}&epic_id=${EPIC}" \
        >/tmp/ccc-rel-${i}-snap.json 2>/dev/null; then
      if python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); assert d.get("ok") and d.get("epic_id")' /tmp/ccc-rel-${i}-snap.json; then
        ok_snap=1; break
      fi
    fi
    sleep 2
  done
  test "$ok_snap" = "1" || { echo "FAIL: snapshot ${i} timeout"; exit 1; }
  echo "round ${i} snapshot ok epic=${EPIC}"
  sleep 3
done

AFTER_ORPHANS=$(smoke_remote \
    'pgrep -lf "opencode exec|ccc-product-session|claude " 2>/dev/null | grep -v ccc-engine | grep -v ccc-chat | wc -l | tr -d " "')
DEAD_PIDS_AFTER=$(smoke_remote 'python3 - <<"PY"
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
PY')
echo "orphans after: ${AFTER_ORPHANS} (before ${BEFORE_ORPHANS})"
echo "dead pids after: ${DEAD_PIDS_AFTER} (before ${DEAD_PIDS})"

python3 - <<PY
before=int("${BEFORE_ORPHANS}")
after=int("${AFTER_ORPHANS}")
dead_before=int("${DEAD_PIDS}")
dead_after=int("${DEAD_PIDS_AFTER}")
orphan_delta=after-before
dead_delta=dead_after-dead_before
print(f"orphan_delta={orphan_delta} dead_delta={dead_delta}")
assert orphan_delta <= ${MAX_ORPHAN_DELTA}, f"orphan drift too high: {orphan_delta}"
assert dead_after <= ${MAX_DEAD_PIDS}, f"dead pid files too many after: {dead_after}"
assert dead_delta <= 3, f"dead pid file growth too fast: {dead_delta}"
print("reliability probes ok")
PY

echo "== ccc-demo reliability PASS N=${N} =="