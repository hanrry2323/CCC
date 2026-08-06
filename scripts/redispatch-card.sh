#!/usr/bin/env bash
# ── CCC：打回卡人工重新分派（打回 → 待分派，重试计数归零）──
#
# 用法：
#   scripts/redispatch-card.sh <card-id> [<card-id>...]
#
# 校验：卡当前为「打回」（含括号原因）。
# 动作：卡头状态改回纯「待分派」；保留 `## 人工批注` 与 `打回次数` 历史；
#       引擎重试计数归零（状态串无「重试n」标记），下轮心跳自动再派。
# 建议：先看卡上打回原因，在 `## 人工批注` 写好审核意见后再执行本脚本。

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHON_BIN="${CCC_PYTHON_BIN:-python3}"

IDS=()
DISPATCH_DIR=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help) sed -n '2,14p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    --dispatch-dir) DISPATCH_DIR="$2"; shift 2 ;;
    *) IDS+=("$1"); shift ;;
  esac
done

if [[ ${#IDS[@]} -eq 0 ]]; then
  echo "[ERROR] 缺少卡 ID（用法：scripts/redispatch-card.sh <card-id>）" >&2
  exit 2
fi

cd "$PROJECT_ROOT"

rc=0
for cid in "${IDS[@]}"; do
  if [[ -n "$DISPATCH_DIR" ]]; then
    if ! "$PYTHON_BIN" -m server.board.redispatch "$cid" --dispatch-dir "$DISPATCH_DIR"; then
      rc=1
    fi
  elif ! "$PYTHON_BIN" -m server.board.redispatch "$cid"; then
    rc=1
  fi
done
exit "$rc"
