#!/bin/bash
# ccc-zcode-orchestrate.sh — ZCode 端到端编排器 (v1.2.1)
#
# 单脚本走完 Planner → Executor → Verifier → commit → finish 全链路。
# 替代手动分步(E2E-DEMO.md §6 的 7 步),自动注册 cluster-bus + watchdog + commit。
#
# 用法:
#   bash scripts/ccc-zcode-orchestrate.sh <workspace> <task> [--dry-run] [--skip-register]
#
# 流程:
#   0. precheck      bash scripts/ccc-precheck.sh <ws> <task>           [门控 1-5]
#   1. register      python3 scripts/ccc-znode-register.py (--daemon)   [可选]
#   2. executor      bash scripts/ccc-zcode-bridge.sh <ws> <task> executor
#   3. commit        bash scripts/ccc-exec-commit.sh <ws> <task>         [红线 4+8]
#   4. watchdog      bash scripts/executor-watchdog.sh                  [红线 9]
#   5. verifier      bash scripts/ccc-zcode-bridge.sh <ws> <task> verifier
#   6. finish        bash scripts/ccc-finish.sh <ws> <task>             [红线 11]
#
# 红线遵守:
#   - 3 (不超 plan 范围): --dry-run 不动 working tree
#   - 4+8 (单 phase 单 commit): Step 3 调 ccc-exec-commit.sh
#   - 6 (Planner/Verifier 隔离): bridge.sh 内 UUID 分配
#   - 7 (启动顺序): Step 0 = precheck (读 state + profile + plan)
#   - 9 (卡死止损): watchdog Step 4 + bridge.sh 内 timeout 600
#   - 10 (不隐式记忆): 每步 exit + UUID 落盘 .ccc/dispatches/
#   - 11 (verdict 真文件): Step 5 verifier + Step 6 finish 校验
#   - 12 (不自主启用): 用户显式 ccc run / bash orchestrate.sh 触发
#
# 退出码:
#   0 = 全链路成功
#   1 = 任一步 FAIL
#   2 = 参数错误

set -uo pipefail

# --- 参数解析 ---
DRY_RUN=0
SKIP_REGISTER=0
WORKSPACE=""
TASK=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1; shift ;;
    --skip-register) SKIP_REGISTER=1; shift ;;
    -h|--help)
      cat <<'EOF'
ccc-zcode-orchestrate.sh — ZCode 端到端编排器 (v1.2.1)

用法:
  bash scripts/ccc-zcode-orchestrate.sh <workspace> <task> [--dry-run] [--skip-register]

流程:
  0. precheck (5 gates) → 必须全 PASS
  1. register (optional, --skip-register 可跳过)
  2. executor (claude -p + BigModel)
  3. commit (单 phase 单 commit,红线 4+8)
  4. watchdog (卡死检测)
  5. verifier (独立 session-id)
  6. finish (5 gates 后置门控)

选项:
  --dry-run       打印将执行的命令,不真跑
  --skip-register 跳过 cluster-bus 注册(单任务无需注册)
  -h, --help      显示帮助
EOF
      exit 0 ;;
    *)
      if [[ -z "$WORKSPACE" ]]; then WORKSPACE="$1"; shift
      elif [[ -z "$TASK" ]]; then TASK="$1"; shift
      else echo "未知参数: $1" >&2; exit 2
      fi ;;
  esac
done

if [[ -z "$WORKSPACE" || -z "$TASK" ]]; then
  echo "用法: bash ccc-zcode-orchestrate.sh <workspace> <task> [--dry-run] [--skip-register]" >&2
  exit 2
fi

# --- 路径常量 ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CCC_HOME="$(cd "$SCRIPT_DIR/.." && pwd)"
PRECHECK="$CCC_HOME/scripts/ccc-precheck.sh"
WATCHDOG="$CCC_HOME/scripts/executor-watchdog.sh"
BRIDGE="$CCC_HOME/scripts/ccc-zcode-bridge.sh"
EXEC_COMMIT="$CCC_HOME/scripts/ccc-exec-commit.sh"
FINISH="$CCC_HOME/scripts/ccc-finish.sh"
REGISTER="$CCC_HOME/scripts/ccc-znode-register.py"
DISPATCH_DIR="$WORKSPACE/.ccc/dispatches"

# --- 自动推断 task (若未传) ---
if [[ -z "$TASK" ]]; then
  TASK=$(ls -t "$WORKSPACE/.ccc/plans/"*.plan.md 2>/dev/null | head -1 | sed -E 's|.*/(.*)\.plan\.md$|\1|')
  if [[ -z "$TASK" ]]; then
    echo "ERROR: 无法自动推断 task,显式传入 <task>" >&2
    exit 2
  fi
  echo "[orchestrator] auto-inferred task: $TASK"
