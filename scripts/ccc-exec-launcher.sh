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
#   6  = router 健康检查失败（127.0.0.1:4000 无可用回退 upstream）
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

CWD="${CWD:-$PWD}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="${HOME}/.ccc/logs"
mkdir -p "$LOG_DIR"
# 日志按 phase_id 隔离（不是真 bug，验证过）
# 多 phase 并发时各自 LOG_FILE 不同，不交错
LOG_FILE="$LOG_DIR/launcher-${PHASE_ID}-$(date +%s).log"

log() { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG_FILE"; }

log "=== launcher start: phase=$PHASE_ID prompt=$PROMPT_FILE timeout=${TIMEOUT}s ==="

ROUTER_HEALTH_URL="${ROUTER_HEALTH_URL:-http://127.0.0.1:4000/health}"
UPSTREAMS_FILE="${UPSTREAMS_FILE:-${HOME}/program/ai-loop-router/upstreams.json}"

# ── router 健康检查（单品）──
# 返回 0=健康，1=不可用
check_upstream_health() {
  local url="${1:-$ROUTER_HEALTH_URL}"
  local code
  code="$(curl -sS --connect-timeout 5 --max-time 10 -o /dev/null -w '%{http_code}' "$url" 2>>"$LOG_FILE" || echo "000")"
  [[ "$code" =~ ^2[0-9][0-9]$ ]] && return 0
  return 1
}

# ── 从 upstreams.json 选首个可用回退 upstream ──
# 输出 JSON: {"base_url":"...","api_key":"..."} 或空字符串
# 只选 enabled=true 且 tier_priority 最小的
_read_upstreams_fallback() {
  local file="$1"
  [[ ! -f "$file" ]] && { echo ""; return 1; }
  # 用 python3 解析 JSON（比 bash jq 更可靠，不依赖额外依赖）
  python3 -c "
import json, sys
try:
    with open('$file') as f:
        data = json.load(f)
    enabled = [u for u in data if u.get('enabled', False)]
    if not enabled:
        sys.exit(1)
    # 按 tier_priority 升序
    enabled.sort(key=lambda u: u.get('tier_priority', 999))
    best = enabled[0]
    print(json.dumps({'base_url': best.get('base_url', ''), 'api_key': best.get('api_key', '')}))
except Exception:
    sys.exit(1)
" 2>>"$LOG_FILE" || echo ""
}

# ── 对 upstream base_url 做连通性检查 ──
# 返回 0=通，1=不通
_try_alternative_upstream() {
  local base_url="$1"
  # 只做 TCP 握手检查（--connect-timeout 5，不请求具体路径）
  curl -sS --connect-timeout 5 --max-time 10 -o /dev/null -w '%{http_code}' "${base_url%/}" 2>>"$LOG_FILE" | grep -qE '^[0-9]+$' && return 0
  return 1
}

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

# --- Step 1.5: router 健康检查 + upstream 回退（红线：避免在 down router 上浪费重试）---
log "Step 1.5: router health check ($ROUTER_HEALTH_URL)"
if check_upstream_health "$ROUTER_HEALTH_URL"; then
  log " router 健康: $ROUTER_HEALTH_URL"
else
  log " router 健康检查 FAIL — 尝试从 upstreams.json 回退"
  FALLBACK_JSON="$(_read_upstreams_fallback "$UPSTREAMS_FILE")"
  if [[ -n "$FALLBACK_JSON" ]]; then
    FB_BASE_URL="$(echo "$FALLBACK_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin).get('base_url',''))")"
    FB_API_KEY="$(echo "$FALLBACK_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin).get('api_key',''))")"
    if [[ -n "$FB_BASE_URL" ]] && _try_alternative_upstream "$FB_BASE_URL"; then
      log " 回退 upstream 可用: $FB_BASE_URL"
      export UPSTREAM_BASE_URL="$FB_BASE_URL"
      export UPSTREAM_API_KEY="$FB_API_KEY"
    else
      log " 回退 upstream 不可用: $FB_BASE_URL"
      FALLBACK_JSON=""
    fi
  fi
  if [[ -z "$FALLBACK_JSON" ]]; then
    log " 无可用 upstream 回退 — 拒绝启动 executor"
    bash "$SCRIPT_DIR/ccc-notify.sh" L2 "router DOWN: $PHASE_ID" \
      "无可用 upstream 回退 phase=$PHASE_ID" >/dev/null 2>&1 || true
    exit 6
  fi
