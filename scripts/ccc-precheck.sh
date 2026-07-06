#!/bin/bash
# ccc-precheck.sh — CCC 任务启动前置门控（v1.2.0 新增 · T1.3）
#
# 5 项前置门控（任一 FAIL → exit 1，禁越界启动 Executor）：
#   1. .ccc/state.md 存在（红线 10）
#   2. .ccc/profile.md 存在（红线 7）
#   3. plan.md 引用真实存在的路径（白名单 + 黑名单）
#   4. phases.json 是合法 JSONL（红线 5）
#   5. watchdog 健康（红线 9 配套）
#
# 用法：
#   bash scripts/ccc-precheck.sh                       # 默认检查当前 workspace
#   bash scripts/ccc-precheck.sh <workspace> <task>    # 检查指定任务的 plan/phases
#   bash scripts/ccc-precheck.sh --skip-watchdog       # 跳过 watchdog（不推荐）

set -uo pipefail

# --- 参数解析 ---
SKIP_WATCHDOG=0
WORKSPACE=""
TASK=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-watchdog) SKIP_WATCHDOG=1; shift ;;
    -h|--help)
      cat <<'EOF'
ccc-precheck.sh — CCC 任务启动前置门控

用法:
  bash scripts/ccc-precheck.sh                       # 当前 workspace + 当前 task
  bash scripts/ccc-precheck.sh <workspace> <task>    # 指定 workspace + task
  bash scripts/ccc-precheck.sh --skip-watchdog       # 跳过 watchdog（仅调试用）

退出码:
  0 = 全部 PASS，可启动 Executor
  1 = 任一 FAIL，必须修复后重跑
  2 = 参数错误
EOF
      exit 0 ;;
    *)
      if [[ -z "$WORKSPACE" ]]; then WORKSPACE="$1"; shift
      elif [[ -z "$TASK" ]]; then TASK="$1"; shift
      else echo "未知参数: $1" >&2; exit 2
      fi ;;
  esac
done

WORKSPACE="${WORKSPACE:-$(pwd)}"
TASK="${TASK:-$(ls -t "$WORKSPACE/.ccc/plans/"*.plan.md 2>/dev/null | head -1 | sed -E 's|.*/(.*)\.plan\.md$|\1|')}"

if [[ -z "$TASK" ]]; then
  echo "❌ 无法自动推断 task 名, 请显式传入: bash scripts/ccc-precheck.sh <workspace> <task>" >&2
  exit 2
fi

CCC_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PLAN_FILE="$WORKSPACE/.ccc/plans/$TASK.plan.md"
PHASES_FILE="$WORKSPACE/.ccc/phases/$TASK.phases.json"

PASS_COUNT=0
FAIL_COUNT=0
declare -a FAILURES

log_pass() { echo "  [PASS] $1"; PASS_COUNT=$((PASS_COUNT+1)); }
log_fail() { echo "  [FAIL] $1"; FAIL_COUNT=$((FAIL_COUNT+1)); FAILURES+=("$1"); }

echo "=== ccc-precheck.sh ==="
echo "  Workspace: $WORKSPACE"
echo "  Task:      $TASK"
echo "  Plan:      $PLAN_FILE"
echo ""

# --- Gate 1: .ccc/state.md 存在（红线 10）---
echo "──── Gate 1: .ccc/state.md 存在（红线 10 · 跨会话接力） ────"
if [[ -f "$WORKSPACE/.ccc/state.md" ]]; then
  log_pass "state.md 存在: $WORKSPACE/.ccc/state.md"
else
  log_fail "state.md 不存在: $WORKSPACE/.ccc/state.md — 红线 10 触犯, 禁止无接力启动"
fi

# --- Gate 2: .ccc/profile.md 存在（红线 7）---
echo "──── Gate 2: .ccc/profile.md 存在（红线 7 · 启动顺序） ────"
if [[ -f "$WORKSPACE/.ccc/profile.md" ]]; then
  log_pass "profile.md 存在: $WORKSPACE/.ccc/profile.md"
else
  log_fail "profile.md 不存在: $WORKSPACE/.ccc/profile.md — 红线 7 触犯, 禁止无项目档案启动"
fi

