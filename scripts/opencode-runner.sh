#!/bin/bash
# opencode-runner.sh — 后台运行 opencode-exec.py，结果持久化
# 被 ccc-board.py dev_role() 通过 Popen 调用
set -uo pipefail

TASK_ID="$1"
CCC_HOME="$2"
shift 2

RESULT_FILE="${CCC_HOME}/.ccc/reports/${TASK_ID}.result.json"
# 跑 opencode-exec，输出写文件
python3 "${CCC_HOME}/scripts/opencode-exec.py" "$@" > "$RESULT_FILE" 2>&1
RC=$?

# 写完成标记
echo "$RC" > "${CCC_HOME}/.ccc/pids/${TASK_ID}.exitcode"
echo "done" > "${CCC_HOME}/.ccc/pids/${TASK_ID}.done"
exit $RC
