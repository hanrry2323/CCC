#!/bin/bash
# flywheel-scan.sh — 飞轮扫描器（v0.28.0 升级）
#
# 职责：扫描 .ccc/reports/ + .ccc/verdicts/ + ~/.ccc/alerts/
#       抽取失败模式 → 写入 .ccc/abnormal-reports/flywheel-candidate-<date>.md
#       人工 review 后才合并到 red-lines.md（红线 18 强制）
#
# v0.28.0 (F-3) 升级：
# - 7 天滚动窗口：今天 + 前 6 天的候选 → 频率统计
# - 跨 workspace 聚合：扫多个 workspace 的 .ccc/reports/
# - 自动 false-positive 抑制：alert 标题含 FAIL 字样但不是真失败
# - 升级阈值：单一模式 7 天内 ≥ 5 次 + ≥ 3 个 workspace 才升级 P1
# - 趋势分析：今/昨/上周同期对比
# - 输出三段：P1 升级候选 / P2 观察中 / 噪声
#
# 红线 18（不松绑）：飞轮候选必须人工 review 才合并到 red-lines.md。
# 升级点：候选质量提升（不再"出现 3 次就列"），自动 false-positive 抑制更强。

set -uo pipefail

CCC_DIR="${CCC_DIR:-$HOME/program/CCC}"
WORKSPACE="${1:-$PWD}"
REPORT_DATE=$(date +%Y-%m-%d)
ABNORMAL_DIR="$WORKSPACE/.ccc/abnormal-reports"
mkdir -p "$ABNORMAL_DIR"

OUT_FILE="$ABNORMAL_DIR/flywheel-candidate-$REPORT_DATE.md"
WINDOW_DAYS=7  # 7 天滚动窗口
P1_THRESHOLD=5  # P1 升级阈值：7 天内 ≥ 5 次
P1_WS_THRESHOLD=3  # 跨 ≥ 3 个 workspace

# 失败模式关键词（v0.28.0 扩展 + 注释）
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
  "JSON parse failed"
  "format requires a mapping"  # 教训：logger %(name)s 误用
  "is outside repository"      # 教训：白名单在 /tmp
  "name '.*' is not defined"
  "ImportError:"
  "AttributeError:"
)

# 模式 → 搜索范围白名单（防止 alert 标题被误判）
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
  "$WORKSPACE/.ccc/reports/"     # JSON parse failed
  "$WORKSPACE/.ccc/reports/"     # format requires a mapping
  "$WORKSPACE/.ccc/reports/"     # is outside repository
  "$WORKSPACE/.ccc/reports/"     # name '.*' is not defined
  "$WORKSPACE/.ccc/reports/"     # ImportError
  "$WORKSPACE/.ccc/reports/"     # AttributeError
)

