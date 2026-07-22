#!/usr/bin/env bash
# After file edit: quiet dry-run; inject context if RED (no notify spam).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
tmp_in="$(mktemp)"
tmp_out="$(mktemp)"
trap 'rm -f "$tmp_in" "$tmp_out"' EXIT
cat >"$tmp_in" || true

path="$(python3 -c 'import json,sys
p=""
try:
  d=json.load(open(sys.argv[1]))
  p=d.get("path") or d.get("file") or d.get("file_path") or ""
except Exception:
  pass
print(p)' "$tmp_in")"

case "$path" in
  *docs/product*|*hub_voice*|*transfer_gate*|*loop-engineer*|*authority-patrol*|*dev-channel*|*desktop-connection*|*AppModel.swift*)
    ;;
  *)
    printf '%s\n' '{"ok":true}'
    exit 0
    ;;
esac

set +e
CCC_NOTIFY=0 python3 scripts/ccc-authority-patrol.py --dry-run --json >"$tmp_out" 2>/dev/null
set -e

python3 -c '
import json, sys
path = open(sys.argv[1]).read().strip() if False else None
d = json.load(open(sys.argv[1]))
if d.get("ok"):
    print(json.dumps({"ok": True}))
    raise SystemExit(0)
titles = [str(f.get("title") or f.get("id")) for f in (d.get("findings") or [])][:3]
ctx = (
    "权威巡查（编辑后轻检）发现可能违背："
    + "；".join(titles)
    + "。勿擅自改红线；会话结束会再巡查，或手动 python3 scripts/ccc-authority-patrol.py。"
)
print(json.dumps({"ok": True, "additional_context": ctx}, ensure_ascii=False))
' "$tmp_out"
exit 0
