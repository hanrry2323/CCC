#!/bin/bash
# ccc-auto-dev.sh — 自动化开发入口（v0.15b）
#
# 职责: 你说"按 CCC 跑 X"后, 这个脚本做 4 件事:
#   1. 写 plan.md + phases.json 到 <workspace>/.ccc/
#   2. 调 opencode-exec.py 跑每个 phase (opencode 写代码)
#   3. post-exec 钩子自动 commit + push
#   4. 跑完通知 (桌面通知 + log)
#
# 用法:
#   ccc-auto-dev.sh <workspace> <task> "<goal>"
#     workspace: 项目根目录
#     task: 任务 ID (如 qx-cc-batch-c)
#     goal: 任务目标 (1 句话, 写入 plan.md)
#
# v0.15b 配套:
#   - opencode exec 必须用 loop/flash (CLAUDE.md 红线)
#   - ~/.ccc/hooks/post-exec.sh 必须装 (含 git push)
#   - launcher 内部跑 watchdog (红线 X2/X3)
set -uo pipefail

WORKSPACE="${1:?usage: ccc-auto-dev.sh <workspace> <task> <goal>}"
TASK="${2:?usage: ccc-auto-dev.sh <workspace> <task> <goal>}"
GOAL="${3:?usage: ccc-auto-dev.sh <workspace> <task> <goal>}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CCC_HOME="$(cd "$SCRIPT_DIR/.." && pwd)"

# 准备 .ccc 目录
mkdir -p "$WORKSPACE/.ccc/plans" "$WORKSPACE/.ccc/phases" "$WORKSPACE/.ccc/reports" "$WORKSPACE/.ccc/verdicts"

# 1. 写 plan.md
PLAN_FILE="$WORKSPACE/.ccc/plans/$TASK.plan.md"
cat > "$PLAN_FILE" <<EOF
# $TASK

> 目标: $GOAL
> 执行人: opencode (loop/flash) via ccc-auto-dev.sh
> 时间: $(date '+%Y-%m-%d %H:%M:%S')

## 目标

$GOAL

## Phase

(由 ccc-auto-dev 自动生成)

## 只改文件

(由 ccc-auto-dev 自动扫描)

## Commit 计划

- 每 phase 完成后, post-exec 钩子自动 commit + push
- 1 phase = 1 commit

## 红线

- 红线 1: 不动系统文件
- 红线 2: 验收可执行
- 红线 12: 用户显式触发 (本调用即触发)
- 红线 13: 不预留路线代码
EOF

# 2. 写 phases.json (单 phase, 跑 opencode 改 + commit)
PHASES_FILE="$WORKSPACE/.ccc/phases/$TASK.phases.json"
cat > "$PHASES_FILE" <<EOF
{"phase":"$TASK-p1","status":"in_progress","description":"$GOAL"}
EOF

# 3. 调 launcher 跑 phase (opencode 写代码)
PROMPT_FILE="/tmp/ccc-auto-dev-$TASK.txt"
cat > "$PROMPT_FILE" <<EOF
你是 opencode 执行器 (loop/flash), 在 $WORKSPACE 项目下执行任务 $TASK。

任务: $GOAL

## 步骤
1. cd $WORKSPACE
2. 读 .ccc/profile.md (项目档案, 红线 7 强制)
3. 读 .ccc/state.md (接力索引, 红线 10 强制)
4. 读 .ccc/plans/$TASK.plan.md (本次任务)
5. 执行任务 (改代码 + 改测试 + 跑测试)
6. 写 .ccc/reports/$TASK.report.md (3 段: 做了什么 / 怎么验 / 有什么风险)
7. 写 .ccc/verdicts/$TASK.verdict.md (≥3 probes, 末行 ## VERDICT: PASS|FAIL|CONDITIONAL_PASS)

## 红线
- 不动 ~/.env / 密钥
- 不改 schema.sql (除非有 v2 migration)
- 不引入新依赖
- 不删现存测试 (只改 mock target)
- commit msg 格式: $TASK: <一句话>

完成后 commit msg 用 "<一句话>" 然后退出。
EOF

echo "[ccc-auto-dev] 启动 launcher 跑 opencode: $TASK"
echo "[ccc-auto-dev] plan: $PLAN_FILE"
echo "[ccc-auto-dev] prompt: $PROMPT_FILE"

# 4. 调 launcher (post-exec 钩子自动 commit + push)
# export CCC_WORKSPACE 让 post-exec 知道在哪个仓库 commit
# v0.15b: 传 --cwd 让 launcher 启动 opencode 时在 workspace 跑
export CCC_WORKSPACE="$WORKSPACE"
export CCC_PLAN_NAME="$TASK"
export CCC_PHASE_INDEX="$TASK-p1"
bash "$SCRIPT_DIR/ccc-exec-launcher.sh" "$TASK-p1" "$PROMPT_FILE" --timeout 600 --cwd "$WORKSPACE"
RC=$?

# 5. 写 phase 状态
if [[ $RC -eq 0 ]]; then
  python3 -c "
import json
fp = '$PHASES_FILE'
lines = []
with open(fp) as f:
    for line in f:
        line = line.rstrip()
        if not line: continue
        obj = json.loads(line)
        obj['status'] = 'done'
        lines.append(json.dumps(obj, ensure_ascii=False))
with open(fp, 'w') as f:
    f.write('\n'.join(lines) + '\n')
"
  bash "$SCRIPT_DIR/ccc-notify.sh" L2 "ccc-auto-dev PASS: $TASK" "opencode 写代码 + post-exec 落远端" >/dev/null 2>&1 || true
  echo "[ccc-auto-dev] ✅ $TASK done, post-exec 已 commit+push"
else
  bash "$SCRIPT_DIR/ccc-notify.sh" L3 "ccc-auto-dev FAIL: $TASK" "exit=$RC" >/dev/null 2>&1 || true
  echo "[ccc-auto-dev] ❌ $TASK 失败, exit=$RC"
fi

rm -f "$PROMPT_FILE"
exit $RC
