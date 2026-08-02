#!/usr/bin/env bash
# Spike：M1 本机 Agent Sidecar（loop-code）TTFB
# 架构对齐 2026-07-19：Hub /api/chat 已删；对话主入口 = M1 sidecar :7788
# 用法：
#   bash scripts/ccc-agent-sidecar.sh &   # 另开终端
#   bash scripts/spike-loopcode-ttfb.sh
#   CCC_AGENT=http://127.0.0.1:7788 bash scripts/spike-loopcode-ttfb.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

AGENT="${CCC_AGENT:-http://127.0.0.1:7788}"
PROJECT="${CCC_DESKTOP_SMOKE_PROJECT:-ccc-demo}"
PROMPT="${SPIKE_PROMPT:-只回四个字：测速OK}"

run_one() {
  local name="$1" url="$2"
  local sid out timings
  sid="spike-${name}-$(date +%s)"
  out="$(mktemp)"
  timings="$(mktemp)"
  echo "-- $name → $url"
  set +e
  curl -sS -N -m 120 \
    -H 'Content-Type: application/json' -H 'Accept: text/event-stream' \
    -o "$out" -w "ttfb=%{time_starttransfer}\ntotal=%{time_total}\n" \
    -X POST "$url" \
    -d "{\"project\":\"${PROJECT}\",\"session_id\":\"${sid}\",\"messages\":[{\"role\":\"user\",\"content\":\"${PROMPT}\"}],\"project_path\":\"${ROOT}\"}" \
    >"$timings" 2>/tmp/spike-err.txt
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

if curl -sf -m 2 "${AGENT%/}/health" >/dev/null 2>&1; then
  run_one "local-agent" "${AGENT%/}/api/chat"
else
  echo "-- local-agent SKIP (not running at $AGENT)"
  echo "   start: bash scripts/ccc-agent-sidecar.sh"
fi

echo "== spike done =="
