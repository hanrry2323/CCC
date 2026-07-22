#!/usr/bin/env bash
# After agent stop: full authority patrol; notify only on RED.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
cat >/dev/null || true

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT
set +e
CCC_NOTIFY=0 python3 scripts/ccc-authority-patrol.py --dry-run --json >"$tmp" 2>/dev/null
rc=$?
set -e

if python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); raise SystemExit(0 if d.get("ok") else 1)' "$tmp"; then
  printf '%s\n' '{"ok":true}'
  exit 0
fi

# RED: fire notify (unless muted)
set +e
python3 scripts/ccc-authority-patrol.py >/dev/null 2>&1
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
