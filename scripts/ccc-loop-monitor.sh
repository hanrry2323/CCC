#!/bin/bash
# ccc-loop-monitor.sh — 可选健康观察（默认不自启 Engine）
#
# 根因修复 (v0.38.1):
#   旧版每 5 分钟发现 Engine 死后执行 `python3 ccc-engine.py &`，
#   导致 plist 已卸/用户已杀仍被强制拉起（双 engine / 内存爆）。
#   现行为：仅观察写日志；永不自启；尊重 ~/.ccc/DISABLED。
#
# 不建议装进 crontab。若需监控，请人工执行或仅在明确启用 CCC 后使用。

set -uo pipefail

LOG="${HOME}/.ccc/loop-monitor.log"
WS="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SENTINEL="${HOME}/.ccc/DISABLED"
mkdir -p "$(dirname "$LOG")"
cd "$WS"

echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] === loop-monitor tick ===" >> "$LOG"

if [[ -f "$SENTINEL" ]]; then
  echo "CCC DISABLED ($SENTINEL) — skip patrol/restart" >> "$LOG"
  exit 0
fi

# Step 1: Patrol check（patrol 自身也不再强制拉起，见 ccc-patrol-v4.py）
if [[ -f scripts/ccc-patrol-v4.py ]]; then
  python3 scripts/ccc-patrol-v4.py --no-restart >> "$LOG" 2>&1 || true
  echo "patrol exit=$?" >> "$LOG"
fi

# Step 2: 仅报告 Engine 是否存活 — 绝不后台启动
if pgrep -f 'ccc-engine\.py' > /dev/null 2>&1; then
  echo "ENGINE alive: $(pgrep -f 'ccc-engine\.py' | tr '\n' ' ')" >> "$LOG"
else
  echo "ENGINE down (will NOT auto-restart; enable via launchd or ccc-autostart-guard.sh)" >> "$LOG"
fi

# Step 3: 看板摘要
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

tail -3 "$LOG" 2>/dev/null || true
