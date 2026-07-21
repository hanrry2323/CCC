#!/usr/bin/env bash
# 断言 M1 本机 sidecar :7788 = loop-code（对话 SSOT），并跑一轮完整 chat SSE
# 架构对齐 2026-07-19：Hub /api/chat 已删；对话主入口 = M1 Desktop + sidecar :7788
# 用法：CCC_SERVER=http://192.168.3.116:7777 CCC_AGENT=http://127.0.0.1:7788 bash scripts/smoke-desktop-agent.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
SERVER="${CCC_SERVER:-http://192.168.3.116:7777}"
AGENT="${CCC_AGENT:-http://127.0.0.1:7788}"
USER="${CCC_CHAT_USER:-ccc}"
PASS="${CCC_CHAT_PASS:-ccc}"
PROJECT="${CCC_DESKTOP_SMOKE_PROJECT:-ccc-demo}"

echo "== Desktop Agent smoke: server=${SERVER} agent=${AGENT} =="

# 1) Hub /api/desktop/config 仍可用（编排面 API host）
CFG="$(curl -sf -u "${USER}:${PASS}" --connect-timeout 5 "${SERVER%/}/api/desktop/config" 2>/dev/null || true)"
if [ -n "$CFG" ]; then
  echo "$CFG" | python3 -c "
import json,sys
d=json.load(sys.stdin)
print('hub agent_runtime=', d.get('agent_runtime') or '')
print('hub agent_cli=', d.get('agent_cli') or '')
assert d.get('ok') is True, d
print('OK hub /api/desktop/config')
" 2>/dev/null || echo "WARN: hub /api/desktop/config parse failed (non-fatal)"
else
  echo "SKIP: hub /api/desktop/config unreachable (non-fatal; sidecar is the dialogue path)"
fi

# 2) sidecar /health（对话热路径；cli 仅 basename）
HEALTH="$(curl -sf -m 3 "${AGENT%/}/health")"
echo "$HEALTH" | python3 -c "
import json,sys
d=json.load(sys.stdin)
rt=d.get('agent_runtime') or ''
cli=d.get('agent_cli') or ''
cfg=d.get('config_dir') or ''
print('sidecar agent_runtime=', rt)
print('sidecar agent_cli=', cli)
print('sidecar config_dir=', cfg)
print('sidecar auth_required=', d.get('auth_required'))
assert d.get('ok') is True, d
assert rt == 'loop-code', f'sidecar SSOT requires loop-code, got runtime={rt!r} cli={cli!r}'
assert cli in ('cli', 'loop-code') or 'loop' in cli.lower() or cli == 'cli', f'unexpected cli basename: {cli!r}'
assert '.ccc/loop-code' in str(cfg).replace('\\\\', '/'), f'config_dir must be ~/.ccc/loop-code, got {cfg!r}'
print('OK sidecar agent=loop-code config_dir')
"
# 本机 sidecar token（~/.ccc/agent-token）
TOKEN_FILE="${HOME}/.ccc/agent-token"
AGENT_TOKEN="${CCC_AGENT_TOKEN:-}"
if [[ -z "$AGENT_TOKEN" && -f "$TOKEN_FILE" ]]; then
  AGENT_TOKEN="$(tr -d '[:space:]' < "$TOKEN_FILE")"
fi
AUTH_H=()
if [[ -n "$AGENT_TOKEN" ]]; then
  AUTH_H=(-H "Authorization: Bearer ${AGENT_TOKEN}" -H "X-CCC-Agent-Token: ${AGENT_TOKEN}")
fi

# 3) sidecar /api/chat SSE（对话主路径）
SID="agent-smoke-$(date +%s)"
OUT="$(mktemp)"
trap 'rm -f "$OUT"' EXIT
BODY="$(python3 -c "import json; print(json.dumps({
  'messages': [{'role':'user','content':'请只回复四个字：代理OK。不要用工具。'}],
  'project_path': '${ROOT}'
}))")"

curl -sS -N -m 120 \
  -H 'Content-Type: application/json' \
  -H 'Accept: text/event-stream' \
  "${AUTH_H[@]}" \
  -X POST "${AGENT%/}/api/chat" \
  -d "$BODY" >"$OUT"

python3 - <<PY
import json,re
from pathlib import Path
t=Path("$OUT").read_text(errors="replace")
assert t.strip(), "empty SSE body"
text=""
done=None
errs=[]
for m in re.finditer(r"^data: (.+)$", t, re.M):
    try:
        o=json.loads(m.group(1))
    except Exception:
        continue
    if o.get("type")=="delta":
        text += o.get("content") or ""
    if o.get("type")=="error":
        errs.append(o.get("content") or o.get("message") or str(o))
    if o.get("type")=="done":
        done=o
assert done is not None, "missing done event:\n"+t[-500:]
assert not errs, "SSE error: " + "; ".join(errs)
assert done.get("partial") in (None, False), f"partial reply: {done}"
assert text.strip(), "empty assistant text:\n"+t[-500:]
print("OK sidecar chat SSE done partial=false text=", repr(text[:80]))
print("== Desktop Agent smoke PASS ==")
PY
