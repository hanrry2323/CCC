#!/usr/bin/env bash
set -uo pipefail
# CCC平台每日健康巡检（M1开发机）
# 输出：/tmp/ccc-health-daily-<date>.md
# ruff 不在 venv（在 /opt/homebrew/bin），pytest 在 .venv/bin
DATE=$(date +%Y%m%d)
OUT=/tmp/ccc-health-daily-$DATE.md
cd /Users/apple/program/CCC || exit 1
echo "# CCC平台健康巡检 $DATE" > "$OUT"
echo "" >> "$OUT"

# 1. 代码质量
echo "## 1. Ruff" >> "$OUT"
/opt/homebrew/bin/ruff check server/ --output-format=concise 2>&1 | tail -5 >> "$OUT"
echo "" >> "$OUT"

# 2. 测试
echo "## 2. Pytest" >> "$OUT"
.venv/bin/pytest server/tests/ -q 2>&1 | tail -3 >> "$OUT"
echo "" >> "$OUT"

# 3. 卡状态分布
echo "## 3. 卡状态" >> "$OUT"
for s in 待分派 执行中 已回写 已关闭 打回; do
  c=$(rg -l "状态：$s" docs/dispatch/ --glob '*.md' 2>/dev/null | grep -v legacy | wc -l | tr -d ' ')
  echo "- $s: $c" >> "$OUT"
done
echo "" >> "$OUT"

# 4. 未完成卡
echo "## 4. 非关闭卡" >> "$OUT"
rg -l "状态：(待分派|执行中|已回写|打回)" docs/dispatch/ --glob '*.md' 2>/dev/null | grep -v legacy | head -20 >> "$OUT"
echo "" >> "$OUT"

# 5. config.env存在性
echo "## 5. config.env: $(test -f server/config/config.env && echo 存在 || echo 缺失)" >> "$OUT"
echo "完成: $OUT"