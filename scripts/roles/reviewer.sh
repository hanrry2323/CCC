#!/bin/bash
# ccc-reviewer — reviewer 角色轮询入口 (v0.16b)
# 由 launchd plist com.ccc.reviewer 每 N 秒调一次
# 实际逻辑走 ccc-board.py <role> 子命令

set -uo pipefail

CCC_HOME="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LOG="${HOME}/.ccc/logs/role-reviewer-$(date +%s).log"
mkdir -p "$(dirname "$LOG")"

echo "[$(date '+%H:%M:%S')] reviewer tick" >> "$LOG"
python3 "$CCC_HOME/scripts/ccc-board.py" reviewer >> "$LOG" 2>&1
RC=$?
echo "[$(date '+%H:%M:%S')] reviewer exit=$RC" >> "$LOG"
exit $RC
