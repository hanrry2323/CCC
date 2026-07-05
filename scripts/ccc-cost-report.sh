#!/usr/bin/env bash
#
# ccc-cost-report.sh — 统计指定工作区 .ccc/reports/*.report.md 的成本指标
#
# Usage:
#   ccc-cost-report.sh [WORKSPACE]
#
# 如果未提供 WORKSPACE，则使用当前目录 (.)。
# 输出同时写到 stdout 和 <workspace>/.ccc/cost-report.md。
#
set -euo pipefail

WORKSPACE="${1:-.}"

# 规范化为绝对路径（如果存在），便于后续 mtime 比较
if [ -d "$WORKSPACE" ]; then
    WORKSPACE_ABS="$(cd "$WORKSPACE" && pwd)"
else
    echo "Error: workspace '$WORKSPACE' 不存在" >&2
    exit 1
fi

REPORTS_DIR="$WORKSPACE_ABS/.ccc/reports"
OUT_FILE="$WORKSPACE_ABS/.ccc/cost-report.md"

# 计算每个 report 文件的 frontmatter 字符数（仅在文件以 --- 起头时）
# 返回该文件的非 frontmatter 字符数（用于估算 token）。
body_chars_of() {
    local f="$1"
    awk '
        BEGIN { in_fm=0; fm_started=0; body_chars=0 }
        {
            if (fm_started == 0 && $0 == "---") {
                # 起始 frontmatter delimiter
                fm_started = 1
                in_fm = 1
                next
            }
            if (in_fm == 1) {
                if ($0 == "---") {
                    # 结束 frontmatter delimiter
                    in_fm = 0
                    next
                }
                # frontmatter 行，不计入 body
                next
            }
            body_chars += length($0) + 1
        }
        END { print body_chars + 0 }
    ' "$f"
}

# 收集所有 report 文件列表（数组）
REPORT_FILES=()
if [ -d "$REPORTS_DIR" ]; then
    while IFS= read -r -d '' f; do
        REPORT_FILES+=("$f")
    done < <(find "$REPORTS_DIR" -maxdepth 1 -type f -name '*.report.md' -print0 | sort -z)
fi

FILE_COUNT=${#REPORT_FILES[@]}

if [ "$FILE_COUNT" -eq 0 ]; then
    msg="未在 $REPORTS_DIR 找到任何 *.report.md 文件，无需统计。"
    echo "$msg"
    mkdir -p "$WORKSPACE_ABS/.ccc"
    {
        echo "# Cost Report"
        echo
        echo "$msg"
    } > "$OUT_FILE"
    exit 0
fi

TOTAL_LINES=0
TOTAL_BYTES=0
TOTAL_BODY_CHARS=0
EARLIEST_MTIME_EPOCH=9999999999
LATEST_MTIME_EPOCH=0
EARLIEST_MTIME_STR=""
LATEST_MTIME_STR=""

for f in "${REPORT_FILES[@]}"; do
    lines=$(wc -l < "$f" | tr -d ' ')
    TOTAL_LINES=$((TOTAL_LINES + lines))

    bytes=$(wc -c < "$f" | tr -d ' ')
    TOTAL_BYTES=$((TOTAL_BYTES + bytes))

    body_chars=$(body_chars_of "$f")
    TOTAL_BODY_CHARS=$((TOTAL_BODY_CHARS + body_chars))

    # 文件 mtime（秒）
    if [[ "$OSTYPE" == "darwin"* ]]; then
        mtime_epoch=$(stat -f '%m' "$f")
        mtime_str=$(stat -f '%Sm' "$f")
    else
        mtime_epoch=$(stat -c '%Y' "$f")
        mtime_str=$(stat -c '%y' "$f")
    fi

    if [ "$mtime_epoch" -lt "$EARLIEST_MTIME_EPOCH" ]; then
        EARLIEST_MTIME_EPOCH=$mtime_epoch
        EARLIEST_MTIME_STR=$mtime_str
    fi
    if [ "$mtime_epoch" -gt "$LATEST_MTIME_EPOCH" ]; then
        LATEST_MTIME_EPOCH=$mtime_epoch
        LATEST_MTIME_STR=$mtime_str
    fi
done

# token 估算：4 字符 ≈ 1 token，按正文（不含 frontmatter）
EST_TOKENS=$((TOTAL_BODY_CHARS / 4))

GENERATED_AT="$(date '+%Y-%m-%d %H:%M:%S %z')"

# 组装 markdown 输出
OUTPUT="# Cost Report

> 工作区：\`$WORKSPACE_ABS\`
> 生成时间：$GENERATED_AT

## 概览

| 指标 | 值 |
|------|----|
| 报告文件数 | $FILE_COUNT |
| 总行数 | $TOTAL_LINES |
| 总字节数 | $TOTAL_BYTES |
| 正文字符数（已跳过 YAML frontmatter） | $TOTAL_BODY_CHARS |
| 估算 token 数（≈ 4 字符 / token） | $EST_TOKENS |
| 最早 mtime | $EARLIEST_MTIME_STR |
| 最晚 mtime | $LATEST_MTIME_STR |

## 文件清单

| # | 路径 | 行数 | 字节数 | 正文字符数 | mtime |
|---|------|------|--------|------------|-------|
"

i=1
for f in "${REPORT_FILES[@]}"; do
    rel="${f#"$WORKSPACE_ABS"/}"
    lines=$(wc -l < "$f" | tr -d ' ')
    bytes=$(wc -c < "$f" | tr -d ' ')
    body_chars=$(body_chars_of "$f")
    if [[ "$OSTYPE" == "darwin"* ]]; then
        mtime_str=$(stat -f '%Sm' "$f")
    else
        mtime_str=$(stat -c '%y' "$f")
    fi
    OUTPUT+="| $i | \`$rel\` | $lines | $bytes | $body_chars | $mtime_str |"$'\n'
    i=$((i + 1))
done

# 写文件 + 输出
mkdir -p "$WORKSPACE_ABS/.ccc"
# 写文件：用 printf 保留末尾换行（与 stdout 一致）
printf '%s\n' "$OUTPUT" > "$OUT_FILE"

echo "$OUTPUT"