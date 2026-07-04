#!/usr/bin/env bash
# executor-watchdog.sh — CCC 框架 Executor 启动前健康检查
#
# 目的：
#   启动 Executor (claude -p ...) 之前，检测系统状态，提前清理可能的
#   hang 进程 / stuck session，避免新任务被旧的卡死状态污染。
#
# 用法（在 Executor 启动命令之前调用）：
#   bash ~/program/CCC/scripts/executor-watchdog.sh [--force-kill] [--quiet]
#
# 退出码：
#   0 = 健康，可以启动 Executor
#   1 = 发现疑似 hang，已给提示但未清理
#   2 = 检测到严重问题，建议人工介入
#   3 = --force-kill 模式下清理了 hang 进程
#
# 触发：Lesson 7 — Mavis Executor 系统性卡死
# 修法：Lesson 8 — 启动前 watchdog + 自动 abort 老的 session
# 作者：qxo-CC Planner（用户授权 "必须修好"）

set -euo pipefail

FORCE_KILL=0
QUIET=0
HANG_THRESHOLD_MINUTES=15  # claude 跑超过这么久 + CPU 低 = 怀疑 hang

# ── 参数解析 ────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --force-kill) FORCE_KILL=1; shift ;;
    --quiet)      QUIET=1; shift ;;
    --hang-threshold)
      HANG_THRESHOLD_MINUTES="$2"; shift 2 ;;
    -h|--help)
      grep '^# ' "$0" | head -20
      exit 0 ;;
    *)
      echo "UNKNOWN ARG: $1" >&2
      exit 2 ;;
  esac
done

log() { [[ $QUIET -eq 1 ]] || echo "[watchdog] $*"; }
warn() { echo "[watchdog][WARN] $*" >&2; }

# ── Check 1：老 claude 进程健康度 ─────────────────────────────
# 长跑 + CPU < 1% + STAT 含 'S' (sleeping) = 怀疑 hang
log "──── Check 1: hang claude process scan ────"
HANG_PIDS=()
while IFS= read -r line; do
  pid=$(echo "$line" | awk '{print $1}')
  [[ -z "$pid" ]] && continue
  # 排除当前 shell 的祖先进程
  ppid_of=$(ps -o ppid= -p "$pid" 2>/dev/null | tr -d ' ' || echo "0")
  if [[ "$ppid_of" == "$$" || "$ppid_of" == "0" ]]; then
    continue
  fi

  # 用 ps 看 etime + pcpu + state
  stat_line=$(ps -o stat=,etime=,pcpu=,comm= -p "$pid" 2>/dev/null || echo "")
  [[ -z "$stat_line" ]] && continue

  # 提取 elapsed time（分钟数）：格式 HHH:MM:SS 或 MM:SS
  etime=$(echo "$stat_line" | awk '{print $2}')
  pcpu=$(echo "$stat_line" | awk '{print $3}')
  state=$(echo "$stat_line" | awk '{print $1}')

  # elapsed 转分钟
  etime_min=0
  if [[ "$etime" =~ ^([0-9]+):([0-9]+):([0-9]+)$ ]]; then
    etime_min=$(( ${BASH_REMATCH[1]} * 60 + ${BASH_REMATCH[2]} ))
  elif [[ "$etime" =~ ^([0-9]+):([0-9]+)$ ]]; then
    etime_min=${BASH_REMATCH[1]}
  fi

  # 判定：etime > threshold && pcpu < 1.0 && state 在 S 类（sleeping）
  pcpu_int=$(printf "%.0f" "$pcpu" 2>/dev/null || echo "0")
  if [[ $etime_min -gt $HANG_THRESHOLD_MINUTES && $pcpu_int -lt 1 ]]; then
    HANG_PIDS+=("$pid:$etime:$pcpu:$state")
  fi
done < <(pgrep -f 'claude$' 2>/dev/null || pgrep 'claude' 2>/dev/null || true)

