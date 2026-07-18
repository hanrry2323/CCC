#!/usr/bin/env bash
# P3：转任务 → 扇出（带 executor）→ flow snapshot → 多执行面至少 2 种
# 用法：
#   CCC_SERVER=http://127.0.0.1:7777 bash scripts/smoke-desktop-e2e.sh
#   或对着 Mac2017：CCC_SERVER=http://192.168.3.116:7777 ...
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

SERVER="${CCC_SERVER:-http://127.0.0.1:7777}"
USER="${CCC_CHAT_USER:-ccc}"
PASS="${CCC_CHAT_PASS:-ccc}"
AUTH=(-u "${USER}:${PASS}")
PROJECT="${CCC_DESKTOP_SMOKE_PROJECT:-ccc-demo}"
LOCAL_ONLY="${CCC_DESKTOP_SMOKE_LOCAL:-0}"

echo "== Desktop E2E against ${SERVER} project=${PROJECT} =="

# 始终跑本地扇出 + 双执行面（不依赖远端 Server）
run_local_fanout() {
python3 <<'PY'
import sys, tempfile
from pathlib import Path
sys.path.insert(0, "scripts")
from _board_store import FileBoardStore
from _product_fanout import apply_fanout
from executors.registry import run_executor

with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    store = FileBoardStore(root)
    store.create_task(
        {
            "id": "e2e-epic",
            "title": "E2E",
            "tags": ["exec:opencode"],
            "description": "executor_intent: opencode",
        },
        column="backlog",
    )
    epic = store.list_tasks("backlog")[0]
    children = []
    for cid, ex, scope in (
        ("e2e-epic-w-oc", "opencode", "a.py"),
        ("e2e-epic-w-py", "python", "b.py"),
    ):
        children.append(
            {
                "id": cid,
                "title": cid,
                "description": "d",
                "executor": ex,
                "plan_md": f"# {cid}\n\n## 验收\n- x\n",
                "phases": [
                    {
                        "phase": 1,
                        "status": "pending",
                        "description": "d",
                        "scope": [scope],
                        "subtasks": {"1.1": "pending"},
                        "timeout": 60,
                        "commit": None,
                        "notes": "",
                    }
                ],
            }
        )
    r = apply_fanout(store, epic, children_raw=children)
    assert r["ok"], r
    _, w1 = store.find_task("e2e-epic-w-oc")
    _, w2 = store.find_task("e2e-epic-w-py")
    assert w1["executor"] == "opencode", w1
    assert w2["executor"] == "python", w2
    py = run_executor({"executor": "python", "cwd": str(root), "work_id": "e2e-epic-w-py"})
    assert py.ok, py
    assert (root / ".ccc" / "executor-python.ok").is_file()
    print("fanout+executors ok", r["child_ids"])
PY
}

run_local_fanout

if [[ "$LOCAL_ONLY" == "1" ]]; then
  echo "== Desktop E2E LOCAL PASS (pytest API separately) =="
  python3 -m pytest scripts/tests/test_desktop_api.py scripts/tests/test_desktop_transfer_gate.py -q
  exit 0
fi

curl -sf --connect-timeout 3 "${AUTH[@]}" "${SERVER}/api/desktop/config" | python3 -c '
import json,sys
d=json.load(sys.stdin)
assert d.get("threads")=="unified", d
assert d.get("transfer")=="epic_only", d
print("config ok", d.get("product"))
'

# Gate reject
code=$(curl -s -o /tmp/ccc-gate.json -w "%{http_code}" "${AUTH[@]}" \
  -H 'Content-Type: application/json' \
  -d "{\"project_id\":\"${PROJECT}\",\"title\":\"x\"}" \
  "${SERVER}/api/desktop/transfer")
test "$code" = "400"
python3 -c '
import json
d=json.load(open("/tmp/ccc-gate.json"))
assert d.get("ok") is False
assert d.get("errors")
print("gate reject ok", [e["code"] for e in d["errors"]])
'

# Transfer epic (opencode intent)
EPIC_OC="desktop-smoke-oc-$(date +%s | tail -c 6)"
curl -sf "${AUTH[@]}" -H 'Content-Type: application/json' \
  -d "{
    \"project_id\": \"${PROJECT}\",
    \"epic_id\": \"${EPIC_OC}\",
    \"title\": \"Desktop smoke opencode\",
    \"goal\": \"验证 Desktop 转任务写 epic\",
    \"acceptance\": [\"看板存在该 epic\"],
    \"pipeline\": \"dev\",
    \"feasibility\": \"ok\",
    \"executor_intent\": \"opencode\",
    \"plan_md\": \"# Plan\\n\\n## 目标\\nsmoke\\n\\n## 验收\\n- epic 存在\\n\"
  }" \
  "${SERVER}/api/desktop/transfer" | tee /tmp/ccc-transfer-oc.json | python3 -c '
import json,sys
d=json.load(sys.stdin)
assert d.get("ok") and d.get("epic_id"), d
print("transfer opencode", d["epic_id"])
'

# Transfer epic (python intent)
EPIC_PY="desktop-smoke-py-$(date +%s | tail -c 6)"
curl -sf "${AUTH[@]}" -H 'Content-Type: application/json' \
  -d "{
    \"project_id\": \"${PROJECT}\",
    \"epic_id\": \"${EPIC_PY}\",
    \"title\": \"Desktop smoke python\",
    \"goal\": \"验证 python 执行面意图\",
    \"acceptance\": [\"executor tag\"],
    \"pipeline\": \"python\",
    \"feasibility\": \"ok\",
    \"executor_intent\": \"python\",
    \"plan_md\": \"# Plan\\n\\n## 目标\\nsmoke py\\n\\n## 验收\\n- tag exec:python\\n\"
  }" \
  "${SERVER}/api/desktop/transfer" | tee /tmp/ccc-transfer-py.json | python3 -c '
import json,sys
d=json.load(sys.stdin)
assert d.get("ok") and d.get("executor_intent")=="python", d
print("transfer python", d["epic_id"])
'

# Flow snapshot for last epic
curl -sf "${AUTH[@]}" \
  "${SERVER}/api/desktop/flow/snapshot?project_id=${PROJECT}&epic_id=${EPIC_PY}" \
  | python3 -c '
import json,sys
d=json.load(sys.stdin)
assert d.get("ok")
assert d.get("epic_id")
print("snapshot", d.get("epic_id"), "works", len(d.get("works") or []))
'

echo "== Desktop E2E PASS =="
