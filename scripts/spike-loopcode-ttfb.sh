#!/usr/bin/env bash
# Spike：本机 Agent Sidecar（loop-code）vs Hub /api/chat TTFB
# 用法：
#   bash scripts/ccc-agent-sidecar.sh &   # 另开终端
#   bash scripts/spike-loopcode-ttfb.sh
#   CCC_AGENT=http://127.0.0.1:7788 CCC_SERVER=http://192.168.3.116:7777 bash scripts/spike-loopcode-ttfb.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

HUB="${CCC_SERVER:-http://192.168.3.116:7777}"
AGENT="${CCC_AGENT:-http://127.0.0.1:7788}"
USER="${CCC_CHAT_USER:-ccc}"
PASS="${CCC_CHAT_PASS:-ccc}"
PROJECT="${CCC_DESKTOP_SMOKE_PROJECT:-ccc-demo}"
PROMPT="${SPIKE_PROMPT:-只回四个字：测速OK}"

run_one() {
  local name="$1" url="$2" use_auth="$3"
  local sid out timings
  sid="spike-${name}-$(date +%s)"
  out="$(mktemp)"
  timings="$(mktemp)"
  echo "-- $name → $url"
  set +e
  if [[ "$use_auth" == "1" ]]; then
    curl -sS -N -m 120 -u "${USER}:${PASS}" \
      -H 'Content-Type: application/json' -H 'Accept: text/event-stream' \
      -o "$out" -w "ttfb=%{time_starttransfer}\ntotal=%{time_total}\n" \
      -X POST "$url" \
      -d "{\"project\":\"${PROJECT}\",\"session_id\":\"${sid}\",\"messages\":[{\"role\":\"user\",\"content\":\"${PROMPT}\"}],\"project_path\":\"${ROOT}\"}" \
      >"$timings" 2>/tmp/spike-err.txt
  else
    curl -sS -N -m 120 \
      -H 'Content-Type: application/json' -H 'Accept: text/event-stream' \
      -o "$out" -w "ttfb=%{time_starttransfer}\ntotal=%{time_total}\n" \
      -X POST "$url" \
      -d "{\"project\":\"${PROJECT}\",\"session_id\":\"${sid}\",\"messages\":[{\"role\":\"user\",\"content\":\"${PROMPT}\"}],\"project_path\":\"${ROOT}\"}" \
      >"$timings" 2>/tmp/spike-err.txt
  fi
  local ec=$?
  set -e
  cat "$timings"
  python3 - <<PY
import json, re
from pathlib import Path
t = Path("$out").read_text(errors="replace")
chunks, err, done = [], None, None
for m in re.finditer(r"^data: (.+)$", t, re.M):
    try:
        o = json.loads(m.group(1))
    except Exception:
        continue
    if o.get("type") == "delta":
        chunks.append(o.get("content") or "")
    if o.get("type") == "error":
        err = o.get("content")
    if o.get("type") == "done":
        done = o
print("text=", repr("".join(chunks)[:80]))
print("err=", err)
print("done_partial=", None if not done else done.get("partial"))
print("bytes=", len(t))
PY
  if [[ $ec -ne 0 ]]; then
    echo "FAIL curl_exit=$ec"
    cat /tmp/spike-err.txt 2>/dev/null | tail -5 || true
  fi
  rm -f "$out" "$timings"
  echo
}

echo "== spike-loopcode-ttfb =="
echo "ROOT=$ROOT"
echo "PROMPT=$PROMPT"

run_one "hub" "${HUB%/}/api/chat" 1

if curl -sf -m 2 "${AGENT%/}/health" >/dev/null 2>&1; then
  run_one "local-agent" "${AGENT%/}/api/chat" 0
else
  echo "-- local-agent SKIP (not running at $AGENT)"
  echo "   start: bash scripts/ccc-agent-sidecar.sh"
fi

echo "== spike done =="
