#!/usr/bin/env bash
# ── scripts/update-card.sh ──
# 更新任务卡内容（原子 commit + push，仅限 dispatch 目录）。
#
# 用法：
#   scripts/update-card.sh <卡文件相对路径，如 docs/dispatch/tst/tst900-smoke-full-flow.md> \
#     ["提交说明（默认 docs(card): <文件名> 内容更新）"]
#
# 机制（与 new-card.sh 尾部同款原子通道）：
#   写卡 → git add 指定卡 → git commit → git push origin <当前分支>。
#   单条命令内完成「写入+提交+推送」，不留落盘未提交的中间态。
#
# 🔴 编辑侧吃单窗处置（2026-09-03 实测 tst900）：
#   engine git_sync 会把 dispatch 强制对齐到 origin（单写者设计行为，不是 bug）。
#   因此本脚本要求：
#   1. 卡内容一次性出全 —— create 后用本脚本更新，禁在 create 后手动 Edit/Write 后
#      延迟提交（未推送的本地编辑会被 git_sync 按未跟踪/未推送对齐抹掉）。
#   2. 写入与提交推送必须同一进程链内（本脚本即为此而生），禁止分步。
#
# 退出码：0=成功；非0=失败（卡文件保留，git 已回滚）。
set -euo pipefail

# 仅限 dispatch 目录（防误推其他路径）
CARD_PATH="${1:?缺卡文件相对路径}"
MSG="${2:-docs(card): $(basename "$CARD_PATH") 内容更新}"

case "$CARD_PATH" in
  docs/dispatch/*) ;;
  *) echo "[ERROR] 仅限 docs/dispatch/ 内卡文件" >&2; exit 2 ;;
esac

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

[[ -f "$CARD_PATH" ]] || { echo "[ERROR] 卡文件不存在: $CARD_PATH" >&2; exit 3; }

git add -- "$CARD_PATH"
git diff --cached --quiet -- "$CARD_PATH" && { echo "[WARN] 卡内容无变化，跳过" >&2; exit 0; }
git commit -m "$MSG"
BRANCH="$(git rev-parse --abbrev-ref HEAD)"
if git remote | grep -q "^origin$"; then
  git push origin "$BRANCH"
  echo "[OK] 已推送 origin/${BRANCH}: $CARD_PATH"
else
  echo "[WARN] 无 origin remote，仅本地提交" >&2
fi
