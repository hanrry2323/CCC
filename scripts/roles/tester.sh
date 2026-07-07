#!/bin/bash
# ccc-tester — tester 角色轮询入口 (v0.16b)
# 由 launchd plist com.ccc.tester 每 N 秒调一次
# 实际逻辑走 ccc-board.py <role> 子命令

set -uo pipefail

CCC_HOME="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LOG="${HOME}/.ccc/logs/role-tester-$(date +%s).log"
mkdir -p "$(dirname "$LOG")"

echo "[$(date '+%H:%M:%S')] tester tick" >> "$LOG"
python3 "$CCC_HOME/scripts/ccc-board.py" tester >> "$LOG" 2>&1
RC=$?
echo "[$(date '+%H:%M:%S')] tester exit=$RC" >> "$LOG"
exit $RC
