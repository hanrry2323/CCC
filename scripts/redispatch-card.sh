#!/usr/bin/env bash
# ── CCC：打回卡人工重新分派（运行时指令，主树卡文件只读）──
#
# 用法：
#   scripts/redispatch-card.sh <card-id> [<card-id>...]
#
# 前置：老板修订指示先写进卡 `## 人工批注` 并 commit+push 到 main
#       （执行体 worktree 从 main 建，天然读到批注）。
# 动作：调用看板 API POST /tasks/<id>/transition（status=待分派）→ 写运行时
#       sidecar（state=待分派、retry_count=0、redispatch=ts），engine 每轮重派。
#       不直接改任何卡文件（主树保持 main 镜像）。

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BOARD_URL="${CCC_BOARD_URL:-http://192.168.3.116:7788}"

# 写端点启用鉴权时由调用方注入短期 token；绝不在脚本或日志中落盘。
AUTH_HEADERS=()
if [[ -n "${CCC_BOARD_TOKEN:-}" ]]; then
  AUTH_HEADERS=(-H "Authorization: Bearer ${CCC_BOARD_TOKEN}")
fi

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
  # P2：预算耗尽卡由 API 返回 awaiting_human/exhausted_class；在重派前显式提示，
  # 确认动作由调用方承担，API 仍负责清零全部预算计数（不绕过鉴权/CAS）。
  detail=""
  if detail="$(curl -sf --max-time 10 "${BOARD_URL}/tasks/${cid}" -H 'Accept: application/json' "${AUTH_HEADERS[@]}" 2>/dev/null)"; then
    if [[ "$detail" == *'"awaiting_human":true'* || "$detail" == *'"reject_budget_exhausted":true'* ]]; then
      exhausted_class="$(printf '%s' "$detail" | sed -n 's/.*"exhausted_class":"\([^"]*\)".*/\1/p')"
      exhausted_class="${exhausted_class:-business}"
      echo "[WARN] ${cid}: 此卡预算耗尽（${exhausted_class}），确认后重派将清零计数" >&2
    fi
  fi
  if out="$(curl -sf --max-time 10 -X POST "${BOARD_URL}/tasks/${cid}/transition" \
      -H 'Content-Type: application/json' "${AUTH_HEADERS[@]}" \
      -d '{"status":"待分派"}' 2>&1)"; then
    echo "[OK] ${cid}: ${out}"
  else
    echo "[ERROR] ${cid}: ${out}" >&2
    rc=1
  fi
done
exit "$rc"
