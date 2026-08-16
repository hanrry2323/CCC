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

# 从 registry.yaml 提取有效前缀（唯一真值：server/board/registry.py，消除 grep 双解析，ccc062）
# PYTHONPATH 指向本脚本真实所在仓（registry.py 定义处），兼容测试复制到临时目录的场景。
_CCC_ROOT_ABS="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON_BIN="${CCC_PYTHON_BIN:-python3}"
VALID_PREFIXES=$(PYTHONPATH="$_CCC_ROOT_ABS" "$PYTHON_BIN" -c "
import sys
from server.board.registry import card_prefixes
print('\\n'.join(sorted(card_prefixes(sys.argv[1]))))
" "$REPO_ROOT/docs/projects/registry.yaml" 2>/dev/null || true)

# 有效状态（ccc-plan-027 状态机统一：方案层去「草案」，草案概念归线路图草案池；已覆盖为兼容旧值）
# 033 F1+M4（2026-08-16）：补「已确定」（Plan 调研态）+「待验收」（卡全关待老板拍板）
VALID_STATES="已确定|待排期|部分执行|待验收|已完成|作废|已覆盖"

ERRORS=0
WARNINGS=0
CHECKED=0

red()  { echo -e "\033[31m$*\033[0m"; }
green(){ echo -e "\033[32m$*\033[0m"; }
yellow(){ echo -e "\033[33m$*\033[0m"; }

# ── 开发卡三要素校验辅助（2026-08-16 子项目层）──
# 功能卡块必须含 颗粒度/依赖/架构位置 声明（颗粒度只查存在性促思考，不硬判大小）。
# 新模型子项目方案（头含「子项目：」）缺三要素=FAIL；旧方案缺=WARN 兼容存量。
_check_func_card_three() {
  local block="$1" rel="$2" is_sp="$3"
  local title=""
  title=$(echo "$block" | grep -m1 '^### ' | sed 's/^### //' | tr -d '\r' || true)
  local missing=""
  echo "$block" | grep -qE '^颗粒度：' || missing="$missing 颗粒度"
  echo "$block" | grep -qE '^依赖：' || missing="$missing 依赖"
  echo "$block" | grep -qE '^架构位置：' || missing="$missing 架构位置"
  if [ -n "$missing" ]; then
    if [ -n "$is_sp" ]; then
      # 注：bash set -u 下全角「」紧跟 $var 会解析错乱，必须 ${var} 定界
      red "  FAIL 功能卡「${title}」缺三要素:${missing}（子项目方案必填）: $rel"
      ERRORS=$((ERRORS + 1))
    else
      yellow "  WARN 功能卡「${title}」缺三要素:${missing}（旧方案兼容，新方案必填）: $rel"
      WARNINGS=$((WARNINGS + 1))
    fi
  fi
}

# ── 功能卡依赖悬空校验（2026-08-16）──
# 依赖项若是卡 ID（[a-z]{2,4}\d{3}）必须存在对应卡文件，否则 FAIL；若是本方案功能卡标题则跳过（同批解析）。
_check_func_card_dep_dangling() {
  local deps="$1" rel="$2"
  local d
  for d in $(echo "$deps" | tr ',，、 ' '\n' | sed '/^$/d'); do
    if echo "$d" | grep -qE '^[a-z]{2,4}[0-9]{3}$'; then
      if ! find "$REPO_ROOT/docs/dispatch" -iname "${d}-*.md" -print -quit 2>/dev/null | grep -q .; then
        red "  FAIL 功能卡依赖悬空（卡 $d 不存在）: $rel"
        ERRORS=$((ERRORS + 1))
      fi
    fi
  done
}

# ── 单功能卡块校验聚合（三要素 + 依赖悬空）──
_check_func_card_block() {
  local block="$1" rel="$2" is_sp="$3"
  _check_func_card_three "$block" "$rel" "$is_sp"
  local deps_line
  deps_line=$(echo "$block" | grep -E '^依赖：' | head -1 | sed 's/^依赖：//' | tr -d '\r' || true)
  if [ -n "$deps_line" ]; then
    _check_func_card_dep_dangling "$deps_line" "$rel"
  fi
}

validate_file() {
  local file="$1"
  CHECKED=$((CHECKED + 1))
  local rel="${file#$REPO_ROOT/}"
  local fname="$(basename "$file")"

  # ── 0. 附加文档跳过（2026-08-17 补）──
  # 非 <NNN>-<ascii-slug>.md 的 plans/*.md 视为方案附加文档（验收打回/点验记录等），
  # 不按方案校验（路径格式/必填字段/编号唯一性均不适用）。
  if ! echo "$rel" | grep -qE '^docs/projects/[a-z]{2,4}/plans/[0-9]{3}-[a-z0-9][-a-z0-9]*\.md$'; then
    return
  fi

  local prefix=$(echo "$rel" | sed -E 's|^docs/projects/([a-z]{2,4})/plans/.*|\1|')
  local num=$(echo "$fname" | sed -E 's/^([0-9]{3})-.*/\1/')
  local slug=$(echo "$fname" | sed -E 's/^[0-9]{3}-(.*)\.md$/\1/')

  # ── 2. prefix 校验 ──
  # ccc 平台自研方案允许存在与查看（2026-08-10 红线仅禁转卡，由 server/board/plans.py convert 拦截）
  if ! echo "$VALID_PREFIXES" | grep -qxF "$prefix" && [ "$prefix" != "ccc" ]; then
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
  status=$(echo "$head_content" | grep '状态：' | head -1 | sed -E 's/.*状态：([^ ]+).*/\1/' | tr -d ' ')
  if [ -n "$status" ] && ! echo "$status" | grep -qE "^($VALID_STATES)"; then
    red "  FAIL 状态非法: ${status}（须为: ${VALID_STATES}）"
    ERRORS=$((ERRORS + 1))
    return
  fi

  # ── 7.5 功能卡段校验（ccc-plan-027 + 2026-08-16 三要素/依赖悬空）──
  if grep -qE '^## 功能卡' "$file"; then
    local fc_section
    fc_section=$(awk '/^## 功能卡/{f=1;next} f&&/^## /{f=0} f' "$file")
    if ! echo "$fc_section" | grep -qE '^### '; then
      red "  FAIL 功能卡段缺少「### 功能卡标题」小节: $rel"
      ERRORS=$((ERRORS + 1))
      return
    fi
    # 新模型子项目方案判定：方案头含「子项目：」字段（未加字段的旧方案只 WARN 不阻断）
    local is_sp=""
    if echo "$head_content" | grep -q '子项目：'; then
      is_sp="1"
    fi
    # 逐功能卡块：三要素存在性 + 依赖悬空（bash3 兼容：进程替换保主 shell 作用域）
    local cblock="" block_no=0
    while IFS= read -r fline; do
      if echo "$fline" | grep -qE '^### '; then
        if [ "$block_no" -gt 0 ]; then
          _check_func_card_block "$cblock" "$rel" "$is_sp"
        fi
        cblock="$fline"
        block_no=$((block_no + 1))
      else
        cblock="${cblock}"$'\n'"${fline}"
      fi
    done < <(printf '%s\n' "$fc_section")
    if [ "$block_no" -gt 0 ]; then
      _check_func_card_block "$cblock" "$rel" "$is_sp"
    fi
  fi

  # ── 7.6 环境准备声明（2026-08-16 子项目层）：新模型子项目方案必须声明「环境准备：」──
  if echo "$head_content" | grep -q '子项目：'; then
    if ! echo "$head_content" | grep -q '环境准备：'; then
      red "  FAIL 子项目方案缺「环境准备」声明: $rel"
      ERRORS=$((ERRORS + 1))
      return
    fi
  fi

  # ── 8. 方案级收尾校验 ──
  # 8.1 方案「已完成」但验收未勾选 -> 报错
  if [ "$status" = "已完成" ]; then
    local in_acceptance=0
    local unchecked_count=0
    local total_count=0
    while IFS= read -r line; do
      if echo "$line" | grep -qE '^## 验收标准'; then
        in_acceptance=1
        continue
      fi
      if [ "$in_acceptance" -eq 1 ]; then
        if echo "$line" | grep -qE '^##'; then
          in_acceptance=0
          break
        fi
        if echo "$line" | grep -qE '^[*-]\s*\[[ xX]*\]'; then
          total_count=$((total_count + 1))
          if echo "$line" | grep -qE '^[*-]\s*\[\s*\]'; then
            unchecked_count=$((unchecked_count + 1))
          fi
        fi
      fi
    done < "$file"

    if [ "$unchecked_count" -gt 0 ]; then
      red "  FAIL 方案已完成但验收未勾选: $rel ($unchecked_count 个未勾选)"
      ERRORS=$((ERRORS + 1))
      return
    fi
  fi

  # 8.2 方案关联卡已全部关闭/作废但方案状态仍为待排期/部分执行（未推进） -> 报错
  # 8.3 作废方案的关联卡必须已关闭/已作废（存在活跃卡 = 孤儿卡） -> 报错
  # 人审调整动作统一化（2026-08-14）：作废=终态，作废卡从方案总数剔除；作废方案不得留孤儿卡。
  if [ "$status" = "待排期" ] || [ "$status" = "部分执行" ] || [ "$status" = "作废" ]; then
    local cards_line
    cards_line=$(echo "$head_content" | grep '关联卡：' | head -1 || true)
    if [ -n "$cards_line" ]; then
      local cards_part
      cards_part=$(echo "$cards_line" | sed -E 's/^.*关联卡：//' | tr -d '\r\n')
      if [ -n "$cards_part" ] && [ "$cards_part" != "无" ]; then
        local card_count=0
        local active_count=0

        # Clean characters like · , and Chinese variants to spaces
        local cleaned_cards=$(echo "$cards_part" | tr '·,()（）' ' ' | tr -s ' ')
        for word in $cleaned_cards; do
          if [[ "$word" =~ ^[a-zA-Z]+-?[0-9]+ ]]; then
            card_count=$((card_count + 1))
            local card_file=""
            card_file=$(find "$REPO_ROOT/docs/dispatch" \( -iname "${word}.md" -o -iname "${word}-*.md" \) -print -quit 2>/dev/null)
            if [ -n "$card_file" ] && [ -f "$card_file" ]; then
              local card_head=$(head -15 "$card_file" 2>/dev/null)
              local c_status=$(echo "$card_head" | grep '状态：' | head -1 | sed -E 's/.*状态：([^ ·\t\r\n]+).*/\1/' | tr -d ' ' || true)
              if [ "$c_status" != "已关闭" ] && [ "$c_status" != "作废" ]; then
                # 活跃卡（未关闭且未作废）；待分派/已回写可能远端滞后，额外 WARN
                active_count=$((active_count + 1))
                if [ "$c_status" = "待分派" ] || [ "$c_status" = "已回写" ]; then
                  yellow "  WARN 方案关联卡本地状态为 '$c_status'（可能滞后，远端可能已关闭/作废）: $word → $rel"
                  WARNINGS=$((WARNINGS + 1))
                fi
              fi
            else
              # If card file is not found, treat as active to be safe
              active_count=$((active_count + 1))
            fi
          fi
        done

        if [ "$status" = "作废" ]; then
          # 8.3：作废方案不得留孤儿卡
          if [ "$card_count" -gt 0 ] && [ "$active_count" -gt 0 ]; then
            red "  FAIL 作废方案存在孤儿卡（关联卡未作废/未关闭）: $rel"
            ERRORS=$((ERRORS + 1))
            return
          fi
        else
          # 8.2：待排期/部分执行 但关联卡已全部关闭/作废（未推进）
          if [ "$card_count" -gt 0 ] && [ "$active_count" -eq 0 ]; then
            red "  FAIL 方案关联卡已全部关闭/作废但状态仍为 '$status': $rel"
            ERRORS=$((ERRORS + 1))
            return
          fi
        fi
      fi
    fi
  fi

  green "  OK   $rel"
}

# ── 9. 全局编号唯一性校验（2026-08-14 补 · 并发窗口撞号拦截）──
# 同前缀 NNN 必须全局唯一；命中即报错。兼容 macOS bash3（无关联数组）。
# 2026-08-17 补：只统计合法方案文件名（<NNN>-<ascii-slug>.md，与 check_file 路径校验同款），
# 排除验收打回/点验记录等附加文档（slug 含中文，非独立方案，否则误报撞号）。
check_unique_numbers() {
  local dir="$1"
  local keys=()
  while read -r f; do
    [ -z "$f" ] && continue
    local rel="${f#$REPO_ROOT/}"
    # 与 validate_file 第 1 步同款：非 <NNN>-<ascii-slug>.md 的文件不参与编号唯一性
    if ! echo "$rel" | grep -qE '^docs/projects/[a-z]{2,4}/plans/[0-9]{3}-[a-z0-9][-a-z0-9]*\.md$'; then
      continue
    fi
    local prefix
    prefix=$(echo "$rel" | sed -E 's|^docs/projects/([a-z]{2,4})/plans/.*|\1|')
    local num
    num=$(basename "$f" | sed -E 's/^([0-9]{3})-.*/\1/')
    keys+=("$prefix/$num")
  done < <(find "$dir" -path "*/plans/*.md" -not -path "*/_template/*" 2>/dev/null | sort)

  local dup_keys
  dup_keys=$(printf '%s\n' "${keys[@]}" | sort | uniq -d)
  if [ -n "$dup_keys" ]; then
    # for 循环而非 while read <<<（bash 3.2 + set -u 下 here-string 崩溃，2026-08-14 修）
    for k in $dup_keys; do
      [ -z "$k" ] && continue
      red "  FAIL 方案编号重复: ${k}（同前缀 NNN 必须唯一——多窗口并发出卡/方案会撞号）"
      ERRORS=$((ERRORS + 1))
    done
  fi
}

# ── 主入口 ──
if [ $# -eq 0 ]; then
  # 全量校验
  echo "=== 方案文件全量校验 ==="
  echo ""

  while read -r f; do
    validate_file "$f"
  done < <(find "$PLANS_DIR" -path "*/plans/*.md" -not -path "*/_template/*" 2>/dev/null | sort)

  check_unique_numbers "$PLANS_DIR"

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
  while read -r f; do
    validate_file "$f"
  done < <(find "$PLANS_DIR/$prefix/plans" -name "*.md" 2>/dev/null | sort)
  check_unique_numbers "$PLANS_DIR/$prefix"
  echo ""
  if [ "$ERRORS" -eq 0 ]; then
    green "全部通过"
  else
    red "$ERRORS 个错误, $WARNINGS 个警告"
  fi

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
