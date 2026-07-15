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

# v0.31 (C1): 墙钟断路器 — 最大 wall-clock 时间（秒）
# 超时后 SIGTERM → 30s 后 SIGKILL（防 SIGSTOP/SIGUSR 类不可杀状态）
# 不读取 Config 类（无 Python 依赖），直接从环境变量取
MAX_WALLCLOCK="${CCC_MAX_WALLCLOCK:-7200}"

# 跑 opencode-exec，输出写文件
# --skip-watchdog: 引擎已管理并发，多个 opencode-exec.py 的 watchdog
# 会相互误杀（一个 task 清理 pid 文件后，另一个 task 的 watchdog 将其
# 视为孤儿进程并 SIGTERM，导致 rc=241）。Lesson 44 实锤。
# 墙钟断路器 v0.31: 用 timeout(1) 封装，-k 30 确保 SIGKILL 兜底
if command -v timeout &>/dev/null; then
  timeout -k 30 "$MAX_WALLCLOCK" \
    python3 "${CCC_HOME}/scripts/opencode-exec.py" --skip-watchdog "$@" > "$RESULT_FILE" 2>&1
  RC=$?
  if [ $RC -eq 124 ]; then
    cat > "$RESULT_FILE" <<WALLCLOCK_EOF
{"error": "wallclock timeout after ${MAX_WALLCLOCK}s", "phase": "${TASK_ID}", "rc": 124}
WALLCLOCK_EOF
  fi
else
  # fallback: timeout(1) 不存在时的纯 bash 兜底
  python3 "${CCC_HOME}/scripts/opencode-exec.py" --skip-watchdog "$@" > "$RESULT_FILE" 2>&1 &
  PY_PID=$!
  (sleep "$MAX_WALLCLOCK" && kill -TERM "$PY_PID" 2>/dev/null && sleep 10 && kill -KILL "$PY_PID" 2>/dev/null) &
  BK_PID=$!
  wait "$PY_PID"
  RC=$?
  kill "$BK_PID" 2>/dev/null
fi

# 写完成标记到 workspace（供 engine 检测）
echo "$RC" > "${PID_DIR}/${TASK_ID}.exitcode"
echo "done" > "${PID_DIR}/${TASK_ID}.done"
exit $RC
