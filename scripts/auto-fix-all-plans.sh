#!/usr/bin/env bash
# 批量补回写：对指定项目的所有方案跑 sync_plan_progress + sync_milestone_progress。
#
# 用途：一次性修复历史债——ccc062(sync_plan_cards) 引入前关闭的卡、或没走
# approve-merge.sh 直接关闭的卡，导致方案进度行滞后（如 0/1 实际应 1/1）。
# 幂等：只重算进度行/状态，不改方案正文；可重复跑。
#
# 用法：bash scripts/auto-fix-all-plans.sh <prefix> [prefix2 ...]
# 例：  bash scripts/auto-fix-all-plans.sh mx hp xy
#
# 退出码：0=完成（含跳过）；1=参数错误。
set -euo pipefail

# ccc088：索引口径兜底——裸 shell（无 CCC_DATA_DIR）下 sync_plan_progress 级联
# （plans.py 作废级联 load_dispatch_cards）经 loader 回落写
# <repo>/data/cards/cards.index.jsonl（陈旧副本），与生产看板双写分裂。
# 仅认 CCC_DATA_DIR 口径（loader 另支持 DATA_DIR，此处不启用），与生产看板同源。
export CCC_DATA_DIR="${CCC_DATA_DIR:-$HOME/.ccc/data}"

if [ $# -lt 1 ]; then
  echo "用法: auto-fix-all-plans.sh <prefix> [prefix2 ...]" >&2
  echo "例:   auto-fix-all-plans.sh mx hp xy" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"
export PYTHONPATH="$REPO_ROOT:${PYTHONPATH:-}"  # auto-fix-plan-progress.py 依赖 import server.board.*

fixed=0
for prefix in "$@"; do
  plans_dir="docs/projects/$prefix/plans"
  if [ ! -d "$plans_dir" ]; then
    echo "[skip] $prefix: 无 plans 目录"
    continue
  fi
  echo "=== $prefix ==="
  for plan in "$plans_dir"/*.md; do
    [ -f "$plan" ] || continue
    rel="docs/projects/$prefix/plans/$(basename "$plan")"
    if python3 scripts/auto-fix-plan-progress.py "$REPO_ROOT" "$rel" "$prefix" 2>&1 | sed "s/^/  /"; then
      fixed=$((fixed + 1))
    fi
  done
done
echo "=== 完成：处理 $fixed 个方案 ==="
