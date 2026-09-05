#!/usr/bin/env bash
# After agent stop: new-stack gate check (card validate). Notify-style followup only on RED.
# Replaces retired scripts/ccc-authority-patrol.py (Hub-era).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT
set +e
python3 -m server.board.validate docs/dispatch >"$tmp" 2>&1
rc=$?
set -e

if [[ "$rc" -eq 0 ]]; then
  printf '%s\n' '{"ok":true}'
  exit 0
fi

# RED: card-header gate failed
python3 - <<PY
import json
print(json.dumps({
  "ok": True,
  "followup_message": (
    "卡头门禁未通过（python -m server.board.validate docs/dispatch）。"
    "请按输出修复卡头五态/字段；勿回退到 Hub 旧巡查脚本。"
  ),
}, ensure_ascii=False))
PY
exit 0
