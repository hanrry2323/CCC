#!/usr/bin/env bash
# Desktop 95+ 对话稳态回归：sidecar 自启、工具轨 SSE、双会话隔离、重开 tool_steps
# 用法：bash scripts/smoke-desktop-stable.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

AGENT="${CCC_AGENT:-http://127.0.0.1:7788}"
SERVER="${CCC_SERVER:-http://127.0.0.1:17777}"
USER="${CCC_CHAT_USER:-ccc}"
PASS="${CCC_CHAT_PASS:-ccc}"
AUTH=(-u "${USER}:${PASS}")
PROJECT="${CCC_DESKTOP_SMOKE_PROJECT:-ccc-demo}"
# M1 无业务第二树：sidecar cwd 用平台仓；业务事实靠 Hub baseline
WS="${CCC_LOCAL_WORKSPACE:-$ROOT}"

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

# 本机 sidecar token（安全对齐后 /warm /api/chat 必带）
TOKEN_FILE="${HOME}/.ccc/agent-token"
AGENT_TOKEN="${CCC_AGENT_TOKEN:-}"
if [[ -z "$AGENT_TOKEN" && -f "$TOKEN_FILE" ]]; then
  AGENT_TOKEN="$(tr -d '[:space:]' < "$TOKEN_FILE")"
fi
AGENT_AUTH_H=()
if [[ -n "$AGENT_TOKEN" ]]; then
  AGENT_AUTH_H=(-H "Authorization: Bearer ${AGENT_TOKEN}" -H "X-CCC-Agent-Token: ${AGENT_TOKEN}")
fi

# 1) Sidecar launchd 常驻 + 模型出口直连 MiniMax
bash scripts/install-agent-sidecar-plist.sh --start >/tmp/ccc-sidecar-install.log 2>&1 || true
check "sidecar health" curl -fsS --max-time 3 "${AGENT}/health" >/dev/null
check "sidecar launchd" bash -c "launchctl print gui/\$(id -u)/com.ccc.agent-sidecar >/dev/null 2>&1"
check "sidecar warm" bash -c '
  tok=""; [[ -f "$HOME/.ccc/agent-token" ]] && tok=$(tr -d "[:space:]" < "$HOME/.ccc/agent-token")
  [[ -n "${CCC_AGENT_TOKEN:-}" ]] && tok="$CCC_AGENT_TOKEN"
  if [[ -n "$tok" ]]; then
    curl -fsS --max-time 5 -X POST "'"${AGENT}"'/warm" -H "Content-Type: application/json" -H "Authorization: Bearer $tok" -d "{}" | grep -q "\"ok\""
  else
    curl -fsS --max-time 5 -X POST "'"${AGENT}"'/warm" -H "Content-Type: application/json" -d "{}" | grep -q "\"ok\""
  fi
'
# 模型出口断言：plist 直连 MiniMax（中转 :4000 已退役）
check "sidecar→MiniMax" bash -c 'plutil -p "$HOME/Library/LaunchAgents/com.ccc.agent-sidecar.plist" 2>/dev/null | grep -q "minimaxi.com"'

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
from pathlib import Path
url = "${AGENT}/api/chat"
body = json.dumps({
    "project_id": "${PROJECT}",
    "session_id": "smoke-stable-validate",
    "messages": [],
}).encode()
headers = {"Content-Type": "application/json"}
tok = __import__("os").environ.get("CCC_AGENT_TOKEN", "").strip()
if not tok:
    p = Path.home() / ".ccc" / "agent-token"
    if p.is_file():
        tok = p.read_text(encoding="utf-8").strip()
if tok:
    headers["Authorization"] = f"Bearer {tok}"
    headers["X-CCC-Agent-Token"] = tok
req = urllib.request.Request(url, data=body, headers=headers, method="POST")
try:
    urllib.request.urlopen(req, timeout=5)
    print("expected 400/401/422", file=sys.stderr)
    sys.exit(1)
except urllib.error.HTTPError as e:
    # 400=空 messages；401=未配 token；503=sidecar 未装 token
    sys.exit(0 if e.code in (400, 401, 422, 503) else 1)
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

# 7) 对话面边界：Desktop 禁止无 sidecar 时打 Hub /api/chat（源码契约）
check "no Hub chat fallback in Desktop" bash -c "! grep -n 'setAgentModeHub\\|Hub 回退' desktop/Sources/CCCDesktop/*.swift && grep -q '本机 Agent 未就绪' desktop/Sources/CCCDesktop/APIClient.swift && grep -q '禁止 Hub' desktop/Sources/CCCDesktop/APIClient.swift"