fi

# --- Step 2: pre-exec 钩子 ---
log "Step 2: pre-exec hook"
if ! bash "$SCRIPT_DIR/ccc-hook.sh" pre-exec "$PHASE_ID" "$PROMPT_FILE" >> "$LOG_FILE" 2>&1; then
  log "❌ pre-exec 钩子阻断"
  exit 2
fi

# --- Step 3: opencode-exec（含重试）---
MAX_RETRY=3
BACKOFF=(60 120 240)
EXEC_RC=1
log "Step 3: opencode-exec (max ${MAX_RETRY} retries)"
for attempt in $(seq 1 $MAX_RETRY); do
  EXEC_ARGS=(--phase "$PHASE_ID" --prompt "$PROMPT_FILE" --timeout "$TIMEOUT")
  # Step 1 已跑 watchdog，不重复（红线 X3 在 launcher 层满足）
  EXEC_ARGS+=(--skip-watchdog)
  [[ -n "$CWD" ]] && EXEC_ARGS+=(--cwd "$CWD")

  set +e
  python3 "$SCRIPT_DIR/opencode-exec.py" "${EXEC_ARGS[@]}" > "$LOG_DIR/opencode-${PHASE_ID}-attempt-${attempt}.json" 2>> "$LOG_FILE"
  EXEC_RC=$?
  set -e
  log "opencode-exec attempt=$attempt exit=$EXEC_RC"

  if [[ $EXEC_RC -eq 0 ]]; then
    break  # 成功，跳出重试
  fi

  if [[ $attempt -lt $MAX_RETRY ]]; then
    WAIT=${BACKOFF[$((attempt - 1))]}
    log "重试 $attempt/$MAX_RETRY，等待 ${WAIT}s…"
    sleep "$WAIT"
  fi
done

# --- Step 4: 失败处理（on-error 钩子 + 通知）---
if [[ $EXEC_RC -ne 0 ]]; then
  log "Step 4a: on-error hook + L2 通知"
  bash "$SCRIPT_DIR/ccc-hook.sh" on-error "$PHASE_ID" "$EXEC_RC" >> "$LOG_FILE" 2>&1 || true
  bash "$SCRIPT_DIR/ccc-notify.sh" L2 "opencode FAIL: $PHASE_ID" "exit=$EXEC_RC log=$LOG_FILE" >/dev/null 2>&1 || true
  # opencode-exec.py 超时返回 -1（bash wrap → 255），非 124
  exit $(( EXEC_RC == 255 ? 4 : 3 ))
fi

# --- Step 5: post-exec 钩子 ---
log "Step 5: post-exec hook"
# v0.15b: 传 workspace 给 post-exec（它要知道在哪个仓库 commit）
if ! bash "$SCRIPT_DIR/ccc-hook.sh" post-exec "$PHASE_ID" "$CWD" >> "$LOG_FILE" 2>&1; then
  log "❌ post-exec 钩子阻断"
  exit 5
fi

# post-exec 已做 git commit → 写标记，防止 exec-commit.sh 重复 commit
COMMIT_MARKER_DIR="$HOME/.ccc/committed-phases"
mkdir -p "$COMMIT_MARKER_DIR"
touch "$COMMIT_MARKER_DIR/${PHASE_ID}.marker"
log "已写 commit 标记: $COMMIT_MARKER_DIR/${PHASE_ID}.marker"

log "✅ phase $PHASE_ID 完成"
exit 0
