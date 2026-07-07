#!/bin/bash
# opencode-watchdog.sh — OpenCode 残留进程扫描 + 清理
#
# 职责（红线 X2 + X3 配套）：
#   1. 扫描 ~/.ccc/opencode-pids/ 下的 pid 文件
#   2. 每个 pid 检查：进程是否还活着？名字是否还叫 opencode？
#   3. 死了：清 pid 文件
#   4. 活着 + 名字不对（说明 pid 被复用）：杀 + 清 pid 文件
#   5. 活着 + 名字对：保留（说明是另一 phase 在跑）
#   6. 兜底：pgrep -f "opencode exec" 扫所有 opencode exec 子进程，孤儿杀掉
#
# 退出码：
#   0 = 干净（无残留 / 全部清理完）
#   1 = 有残留但非致命（建议人工 review）
#   2 = 严重残留（杀不掉 / 权限问题）
#   3 = 已自清（启动条件已修复）

set -uo pipefail

PID_DIR="${HOME}/.ccc/opencode-pids"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[watchdog]${NC} $*"; }
log_warn()  { echo -e "${YELLOW}[watchdog]${NC} $*"; }
log_err()   { echo -e "${RED}[watchdog]${NC} $*"; }

if [[ ! -d "$PID_DIR" ]]; then
  log_info "pid 目录不存在（$PID_DIR），无残留"
  exit 0
fi

CLEANED=0
ORPHAN=0
ALIVE=0

# --- 扫描 pid 文件 ---
for pf in "$PID_DIR"/*.pid; do
  [[ -f "$pf" ]] || continue
  pid=$(cat "$pf" 2>/dev/null || true)
  phase=$(basename "$pf" .pid)

  if [[ -z "$pid" ]]; then
    rm -f "$pf"
    log_info "空 pid 文件: $phase → 已删"
    CLEANED=$((CLEANED+1))
    continue
  fi

  # 进程还活着吗？
  if ! kill -0 "$pid" 2>/dev/null; then
    rm -f "$pf"
    log_info "死进程: $phase (pid=$pid) → 已清 pid 文件"
    CLEANED=$((CLEANED+1))
    continue
  fi

  # 活着：名字对吗？
  proc_name=$(ps -p "$pid" -o command= 2>/dev/null || true)
  if [[ "$proc_name" == *opencode* ]]; then
    ALIVE=$((ALIVE+1))
    log_info "存活: $phase (pid=$pid, name=$proc_name) — 保留"
  else
    # pid 被复用 / 进程名变了 → 杀
    log_warn "pid 复用: $phase (pid=$pid, name=$proc_name) → 杀"
    kill -TERM "$pid" 2>/dev/null || true
    sleep 1
    if kill -0 "$pid" 2>/dev/null; then
      kill -KILL "$pid" 2>/dev/null || true
    fi
    rm -f "$pf"
    CLEANED=$((CLEANED+1))
  fi
done

# --- 兜底：扫所有 opencode exec 子进程（无 pid 文件登记的孤儿）---
# 兜底：扫所有 opencode 子进程（孤儿）。v0.11b-fix 加 run（之前漏了）
# 排除 pgrep 自身（pgrep -f "opencode" 会匹配 pgrep 命令行）
ORPHAN_PIDS=$(pgrep -f "opencode (run|exec)" 2>/dev/null | grep -v "^$$\$" | grep -v "^${PPID}\$" || true)
while read -r opid; do
  # 是否有对应 pid 文件（精确匹配行内容 = pid）
  HAS_PID_FILE=0
  for pf in "$PID_DIR"/*.pid; do
    [[ -f "$pf" ]] || continue
    if [[ "$(cat "$pf" 2>/dev/null)" == "$opid" ]]; then
      HAS_PID_FILE=1
      break
    fi
  done
  if [[ $HAS_PID_FILE -eq 0 ]]; then
    log_warn "孤儿进程: pid=$opid → 杀"
    # 杀整个 process group（opencode 启的 node 孙子进程）
    kill -TERM -"$opid" 2>/dev/null || kill -TERM "$opid" 2>/dev/null || true
    sleep 1
    if kill -0 "$opid" 2>/dev/null; then
      kill -KILL -"$opid" 2>/dev/null || kill -KILL "$opid" 2>/dev/null || true
    fi
    ORPHAN=$((ORPHAN+1))
  fi
done <<< "$ORPHAN_PIDS"

echo ""
log_info "汇总: alive=$ALIVE cleaned=$CLEANED orphan_killed=$ORPHAN"

if [[ $ORPHAN -gt 0 ]]; then
  log_warn "杀了 $ORPHAN 个孤儿进程（建议 review 是哪个 phase 漏了）"
  exit 3  # 已自清
elif [[ $ALIVE -gt 0 ]]; then
  log_info "有 $ALIVE 个 phase 正在跑（合法）"
  exit 0
else
  log_info "完全干净"
  exit 0
fi
