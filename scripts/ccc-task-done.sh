#!/usr/bin/env bash
# ccc-task-done.sh — CCC v0.6 单 phase 完成回调
#
# 目的：
#   调度器循环里的"单 phase 完成"步骤。跑 ccc-finish.sh 验收 +
#   可选 commit + 更新 state.md + 解锁下一任务。
#
# 用法：
#   bash scripts/ccc-task-done.sh <workspace> <task-id> [--skip-commit]
#
# 退出码：
#   0 = 成功
#   1 = finish.sh 失败
#   2 = 参数错误 / report 缺失
#
# 触发：v0.6 scheduler 循环内嵌步骤。

set -euo pipefail

usage() {
  cat <<EOF
用法: bash $(basename "$0") <workspace> <task-id> [--skip-commit]

参数:
  <workspace>    CCC 项目根(必须是绝对路径)
  <task-id>      任务 ID(对应 .ccc/plans/<task-id>.plan.md)
  --skip-commit  跳过 git commit(用于调试或外部已提交场景)

流程:
  1. 跑 bash scripts/ccc-finish.sh <workspace> <task-id>
  2. 若 finish 退出 0 → 该 phase 已 commit(ccc-exec-commit.sh 处理)
  3. 更新 .ccc/state.md 任务状态(由 finish.sh 负责)
  4. 解锁 queue 里下一 task
EOF
}

# ── 参数解析 ──────────────────────────────────────────────────
SKIP_COMMIT=0
if [[ $# -lt 2 ]]; then
  echo "ERROR: missing required arguments" >&2
  usage >&2
  exit 2
fi

WORKSPACE="$1"
TASK_ID="$2"
shift 2

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-commit) SKIP_COMMIT=1; shift ;;
    -h|--help)     usage; exit 0 ;;
    *)
      echo "ERROR: unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

# ── 路径 ──────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── 校验 ──────────────────────────────────────────────────────
if [[ ! -d "$WORKSPACE" ]]; then
  echo "ERROR: workspace not found: $WORKSPACE" >&2
  exit 2
fi

if [[ ! -d "$WORKSPACE/.ccc" ]]; then
  echo "ERROR: workspace missing .ccc/ directory: $WORKSPACE" >&2
  exit 2
fi

REPORT="$WORKSPACE/.ccc/reports/${TASK_ID}.report.md"
if [[ ! -s "$REPORT" ]]; then
  echo "ERROR: report not found: $REPORT" >&2
  exit 2
fi

# ── 跑 ccc-finish.sh ──────────────────────────────────────────
echo "[ccc-task-done] workspace=$WORKSPACE task=$TASK_ID skip_commit=$SKIP_COMMIT"

if ! bash "$SCRIPT_DIR/ccc-finish.sh" "$WORKSPACE" "$TASK_ID"; then
  echo "[ccc-task-done][ERROR] ccc-finish.sh failed for $TASK_ID" >&2
  exit 1
fi

if (( SKIP_COMMIT == 0 )); then
  cd "$WORKSPACE"
  if [[ -n "$(git status --short 2>/dev/null || true)" ]]; then
    echo "[ccc-task-done] working tree has changes, attempting commit via ccc-exec-commit"
    if ! bash "$SCRIPT_DIR/ccc-exec-commit.sh" "$WORKSPACE" "$TASK_ID"; then
      echo "[ccc-task-done][WARN] ccc-exec-commit.sh failed (may be idempotent on empty/no-op)" >&2
    fi
  else
    echo "[ccc-task-done] working tree clean, no commit needed"
  fi
fi

echo "[ccc-task-done] task=$TASK_ID OK"
exit 0
