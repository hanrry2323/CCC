#!/usr/bin/env bash
# ── 正考编排套件 · ② 回写同步（只备不跑：由 15:00 正考调用）──
#
# 用途：把执行分支（codex/<card-id>）上「已回写 + 维护区四问完成」的最终
#       卡面同步回主树镜像（等价 git 历史 b0e86041 手工步骤的参数化版，
#       止血循环派发用）。只写目标卡文件并提示提交，不代 commit/push 流程。
#
# 参数化（shell 环境导出，正考前置）：
#   WEB_HOST         看板主机（正考前导出）——默认 192.168.3.116
#   CCC_BOARD_URL    完整看板地址（设了则优先于 WEB_HOST）
#   CCC_REPO         本仓路径（默认当前目录的 git 根）
#   BRANCH_PREFIX    回写分支前缀（默认 codex/）
#   REQUIRED_STATE   要求的分支卡头状态（默认 已回写；机审后同套件复核可查）
#
# 用法：
#   scripts/exam-writeback-sync.sh <card-id> [--check | --sync]
#     --check 默认：只核对分支卡面状态与维护区，不写主树
#     --sync  ：确认为已回写后把分支卡面覆写主树镜像
#
# 退出码：0=一致/已同步；1=状态不符或脚本缺失；2=参数错误。
set -euo pipefail

REPO_ROOT="${CCC_REPO:-$(git rev-parse --show-toplevel 2>/dev/null || echo "$PWD")}"
BRANCH_PREFIX="${BRANCH_PREFIX:-codex/}"
REQUIRED_STATE="${REQUIRED_STATE:-已回写}"
BOARD_URL="${CCC_BOARD_URL:-http://${WEB_HOST:-192.168.3.116}:7788}"
MODE="check"

usage() {
  sed -n '1,20p' "$0" | sed 's/^# \{0,1\}//'
}

[[ $# -lt 1 ]] && { usage; exit 2; }
CARD_ID="$1"
shift
case "$1" in
  --check) MODE="check" ;;
  --sync) MODE="sync" ;;
  "") ;;
  *) echo "[ERROR] 未知参数: $1" >&2; exit 2 ;;
esac

cd "$REPO_ROOT"

CARD_PATH=""
for f in docs/dispatch/*/"${CARD_ID}"-*.md; do
  [[ -e "$f" ]] && CARD_PATH="$f" && break
done
[[ -z "$CARD_PATH" ]] && { echo "[ERROR] 未找到卡文件: $CARD_ID" >&2; exit 1; }

BRANCH="${BRANCH_PREFIX}${CARD_ID}"
git fetch origin "$BRANCH" >/dev/null 2>&1 \
  || { echo "[ERROR] 远端无回写分支 origin/$BRANCH" >&2; exit 1; }

BRANCH_CARD="$(git show "origin/$BRANCH:$CARD_PATH" 2>/dev/null || true)"
[[ -z "$BRANCH_CARD" ]] && { echo "[ERROR] 分支卡面缺失: origin/$BRANCH:$CARD_PATH" >&2; exit 1; }

STATE_LINE="$(printf '%s\n' "$BRANCH_CARD" | grep "^> .*状态：" | head -1 || true)"
case "$STATE_LINE" in
  *"状态：${REQUIRED_STATE}"*)
    echo "[OK] 分支卡头状态=${REQUIRED_STATE}（$CARD_PATH @ origin/$BRANCH）" ;;
  *"状态：${REQUIRED_STATE}（"*)
    echo "[OK] 分支卡头状态=${REQUIRED_STATE}（含说明）：${STATE_LINE##*状态：}" ;;
  *)
    echo "[ERROR] 分支卡头状态非 ${REQUIRED_STATE}：$STATE_LINE" >&2
    exit 1 ;;
esac

# 维护区四问完成钩子：任一 [是/否] 未勾选即不符（Doc-Gate 口径）
FILLED="$(printf '%s\n' "$BRANCH_CARD" | grep -cE '^\s*[0-9]+\. .*\[[是|有|否|无]\]' || true)"
[[ "$FILLED" -ge 4 ]] || {
  echo "[ERROR] 分支卡 `## 维护区` 四问未逐项勾选（命中 ${FILLED}/4），回写同步拒绝" >&2
  exit 1
}

echo "  看板: $BOARD_URL"
if [[ "$MODE" == "sync" ]]; then
  printf '%s\n' "$BRANCH_CARD" > "$CARD_PATH"
  echo "[OK] 分支回写卡面已同步主树镜像: $CARD_PATH（请 commit+push 让原分支信封落到主树，禁 git add -A）"
else
  echo "[i] 只核对模式（未写主树）；确认后加 --sync 执行同步。"
fi
exit 0