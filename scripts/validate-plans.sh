#!/usr/bin/env bash
# scripts/validate-plans.sh — 方案文件格式校验
#
# 校验 docs/projects/<prefix>/plans/<NNN>-<slug>.md 是否合规。
# 用法:
#   scripts/validate-plans.sh                    # 全量校验
#   scripts/validate-plans.sh <path>              # 单文件校验
#   scripts/validate-plans.sh --prefix <prefix>   # 按前缀校验
#
# 校验项:
#   1. 路径必须在 docs/projects/<prefix>/plans/ 下
#   2. prefix 必须在 registry.yaml 中
#   3. NNN 必须恰好三位数字
#   4. slug 必须小写字母/数字/连字符
#   5. 扩展名必须 .md
#   6. 文件头必须包含必填字段（项目/编号/状态/作者/创建日期）
#   7. 状态必须在五态内

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PLANS_DIR="$REPO_ROOT/docs/projects"

# 从 registry.yaml 提取有效前缀（排除 null）
VALID_PREFIXES=$(grep -E '^\s+- prefix:' "$REPO_ROOT/docs/projects/registry.yaml" | \
  grep -v 'null' | awk '{print $3}' | sort -u || true)

# 有效状态
VALID_STATES="草案|已确认|部分执行|已完成|作废"

ERRORS=0
WARNINGS=0
CHECKED=0

red()  { echo -e "\033[31m$*\033[0m"; }
green(){ echo -e "\033[32m$*\033[0m"; }
yellow(){ echo -e "\033[33m$*\033[0m"; }

validate_file() {
  local file="$1"
  CHECKED=$((CHECKED + 1))
  local rel="${file#$REPO_ROOT/}"
  local fname="$(basename "$file")"

  # ── 1. 路径校验 ──
  # 提取 prefix 和 NNN-slug
  if ! echo "$rel" | grep -qE '^docs/projects/[a-z]{2,4}/plans/[0-9]{3}-[a-z0-9][-a-z0-9]*\.md$'; then
    red "  FAIL 路径格式: $rel"
    red "        期望: docs/projects/<prefix>/plans/<NNN>-<slug>.md"
    ERRORS=$((ERRORS + 1))
    return
  fi

  local prefix=$(echo "$rel" | sed -E 's|^docs/projects/([a-z]{2,4})/plans/.*|\1|')
  local num=$(echo "$fname" | sed -E 's/^([0-9]{3})-.*/\1/')
  local slug=$(echo "$fname" | sed -E 's/^[0-9]{3}-(.*)\.md$/\1/')

  # ── 2. prefix 校验 ──
  if ! echo "$VALID_PREFIXES" | grep -qxF "$prefix"; then
    red "  FAIL 前缀不在 registry: $prefix"
    ERRORS=$((ERRORS + 1))
    return
  fi

  # ── 3. NNN 校验 ──
  if ! echo "$num" | grep -qE '^[0-9]{3}$'; then
    red "  FAIL 编号非三位: $num"
    ERRORS=$((ERRORS + 1))
    return
  fi

  # ── 4. slug 校验 ──
  if ! echo "$slug" | grep -qE '^[a-z0-9][-a-z0-9]*$'; then
    red "  FAIL slug 非法: $slug（须小写字母/数字/连字符）"
    ERRORS=$((ERRORS + 1))
    return
  fi

  # ── 5. 扩展名校验 ──
  if ! echo "$fname" | grep -qE '\.md$'; then
    red "  FAIL 扩展名必须 .md"
    ERRORS=$((ERRORS + 1))
    return
  fi

  # ── 6. 文件头必填字段 ──
  local head_content
  head_content=$(head -30 "$file")

  local missing_fields=""
  echo "$head_content" | grep -q '项目：' || missing_fields="$missing_fields 项目"
  echo "$head_content" | grep -q '编号：' || missing_fields="$missing_fields 编号"
  echo "$head_content" | grep -q '状态：' || missing_fields="$missing_fields 状态"
  echo "$head_content" | grep -q '作者：' || missing_fields="$missing_fields 作者"
  echo "$head_content" | grep -q '创建：' || missing_fields="$missing_fields 创建日期"

  if [ -n "$missing_fields" ]; then
    red "  FAIL 缺少必填字段:$missing_fields"
    ERRORS=$((ERRORS + 1))
    return
  fi

  # ── 7. 状态校验 ──
  local status
  status=$(echo "$head_content" | grep '状态：' | head -1 | sed -E 's/.*状态：([^>]*).*/\1/' | tr -d ' ')
  if [ -n "$status" ] && ! echo "$status" | grep -qE "^($VALID_STATES)"; then
    red "  FAIL 状态非法: $status（须为: $VALID_STATES）"
    ERRORS=$((ERRORS + 1))
    return
  fi

  green "  OK   $rel"
}

# ── 主入口 ──
if [ $# -eq 0 ]; then
  # 全量校验
  echo "=== 方案文件全量校验 ==="
  echo ""

  find "$PLANS_DIR" -path "*/plans/*.md" -not -path "*/_template/*" 2>/dev/null | while read -r f; do
    validate_file "$f"
  done | sort

  echo ""
  if [ "$ERRORS" -eq 0 ]; then
    green "全部通过"
  else
    red "$ERRORS 个错误, $WARNINGS 个警告"
  fi

elif [ "$1" = "--prefix" ]; then
  prefix="${2:-}"
  if [ -z "$prefix" ]; then
    red "用法: $0 --prefix <prefix>"
    exit 1
  fi
  echo "=== 方案校验 · 前缀 $prefix ==="
  echo ""
  find "$PLANS_DIR/$prefix/plans" -name "*.md" 2>/dev/null | while read -r f; do
    validate_file "$f"
  done | sort
  echo ""

else
  # 单文件校验
  if [ ! -f "$1" ]; then
    red "文件不存在: $1"
    exit 1
  fi
  validate_file "$1"
fi

if [ "$ERRORS" -gt 0 ]; then
  exit 1
fi
exit 0