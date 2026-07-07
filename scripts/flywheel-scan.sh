#!/bin/bash
# flywheel-scan.sh — 飞轮扫描器（v0.9b 简化版）
#
# 职责：扫描 .ccc/reports/ + .ccc/verdicts/ + ~/.ccc/alerts/
#       抽取失败模式 → 写入 .ccc/abnormal-reports/flywheel-candidate-<date>.md
#       人工 review 后才合并到 red-lines.md（红线 18 强制）
#
# 简化版 vs 全功能版：
# - 不接 LLM 归纳（避免伪发现）—— 只做 grep + 模式匹配
# - 触发方式：手动跑 / launchd 每日 02:00
# - 输出：候选清单 + 出现次数 + 时间分布
set -uo pipefail

CCC_DIR="${CCC_DIR:-$HOME/program/CCC}"
WORKSPACE="${1:-$PWD}"
REPORT_DATE=$(date +%Y-%m-%d)
ABNORMAL_DIR="$WORKSPACE/.ccc/abnormal-reports"
mkdir -p "$ABNORMAL_DIR"

OUT_FILE="$ABNORMAL_DIR/flywheel-candidate-$REPORT_DATE.md"

# 失败模式关键词（可扩展）
PATTERNS=(
  "exit_code.*[1-9]"
  "FAIL:"
  "killed.*true"
  "timeout after"
  "VERDICT: FAIL"
  "ModuleNotFoundError"
  "Permission denied"
  "ECONNREFUSED"
  "Unexpected server error"
)

echo "# Flywheel Candidates ($REPORT_DATE)" > "$OUT_FILE"
echo "" >> "$OUT_FILE"
echo "扫描源:" >> "$OUT_FILE"
echo "- $WORKSPACE/.ccc/reports/*.md（Executor 报告）" >> "$OUT_FILE"
echo "- $WORKSPACE/.ccc/verdicts/*.md（Verifier 验收，**权威**）" >> "$OUT_FILE"
echo "" >> "$OUT_FILE"
echo "排除: ~/.ccc/alerts/*.md（告警字面量含 FAIL 字符串但不是真失败，红线 18 防伪发现）" >> "$OUT_FILE"
echo "" >> "$OUT_FILE"
echo "## 候选失败模式（出现次数 ≥ 3 才列）" >> "$OUT_FILE"
echo "" >> "$OUT_FILE"

# 模式 → 搜索范围白名单（并行数组，bash 3.2 兼容）
# 防止 v0.9b 的伪发现：alert 标题含 "opencode FAIL:" 字样被误判
SCOPES=(
  "$WORKSPACE/.ccc/reports/"     # exit_code.*[1-9]
  "$WORKSPACE/.ccc/verdicts/"    # FAIL:
  "$WORKSPACE/.ccc/reports/"     # killed.*true
  "$WORKSPACE/.ccc/reports/"     # timeout after
  "$WORKSPACE/.ccc/verdicts/"    # VERDICT: FAIL
  "$WORKSPACE/.ccc/reports/"     # ModuleNotFoundError
  "$WORKSPACE/.ccc/reports/"     # Permission denied
  "$WORKSPACE/.ccc/reports/"     # ECONNREFUSED
  "$WORKSPACE/.ccc/reports/"     # Unexpected server error
)

THRESHOLD=3
TOTAL=0
for i in "${!PATTERNS[@]}"; do
  pat="${PATTERNS[$i]}"
  scope="${SCOPES[$i]}"
  COUNT=$(grep -rh "$pat" "$scope" 2>/dev/null | wc -l | tr -d ' ')
  if [[ $COUNT -ge $THRESHOLD ]]; then
    echo "- **$pat**: $COUNT 次 (scope: $(basename $scope))" >> "$OUT_FILE"
    TOTAL=$((TOTAL+1))
  fi
done

if [[ $TOTAL -eq 0 ]]; then
  echo "（无候选模式，全部通过）" >> "$OUT_FILE"
else
  echo "" >> "$OUT_FILE"
  echo "## 下一步" >> "$OUT_FILE"
  echo "1. 人工 review 本清单" >> "$OUT_FILE"
  echo "2. 拍板合并 → 编辑 references/red-lines.md" >> "$OUT_FILE"
  echo "3. 或标记 false positive 忽略" >> "$OUT_FILE"
  echo "" >> "$OUT_FILE"
  echo "红线 18：飞轮候选必须人工 review 才合并。**禁止**自动写 red-lines.md。" >> "$OUT_FILE"
fi

echo "✅ 飞轮扫描完成: $OUT_FILE (候选 $TOTAL 项)"
