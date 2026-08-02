#!/usr/bin/env bash
# Phase9 live：在 ccc-demo 种 abnormal work → snapshot user_stage=failed → 清理。
# 用法：CCC_SERVER=http://192.168.3.116:7777 bash scripts/smoke-hub-shell-phase9.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

SERVER="${CCC_SERVER:-http://192.168.3.116:7777}"
USER="${CCC_CHAT_USER:-ccc}"
PASS="${CCC_CHAT_PASS:-ccc}"
AUTH=(-u "${USER}:${PASS}")
PROJECT="${CCC_DESKTOP_SMOKE_PROJECT:-ccc-demo}"
# shellcheck source=scripts/_smoke_remote.sh
source "$(dirname "$0")/_smoke_remote.sh"
REMOTE="${SMOKE_REMOTE_HOST}"
WS_REMOTE="${CCC_PHASE9_WS:-/Users/fan/program/apps/ccc-demo}"
TS=$(date +%s)
EPIC="phase9-stoploss-${TS}-$$"
WORK="${EPIC}-w1"

echo "== phase9 stoploss smoke project=${PROJECT} epic=${EPIC} =="

curl -sf --connect-timeout 8 "${AUTH[@]}" "${SERVER}/api/desktop/projects" >/dev/null

ssh -o ConnectTimeout=8 -o BatchMode=yes "${REMOTE}" "python3 - <<'PY'
import json
from pathlib import Path
from datetime import datetime, timezone

ws = Path('${WS_REMOTE}')
board = ws / '.ccc' / 'board'
(board / 'backlog').mkdir(parents=True, exist_ok=True)
(board / 'abnormal').mkdir(parents=True, exist_ok=True)
now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
epic = {
  'id': '${EPIC}',
  'title': 'Phase9 stoploss seed',
  'description': 'smoke seed — safe to hide',
  'card_kind': 'epic',
  'split_status': 'running',
  'child_ids': ['${WORK}'],
  'complexity': 'small',
  'schema_version': '1.2',
  'ui_hidden': False,
  'created_at': now,
  'updated_at': now,
  'color_group': 'Z',
  'color_depth': 0,
  'tags': ['phase9-smoke'],
  'assignee': None,
  'note': None,
  'parent_id': None,
}
work = {
  'id': '${WORK}',
  'title': 'Phase9 abnormal work',
  'description': 'seed abnormal',
  'card_kind': 'work',
  'parent_id': '${EPIC}',
  'status': 'abnormal',
  'complexity': 'small',
  'schema_version': '1.2',
  'ui_hidden': False,
  'created_at': now,
  'updated_at': now,
  'child_ids': [],
  'color_group': 'Z',
  'color_depth': 1,
  'tags': ['phase9-smoke'],
  'assignee': None,
  'note': 'phase9 smoke hang',
  'split_status': None,
}
(board / 'backlog' / f'${EPIC}.jsonl').write_text(json.dumps(epic, ensure_ascii=False) + '\n', encoding='utf-8')
(board / 'abnormal' / f'${WORK}.jsonl').write_text(json.dumps(work, ensure_ascii=False) + '\n', encoding='utf-8')
print('seeded', '${EPIC}', '${WORK}')
PY"

cleanup() {
  ssh -o ConnectTimeout=8 -o BatchMode=yes "${REMOTE}" "python3 - <<'PY'
from pathlib import Path
ws = Path('${WS_REMOTE}')
board = ws / '.ccc' / 'board'
for col, name in [('backlog', '${EPIC}'), ('abnormal', '${WORK}')]:
    p = board / col / f'{name}.jsonl'
    if p.is_file():
        p.unlink()
        print('removed', p)
PY
" || true
}
trap cleanup EXIT

sleep 1
curl -sf --connect-timeout 8 "${AUTH[@]}" \
  "${SERVER}/api/desktop/flow/snapshot?project_id=${PROJECT}&epic_id=${EPIC}" \
  | tee /tmp/ccc-phase9-snap.json | python3 -c '
import json,sys
d=json.load(sys.stdin)
assert d.get("user_stage") == "failed", d
hl = d.get("headline") or ""
assert ("卡住" in hl) or ("止损" in hl), hl
print("snapshot failed ok", hl)
'

echo "== smoke-hub-shell-phase9 PASS =="
