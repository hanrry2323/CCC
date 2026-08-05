#!/usr/bin/env bash
# After file edit: only watch authority-sensitive paths; run new-stack validate dry summary.
# Missing validate module must not false-alarm.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
tmp_in="$(mktemp)"
trap 'rm -f "$tmp_in"' EXIT
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
  *docs/dispatch*|*docs/product/dev-channel*|*CURSOR.md*|*STARTUP-BRIEF*|*CLAUDE.md*|*loop-engineer-consensus*|*location-truth*)
    ;;
  *)
    printf '%s\n' '{"ok":true}'
    exit 0
    ;;
esac

set +e
python3 -m server.board.validate docs/dispatch >/dev/null 2>&1
rc=$?
set -e

if [[ "$rc" -ne 0 ]]; then
  python3 - <<'PY'
import json
print(json.dumps({
  "ok": True,
  "additional_context": (
    "提醒：docs/dispatch 卡头门禁当前非绿。"
    "现行权威=CURSOR.md + .cursor/rules + INDEX §0；勿引用 Hub:7777/sidecar。"
  ),
}, ensure_ascii=False))
  exit 0
fi

printf '%s\n' '{"ok":true}'
exit 0
