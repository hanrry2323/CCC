#!/bin/bash
# ccc-loop-monitor.sh — 观察专用（v0.39）
# 永不自启 Engine。control=disabled 时直接退出。

set -uo pipefail

LOG="${HOME}/.ccc/loop-monitor.log"
WS="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p "$(dirname "$LOG")"
cd "$WS"

echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] === loop-monitor tick ===" >> "$LOG"

if ! python3 -c "import sys; sys.path.insert(0,'scripts'); from _ccc_control import is_enabled; raise SystemExit(0 if is_enabled() else 1)"; then
  echo "CCC control=disabled — skip" >> "$LOG"
  exit 0
fi

# 仅观察：patrol --no-restart
if [[ -f scripts/ccc-patrol-v4.py ]]; then
  python3 scripts/ccc-patrol-v4.py --no-restart >> "$LOG" 2>&1 || true
fi

if pgrep -f 'ccc-engine\.py' > /dev/null 2>&1; then
  echo "ENGINE alive" >> "$LOG"
else
  echo "ENGINE down (no auto-restart by policy)" >> "$LOG"
fi

python3 -c "
import sys
sys.path.insert(0, 'scripts')
from pathlib import Path
from _board_store import FileBoardStore
for name, ws_path in [
    ('CCC', Path.home()/'program/CCC'),
    ('qxo', Path.home()/'program/qx-observer'),
    ('xianyu', Path.home()/'program/xianyu'),
    ('qb', Path.home()/'program/projects/qb'),
    ('qx', Path.home()/'program/projects/qx'),
]:
    if not (ws_path/'.ccc'/'board').exists():
        continue
    store = FileBoardStore(ws_path)
    parts = []
    for col in ('backlog','planned','in_progress','testing','verified','abnormal'):
        n = len(store.list_tasks(col))
        if n:
            parts.append(f'{col}={n}')
    if parts:
        print(f'{name}: ' + ', '.join(parts))
" >> "$LOG" 2>&1 || true