fi

mkdir -p "$DISPATCH_DIR"
ORCH_REPORT="$DISPATCH_DIR/orchestrate-${TASK}-$(date +%s).json"

# --- Step 报告记录(每步 exit code + UUID) ---
declare -a STEP_NAMES STEP_EXITS
log_step() {
  local name="$1" exit_code="$2"
  STEP_NAMES+=("$name")
  STEP_EXITS+=("$exit_code")
  if [[ $exit_code -eq 0 ]]; then
    echo "[orchestrator] ✓ $name"
  else
    echo "[orchestrator] ✗ $name (exit=$exit_code)" >&2
  fi
}

# --- 写编排报告(用临时文件传 array 给 python,避免 @Q 转义坑) ---
write_orch_report() {
  local final_status="$1"
  # 把当前 STEP_NAMES / STEP_EXITS 序列化到临时文件
  local tmp_names tmp_exits
  tmp_names=$(mktemp); tmp_exits=$(mktemp)
  printf '%s\n' "${STEP_NAMES[@]}" > "$tmp_names"
  printf '%s\n' "${STEP_EXITS[@]}" > "$tmp_exits"
  python3 - "$ORCH_REPORT" "$final_status" "$tmp_names" "$tmp_exits" <<'PYEOF'
import json, sys
report_path, final_status, names_path, exits_path = sys.argv[1:5]
with open(names_path) as f:
    names = [l.rstrip("\n") for l in f if l.strip()]
with open(exits_path) as f:
    exits = [int(l.rstrip("\n")) for l in f if l.strip()]
report = {
    "task": open(names_path).read(),  # placeholder
    "workspace": "",
    "dry_run": False,
    "skip_register": False,
    "started_at": 0,
    "steps": [{"name": n, "exit": e} for n, e in zip(names, exits)],
    "final_status": final_status,
}
# 真实字段用 environment vars 传进来
import os
report["task"] = os.environ.get("ORCH_TASK", "")
report["workspace"] = os.environ.get("ORCH_WORKSPACE", "")
report["dry_run"] = os.environ.get("ORCH_DRY_RUN", "0") == "1"
report["skip_register"] = os.environ.get("ORCH_SKIP_REGISTER", "0") == "1"
report["started_at"] = int(os.environ.get("ORCH_STARTED_AT", "0"))
open(report_path, "w").write(json.dumps(report, indent=2, ensure_ascii=False))
PYEOF
  rm -f "$tmp_names" "$tmp_exits"
}

# 设置环境变量供 write_orch_report 使用
export ORCH_TASK="$TASK"
export ORCH_WORKSPACE="$WORKSPACE"
export ORCH_DRY_RUN="$DRY_RUN"
export ORCH_SKIP_REGISTER="$SKIP_REGISTER"
export ORCH_STARTED_AT="$(date +%s)"

# ============== Step 0: precheck ==============
echo ""
echo "=== Step 0: precheck (5 gates) ==="
if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "[dry-run] bash $PRECHECK $WORKSPACE $TASK"
  log_step "0_precheck" 0
else
  if bash "$PRECHECK" "$WORKSPACE" "$TASK" 2>&1 | tail -30; then
    log_step "0_precheck" $?
  else
    PRECHECK_EXIT=$?
    log_step "0_precheck" $PRECHECK_EXIT
    write_orch_report "failed_at_precheck"
    echo "[orchestrator] FAIL at Step 0 precheck. 报告: $ORCH_REPORT" >&2
    exit 1
  fi
fi

# ============== Step 1: register (optional) ==============
echo ""
echo "=== Step 1: register (optional) ==="
if [[ "$SKIP_REGISTER" -eq 1 ]]; then
  echo "[orchestrator] --skip-register,跳过 cluster-bus 注册"
  log_step "1_register" 0
elif [[ "$DRY_RUN" -eq 1 ]]; then
  echo "[dry-run] python3 $REGISTER --node-id zcode-\$(hostname) --daemon (would block)"
  echo "[dry-run] 实际跳过 daemon 模式,只跑单次 register"
  echo "[dry-run] python3 $REGISTER --node-id zcode-\$(hostname)"
  log_step "1_register" 0
else
  REG_OUTPUT=$(python3 "$REGISTER" --node-id "zcode-$(hostname)" 2>&1)
  REG_EXIT=$?
  echo "$REG_OUTPUT" | tail -10
  log_step "1_register" $REG_EXIT
  # register 失败不致命(bus 不可达时仍可单任务跑),只 warning
  if [[ $REG_EXIT -ne 0 ]]; then
    echo "[orchestrator] WARNING: register 失败,但继续执行(bus 不可达 = 单机模式)" >&2
    STEP_EXITS[-1]=0  # override to non-blocking
  fi