# 8) 稳定性契约：cancel 必 drop；stream 错误码化；鉴权不重试
check "cancelChat always drops live slot" grep -q 'reason: reason' desktop/Sources/CCCDesktop/AppModel.swift \
  && grep -q '总是回收 live slot' desktop/Sources/CCCDesktop/AppModel.swift
check "APIError.stream + retry whitelist" grep -q 'case stream(code' desktop/Sources/CCCDesktop/APIClient.swift \
  && grep -q 'isNonRetryableAuthOrClient' desktop/Sources/CCCDesktop/APIClient.swift \
  && grep -q 'isRetryableStreamFailure' desktop/Sources/CCCDesktop/APIClient.swift
check "heal drop before retry" grep -q 'heal-' desktop/Sources/CCCDesktop/AppModel.swift \
  && grep -q 'shouldDropLiveSlotBeforeRetry' desktop/Sources/CCCDesktop/AppModel.swift
check "turn ledger + failure UX" test -f desktop/Sources/CCCDesktop/DesktopChatTurnLedger.swift \
  && grep -q 'lastTurnFailure' desktop/Sources/CCCDesktop/AppModel.swift \
  && grep -q 'retryLastFailedTurn' desktop/Sources/CCCDesktop/ContentView.swift
check "agent probe TTL 10s" grep -q 'addingTimeInterval(10)' desktop/Sources/CCCDesktop/AppModel.swift \
  && grep -q 'invalidateAgentProbeCache' desktop/Sources/CCCDesktop/AppModel.swift

# 9) sidecar：假 connected / drop reason / warm lock 日志
check "sidecar stale cli reconnect" grep -q '_pids_alive' scripts/chat_server/services/claude_session.py \
  && grep -q 'stale slot cli dead' scripts/chat_server/services/claude_session.py
check "sidecar drop reason param" grep -q 'body.get("reason")' scripts/ccc-agent-sidecar.py
check "sidecar warm lock skip log" grep -q 'warm skip lock_timeout' scripts/chat_server/services/claude_session.py

# 9b) drop API 可达（带 token 时）
check "sidecar session drop route" python3 - <<PY
import json, sys, urllib.error, urllib.request
from pathlib import Path
url = "${AGENT}/api/session/drop"
body = json.dumps({
    "project_path": "/tmp",
    "session_id": "smoke-drop-validate",
    "reason": "smoke",
}).encode()
headers = {"Content-Type": "application/json"}
tok = __import__("os").environ.get("CCC_AGENT_TOKEN", "").strip()
if not tok:
    p = Path.home() / ".ccc" / "agent-token"
    if p.is_file():
        tok = p.read_text(encoding="utf-8").strip()
if tok:
    headers["Authorization"] = f"Bearer {tok}"
    headers["X-CCC-Agent-Token"] = tok
req = urllib.request.Request(url, data=body, headers=headers, method="POST")
try:
    with urllib.request.urlopen(req, timeout=5) as resp:
        # /tmp 可能不在 allowlist → 400；或 ok
        sys.exit(0 if resp.status in (200, 400) else 1)
except urllib.error.HTTPError as e:
    # 400=path not allowed；401/503=auth
    sys.exit(0 if e.code in (400, 401, 403, 503) else 1)
except Exception as e:
    print(e, file=sys.stderr)
    sys.exit(1)
PY

# 10) PUT messages 备份语义（Hub 可达时）
if [[ -f /tmp/ccc-stable-hub-config.json ]] && grep -q '"ok"' /tmp/ccc-stable-hub-config.json 2>/dev/null; then
  check "hub messages PUT is backup" python3 - <<PY
import json, urllib.request, base64, sys
server = "${SERVER}".rstrip("/")
auth = base64.b64encode(b"${USER}:${PASS}").decode()
tid = "smoke-backup-$$"
url = f"{server}/api/desktop/threads/{tid}/messages"
body = json.dumps({
    "project_id": "${PROJECT}",
    "messages": [{"role": "user", "content": "backup-probe"}],
}).encode()
req = urllib.request.Request(
    url, data=body,
    headers={"Authorization": f"Basic {auth}", "Content-Type": "application/json"},
    method="PUT",
)
with urllib.request.urlopen(req, timeout=15) as resp:
    d = json.loads(resp.read().decode())
ok = d.get("ok") is True and d.get("role") == "backup"
sys.exit(0 if ok else 1)
PY
else
  echo "SKIP  hub messages PUT is backup (Server unreachable)"
fi

echo "== stable suite: ${pass} pass, ${fail} fail =="
echo "TTFB tip: bash scripts/spike-loopcode-ttfb.sh  # 热路径目标 ≤1s"
test "$fail" -eq 0