if [[ ${#HANG_PIDS[@]} -gt 0 ]]; then
  warn "Found ${#HANG_PIDS[@]} suspected hang claude process(es):"
  for entry in "${HANG_PIDS[@]}"; do
    IFS=: read -r pid etime pcpu state <<< "$entry"
    warn "  PID=$pid etime=$etime pcpu=$pcpu% state=$state"
  done

  if [[ $FORCE_KILL -eq 1 ]]; then
    warn "--force-kill set: killing all hang claude processes"
    for entry in "${HANG_PIDS[@]}"; do
      IFS=: read -r pid _ _ _ <<< "$entry"
      kill -9 "$pid" 2>/dev/null && warn "  → killed $pid" || warn "  → kill $pid failed"
    done
    log "Check 1: cleaned hang processes → exit 3"
    exit 3
  fi

  warn "Suggested: rerun with --force-kill, or kill manually: kill -9 <pid>"
  log "Check 1: warning only → exit 1"
  exit 1
fi

log "Check 1: no hang claude process found (threshold=${HANG_THRESHOLD_MINUTES}min)"

# ── Check 2：Mavis stuck session scan ─────────────────────────
# mavis session list 看 status.type == "started" 但很久没 update 的 → 可能 hang
log "──── Check 2: mavis stuck session scan ────"
if command -v mavis >/dev/null 2>&1; then
  STUCK_SESSIONS=$(mavis session list 2>/dev/null \
    | python3 -c "
import json, sys, time
try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(0)
sessions = data.get('sessions', [])
now = int(time.time() * 1000)
threshold_ms = ${HANG_THRESHOLD_MINUTES} * 60 * 1000
for s in sessions:
    status = s.get('status', {})
    if status.get('type') != 'started':
        continue
    updated = s.get('updatedAt', 0)
    gap = now - updated
    if gap > threshold_ms:
        print(f\"{s['sessionId']}|{gap // 60000}m|{s.get('title', '?')}\")
" 2>/dev/null || echo "")

  if [[ -n "$STUCK_SESSIONS" ]]; then
    warn "Found stuck mavis session(s):"
    while IFS= read -r line; do
      [[ -z "$line" ]] && continue
      IFS='|' read -r sid gap title <<< "$line"
      warn "  session=$sid idle=${gap}min title='$title'"
    done <<< "$STUCK_SESSIONS"

    warn "Suggested: mavis session abort <sessionId>"

    if [[ $FORCE_KILL -eq 1 ]]; then
      warn "--force-kill set: aborting stuck sessions"
      while IFS= read -r line; do
        [[ -z "$line" ]] && continue
        IFS='|' read -r sid _ _ <<< "$line"
        mavis session abort "$sid" 2>/dev/null \
          && warn "  → aborted $sid" \
          || warn "  → abort $sid failed (may already be done)"
      done <<< "$STUCK_SESSIONS"
      log "Check 2: cleaned stuck sessions → exit 3"
      exit 3
    fi

    log "Check 2: warning only → exit 1"
    exit 1
  fi

  log "Check 2: no stuck mavis session found"
else
  log "Check 2: mavis CLI not found, skipping session scan"
fi

# ── Check 3：磁盘 /tmp 卫生（bonus）───────────────────────────
log "──── Check 3: /tmp/qx-stream-*.jsonl cleanup ────"
STALE_COUNT=$(find /tmp -maxdepth 1 -name "qx-stream-*.jsonl" -mmin +60 2>/dev/null | wc -l | tr -d ' ')
if [[ "$STALE_COUNT" -gt 5 ]]; then
  warn "/tmp has $STALE_COUNT stale qx-stream-*.jsonl files (>60min old)"
  warn "Suggested: rm -f /tmp/qx-stream-*.jsonl (only if no live task running)"
  # 不自动删 — 安全优先（可能有 live task 在用）
fi

# ── Check 4：Memory headroom ─────────────────────────
log "──── Check 4: free memory check ────"
if command -v vm_stat >/dev/null 2>&1; then
  # macOS 页面大小通常是 16384 bytes（modern），fallback 4096（legacy）
  # vm_stat 第一行形如: "Mach Virtual Memory Statistics: (page size of 16384 bytes)"
  PAGE_SIZE_LINE=$(vm_stat 2>/dev/null | head -1)
  PAGE_SIZE=$(echo "$PAGE_SIZE_LINE" | grep -oE '[0-9]+ bytes' | head -1 | awk '{print $1}')
  PAGE_SIZE="${PAGE_SIZE:-4096}"

  # 真实可用 = free + inactive + speculative（macOS 里这些都可被回收给 claude）
  PAGES_FREE=$(vm_stat 2>/dev/null | awk '/Pages free/ {print $3}' | tr -d '.' || echo "0")
  PAGES_INACTIVE=$(vm_stat 2>/dev/null | awk '/Pages inactive/ {print $3}' | tr -d '.' || echo "0")
  PAGES_SPECULATIVE=$(vm_stat 2>/dev/null | awk '/Pages speculative/ {print $3}' | tr -d '.' || echo "0")

  AVAILABLE_PAGES=$(( ${PAGES_FREE:-0} + ${PAGES_INACTIVE:-0} + ${PAGES_SPECULATIVE:-0} ))
  AVAILABLE_MB=$(( (AVAILABLE_PAGES * PAGE_SIZE) / 1024 / 1024 ))

  # macOS 阈值：available < 1GB 警告（因为 inactive 通常占用大量，可回收）
  if [[ $AVAILABLE_MB -lt 1024 ]]; then
    warn "Available memory < 1GB (${AVAILABLE_MB}MB) — heavy claude tasks may OOM"
    warn "  page_size=${PAGE_SIZE}B  free=${PAGES_FREE}  inactive=${PAGES_INACTIVE}  speculative=${PAGES_SPECULATIVE}"
    log "Check 4: warning → exit 1"
    exit 1
  fi
  log "Check 4: available=${AVAILABLE_MB}MB (page_size=${PAGE_SIZE}B, free+inactive+speculative, OK)"
fi

# ── All healthy ──────────────────────────────────
log "──── watchdog passed ────"
log "All checks passed. Safe to launch Executor."
exit 0
