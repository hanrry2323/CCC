#!/bin/bash
# ccc-sync-after-push.sh — git push 后自动拉远端(v0.61.0 阶段 E)
#
# 用法:装到 ~/.gitconfig 后
#   [alias]
#       gp = !git push && ccc-sync-after-push
#
# 同步 CCC + 6 个业务仓(qb / xianyu / hp / medio-0 / ccc-demo / qx-observer)
# 用 ssh mac2017 cd ... && git fetch -q && git merge --ff-only
# 失败:non-FF → 黄字警告,**绝不 reset --hard**;SSH 断 → 黄字 SYNC SKIPPED
#
# 不动业务数据,只动 git 历史。

set -uo pipefail

CCC_HOME="${CCC_HOME:-$HOME/program/CCC}"
REMOTE_HOST="${CCC_REMOTE_HOST:-mac2017}"
REMOTE_USER="${CCC_REMOTE_USER:-fan}"
REMOTE_CCC="${CCC_REMOTE_CCC:-/Users/${REMOTE_USER}/program/CCC}"
TIMEOUT_PER_REPO="${CCC_SYNC_TIMEOUT:-10}"
APPS=(
  "qb:$HOME/program/qb"
  "xianyu:$HOME/program/xianyu"
  "hp:$HOME/program/hp"
  "medio-0:$HOME/program/medio-0"
  "ccc-demo:$HOME/program/ccc-demo"
  "qx-observer:$HOME/program/qx-observer"
)

_log() { echo "[$(date +%H:%M:%S)] [ccc-sync] $*" >&2; }

_sync_repo() {
  local name=$1 local_path=$2
  if [[ ! -d "$local_path/.git" ]]; then
    _log "  skip $name (no git repo at $local_path)"
    return 0
  fi
  local remote_name
  remote_name=$(cd "$local_path" 2>/dev/null && git remote get-url origin 2>/dev/null || true)
  if [[ -z "$remote_name" ]]; then
    _log "  skip $name (no origin remote)"
    return 0
  fi
  # 不在远端仓列表的(私仓/非本机路径)skip,避免 ssh 误碰
  if [[ "$remote_name" != *"github.com"* ]]; then
    _log "  skip $name (non-github remote)"
    return 0
  fi
  # 实际同步:远端 cd & git fetch --ff-only
  local out
  local remote_subdir
  remote_subdir=$(echo "$local_path" | sed "s|$HOME/||")
  out=$(timeout "$TIMEOUT_PER_REPO" ssh "$REMOTE_HOST" \
    "cd ~/${REMOTE_USER}/${remote_subdir} 2>/dev/null && git fetch -q origin && git merge --ff-only origin/main 2>&1" 2>&1) || true
  if echo "$out" | grep -q "non-fast-forward\|CONFLICT\|not possible\|would be overwritten"; then
    _log "  ⚠ $name: non-FF merge, stop sync(防止破坏远端)"
    return 1
  fi
  if echo "$out" | grep -qE "Connection refused|timeout|No route|ssh: connect"; then
    _log "  ⚠ $name: SSH 断,skip(不会推/拉,需要手动)"
    return 0
  fi
  if echo "$out" | grep -qE "Already up to date|Updating [0-9a-f]+\.\.[0-9a-f]+|Fast-forward"; then
    _log "  ✓ $name: synced"
    return 0
  fi
  if [[ -n "$out" ]]; then
    _log "  · $name: $out" | head -1
  fi
  return 0
}

# main
_log "→ ccc-sync-after-push (remote=$REMOTE_HOST user=$REMOTE_USER)"

# 1. CCC 仓
_sync_repo "CCC" "$CCC_HOME"

# 2. 业务仓
for entry in "${APPS[@]}"; do
  name="${entry%%:*}"
  path="${entry#*:}"
  _sync_repo "$name" "$path"
done

_log "✓ ccc-sync-after-push 完成"
exit 0
