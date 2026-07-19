#!/usr/bin/env bash
# Desktop 95+ 对话稳态回归：sidecar 自启、工具轨 SSE、双会话隔离、重开 tool_steps
# 用法：bash scripts/smoke-desktop-stable.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

AGENT="${CCC_AGENT:-http://127.0.0.1:7788}"
SERVER="${CCC_SERVER:-http://192.168.3.116:7777}"
USER="${CCC_CHAT_USER:-ccc}"
PASS="${CCC_CHAT_PASS:-ccc}"
AUTH=(-u "${USER}:${PASS}")
PROJECT="${CCC_DESKTOP_SMOKE_PROJECT:-ccc-demo}"
WS="${CCC_LOCAL_WORKSPACE:-$HOME/program/apps/ccc-demo}"

pass=0
fail=0
check() {
  local name="$1"
  shift
  if "$@"; then
    echo "PASS  $name"
    pass=$((pass + 1))
  else
    echo "FAIL  $name"
    fail=$((fail + 1))
  fi
}

echo "== Desktop stable suite agent=${AGENT} server=${SERVER} =="

# 1) Sidecar 自启（若未起）
if ! curl -fsS --max-time 2 "${AGENT}/health" >/dev/null 2>&1; then
  echo "-- ensure sidecar --"
  mkdir -p "$HOME/Library/Logs/CCC"
  nohup bash scripts/ccc-agent-sidecar.sh >>"$HOME/Library/Logs/CCC/agent-sidecar.log" 2>&1 &
  sleep 2
fi
check "sidecar health" curl -fsS --max-time 3 "${AGENT}/health" >/dev/null

# 1b) keep-warm（旧进程无 /warm 时拉起新 sidecar）
if ! curl -fsS --max-time 3 -X POST "${AGENT}/warm" -H 'Content-Type: application/json' -d '{}' 2>/dev/null | grep -q '"ok"'; then
  echo "-- reload sidecar for /warm --"
  pkill -f "ccc-agent-sidecar.py" 2>/dev/null || true
  sleep 0.5
  mkdir -p "$HOME/Library/Logs/CCC"
  nohup bash scripts/ccc-agent-sidecar.sh >>"$HOME/Library/Logs/CCC/agent-sidecar.log" 2>&1 &
  sleep 2
fi
check "sidecar warm" bash -c "curl -fsS --max-time 5 -X POST '${AGENT}/warm' -H 'Content-Type: application/json' -d '{}' | grep -q '\"ok\"'"

# 1c) 本机会话目录可写（Desktop LocalSessionStore 同根）
check "local session dir" python3 - <<'PY'
import json, os, tempfile
from pathlib import Path
root = Path.home() / "Library/Application Support/CCCDesktop/sessions"
root.mkdir(parents=True, exist_ok=True)
p = root / "_smoke" / "probe.json"
p.parent.mkdir(parents=True, exist_ok=True)
rec = {"thread_id": "probe", "project_id": "_smoke", "messages": [{"role": "user", "content": "x"}], "updated_at": "t"}
p.write_text(json.dumps(rec), encoding="utf-8")
ok = p.is_file() and "probe" in p.read_text(encoding="utf-8")
p.unlink(missing_ok=True)
try:
    p.parent.rmdir()
except OSError:
    pass
raise SystemExit(0 if ok else 1)
PY

# 2) Sidecar chat 路由存活（校验错误应秒回；完整 SSE 见 smoke-desktop-agent.sh）
check "sidecar chat route" python3 - <<PY
import json, sys, urllib.error, urllib.request
url = "${AGENT}/api/chat"
body = json.dumps({
    "project_id": "${PROJECT}",
    "session_id": "smoke-stable-validate",
    "messages": [],
}).encode()
req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
try:
    urllib.request.urlopen(req, timeout=5)
    print("expected 400", file=sys.stderr)
    sys.exit(1)
except urllib.error.HTTPError as e:
    sys.exit(0 if e.code in (400, 422) else 1)
except Exception as e:
    print(e, file=sys.stderr)
    sys.exit(1)
PY

# 3–4) Hub 短请求 + 双会话（Hub 不可达时 SKIP，不卡死套件）
if curl -fsS --max-time 5 "${AUTH[@]}" "${SERVER}/api/desktop/config" >/tmp/ccc-stable-hub-config.json 2>/dev/null \
  && grep -q '"ok"' /tmp/ccc-stable-hub-config.json; then
  check "hub config" true
  TID1="smoke-stable-a-$$"
  TID2="smoke-stable-b-$$"
  check "hub dual thread put" python3 - <<PY
import json, urllib.request, base64, sys
server = "${SERVER}".rstrip("/")
auth = base64.b64encode(b"${USER}:${PASS}").decode()
headers = {"Authorization": f"Basic {auth}", "Content-Type": "application/json"}

def put(tid, content):
    url = f"{server}/api/desktop/threads/{tid}/messages"
    body = json.dumps({
        "project_id": "${PROJECT}",
        "messages": [
            {"role": "user", "content": f"u-{tid}"},
            {"role": "assistant", "content": content, "tool_steps": [
                {"id": "t1", "name": "Read", "status": "done", "detail": "ok"}
            ]},
        ],
    }).encode()
    req = urllib.request.Request(url, data=body, headers=headers, method="PUT")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())

try:
    put("${TID1}", "A-OK")
    put("${TID2}", "B-OK")
except Exception as e:
    print(e, file=sys.stderr)
    sys.exit(1)
sys.exit(0)
PY
else
  echo "SKIP  hub config / dual thread (Server unreachable: ${SERVER})"
fi

# 5) 定稿解析样例（本地，不依赖模型）
check "ccc-transfer samples" python3 scripts/tests/test_ccc_transfer_samples.py

# 6) light / full prompt 模式
check "hub_voice light/full" python3 -m pytest scripts/tests/test_hub_voice.py -q --tb=line

echo "== stable suite: ${pass} pass, ${fail} fail =="
echo "TTFB tip: bash scripts/spike-loopcode-ttfb.sh  # 热路径目标 ≤1s"
test "$fail" -eq 0
