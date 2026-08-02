#!/bin/bash
# ccc-reviewer-bg.sh — reviewer LLM 长 session 包装器(v0.62.0 阶段 1, P0-B 修复)
#
# 用法(reviewer.py 调):
#   bash ccc-reviewer-bg.sh \
#     --task-id <id> --workspace <ws> \
#     --model <m> --prompt-file <pf> --out-dir <od> \
#     --claude-bin <path> --marker-dir <md> \
#     [--resume <session-id>] [--max-wait <sec>] [--hard-kill-after <sec>]
#
# 输出(<out-dir>):
#   <task>.reviewer.session_id   -- 完整 claude session_id(v0.62.0 P1-6 不再截 8 字符)
#   <task>.reviewer.out          -- stdout
#   <task>.reviewer.timeout      -- 超时未产出
#   <task>.reviewer.exitcode     -- 进程最终退出码
#
# v0.62.0 修复:
# - P0-B:硬编码 /Users/fan/.npm-global/bin/claude → 用 --claude-bin 参数传入
# - P0-D:解析 stdout 拿 session_id,不再反查 agents --json(避免串 session)
# - P0-E:不做粗筛(同 workspace 多个 task 会串)— reviewer.py 写 session_id 到文件
# - P1-5:不走 bash 字符串插值 python(改用 env 传值)
# - P1-6:不截 session_id 短 sha
# - verdict 提取(写 done 标记)移交给 reviewer.py

set -uo pipefail

# ── 1. 入参解析 ──────────────────────────────
TASK_ID=""
WORKSPACE=""
MODEL=""
PROMPT_FILE=""
OUT_DIR=""
CLAUDE_BIN=""
MarkerDir=""  # 放 .session_id/.out 文件的目录(由 reviewer.py 传入)
RESUME_SESSION_ID=""
MAX_WAIT=600
HARD_KILL_AFTER=1800

while [[ $# -gt 0 ]]; do
  case "$1" in
    --task-id)        shift; TASK_ID="$1" ;;
    --workspace)      shift; WORKSPACE="$1" ;;
    --model)          shift; MODEL="$1" ;;
    --prompt-file)    shift; PROMPT_FILE="$1" ;;
    --out-dir)        shift; OUT_DIR="$1" ;;
    --claude-bin)     shift; CLAUDE_BIN="$1" ;;
    --marker-dir)     shift; MarkerDir="$1" ;;
    --resume)         shift; RESUME_SESSION_ID="$1" ;;
    --max-wait)       shift; MAX_WAIT="$1" ;;
    --hard-kill-after) shift; HARD_KILL_AFTER="$1" ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
  shift
done

# 必填校验
for v in TASK_ID PROMPT_FILE OUT_DIR CLAUDE_BIN; do
  [[ -n "$v" ]] || { echo "missing required arg" >&2; exit 2; }
done

# 防御:CLAUDE_BIN 必须存在且可执行(P0-B)
if [[ ! -x "$CLAUDE_BIN" ]]; then
  echo "CLAUDE_BIN not executable: $CLAUDE_BIN" >&2
  exit 2
fi

if [[ -z "$MarkerDir" ]]; then
  MarkerDir="$OUT_DIR"
fi

SESSION_FILE="$MarkerDir/${TASK_ID}.reviewer.session_id"
OUT_FILE="$MarkerDir/${TASK_ID}.reviewer.out"
DONE_FILE="$MarkerDir/${TASK_ID}.reviewer.done"
TIMEOUT_FILE="$MarkerDir/${TASK_ID}.reviewer.timeout"
EXIT_FILE="$MarkerDir/${TASK_ID}.reviewer.exitcode"

mkdir -p "$MarkerDir"

_log() { echo "[$(date +%H:%M:%S)] [reviewer-bg] $*" >&2; }

# ── 2. 启动 claude --bg(resume 或 新建)─────────────────
# v0.62.0(P0-D/P0-E):从 stdout 解析 session_id 写入文件
# (不再用 agents --json 反查,避免多 task 串 session)
PROMPT_BODY="$(cat "$PROMPT_FILE")"
if [[ -n "$RESUME_SESSION_ID" ]]; then
  _log "resume session=$RESUME_SESSION_ID task=$TASK_ID"
  {
    echo "----- claude --resume at $(date -Iseconds) -----"
    echo "$PROMPT_BODY"
  } >> "$OUT_FILE"
  "$CLAUDE_BIN" --resume "$RESUME_SESSION_ID" \
    -p "$PROMPT_BODY" --model "$MODEL" \
    >> "$OUT_FILE" 2>&1 &
  SCRIPT_PID=$!
