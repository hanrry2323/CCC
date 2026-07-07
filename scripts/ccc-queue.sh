#!/bin/bash
# ccc-queue.sh — CCC 队列执行器（v0.9b 简化版）
#
# 职责：按 phases.json 顺序跑 phase，
#       - 单 phase 失败 → on-error 钩子 + L2 通知
#       - 失败 3 次 → L3 通知 + 暂停队列（红线：升级链）
#       - 成功 → post-exec 钩子（commit 等）
#
# 与 launcher 区别：
#   - launcher: 跑 1 个 phase
#   - queue: 跑 N 个 phase + 失败升级 + 暂停
#
# 用法：
#   bash ccc-queue.sh <workspace> [task]
#     workspace: 含 .ccc/phases/<task>.phases.json 的目录
#     task: 任务 ID（默认取最近 plan）
set -uo pipefail

WORKSPACE="${1:-$PWD}"
TASK="${2:-}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ -z "$TASK" ]]; then
  TASK=$(ls -t "$WORKSPACE/.ccc/plans/"*.plan.md 2>/dev/null | head -1 | sed -E 's|.*/(.*)\.plan\.md$|\1|')
  if [[ -z "$TASK" ]]; then
    echo "❌ 无法推断 task, 请显式传入" >&2
    exit 2
  fi
fi

PHASES_FILE="$WORKSPACE/.ccc/phases/$TASK.phases.json"
if [[ ! -f "$PHASES_FILE" ]]; then
  echo "❌ phases.json 不存在: $PHASES_FILE" >&2
  exit 3
fi

MAX_RETRIES=3
echo "=== CCC Queue: task=$TASK ==="
echo "  Workspace: $WORKSPACE"
echo "  Phases:    $PHASES_FILE"
echo "  Max retry: $MAX_RETRIES"
echo ""

# 逐 phase 跑
PHASE_IDS=$(python3 -c "
import json, sys
with open('$PHASES_FILE') as f:
    for line in f:
        line = line.strip()
        if not line: continue
        obj = json.loads(line)
        pid = obj.get('phase') or obj.get('phase_id')
        print(pid)
" 2>/dev/null)

if [[ -z "$PHASE_IDS" ]]; then
  echo "❌ phases.json 没解析出 phase_id" >&2
  exit 4
fi

# 临时 prompt 目录
PROMPT_DIR=$(mktemp -d)
trap "rm -rf $PROMPT_DIR" EXIT

for PHASE_ID in $PHASE_IDS; do
  echo ""
  echo "──── Phase: $PHASE_ID ────"
  
  PROMPT_FILE="$PROMPT_DIR/$PHASE_ID.txt"
  cat > "$PROMPT_FILE" <<EOF
Phase $PHASE_ID of task $TASK
EOF
  
  RETRY=0
  SUCCESS=0
  while [[ $RETRY -lt $MAX_RETRIES ]]; do
    RETRY=$((RETRY+1))
    echo "  [attempt $RETRY/$MAX_RETRIES] launcher..."
    
    if bash "$SCRIPT_DIR/ccc-exec-launcher.sh" "$PHASE_ID" "$PROMPT_FILE" --timeout 120; then
      echo "  ✅ phase $PHASE_ID 成功 (retry=$RETRY)"
      SUCCESS=1
      break
    else
      RC=$?
      echo "  ⚠️ phase $PHASE_ID 失败 (exit=$RC, retry=$RETRY/$MAX_RETRIES)"
      bash "$SCRIPT_DIR/ccc-notify.sh" L2 "queue phase FAIL: $PHASE_ID" "exit=$RC retry=$RETRY" >/dev/null 2>&1 || true
    fi
  done
  
  if [[ $SUCCESS -eq 0 ]]; then
    echo ""
    echo "❌ phase $PHASE_ID 失败 $MAX_RETRIES 次, 暂停队列"
    bash "$SCRIPT_DIR/ccc-notify.sh" L3 "queue paused: $PHASE_ID" "task=$TASK 需老板拍板" >/dev/null 2>&1
    echo "Queue paused at phase $PHASE_ID. 老板拍板后: bash ccc-queue.sh $WORKSPACE $TASK 续跑"
    exit 5
  fi
done

echo ""
echo "✅ 所有 phase 跑完: $TASK"
exit 0