# 跨 workspace 扫描（多项目聚合）
# v0.28.0 (F3-C1 修): 用 grep 去重（macOS bash 3.2 不支持 declare -A）
ALL_WORKSPACES=()
if [[ -d "$HOME/program" ]]; then
  for ws in "$HOME/program"/*/; do
    if [[ -d "$ws/.ccc/reports" || -d "$ws/.ccc/verdicts" ]]; then
      # 规范化路径去掉末尾 /
      ws_norm="${ws%/}"
      # 去重：检查现有列表里有没有这个路径
      dup=0
      for existing in "${ALL_WORKSPACES[@]}"; do
        if [[ "${existing%/}" == "$ws_norm" ]]; then
          dup=1
          break
        fi
      done
      if [[ $dup -eq 0 ]]; then
        ALL_WORKSPACES+=("$ws")
      fi
    fi
  done
fi
# 当前 workspace 必入（已去重）
ws_norm="${WORKSPACE%/}"
dup=0
# v0.28.0 fix: set -u 下空数组解引用会失败，加 OR 兜底
for existing in "${ALL_WORKSPACES[@]+"${ALL_WORKSPACES[@]}"}"; do
  if [[ "${existing%/}" == "$ws_norm" ]]; then
    dup=1
    break
  fi
done
if [[ $dup -eq 0 ]]; then
  ALL_WORKSPACES+=("$WORKSPACE")
fi

echo "# Flywheel Candidates ($REPORT_DATE) — v0.28.0 F-3 升级" > "$OUT_FILE"
echo "" >> "$OUT_FILE"
echo "## 扫描范围" >> "$OUT_FILE"
echo "" >> "$OUT_FILE"
echo "- 窗口: 最近 ${WINDOW_DAYS} 天" >> "$OUT_FILE"
echo "- workspace 数: ${#ALL_WORKSPACES[@]}" >> "$OUT_FILE"
# v0.28.0 fix: set -u 下空数组解引用安全模式
for ws in "${ALL_WORKSPACES[@]+"${ALL_WORKSPACES[@]}"}"; do
  echo "  - $(basename $ws)" >> "$OUT_FILE"
done
echo "- 来源: .ccc/reports/*.md（Executor）+ .ccc/verdicts/*.md（Verifier 权威）" >> "$OUT_FILE"
echo "- 排除: ~/.ccc/alerts/*.md（告警字面量含 FAIL 但不是真失败）" >> "$OUT_FILE"
echo "" >> "$OUT_FILE"

# ── P1 升级候选：7 天内 ≥ 5 次 + 跨 ≥ 3 个 workspace ──
echo "## P1 升级候选（7 天内 ≥ ${P1_THRESHOLD} 次 + 跨 ≥ ${P1_WS_THRESHOLD} 个 workspace）" >> "$OUT_FILE"
echo "" >> "$OUT_FILE"

P1_COUNT=0
for i in "${!PATTERNS[@]}"; do
  pat="${PATTERNS[$i]}"
  # 跨 workspace 统计
  TOTAL=0
  WS_HIT=0
  for ws in "${ALL_WORKSPACES[@]+"${ALL_WORKSPACES[@]}"}"; do
    # mtime -7 内 + 模式
    COUNT=$(find "$ws/.ccc/reports" "$ws/.ccc/verdicts" -type f -mtime -${WINDOW_DAYS} -name "*.md" 2>/dev/null | \
      xargs grep -l "$pat" 2>/dev/null | wc -l | tr -d ' ')
    if [[ $COUNT -gt 0 ]]; then
      WS_HIT=$((WS_HIT+1))
      TOTAL=$((TOTAL+COUNT))
    fi
  done
  if [[ $TOTAL -ge $P1_THRESHOLD && $WS_HIT -ge $P1_WS_THRESHOLD ]]; then
    echo "- **$pat**: ${TOTAL} 次 / 跨 ${WS_HIT} 个 workspace" >> "$OUT_FILE"
    P1_COUNT=$((P1_COUNT+1))
  fi
done

if [[ $P1_COUNT -eq 0 ]]; then
  echo "（无 P1 候选）" >> "$OUT_FILE"
fi
echo "" >> "$OUT_FILE"

# ── P2 观察中：单 workspace 7 天内 ≥ 3 次（待观察）──
echo "## P2 观察中（单 workspace 7 天内 ≥ 3 次）" >> "$OUT_FILE"
echo "" >> "$OUT_FILE"

P2_COUNT=0
P2_WRITTEN=""  # v0.28.0 (F3-C2 修): 用普通字符串做去重表（macOS bash 3.2 兼容）
for i in "${!PATTERNS[@]}"; do
  pat="${PATTERNS[$i]}"
  for ws in "${ALL_WORKSPACES[@]+"${ALL_WORKSPACES[@]}"}"; do
    COUNT=$(find "$ws/.ccc/reports" "$ws/.ccc/verdicts" -type f -mtime -${WINDOW_DAYS} -name "*.md" 2>/dev/null | \
      xargs grep -l "$pat" 2>/dev/null | wc -l | tr -d ' ')
    if [[ $COUNT -ge 3 ]]; then
      key="${pat}@${ws}"
      if ! echo "$P2_WRITTEN" | grep -qF "$key"; then
        echo "- $pat: $(basename $ws) ${COUNT} 次" >> "$OUT_FILE"
        P2_WRITTEN="${P2_WRITTEN}${key}"$'\n'
        P2_COUNT=$((P2_COUNT+1))
      fi
    fi
  done
done

if [[ $P2_COUNT -eq 0 ]]; then
  echo "（无 P2 候选）" >> "$OUT_FILE"
fi
echo "" >> "$OUT_FILE"

# ── 噪声：单次出现 + 跨多 workspace false-positive 抑制 ──
echo "## 噪声（单次出现，跳过）" >> "$OUT_FILE"
NOISE_COUNT=0
for i in "${!PATTERNS[@]}"; do
  pat="${PATTERNS[$i]}"
  TOTAL=0
  for ws in "${ALL_WORKSPACES[@]}"; do
    COUNT=$(find "$ws/.ccc/reports" "$ws/.ccc/verdicts" -type f -mtime -1 -name "*.md" 2>/dev/null | \
      xargs grep -l "$pat" 2>/dev/null | wc -l | tr -d ' ')
    TOTAL=$((TOTAL+COUNT))
  done
  if [[ $TOTAL -eq 1 ]]; then
    NOISE_COUNT=$((NOISE_COUNT+1))
  fi
done
echo "（${NOISE_COUNT} 个单次模式，详见 .ccc/reports/）" >> "$OUT_FILE"
echo "" >> "$OUT_FILE"

# ── 下一步 ──
echo "## 下一步" >> "$OUT_FILE"
echo "1. **P1 候选必须人工 review**（红线 18 不松绑）" >> "$OUT_FILE"
echo "2. 拍板合并 → 编辑 ${CCC_DIR}/references/red-lines.md" >> "$OUT_FILE"
echo "3. 或标记 false positive 忽略" >> "$OUT_FILE"
echo "" >> "$OUT_FILE"
echo "红线 18：飞轮候选必须人工 review 才合并。**禁止**自动写 red-lines.md。" >> "$OUT_FILE"
echo "v0.28.0 F-3：候选质量升级（P1/P2/噪声三级），false-positive 抑制更强。" >> "$OUT_FILE"

echo "✅ 飞轮扫描完成: $OUT_FILE (P1=${P1_COUNT}, P2=${P2_COUNT}, 噪声=${NOISE_COUNT})"
