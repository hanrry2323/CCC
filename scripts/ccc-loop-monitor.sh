#!/bin/bash
# ccc-loop-monitor.sh — 每 5 分钟检查 CCC pipeline 状态，24h 持续运行
# 用法: (crontab -l; echo "*/5 * * * * /Users/apple/program/CCC/scripts/ccc-loop-monitor.sh") | crontab -

LOG=/Users/apple/.ccc/loop-monitor.log
WS=/Users/apple/program/CCC
cd "$WS"

echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] === loop-monitor tick ===" >> "$LOG"

# Step 1: Patrol check
python3 scripts/ccc-patrol-v4.py >> "$LOG" 2>&1
PATROL_RC=$?
echo "patrol exit=$PATROL_RC" >> "$LOG"

# Step 2: Check Engine alive
if ! pgrep -f ccc-engine.py > /dev/null 2>&1; then
    echo "ENGINE DEAD — restarting" >> "$LOG"
    python3 scripts/ccc-engine.py &
    sleep 2
fi

# Step 3: Check in_progress tasks 
python3 -c "
import sys; sys.path.insert(0, 'scripts')
from pathlib import Path
from _board_store import FileBoardStore

tasks_running = 0
for name, ws_path in [
    ('CCC', Path.home()/'program/CCC'),
    ('qxo', Path.home()/'program/qx-observer'),
    ('xianyu', Path.home()/'program/xianyu'),
    ('qb', Path.home()/'program/qb'),
    ('qx', Path.home()/'program/projects/qx'),
]:
    board = ws_path / '.ccc' / 'board'
    if not board.exists(): continue
    store = FileBoardStore(ws_path)
    ip = store.list_tasks('in_progress')
    pl = store.list_tasks('planned')
    bl = store.list_tasks('backlog')
    if ip: print(f'{name} IN_PROGRESS: {len(ip)} tasks')
    if pl: print(f'{name} PLANNED: {len(pl)} tasks')
    if bl: print(f'{name} BACKLOG: {len(bl)} tasks')
    tasks_running += len(ip)
print(f'TOTAL RUNNING: {tasks_running}')
if tasks_running == 0:
    print('WARN: no tasks running in any workspace')
" >> "$LOG" 2>&1

# Step 4: Check blockages - tasks stuck >30min
python3 -c "
import sys; sys.path.insert(0, 'scripts')
from pathlib import Path
from _board_store import FileBoardStore
from _utils import now_iso
from datetime import datetime, timezone

now = datetime.now(timezone.utc)
for ws_path in [Path.home()/'program/CCC']:
    board = ws_path / '.ccc' / 'board'
    if not board.exists(): continue
    store = FileBoardStore(ws_path)
    for col in ['in_progress', 'testing']:
        tasks = store.list_tasks(col)
        for t in tasks:
            ts = t.get('ts', '')
            if ts:
                try:
                    dt = datetime.fromisoformat(ts)
                    age = (now - dt).total_seconds() / 60
                    if age > 30:
                        print(f'STALE: {t[\"id\"]} in {col} for {age:.0f}min')
                except: pass
" >> "$LOG" 2>&1

tail -5 "$LOG"
