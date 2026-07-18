#!/usr/bin/env bash
# 断言 Hub 方案 Agent = loop-code（SSOT），并跑一轮完整 chat SSE
# 用法：CCC_SERVER=http://192.168.3.116:7777 bash scripts/smoke-desktop-agent.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
SERVER="${CCC_SERVER:-http://127.0.0.1:7777}"
USER="${CCC_CHAT_USER:-ccc}"
PASS="${CCC_CHAT_PASS:-ccc}"
PROJECT="${CCC_DESKTOP_SMOKE_PROJECT:-ccc-demo}"

echo "== Desktop Agent smoke against ${SERVER} =="

CFG="$(curl -sf -u "${USER}:${PASS}" --connect-timeout 5 "${SERVER%/}/api/desktop/config")"
echo "$CFG" | python3 -c "
import json,sys
d=json.load(sys.stdin)
rt=d.get('agent_runtime') or ''
cli=d.get('agent_cli') or ''
print('agent_runtime=', rt)
print('agent_cli=', cli)
assert d.get('ok') is True, d
assert rt == 'loop-code', f'SSOT requires loop-code, got runtime={rt!r} cli={cli!r}'
assert 'vendor/loop-code/cli' in cli.replace('\\\\','/'), f'cli path not loop-code: {cli!r}'
print('OK config agent=loop-code')
"

SID="agent-smoke-$(date +%s)"
OUT="$(mktemp)"
trap 'rm -f "$OUT"' EXIT
BODY="$(python3 -c "import json; print(json.dumps({
  'project': '${PROJECT}',
  'session_id': '${SID}',
  'messages': [{'role':'user','content':'请只回复四个字：代理OK。不要用工具。'}]
}))")"

curl -sS -N -m 120 -u "${USER}:${PASS}" \
  -H 'Content-Type: application/json' \
  -H 'Accept: text/event-stream' \
  -X POST "${SERVER%/}/api/chat" \
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
print("OK chat SSE done partial=false text=", repr(text[:80]))
print("== Desktop Agent smoke PASS ==")
PY