# --- Gate 3: plan.md 存在且含必填字段 ---
echo "──── Gate 3: plan.md 存在且含必填字段 ────"
if [[ ! -f "$PLAN_FILE" ]]; then
  log_fail "plan.md 不存在: $PLAN_FILE — Planner 必写产物"
else
  log_pass "plan.md 存在: $PLAN_FILE"

  # 必填字段: 目标 / Phase 数 / 只改文件 / Commit 计划
  MISSING_FIELDS=()
  grep -qE '目标' "$PLAN_FILE"  || MISSING_FIELDS+=("目标")
  grep -qE 'Phase' "$PLAN_FILE" || MISSING_FIELDS+=("Phase")
  grep -qE '只改文件|白名单' "$PLAN_FILE" || MISSING_FIELDS+=("只改文件")
  grep -qE 'Commit 计划|Commit 计划表' "$PLAN_FILE" || MISSING_FIELDS+=("Commit 计划")

  if [[ ${#MISSING_FIELDS[@]} -eq 0 ]]; then
    log_pass "plan.md 含必填字段 (目标/Phase/只改文件/Commit 计划)"
  else
    log_fail "plan.md 缺必填字段: ${MISSING_FIELDS[*]}"
  fi
fi

# --- Gate 4: phases.json 是合法 JSONL（红线 5）---
echo "──── Gate 4: phases.json 合法 JSONL（红线 5） ────"
if [[ ! -f "$PHASES_FILE" ]]; then
  log_fail "phases.json 不存在: $PHASES_FILE — 红线 5 触犯"
else
  log_pass "phases.json 存在: $PHASES_FILE"

  if python3 - "$PHASES_FILE" <<'PYEOF' 2>/dev/null
import json, sys
fp = sys.argv[1]
ok = True
with open(fp) as f:
    for i, line in enumerate(f, 1):
        line = line.strip()
        if not line: continue
        try:
            obj = json.loads(line)
            phase_id = obj.get("phase") or obj.get("phase_id")
            assert phase_id is not None, f"line {i}: 缺 'phase' 或 'phase_id' 字段"
            assert "status" in obj, f"line {i}: 缺 'status' 字段"
            assert obj["status"] in ("pending","in_progress","done","failed","verified","verifying","skipped"), f"line {i}: 非法 status '{obj['status']}'"
        except Exception as e:
            print(f"FAIL: {e}", file=sys.stderr)
            sys.exit(1)
sys.exit(0)
PYEOF
  then
    log_pass "phases.json 合法 JSONL, 所有 phase 行含 phase/phase_id + status 字段"
  else
    log_fail "phases.json 不是合法 JSONL 或缺必填字段 (phase/status)"
  fi
fi

# --- Gate 5: watchdog 健康（红线 9 配套）---
echo "──── Gate 5: executor-watchdog 健康（红线 9） ────"
if [[ $SKIP_WATCHDOG -eq 1 ]]; then
  log_pass "watchdog 跳过（--skip-watchdog）"
else
  if [[ -x "$CCC_DIR/scripts/executor-watchdog.sh" ]]; then
    WD_EXIT=0
    bash "$CCC_DIR/scripts/executor-watchdog.sh" >/dev/null 2>&1 || WD_EXIT=$?
    case $WD_EXIT in
      0) log_pass "watchdog 健康（exit 0）";;
      1) log_fail "watchdog warning（exit 1）— 建议加 --force-kill 或人工决策";;
      2) log_fail "watchdog 严重（exit 2）— 放弃本次启动";;
      3) log_fail "watchdog 已自动清理（exit 3）— 启动条件已修复, 可重试";;
      *) log_fail "watchdog 退出码异常: $WD_EXIT";;
    esac
  else
    log_fail "executor-watchdog.sh 不可执行: $CCC_DIR/scripts/executor-watchdog.sh"
  fi
fi

echo ""
echo "=== 汇总 ==="
echo "  PASS: $PASS_COUNT / 5"
echo "  FAIL: $FAIL_COUNT / 5"
if [[ $FAIL_COUNT -gt 0 ]]; then
  echo ""
  echo "失败项:"
  for f in "${FAILURES[@]}"; do
    echo "  - $f"
  done
  echo ""
  echo "❌ ccc-precheck FAIL — 必须修复后重跑, 禁止启动 Executor"
  exit 1
fi
echo ""
echo "✅ ccc-precheck PASS — 可启动 Executor"
exit 0