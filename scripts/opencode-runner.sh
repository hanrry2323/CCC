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
EXEC_LOG="${RESULT_DIR}/${TASK_ID}.exec.log"

PID_DIR="${ROOT_DIR}/.ccc/pids"
mkdir -p "$PID_DIR"

# v0.31 (C1): 墙钟断路器 — 最大 wall-clock 时间（秒）
# 超时后 SIGTERM → 30s 后 SIGKILL（防 SIGSTOP/SIGUSR 类不可杀状态）
# 不读取 Config 类（无 Python 依赖），直接从环境变量取
MAX_WALLCLOCK="${CCC_MAX_WALLCLOCK:-7200}"

PY_PID=""
BK_PID=""

_reap_workspace_opencode() {
  # Runner 退出后强制收尸同仓 opencode（防 node 孙子占同仓互斥槽）
  python3 - <<'PY' "$CCC_HOME" "$ROOT_DIR" 2>/dev/null || true
import sys
from pathlib import Path
sys.path.insert(0, str(Path(sys.argv[1]) / "scripts"))
from _opencode_reap import reap_opencode_workspace
killed = reap_opencode_workspace(Path(sys.argv[2]), max_age_sec=0, grace_sec=0.2)
if killed:
    print(f"runner-reap: {killed}", file=sys.stderr)
PY
}

_cleanup() {
  # 杀 python/exec 进程组 + 同仓残留 opencode
  if [ -n "${PY_PID}" ]; then
    kill -TERM "-${PY_PID}" 2>/dev/null || kill -TERM "${PY_PID}" 2>/dev/null || true
    sleep 1
    kill -KILL "-${PY_PID}" 2>/dev/null || kill -KILL "${PY_PID}" 2>/dev/null || true
  fi
  if [ -n "${BK_PID}" ]; then
    kill "${BK_PID}" 2>/dev/null || true
  fi
  _reap_workspace_opencode
}
trap _cleanup EXIT

# 纯 JSON → result.json；stdout/stderr → exec.log（产线提效 P2）
# --skip-watchdog: 引擎已管理并发，多个 opencode-exec.py 的 watchdog
# 会相互误杀（一个 task 清理 pid 文件后，另一个 task 的 watchdog 将其
# 视为孤儿进程并 SIGTERM，导致 rc=241）。Lesson 44 实锤。
# 墙钟断路器 v0.31: 用 timeout(1) 封装，-k 30 确保 SIGKILL 兜底
# mac 常无 timeout → 用 setsid + bash 墙钟，退出时 killpg
EXEC_ARGS=(--skip-watchdog --result-file "$RESULT_FILE" "$@")

if command -v timeout &>/dev/null; then
  # GNU timeout 在新 session 里跑，便于 EXIT trap 收尸
  if command -v setsid &>/dev/null; then
    setsid timeout -k 30 "$MAX_WALLCLOCK" \
      python3 "${CCC_HOME}/scripts/opencode-exec.py" "${EXEC_ARGS[@]}" > "$EXEC_LOG" 2>&1 &
  else
    timeout -k 30 "$MAX_WALLCLOCK" \
      python3 "${CCC_HOME}/scripts/opencode-exec.py" "${EXEC_ARGS[@]}" > "$EXEC_LOG" 2>&1 &
  fi
  PY_PID=$!
  wait "$PY_PID"
  RC=$?
  PY_PID=""
  if [ $RC -eq 124 ]; then
    cat > "$RESULT_FILE" <<WALLCLOCK_EOF
{"error": "wallclock timeout after ${MAX_WALLCLOCK}s", "phase": "${TASK_ID}", "rc": 124}
WALLCLOCK_EOF
  fi
else
  # fallback: timeout(1) 不存在时的纯 bash 兜底（macOS 常见）
  if command -v setsid &>/dev/null; then
    setsid python3 "${CCC_HOME}/scripts/opencode-exec.py" "${EXEC_ARGS[@]}" > "$EXEC_LOG" 2>&1 &
  else
    python3 "${CCC_HOME}/scripts/opencode-exec.py" "${EXEC_ARGS[@]}" > "$EXEC_LOG" 2>&1 &
  fi
  PY_PID=$!
  (
    sleep "$MAX_WALLCLOCK"
    # 优先杀进程组（setsid 时 pgid==pid）
    kill -TERM "-${PY_PID}" 2>/dev/null || kill -TERM "${PY_PID}" 2>/dev/null
    sleep 10
    kill -KILL "-${PY_PID}" 2>/dev/null || kill -KILL "${PY_PID}" 2>/dev/null
  ) &
  BK_PID=$!
  wait "$PY_PID"
  RC=$?
  kill "${BK_PID}" 2>/dev/null || true
  wait "${BK_PID}" 2>/dev/null || true
  BK_PID=""
  PY_PID=""
fi

# 若 exec 未写出 result（异常退出），尝试从 exec.log 末尾抽 JSON
if [ ! -s "$RESULT_FILE" ] && [ -s "$EXEC_LOG" ]; then
  python3 - <<'PY' "$CCC_HOME" "$EXEC_LOG" "$RESULT_FILE" 2>/dev/null || true
import sys
from pathlib import Path
sys.path.insert(0, str(Path(sys.argv[1]) / "scripts"))
from _result_json import extract_json_object
import json
raw = Path(sys.argv[2]).read_text(encoding="utf-8", errors="replace")
obj = extract_json_object(raw)
if obj:
    Path(sys.argv[3]).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n")
PY
fi

# 先收尸同仓 opencode，再写 .done（避免 engine 见 done 立刻启下一卡时撞残留）
trap - EXIT
_reap_workspace_opencode
echo "$RC" > "${PID_DIR}/${TASK_ID}.exitcode"
echo "done" > "${PID_DIR}/${TASK_ID}.done"
exit $RC
