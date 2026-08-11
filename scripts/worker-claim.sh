#!/usr/bin/env bash
# =============================================================================
# worker-claim.sh —— 集群 Worker 认领脚本（认领协议 v1 · ccc-plan-020）
#
# 作用（在 Worker 机器上由 daemon/cron 定期运行）：
#   1. pull origin main 同步
#   2. 扫描 dispatch 找「执行体=<本 Worker W号> 且 状态=待分派 且 无认领」的卡
#   3. 写认领标记（卡头 `认领：<W号> · 认领时间：<ts>`）→ commit → push origin
#   4. 执行卡：读卡 → 按卡要求执行（业务仓/worktree）→ 回写卡头 `状态=已回写` → commit → push
#
# Engine 侧按「认领态」收单（_claim_round），不靠本地 PID。
#
# 用法：WORKER_ID=W9 scripts/worker-claim.sh [--claim-only]
#   --claim-only：只认领不执行（配合外部执行器）
#
# 环境变量：
#   WORKER_ID        本 Worker W 号（必填）
#   CCC_REPO         CCC 仓路径（默认当前目录；Worker 需已 clone）
#   EXEC_TOOL        执行工具（默认 opencode；可用 claude -p）
#   CLAIM_TIMEOUT    认领超时秒数（默认同 Engine EXECUTOR_TIMEOUT_SECONDS=900）
# =============================================================================
set -euo pipefail

: "${WORKER_ID:?需要 WORKER_ID（如 W9）}"
CCC_REPO="${CCC_REPO:-$(pwd)}"
EXEC_TOOL="${EXEC_TOOL:-opencode}"
CLAIM_ONLY="${1:-}"
CLAIM_TIMEOUT="${CLAIM_TIMEOUT:-900}"

cd "$CCC_REPO"

log() { echo "[worker-claim:$WORKER_ID] $*"; }

# 1. 同步
git pull --rebase --autostash origin main >/dev/null 2>&1 || git pull origin main >/dev/null 2>&1
log "已同步 origin/main: $(git rev-parse --short HEAD)"

# 2. 扫描本 Worker 的待分派卡（执行体=W号 + 状态=待分派 + 无认领字段）
find_cards() {
    grep -rl "^> 关联：.*执行体：$WORKER_ID" docs/dispatch/ 2>/dev/null || true
}

claim_one() {
    local card="$1"
    local ts
    ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    # 校验：状态=待分派 + 无认领
    if ! grep -q "状态：待分派" "$card"; then
        return 1
    fi
    if grep -q "认领：" "$card"; then
        return 1
    fi
    # 定时门禁（2026-08-11）：卡头「定时：HH:MM」未到点不认领（配合 scheduler 触发）
    SCHEDULE_TIME="$(grep -oE "定时[:：][[:space:]]*[0-9]{2}:[0-9]{2}" "$card" | grep -oE "[0-9]{2}:[0-9]{2}" | head -1)"
    if [ -n "$SCHEDULE_TIME" ]; then
        NOW_TS="$(date +%H:%M)"
        if [[ "$NOW_TS" < "$SCHEDULE_TIME" ]]; then
            return 1  # 未到定时点，不认领
        fi
    fi
    # 3. 写认领标记
    python3 - "$card" "$WORKER_ID" "$ts" <<'PY'
import sys
from pathlib import Path
import re
card = Path(sys.argv[1])
wid = sys.argv[2]
ts = sys.argv[3]
text = card.read_text(encoding="utf-8")
m = re.search(r"^(>[^\n]*?)(?:\n|$)", text, re.MULTILINE)
if not m:
    sys.exit(1)
first = m.group(1)
if "执行体：" not in first:
    sys.exit(1)
if "认领：" in first:
    sys.exit(1)
new_first = first + f" · 认领：{wid} · 认领时间：{ts}"
text = text[:m.start(1)] + new_first + text[m.end(1):]
card.write_text(text, encoding="utf-8")
print(f"认领标记已写入: {card.name}")
PY
    git add "$card"
    git commit -q -m "claim($WORKER_ID): 认领 ${card_name:-unknown}"
    git push origin main >/dev/null 2>&1
    log "已认领 ${card_name:-unknown}（$WORKER_ID @ $ts）"
    return 0
}

card_name=""
claimed=""
for card in $(find_cards); do
    card_name="$(basename "$card")"
    if claim_one "$card"; then
        claimed="$card"
        break  # 一次认领一张，执行完再下一轮
    fi
done

if [ -z "$claimed" ]; then
    log "无待认领卡"
    exit 0
fi

if [ "$CLAIM_ONLY" = "--claim-only" ]; then
    log "已认领 $card_name（--claim-only，不执行）"
    exit 0
fi

# 4. 执行卡前：skill 存在性校验（③ · ccc-plan-020 A 轨第 4 项）
#    调 sync-skills.py --check 校验本节点 skill 与仓 hash 一致；MISMATCH → 自动同步再执行。
log "skill 校验（认领前）..."
if ! python3 "$CCC_REPO/scripts/sync-skills.py" --node "${WORKER_NODE:-M1}" --check 2>&1 | grep -q "MISMATCH"; then
    log "skill 校验通过"
else
    log "skill 存在 MISMATCH → 自动同步"
    python3 "$CCC_REPO/scripts/sync-skills.py" --node "${WORKER_NODE:-M1}" 2>&1 | tail -3
    if python3 "$CCC_REPO/scripts/sync-skills.py" --node "${WORKER_NODE:-M1}" --check 2>&1 | grep -q "MISMATCH"; then
        log "同步后仍 MISMATCH → 打标待处理（不阻塞执行，但记录）"
    fi
fi

# 4b. 执行卡：读卡 → 调用执行工具 → 回写
log "执行 $card_name ..."
"$EXEC_TOOL" run --auto --dir "$CCC_REPO" \
    "请严格按任务卡 $claimed 完成（集群 Worker $WORKER_ID 认领执行）。先 Read 卡全文，按卡内要求开发；完成后把卡头「状态」改为「已回写」并填回写区，commit+push 到该卡对应分支。禁止自置已关闭。" \
    || log "执行未成功完成（可人工跟进或超时回收）"

# 5. 回写检查：若执行器未自动回写，脚本不重复回写（回写由执行器按卡流程完成）
log "认领执行流程结束: $card_name"
