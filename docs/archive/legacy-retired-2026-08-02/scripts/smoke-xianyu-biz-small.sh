#!/usr/bin/env bash
# xianyu 业务向 small（非 flow-smoke）：补 README 时间戳小节 → 无人值守至 done + commit 触达。
# 仿 scripts/smoke-qb-biz-small.sh / smoke-hp-biz-small.sh（F3-1/F3-2）。
# 用法：CCC_SERVER=http://192.168.3.116:7777 bash scripts/smoke-xianyu-biz-small.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

SERVER="${CCC_SERVER:-http://192.168.3.116:7777}"
USER="${CCC_CHAT_USER:-ccc}"
PASS="${CCC_CHAT_PASS:-ccc}"
AUTH=(-u "${USER}:${PASS}")
PROJECT="${CCC_XIANYU_SMOKE_PROJECT:-xianyu}"
WAIT_SEC="${CCC_XIANYU_WAIT_SEC:-1200}"
POLL="${CCC_XIANYU_POLL_SEC:-15}"
# shellcheck source=scripts/_smoke_remote.sh
source "$(dirname "$0")/_smoke_remote.sh"
REMOTE="${SMOKE_REMOTE_HOST}"
XY_WS="${CCC_XIANYU_WS:-/Users/fan/program/apps/xianyu}"
TS=$(date +%s)
SUFFIX=$(printf '%x' "$$")
EPIC_ID="xianyu-biz-small-${TS}-${SUFFIX}"
CRID="xianyu-biz-${TS}-${SUFFIX}"
STAMP="xianyu-biz-${TS}"
export STAMP EPIC_ID PROJECT CRID

echo "== xianyu biz-small smoke against ${SERVER} epic=${EPIC_ID} =="

hub_ok=0
for _ in 1 2 3 4 5; do
  if curl -sf --connect-timeout 8 --max-time 20 "${AUTH[@]}" \
    "${SERVER}/api/desktop/projects" >/dev/null; then
    hub_ok=1
    break
  fi
  sleep 3
done
test "$hub_ok" = "1" || { echo "ERROR: Hub unreachable" >&2; exit 1; }
ssh -o ConnectTimeout=8 -o BatchMode=yes "${REMOTE}" \
  'pgrep -f "ccc-engine.py" >/dev/null' || {
  echo "ERROR: Engine not running on ${REMOTE}" >&2
  exit 1
}

BODY=$(python3 - <<'PY'
import json, os
stamp = os.environ["STAMP"]
epic = os.environ["EPIC_ID"]
project = os.environ["PROJECT"]
crid = os.environ["CRID"]
print(json.dumps({
  "project_id": project,
  "epic_id": epic,
  "thread_id": f"{project}::xianyu-biz-small",
  "client_request_id": crid,
  "title": f"写入并提交 README 双机路径备忘 stamp={stamp}",
  "goal": (
    f"在已跟踪的 README.md 追加一小节「CCC 双机路径（smoke {stamp}）」，"
    "并 git commit（message 含任务/epic id）。禁止改 AGENTS.md / CLAUDE.md。"
  ),
  "acceptance": [
    f"README.md 含 stamp={stamp}",
    "git log 含本 epic 或 work id",
    "work released / epic done",
  ],
  "pipeline": "dev",
  "feasibility": "ok",
  "executor_intent": "opencode",
  "complexity": "small",
  "plan_md": (
    f"# Plan — {epic}\n\n"
    f"## 目标\n在 README.md 追加双机路径备忘（stamp={stamp}）。\n\n"
    f"## 范围\n- **只改文件**: `README.md`\n"
    f"- **禁止**: AGENTS.md、CLAUDE.md、.ccc/\n\n"
    f"## 步骤\n1. 在 README 末尾追加小节，含 stamp={stamp}\n"
    f"2. git add README.md + commit（message 含任务 id）\n"
    f"3. report 注明 ALL SELF-CHECKS PASSED\n\n"
    f"## 验收\n- README 含 stamp\n- commit 可查\n"
  ),
}))
PY
)

transfer() {
  local tries=0
  while (( tries < 5 )); do
    if curl -sf --connect-timeout 8 --max-time 45 "${AUTH[@]}" \
      -H 'Content-Type: application/json' -d "${BODY}" \
      "${SERVER}/api/desktop/transfer" | tee /tmp/ccc-xianyu-biz-transfer.json \
      | python3 -c '
import json,sys
d=json.load(sys.stdin)
assert d.get("ok") and d.get("epic_id"), d
print("transfer ok", d["epic_id"])
open("/tmp/ccc-xianyu-biz-epic.txt","w").write(d["epic_id"])
'; then
      return 0
    fi
    tries=$((tries + 1))
    echo "transfer retry ${tries}…"
    sleep 4
  done
  return 1
}

transfer
EPIC=$(cat /tmp/ccc-xianyu-biz-epic.txt)

deadline=$((SECONDS + WAIT_SEC))
last_stage=""
while (( SECONDS < deadline )); do
  if curl -sf --connect-timeout 8 "${AUTH[@]}" \
    "${SERVER}/api/desktop/flow/snapshot?project_id=${PROJECT}&epic_id=${EPIC}" \
    >/tmp/ccc-xianyu-biz-snap.json 2>/dev/null; then
    eval "$(python3 - <<'PY'
import json
d=json.load(open("/tmp/ccc-xianyu-biz-snap.json"))
stage=d.get("user_stage") or ""
works=d.get("works") or []
statuses=",".join(sorted({str(w.get("status") or "?") for w in works})) or "-"
print(f'stage="{stage}"')
print(f'n_works={len(works)}')
print(f'statuses="{statuses}"')
print(f'released={sum(1 for w in works if w.get("status")=="released")}')
print(f'verified_or_released={sum(1 for w in works if w.get("status") in ("verified","released"))}')
print(f'abnormal={sum(1 for w in works if w.get("status")=="abnormal")}')
PY
)"
    if [[ "${stage}" != "${last_stage}" ]]; then
      echo "t+$((SECONDS))s stage=${stage} works=${n_works} statuses=${statuses}"
      last_stage="${stage}"
    fi
    if [[ "${stage}" == "failed" || "${abnormal}" -gt 0 ]]; then
      echo "FAIL: stage=${stage} abnormal=${abnormal}" >&2
      cat /tmp/ccc-xianyu-biz-snap.json >&2 || true
      exit 1
    fi
    if [[ "${stage}" == "done" && ( "${released}" -gt 0 || "${verified_or_released}" -eq "${n_works}" ) ]]; then
      echo "pipeline done; verifying README commit on ${REMOTE}…"
      ssh -o ConnectTimeout=8 -o BatchMode=yes "${REMOTE}" \
        "cd '${XY_WS}' && git log -20 --oneline | grep -E '${EPIC}|${STAMP}' && grep -q '${STAMP}' README.md"
      echo "== xianyu biz-small PASS epic=${EPIC} stamp=${STAMP} =="
      exit 0
    fi
  fi
  sleep "${POLL}"
done

echo "FAIL: timeout waiting for done" >&2
exit 1
