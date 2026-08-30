#!/usr/bin/env bash
# ── 正考编排套件 · ① 信封搬运（只备不跑：由 15:00 正考调用）──
#
# 用途：从执行分支（codex/<card-id>）提取「分支信封」——已回写 + 机审通过
#       的最终卡面与被审钉证据，供环节② 审核合入前取证（近似 approve-merge.sh
#       信封定位的轻量专用版，零改动引擎/闸门/风控代码）。
#
# 参数化（shell 环境导出，正考前置）：
#   WEB_HOST         看板主机（正考前导出）——默认 192.168.3.116
#   CCC_BOARD_URL    完整看板地址（设了则优先于 WEB_HOST）
#   CCC_REPO         本仓路径（默认当前目录的 git 根）
#   BRANCH_PREFIX    信封分支前缀（默认 codex/）
#
# 用法：
#   scripts/exam-envelope-lift.sh <card-id>            # 默认只读取证（推荐）
#   scripts/exam-envelope-lift.sh <card-id> --apply   # 搬运信封卡面覆写主树镜像
#
# 退出码：0=信封定位并取证成功；1=卡/分支/信封任一缺失；2=参数错误。
set -euo pipefail

REPO_ROOT="${CCC_REPO:-$(git rev-parse --show-toplevel 2>/dev/null || echo "$PWD")}"
BRANCH_PREFIX="${BRANCH_PREFIX:-codex/}"
BOARD_URL="${CCC_BOARD_URL:-http://${WEB_HOST:-192.168.3.116}:7788}"
APPLY=false

usage() {
  sed -n '1,18p' "$0" | sed 's/^# \{0,1\}//'
}

[[ $# -lt 1 ]] && { usage; exit 2; }
CARD_ID="$1"
shift
case "$1" in
  --apply) APPLY=true ;;
  "") ;;
  *) echo "[ERROR] 未知参数: $1" >&2; exit 2 ;;
esac

cd "$REPO_ROOT"

# 定位卡文件（docs/dispatch/<prefix>/<id>-*.md）
CARD_PATH=""
for f in docs/dispatch/*/"${CARD_ID}"-*.md; do
  [[ -e "$f" ]] && CARD_PATH="$f" && break
done
[[ -z "$CARD_PATH" ]] && { echo "[ERROR] 未找到卡文件: $CARD_ID（docs/dispatch 无 <id>-*.md）" >&2; exit 1; }

BRANCH="${BRANCH_PREFIX}${CARD_ID}"
git fetch origin "$BRANCH" >/dev/null 2>&1 \
  || { echo "[ERROR] 远端无信封分支 origin/$BRANCH" >&2; exit 1; }

BRANCH_CARD="$(git show "origin/$BRANCH:$CARD_PATH" 2>/dev/null || true)"
[[ -z "$BRANCH_CARD" ]] && { echo "[ERROR] 分支信封卡面缺失: origin/$BRANCH:$CARD_PATH" >&2; exit 1; }

# 信封证据：机审结论 + 被审钉（仅读取展示）
ENV_COMMITS="$(git log --format='%H %ct' "origin/$BRANCH" -- "$CARD_PATH")"
MACHINE_LINE="$(printf '%s\n' "$BRANCH_CARD" | grep -E "机审：(通过|不通过)" | head -1 || true)"
STATE_LINE="$(printf '%s\n' "$BRANCH_CARD" | grep "状态：" | head -1 || true)"

echo "[OK] 信封定位: origin/$BRANCH → $CARD_PATH"
echo "  $STATE_LINE"
[[ -n "$MACHINE_LINE" ]] && echo "  $MACHINE_LINE"
echo "  看板: $BOARD_URL"
[[ -n "$ENV_COMMITS" ]] && printf '  信封提交: %s\n' "$(printf '%s\n' "$ENV_COMMITS" | head -1 | cut -d' ' -f1)"

if [[ "$APPLY" == true ]]; then
  printf '%s\n' "$BRANCH_CARD" > "$CARD_PATH"
  echo "[OK] 信封卡面已覆写主树镜像: $CARD_PATH（同名改动请 commit+push，禁 git add -A）"
else
  echo "[i] 只读取证模式（未覆写）；加 --apply 才搬运覆写主树镜像。"
fi
exit 0