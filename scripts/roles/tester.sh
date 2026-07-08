#!/bin/bash
# ccc-tester — tester 角色轮询入口 (v0.18)
# 由 launchd plist com.ccc.tester 每 N 秒调一次
# 加载 skills/ccc-tester/SKILL.md 后走 ccc-board.py

set -uo pipefail

CCC_HOME="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
export CCC_WORKSPACE="${CCC_WORKSPACE:-$CCC_HOME}"  # 保留环境变量传入值（如 qxo plist），默认 CCC
CCC_ROLE="tester"
export CCC_ROLE
export CCC_ROLE_SKILL="${CCC_HOME}/skills/ccc-${CCC_ROLE}/SKILL.md"

LOG="${HOME}/.ccc/logs/role-${CCC_ROLE}-$(date +%s).log"
mkdir -p "$(dirname "$LOG")"

# 修复 launchd 环境缺 PATH
export PATH="/Users/apple/.npm-global/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

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