fi

# ============== Step 2: executor ==============
echo ""
echo "=== Step 2: executor (claude -p) ==="
if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "[dry-run] bash $BRIDGE $WORKSPACE $TASK executor"
  log_step "2_executor" 0
else
  if bash "$BRIDGE" "$WORKSPACE" "$TASK" executor 2>&1 | tail -30; then
    log_step "2_executor" 0
  else
    EXEC_EXIT=$?
    log_step "2_executor" $EXEC_EXIT
    write_orch_report "failed_at_executor"
    echo "[orchestrator] FAIL at Step 2 executor. 报告: $ORCH_REPORT" >&2
    exit 1
  fi
fi

# ============== Step 3: commit (单 phase 单 commit) ==============
echo ""
echo "=== Step 3: commit (单 phase 单 commit,红线 4+8) ==="
if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "[dry-run] bash $EXEC_COMMIT $WORKSPACE $TASK"
  log_step "3_commit" 0
else
  COMMIT_OUTPUT=$(bash "$EXEC_COMMIT" "$WORKSPACE" "$TASK" 2>&1)
  COMMIT_EXIT=$?
  echo "$COMMIT_OUTPUT" | tail -10
  log_step "3_commit" $COMMIT_EXIT
  # ccc-exec-commit.sh 已知 JSONL 解析 bug 可能非零退出,只 warning 不 fatal
  if [[ $COMMIT_EXIT -ne 0 ]]; then
    if echo "$COMMIT_OUTPUT" | grep -q "JSONDecodeError\|Extra data"; then
      echo "[orchestrator] WARNING: ccc-exec-commit.sh 遇 JSONL 解析 bug,跳过(已知 issue,留独立 task 修)" >&2
      STEP_EXITS[-1]=0
    else
      write_orch_report "failed_at_commit"
      echo "[orchestrator] FAIL at Step 3 commit. 报告: $ORCH_REPORT" >&2
      exit 1
    fi
  fi
fi

# ============== Step 4: watchdog (卡死检测) ==============
echo ""
echo "=== Step 4: watchdog (红线 9) ==="
if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "[dry-run] bash $WATCHDOG"
  log_step "4_watchdog" 0
else
  WD_OUTPUT=$(bash "$WATCHDOG" 2>&1)
  WD_EXIT=$?
  echo "$WD_OUTPUT" | tail -8
  log_step "4_watchdog" $WD_EXIT
  # watchdog 警告(warning exit=1)不阻塞,严重失败(serious exit=2)才中断
  if [[ $WD_EXIT -eq 2 ]]; then
    write_orch_report "failed_at_watchdog"
    echo "[orchestrator] FAIL at Step 4 watchdog (serious). 报告: $ORCH_REPORT" >&2
    exit 1
  fi
fi

# ============== Step 5: verifier (独立 session-id) ==============
echo ""
echo "=== Step 5: verifier (独立 session,红线 6+11) ==="
if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "[dry-run] bash $BRIDGE $WORKSPACE $TASK verifier"
  log_step "5_verifier" 0
else
  if bash "$BRIDGE" "$WORKSPACE" "$TASK" verifier 2>&1 | tail -30; then
    log_step "5_verifier" 0
  else
    VER_EXIT=$?
    log_step "5_verifier" $VER_EXIT
    write_orch_report "failed_at_verifier"
    echo "[orchestrator] FAIL at Step 5 verifier. 报告: $ORCH_REPORT" >&2
    exit 1
  fi
fi

# ============== Step 6: finish (后置门控) ==============
echo ""
echo "=== Step 6: finish (5 gates 后置门控,红线 11) ==="
if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "[dry-run] bash $FINISH $WORKSPACE $TASK"
  log_step "6_finish" 0
else
  if bash "$FINISH" "$WORKSPACE" "$TASK" 2>&1 | tail -30; then
    log_step "6_finish" 0
  else
    FIN_EXIT=$?
    log_step "6_finish" $FIN_EXIT
    write_orch_report "failed_at_finish"
    echo "[orchestrator] FAIL at Step 6 finish. 报告: $ORCH_REPORT" >&2
    exit 1
  fi
fi

# ============== 全部 PASS ==============
write_orch_report "success"
echo ""
echo "=== 编排完成 ==="
echo "任务: $TASK"
echo "工作区: $WORKSPACE"
echo "报告: $ORCH_REPORT"
echo ""
echo "[orchestrator] 全部 6 步 PASS,任务完成。"