else
  _log "launch bg task=$TASK_ID model=$MODEL"
  {
    echo "----- claude --bg at $(date -Iseconds) -----"
    echo "$PROMPT_BODY"
  } >> "$OUT_FILE"
  # v0.62.0(P0-E):session_id 由 stdout 解析;--output-format json 让 claude 输出 JSON
  "$CLAUDE_BIN" --bg "$PROMPT_BODY" \
    --model "$MODEL" \
    --output-format json \
    >> "$OUT_FILE" 2>&1 &
  SCRIPT_PID=$!
fi

_log "  spawned wrapper pid=$SCRIPT_PID"

# ── 3. 解析 stdout 拿 session_id(写入文件)────────
# v0.62.0(P0-D):从 $OUT_FILE 末尾(追加方式)提取 claude --bg 输出的 session_id
# claude --bg 输出 JSON:{"sessionId": "..."}
# 解析后立即写入 $SESSION_FILE(reviewer.py 也从此文件读)
_extract_session_id() {
  if [[ -s "$SESSION_FILE" ]]; then
    return  # 已写过
  fi
  # 从 OUT_FILE 找最后一个 JSON 块,提 sessionId
  if [[ -s "$OUT_FILE" ]]; then
    local sid
    sid=$(grep -oE '"sessionId"[[:space:]]*:[[:space:]]*"[a-f0-9-]{8,}"' "$OUT_FILE" | tail -1 \
        | grep -oE '[a-f0-9-]{8,}')
    if [[ -n "$sid" ]]; then
      echo "$sid" > "$SESSION_FILE"
      _log "  session_id=$sid(v0.62.0 P0-D 解析 stdout 写入)"
      return
    fi
  fi
}

# ── 4. 轮询等 verdict 提取(reviewer.py 写 done 标记)──
DEADLINE=$((SECONDS + MAX_WAIT))
while (( SECONDS < DEADLINE )); do
  # 解析 session_id 一次(若还没写)
  _extract_session_id
  # verdict 提取在 reviewer.py 进程(P0-C 修复:不依赖 shell 解析)
  if [[ -s "$DONE_FILE" ]]; then
    _log "  verdict done"
    break
  fi
  sleep 5
done

# ── 5. 超时 fallback ─────────────────────────────
if [[ ! -s "$DONE_FILE" ]]; then
  _log "  TIMEOUT (>${MAX_WAIT}s) — 写 timeout 标记"
  echo "timeout after ${MAX_WAIT}s" > "$TIMEOUT_FILE"
  if [[ -s "$SESSION_FILE" ]]; then
    _log "  session_id 保留给 Engine resume"
  fi
fi

# ── 6. 写 exitcode(等进程自然退出)────────────────
# v0.62.0(P0-D):SCRIPT_PID 是 wrapper 进程(--bg 立即 fork 后退),
# 不是真 claude session. wrapper 死后,SCRIPT_PID 已死;真 bg session
# 进程不在我们管。Engine 通过 register_bg_session 跟踪 session_id,
# 通过 verify_bg_session 调 ps -o state= 探活。
if kill -0 "$SCRIPT_PID" 2>/dev/null; then
  _log "  waiting wrapper $SCRIPT_PID up to ${HARD_KILL_AFTER}s"
  for _ in $(seq 1 "$HARD_KILL_AFTER"); do
    kill -0 "$SCRIPT_PID" 2>/dev/null || break
    sleep 1
  done
  if kill -0 "$SCRIPT_PID" 2>/dev/null; then
    _log "  hard-kill wrapper $SCRIPT_PID"
    kill -TERM "$SCRIPT_PID" 2>/dev/null
    sleep 2
    kill -KILL "$SCRIPT_PID" 2>/dev/null
  fi
fi
wait "$SCRIPT_PID" 2>/dev/null
EXIT=$?
echo "$EXIT" > "$EXIT_FILE"

# 最后一次解析 session_id(可能后台启动时还没立即写完)
_extract_session_id

_log "  exit=$EXIT done file $(test -s "$DONE_FILE" && echo yes || echo no)"
exit 0
