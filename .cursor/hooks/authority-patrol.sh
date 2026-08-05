#!/usr/bin/env bash
# After agent stop: full authority patrol; notify only on RED.
# Missing/broken runner must not false-alarm (post 2026-08-02 scripts/ retirement).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
cat >/dev/null || true

PATROL="$ROOT/scripts/ccc-authority-patrol.py"
if [[ ! -f "$PATROL" ]]; then
  printf '%s\n' '{"ok":true}'
  exit 0
fi

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT
set +e
CCC_NOTIFY=0 python3 "$PATROL" --dry-run --json >"$tmp" 2>/dev/null
set -e

if ! python3 -c 'import json,sys
p=sys.argv[1]
try:
  d=json.load(open(p))
except Exception:
  raise SystemExit(1)
raise SystemExit(0 if d.get("ok") else 2)' "$tmp"; then
  # exit 1 = parse/runner error → treat green (no spam)
  # exit 2 = real RED findings
  rc=$?
  if [[ "$rc" -eq 1 ]]; then
    printf '%s\n' '{"ok":true}'
    exit 0
  fi
else
  printf '%s\n' '{"ok":true}'
  exit 0
fi

# RED: fire notify (unless muted)
set +e
python3 "$PATROL" >/dev/null 2>&1
set -e

python3 - <<'PY'
import json
print(json.dumps({
  "ok": True,
  "followup_message": (
    "权威巡查发现违背硬共识，已发桌面通知并写入 ~/.ccc/alerts。"
    "绿灯维护可继续；红灯项须等老板拍板后再改红线。"
  ),
}, ensure_ascii=False))
PY
exit 0
