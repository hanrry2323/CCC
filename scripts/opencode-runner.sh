#!/bin/bash
# opencode-runner.sh — 后台运行 opencode-exec.py，结果持久化
# 被 ccc-board.py dev_role() / engine 通过 Popen 调用
# Usage: opencode-runner.sh <task_id> <ccc_home> <workspace> [opencode-exec args...]
set -uo pipefail

TASK_ID="$1"
CCC_HOME="$2"
ROOT_DIR="$3"
shift 3

RESULT_DIR="${ROOT_DIR}/.ccc/reports"
mkdir -p "$RESULT_DIR"
RESULT_FILE="${RESULT_DIR}/${TASK_ID}.result.json"

PID_DIR="${ROOT_DIR}/.ccc/pids"
mkdir -p "$PID_DIR"

# 跑 opencode-exec，输出写文件
python3 "${CCC_HOME}/scripts/opencode-exec.py" "$@" > "$RESULT_FILE" 2>&1
RC=$?

# 写完成标记到 workspace（供 engine 检测）
echo "$RC" > "${PID_DIR}/${TASK_ID}.exitcode"
echo "done" > "${PID_DIR}/${TASK_ID}.done"
exit $RC
