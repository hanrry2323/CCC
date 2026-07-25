#!/bin/bash
# ccc-reviewer-bg.sh — reviewer LLM 长 session 包装器(v0.62.0 阶段 1)
#
# 替代 ccc-product-session 的 reviewer 版本:
#   - 启动:`claude --bg "<verdict_prompt>"` 走 background session
#   - 等 verdict:轮询 <task>.reviewer.done 标记文件(20s × N)
#   - 失败回环:`claude --resume <session_id> -p "<next_prompt>"`
#   - 收尾:写 <task>.reviewer.{session_id,done,timeout,out,exitcode}
#
# 用法:
#   bash ccc-reviewer-bg.sh <task_id> <phase_id> <workspace> \
#       <model> <prompt_file> <out_dir> [--resume <session_id>] [--hard-kill-after <sec>]
#
# 输出文件(<out_dir>):
#   <task>.reviewer.session_id    -- claude session_id(短 sha)
#   <task>.reviewer.out           -- 启动 stdout + 后续 verdict 内容
#   <task>.reviewer.done          -- verdict 出来后 touch,内容是 verdict JSON
#   <task>.reviewer.timeout       -- 超时未产出 touch
#   <task>.reviewer.exitcode      -- 进程最终退出码

set -uo pipefail

CCC_HOME="${CCC_HOME:-$HOME/program/CCC}"

# 入参
TASK_ID="${1:?usage: ccc-reviewer-bg.sh <task_id> <phase_id> <workspace> <model> <prompt_file> <out_dir> [--resume <session_id>]}"
PHASE_ID="${2:?missing phase_id}"
WORKSPACE="${3:?missing workspace}"
MODEL="${4:?missing model}"
PROMPT_FILE="${5:?missing prompt_file}"
OUT_DIR="${6:?missing out_dir}"

# 选参
RESUME_SESSION_ID=""
HARD_KILL_AFTER=1800  # 30min 默认
shift 6
while [[ $# -gt 0 ]]; do
  case "$1" in
    --resume)        shift; RESUME_SESSION_ID="$1" ;;
    --hard-kill-after) shift; HARD_KILL_AFTER="$1" ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
  shift
done

mkdir -p "$OUT_DIR"
SESSION_FILE="$OUT_DIR/${TASK_ID}.reviewer.session_id"
OUT_FILE="$OUT_DIR/${TASK_ID}.reviewer.out"
DONE_FILE="$OUT_DIR/${TASK_ID}.reviewer.done"
TIMEOUT_FILE="$OUT_DIR/${TASK_ID}.reviewer.timeout"
EXIT_FILE="$OUT_DIR/${TASK_ID}.reviewer.exitcode"

_log() { echo "[$(date +%H:%M:%S)] [reviewer-bg] $*" >&2; }

# ── 1. 启动 claude --bg(resume 或 新建)─────────────────
if [[ -n "$RESUME_SESSION_ID" ]]; then
  _log "resume session=$RESUME_SESSION_ID task=$TASK_ID"
  # claude --resume 必接 prompt;--print 不行(--bg 互斥);
  # 续对话方式:用 "continue: <next-prompt>" 让 claude 接着审
  PROMPT_BODY="$(cat "$PROMPT_FILE")"
  {
    echo "----- claude --resume at $(date -Iseconds) -----"
    echo "$PROMPT_BODY"
  } >> "$OUT_FILE"
  nohup /Users/fan/.npm-global/bin/claude --resume "$RESUME_SESSION_ID" \
      -p "$PROMPT_BODY" --model "$MODEL" \
    >> "$OUT_FILE" 2>&1 &
  SCRIPT_PID=$!
else
  _log "launch bg task=$TASK_ID model=$MODEL"
  PROMPT_BODY="$(cat "$PROMPT_FILE")"
  {
    echo "----- claude --bg at $(date -Iseconds) -----"
    echo "$PROMPT_BODY"
  } >> "$OUT_FILE"
  nohup /Users/fan/.npm-global/bin/claude --bg "$PROMPT_BODY" \
      --model "$MODEL" \
    >> "$OUT_FILE" 2>&1 &
  SCRIPT_PID=$!
fi

_log "  spawned wrapper pid=$SCRIPT_PID"

# ── 2. 轮询 session_id(短 ID)+ 等 verdict 文件 ──────
MAX_WAIT=600  # 默认 10 分钟
DEADLINE=$((SECONDS + MAX_WAIT))
LAST_HEARTBEAT=0

while (( SECONDS < DEADLINE )); do
  # 等 session_id 文件出现(<task>.reviewer.session_id)
  if [[ -s "$SESSION_FILE" ]] || /Users/fan/.npm-global/bin/claude agents --json 2>/dev/null | grep -q "$TASK_ID"; then
    # 解析短 ID:从 agents --json 拿最近且 task 名匹配
    SHORT_ID=$(
      /Users/fan/.npm-global/bin/claude agents --json 2>/dev/null \
        | python3 -c "
import json, sys, os
try:
  d = json.load(sys.stdin)
except: sys.exit(0)
for s in d:
  cwd = s.get('cwd','') or s.get('projectPath','')
  # 用 task id 匹配 workdir 中的 task 文件名作为粗筛
  if '$WORKSPACE' in cwd or '$TASK_ID' in str(s):
    sid = s.get('sessionId') or s.get('id') or ''
    if sid: print(sid[:8]); sys.exit(0)
" 2>/dev/null | head -1
    )
    if [[ -n "$SHORT_ID" ]]; then
      echo "$SHORT_ID" > "$SESSION_FILE"
      _log "  session short_id=$SHORT_ID"
    fi
  fi

  # 检查 verdict 标记(由 ver 提取函数在 done 时写)
  if [[ -s "$DONE_FILE" ]]; then
    _log "  verdict done"
    break
  fi
  sleep 5
done

# ── 3. 超时 fallback ──────────────────────────────────
if [[ ! -s "$DONE_FILE" ]]; then
  _log "  TIMEOUT (>${MAX_WAIT}s) — 写 timeout 标记"
  echo "timeout after ${MAX_WAIT}s" > "$TIMEOUT_FILE"
  # 不立刻 kill 进程 — 留给 Engine 下个 tick 用 --resume 续
  if [[ -n "${RESUME_SESSION_ID:-}" ]] || [[ -s "$SESSION_FILE" ]]; then
    _log "  session_id 保留给 Engine resume"
  fi
fi

# ── 4. 写 exitcode(等进程自然退出,或 hard-kill)────
if kill -0 "$SCRIPT_PID" 2>/dev/null; then
  _log "  waiting process $SCRIPT_PID up to ${HARD_KILL_AFTER}s"
  for _ in $(seq 1 "$HARD_KILL_AFTER"); do
    kill -0 "$SCRIPT_PID" 2>/dev/null || break
    sleep 1
  done
  if kill -0 "$SCRIPT_PID" 2>/dev/null; then
    _log "  hard-kill process $SCRIPT_PID"
    kill -TERM "$SCRIPT_PID" 2>/dev/null
    sleep 2
    kill -KILL "$SCRIPT_PID" 2>/dev/null
  fi
fi
wait "$SCRIPT_PID" 2>/dev/null
EXIT=$?
echo "$EXIT" > "$EXIT_FILE"

_log "  exit=$EXIT done file $(test -s "$DONE_FILE" && echo yes || echo no)"
exit 0
