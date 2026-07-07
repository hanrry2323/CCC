#!/bin/bash
# ccc-exec-launcher.sh — OpenCode 执行器启动入口（v0.8 重构）
#
# 职责：单 phase 启动入口，串联 watchdog → 钩子 → opencode-exec
#   1. 跑 opencode-watchdog.sh（红线 X3：启动前必清残留）
#   2. 跑 pre-exec 钩子（用户自定义）
#   3. 调 opencode-exec.py 执行 phase
#   4. 跑 post-exec 钩子（commit、状态写回）
#   5. 失败时跑 on-error 钩子 + 桌面通知
#
# 用法：
#   ccc-exec-launcher.sh <phase-id> <prompt-file> [--timeout 1800] [--cwd <dir>]
#
# 退出码：
#   0  = phase 成功
#   1  = watchdog 失败（残留进程未清）
#   2  = pre-exec 钩子阻断
#   3  = opencode-exec 调用失败
#   4  = opencode exec 本身非零退出
#   5  = post-exec 钩子阻断
#   10 = on-error 钩子失败（仅日志，不阻断）
#
# v0.8 配套：从 tmux + claude 改为直接 opencode CLI

set -uo pipefail

PHASE_ID="${1:?usage: ccc-exec-launcher.sh <phase-id> <prompt-file> [--timeout 1800] [--cwd <dir>]}"
PROMPT_FILE="${2:?usage: ccc-exec-launcher.sh <phase-id> <prompt-file> [--timeout 1800] [--cwd <dir>]}"
shift 2

TIMEOUT=1800
CWD=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --timeout) TIMEOUT="$2"; shift 2 ;;
    --cwd)     CWD="$2"; shift 2 ;;
    *) echo "未知参数: $1" >&2; exit 2 ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="${HOME}/.ccc/logs"
mkdir -p "$LOG_DIR"
# 日志按 phase_id 隔离（不是真 bug，验证过）
# 多 phase 并发时各自 LOG_FILE 不同，不交错
LOG_FILE="$LOG_DIR/launcher-${PHASE_ID}-$(date +%s).log"

log() { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG_FILE"; }

log "=== launcher start: phase=$PHASE_ID prompt=$PROMPT_FILE timeout=${TIMEOUT}s ==="

# --- Step 1: 残留扫描（红线 X3）---
log "Step 1: opencode-watchdog"
if ! bash "$SCRIPT_DIR/opencode-watchdog.sh" >> "$LOG_FILE" 2>&1; then
  WD_RC=$?
  if [[ $WD_RC -eq 3 ]]; then
    log "watchdog 已自清（exit 3），继续"
  else
    log "❌ watchdog FAIL (exit=$WD_RC)，残留进程未清理，阻断"
    bash "$SCRIPT_DIR/ccc-notify.sh" L2 "watchdog FAIL: $PHASE_ID" "phase=$PHASE_ID 启动前残留扫描失败" >/dev/null 2>&1
    exit 1
  fi
fi

# --- Step 2: pre-exec 钩子 ---
log "Step 2: pre-exec hook"
if ! bash "$SCRIPT_DIR/ccc-hook.sh" pre-exec "$PHASE_ID" "$PROMPT_FILE" >> "$LOG_FILE" 2>&1; then
  log "❌ pre-exec 钩子阻断"
  exit 2
fi

# --- Step 3: opencode-exec ---
log "Step 3: opencode-exec"
EXEC_ARGS=(--phase "$PHASE_ID" --prompt "$PROMPT_FILE" --timeout "$TIMEOUT")
[[ -n "$CWD" ]] && EXEC_ARGS+=(--cwd "$CWD")

set +e
python3 "$SCRIPT_DIR/opencode-exec.py" "${EXEC_ARGS[@]}" > "$LOG_DIR/opencode-${PHASE_ID}.json" 2>> "$LOG_FILE"
EXEC_RC=$?
set -e
log "opencode-exec exit=$EXEC_RC"

# --- Step 4: 失败处理（on-error 钩子 + 通知）---
if [[ $EXEC_RC -ne 0 ]]; then
  log "Step 4a: on-error hook + L2 通知"
  bash "$SCRIPT_DIR/ccc-hook.sh" on-error "$PHASE_ID" "$EXEC_RC" >> "$LOG_FILE" 2>&1 || true
  bash "$SCRIPT_DIR/ccc-notify.sh" L2 "opencode FAIL: $PHASE_ID" "exit=$EXEC_RC log=$LOG_FILE" >/dev/null 2>&1 || true
  exit $(( EXEC_RC == 124 ? 4 : 3 ))
fi

# --- Step 5: post-exec 钩子 ---
log "Step 5: post-exec hook"
if ! bash "$SCRIPT_DIR/ccc-hook.sh" post-exec "$PHASE_ID" >> "$LOG_FILE" 2>&1; then
  log "❌ post-exec 钩子阻断"
  exit 5
fi

log "✅ phase $PHASE_ID 完成"
exit 0
