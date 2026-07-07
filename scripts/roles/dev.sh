#!/bin/bash
# ccc-dev — dev 角色轮询入口 (v0.18)
# 由 launchd plist com.ccc.dev 每 N 秒调一次
# 加载 skills/ccc-dev/SKILL.md 后走 ccc-board.py

set -uo pipefail

CCC_HOME="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
export CCC_WORKSPACE="$CCC_HOME"
CCC_ROLE="dev"
export CCC_ROLE
export CCC_ROLE_SKILL="${CCC_HOME}/skills/ccc-${CCC_ROLE}/SKILL.md"

LOG="${HOME}/.ccc/logs/role-${CCC_ROLE}-$(date +%s).log"
mkdir -p "$(dirname "$LOG")"

# 加载 skill
echo "[$(date '+%H:%M:%S')] ===== ${CCC_ROLE} tick =====" >> "$LOG"
if [ -f "$CCC_ROLE_SKILL" ]; then
    echo "--- skill: ${CCC_ROLE_SKILL} ---" >> "$LOG"
    head -6 "$CCC_ROLE_SKILL" >> "$LOG"
    echo "---" >> "$LOG"
else
    echo "[skill] MISSING: ${CCC_ROLE_SKILL}" >> "$LOG"
fi

python3 "$CCC_HOME/scripts/ccc-board.py" "$CCC_ROLE" >> "$LOG" 2>&1
RC=$?
echo "[$(date '+%H:%M:%S')] ${CCC_ROLE} exit=$RC" >> "$LOG"
exit $RC
