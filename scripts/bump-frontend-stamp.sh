#!/usr/bin/env bash
# bump-frontend-stamp.sh — 前端缓存版本号统一递增（P3-11 自动化）
#
# 背景：CCC 前端无构建，静态资源用查询串版本号做缓存失效。
# 版本号散落 index.html（CSS/JS 资源）与 bootloader.js，改版需手改两文件多处。
# 本脚本把全部版本号换成新值，避免漏改导致浏览器缓存旧资源。
#
# 用法：
#   scripts/bump-frontend-stamp.sh [NEW_STAMP]
#     不带参数 → 自动生成 `YYYYMMDDtN`（今日第 N 次递增）
#     带参数   → 用给定值（如 `20260815t2`）
#
# 注意：只替换形如 `\d{8}t\d+` 的版本号 token，其余文本不动。

set -euo pipefail

cd "$(dirname "$0")/.."   # 仓根

OLD_STAMP=""
# 取现有版本号（index.html 首个 CSS 资源版本）
if grep -q '?v=[0-9]\{8\}t[0-9]\+' server/web/legacy-chat/index.html; then
  OLD_STAMP=$(grep -o '?v=[0-9]\{8\}t[0-9]\+' server/web/legacy-chat/index.html | head -1 | sed 's/?v=//')
fi

NEW_STAMP=""
if [ "$#" -ge 1 ] && [ -n "$1" ]; then
  NEW_STAMP="$1"
else
  TODAY=$(date +%Y%m%d)
  # 当日已出现的序号 → 递增
  if [ -n "$OLD_STAMP" ] && [[ "$OLD_STAMP" == "${TODAY}t"* ]]; then
    N=$(( ${OLD_STAMP#${TODAY}t} + 1 ))
  else
    N=1
  fi
  NEW_STAMP="${TODAY}t${N}"
fi

if [ -z "$OLD_STAMP" ]; then
  echo "错误：index.html 中找不到版本号 token" >&2
  exit 1
fi

FILES=(
  server/web/legacy-chat/index.html
  server/web/legacy-chat/js/bootloader.js
)

echo "前端版本号：${OLD_STAMP} → ${NEW_STAMP}"
for f in "${FILES[@]}"; do
  if [ -f "$f" ]; then
    # macOS sed 需要 -i '' 后缀；兼容 GNU sed
    if sed --version >/dev/null 2>&1; then
      sed -i "s/${OLD_STAMP}/${NEW_STAMP}/g" "$f"
    else
      sed -i '' "s/${OLD_STAMP}/${NEW_STAMP}/g" "$f"
    fi
    echo "  ✓ $f"
  fi
done

echo "完成：请 git add + commit（build-stamp 显示为新版）"
