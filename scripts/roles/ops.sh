#!/bin/bash
# ccc-ops — ops 角色轮询入口 (v0.16b)
# 由 launchd plist com.ccc.ops 每 N 秒调一次
# 实际逻辑走 ccc-board.py <role> 子命令

set -uo pipefail

CCC_HOME="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LOG="${HOME}/.ccc/logs/role-ops-$(date +%s).log"
mkdir -p "$(dirname "$LOG")"

echo "[$(date '+%H:%M:%S')] ops tick" >> "$LOG"
python3 "$CCC_HOME/scripts/ccc-board.py" ops >> "$LOG" 2>&1
RC=$?
echo "[$(date '+%H:%M:%S')] ops exit=$RC" >> "$LOG"
exit $RC
