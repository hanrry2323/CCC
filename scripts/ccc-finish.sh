#!/bin/bash
# ccc-finish.sh — CCC 任务完成后置门控（v1.2.0 新增 · T1.4）
#
# 5 项后置门控（任一 FAIL → exit 1，禁越界宣告完成）：
#   1. report.md 已写且非空（红线 4/8 + Lesson 4）
#   2. verdict.md 存在且 ≥3 adversarial probes（红线 11 · Lesson 28）
#   3. report.md 含 `> VERDICT:` 引用段（红线 11 · 强证据闭环）
#   4. 改动文件 ⊆ plan 范围白名单（红线 3）
#   5. 单 phase 单 commit 闭环：phases.json status=done 行数 ≥ plan phase 数
#
# 用法：
#   bash scripts/ccc-finish.sh                          # 当前 workspace + 当前 task
#   bash scripts/ccc-finish.sh <workspace> <task>       # 指定任务
#   bash scripts/ccc-finish.sh --fill-verdict-ref       # 自动回填 verdict 路径到 report.md

set -uo pipefail

# --- 参数解析 ---
FILL_VERDICT_REF=0
WORKSPACE=""
TASK=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --fill-verdict-ref) FILL_VERDICT_REF=1; shift ;;
    -h|--help)
      cat <<'EOF'
ccc-finish.sh — CCC 任务完成后置门控

用法:
  bash scripts/ccc-finish.sh                          # 当前 workspace + 当前 task
  bash scripts/ccc-finish.sh <workspace> <task>       # 指定任务
  bash scripts/ccc-finish.sh --fill-verdict-ref       # 自动回填 verdict 路径到 report.md

退出码:
  0 = 全部 PASS，任务可宣告完成
  1 = 任一 FAIL，必须修复后重跑
  2 = 参数错误
EOF
      exit 0 ;;
    *)
      if [[ -z "$WORKSPACE" ]]; then WORKSPACE="$1"; shift
      elif [[ -z "$TASK" ]]; then TASK="$1"; shift
      else echo "未知参数: $1" >&2; exit 2
      fi ;;
  esac
done

WORKSPACE="${WORKSPACE:-$(pwd)}"
TASK="${TASK:-$(ls -t "$WORKSPACE/.ccc/plans/"*.plan.md 2>/dev/null | head -1 | sed -E 's|.*/(.*)\.plan\.md$|\1|')}"

if [[ -z "$TASK" ]]; then
  echo "❌ 无法自动推断 task 名, 请显式传入: bash scripts/ccc-finish.sh <workspace> <task>" >&2
  exit 2
fi

PLAN_FILE="$WORKSPACE/.ccc/plans/$TASK.plan.md"
PHASES_FILE="$WORKSPACE/.ccc/phases/$TASK.phases.json"
REPORT_FILE="$WORKSPACE/.ccc/reports/$TASK.report.md"
VERDICT_FILE="$WORKSPACE/.ccc/verdicts/$TASK.verdict.md"

PASS_COUNT=0
FAIL_COUNT=0
declare -a FAILURES

log_pass() { echo "  [PASS] $1"; PASS_COUNT=$((PASS_COUNT+1)); }
log_fail() { echo "  [FAIL] $1"; FAIL_COUNT=$((FAIL_COUNT+1)); FAILURES+=("$1"); }
log_info() { echo "  [INFO] $1"; }

echo "=== ccc-finish.sh ==="
echo "  Workspace: $WORKSPACE"
echo "  Task:      $TASK"
echo "  Report:    $REPORT_FILE"
echo "  Verdict:   $VERDICT_FILE"
echo ""

# --- Gate 1: report.md 已写且非空（Lesson 4 修复）---
echo "──── Gate 1: report.md 已写且非空（Lesson 4） ────"
if [[ -f "$REPORT_FILE" ]] && [[ -s "$REPORT_FILE" ]]; then
  REPORT_SIZE=$(wc -l < "$REPORT_FILE" | tr -d ' ')
  log_pass "report.md 存在且非空（$REPORT_SIZE 行）"
else
  log_fail "report.md 不存在或为空: $REPORT_FILE — Lesson 4 触犯, 报告必须先写"
fi

# --- Gate 2: verdict.md 存在且 ≥3 probes（红线 11）---
echo "──── Gate 2: verdict.md 存在且 ≥3 probes（红线 11） ────"
if [[ ! -f "$VERDICT_FILE" ]]; then
  log_fail "verdict.md 不存在: $VERDICT_FILE — 红线 11 触犯, 口头 PASS 不算 PASS"
else
  log_pass "verdict.md 存在: $VERDICT_FILE"

  # 探针数量: ## Probe N 格式
  PROBE_COUNT=$(grep -cE '^## Probe [0-9]+' "$VERDICT_FILE" || echo 0)
  if [[ "$PROBE_COUNT" -ge 3 ]]; then
    log_pass "verdict.md 含 $PROBE_COUNT 个 adversarial probes (≥3)"
  else
    log_fail "verdict.md 仅 $PROBE_COUNT 个 probe, 需 ≥3"
  fi

  # VERDICT 三选一
  if grep -qE '^## VERDICT:|^VERDICT:|^> VERDICT:' "$VERDICT_FILE"; then
    if grep -qE 'VERDICT:\s*(PASS|CONDITIONAL_PASS|FAIL)' "$VERDICT_FILE"; then
      log_pass "verdict.md 含 VERDICT: PASS/CONDITIONAL_PASS/FAIL 三选一"
    else
      log_fail "verdict.md 含 VERDICT 字段但非三选一"
    fi
  else
    log_fail "verdict.md 缺 VERDICT 行"
  fi
fi

# --- Gate 3: report.md 含 `> VERDICT:` 引用段（红线 11 · 强证据闭环）---
echo "──── Gate 3: report.md 含 > VERDICT: 引用段（红线 11 · 闭环） ────"
if [[ ! -f "$REPORT_FILE" ]]; then
  log_fail "report.md 不存在, 跳过 VERDICT 引用检查"
else
  if grep -qE '^> VERDICT:|VERDICT:.*verdicts/.*\.verdict\.md' "$REPORT_FILE"; then
    # 检查是否指向正确路径
    EXPECTED_REF="verdicts/$TASK.verdict.md"
    if grep -q "$EXPECTED_REF" "$REPORT_FILE"; then
      log_pass "report.md 含 > VERDICT: 引用且指向正确路径 ($EXPECTED_REF)"
    else
      log_fail "report.md 含 VERDICT 引用但路径非 $EXPECTED_REF"
    fi
  else
    log_fail "report.md 缺 > VERDICT: 引用段 — 红线 11 闭环断点"

    # 自动回填模式
    if [[ $FILL_VERDICT_REF -eq 1 ]]; then
      echo "  [INFO] --fill-verdict-ref 模式: 尝试自动回填"
      if [[ -f "$REPORT_FILE" ]]; then
        # 在 report 顶部加 VERDICT 引用段
        REL_VERDICT_PATH=".ccc/verdicts/$TASK.verdict.md"
        if grep -q "^> VERDICT:" "$REPORT_FILE"; then
          log_fail "VERDICT 引用已存在但路径不匹配, 需人工检查"
        else
          TMPFILE=$(mktemp)
          {
            echo "> **VERDICT: $REL_VERDICT_PATH**"
            echo "> *(verifier 已写入, 见上方 Gate 2)*"
            echo ""
            cat "$REPORT_FILE"
          } > "$TMPFILE"
          mv "$TMPFILE" "$REPORT_FILE"
          log_pass "自动回填 VERDICT 引用成功: $REL_VERDICT_PATH"
        fi
      fi
    fi
  fi
fi

# --- Gate 4: 改动文件 ⊆ plan 范围白名单（红线 3）---
echo "──── Gate 4: 改动文件 ⊆ plan 范围白名单（红线 3） ────"
if ! git -C "$WORKSPACE" rev-parse --git-dir >/dev/null 2>&1; then
  log_fail "workspace 不是 git 仓库: $WORKSPACE"
else
  # 收集实际改动（working tree + 已暂存 + 范围从上次 commit 到 HEAD 的 diff）
  # 排除 .ccc/ (Plan 产物) + .claude/ (工具 metadata, 不属于源码)
  CHANGED_FILES=$(git -C "$WORKSPACE" status --short | awk '{print $2}' | grep -vE '^\.ccc/' | grep -vE '^\.claude/' | sort -u)

  # 如果无未提交改动, 改看最近 1 个 commit 的 diff (针对已 commit 的任务)
  if [[ -z "$CHANGED_FILES" ]]; then
    LAST_COMMIT_FILES=$(git -C "$WORKSPACE" show --name-only --format= HEAD | tail -n +2 | grep -vE '^\.ccc/' | grep -vE '^\.claude/' | sort -u)
    if [[ -n "$LAST_COMMIT_FILES" ]] && echo "$LAST_COMMIT_FILES" | grep -q "ccc-task-id=$TASK"; then
      CHANGED_FILES="$LAST_COMMIT_FILES"
      log_info "无 working tree 改动, 改用最近 ccc-task-id=$TASK 的 commit diff"
    fi
  fi

  if [[ -z "$CHANGED_FILES" ]]; then
    log_pass "无改动（可能已 commit 且未匹配 ccc-task-id）"
  else
    # 从 plan.md 提取"只改文件"白名单
    WHITELIST_PATTERN=$(python3 - "$PLAN_FILE" <<'PYEOF' 2>/dev/null
import sys, re, os
fp = sys.argv[1]
if not os.path.exists(fp):
    sys.exit(0)
text = open(fp).read()

# 方式 1: 找 "只改文件" 段（plan-spec.md 规范）
files = []
m = re.search(r'只改文件[:：].*?(?=\n##|\n- \*\*不改|$)', text, re.DOTALL)
if m:
    section = m.group(0)
    files += re.findall(r'`([^`]+)`', section)
    files += re.findall(r'`\*\*([^*]+)\*\*`', section)

# 方式 2: 找 "改动文件清单" 表格（fallback, 含 | `path` | 模式）
if not files:
    m2 = re.search(r'改动文件清单.*?(?=\n##|$)', text, re.DOTALL)
    if m2:
        files += re.findall(r'\|\s*`([^`]+)`\s*\|', m2.group(0))

# 方式 3: 找 "Phase N: 改动: <files>" 模式
if not files:
    files += re.findall(r'改动[:：]\s*`([^`]+)`', text)

# 输出去重
files = list(dict.fromkeys(files))
escaped = '|'.join(re.escape(f) for f in files)
print(escaped)
PYEOF
    )

    if [[ -z "$WHITELIST_PATTERN" ]]; then
      log_fail "plan.md 缺 '只改文件' 段, 无法验证范围"
    else
      OUT_OF_SCOPE=$(echo "$CHANGED_FILES" | grep -vE "$WHITELIST_PATTERN" || true)
      if [[ -z "$OUT_OF_SCOPE" ]]; then
        log_pass "所有改动 (${#CHANGED_FILES[@]} 文件) 均在 plan 范围内"
      else
        log_fail "越界改动 (红线 3 触犯):"
        for f in $OUT_OF_SCOPE; do
          echo "    - $f"
        done
      fi
    fi
  fi
fi

# --- Gate 5: 单 phase 单 commit 闭环（红线 4 + 8）---
echo "──── Gate 5: phases.json status=done 行数 ≥ plan phase 数（红线 4+8） ────"
if [[ ! -f "$PHASES_FILE" ]]; then
  log_fail "phases.json 不存在"
else
  PLAN_PHASES=$(python3 - "$PHASES_FILE" <<'PYEOF' 2>/dev/null
import sys
fp = sys.argv[1]
import json
count = 0
with open(fp) as f:
    for line in f:
        line = line.strip()
        if not line: continue
        try:
            json.loads(line)
            count += 1
        except: pass
print(count)
PYEOF
)
  PLAN_PHASES=$(echo "$PLAN_PHASES" | tr -d '\n' | head -1)
  DONE_PHASES=$(grep -cE '"status":\s*"done"' "$PHASES_FILE" 2>/dev/null | tr -d '\n' | head -1)
  DONE_PHASES="${DONE_PHASES:-0}"

  if [[ "$DONE_PHASES" -ge "$PLAN_PHASES" ]] && [[ "$PLAN_PHASES" -gt 0 ]]; then
    log_pass "phases.json done 行数 ($DONE_PHASES) ≥ plan phase 数 ($PLAN_PHASES)"
  else
    log_fail "phases.json done 行数 ($DONE_PHASES) < plan phase 数 ($PLAN_PHASES)"
  fi
fi

echo ""
echo "=== 汇总 ==="
echo "  PASS: $PASS_COUNT"
echo "  FAIL: $FAIL_COUNT"
if [[ $FAIL_COUNT -gt 0 ]]; then
  echo ""
  echo "失败项:"
  for f in "${FAILURES[@]}"; do
    echo "  - $f"
  done
  echo ""
  echo "❌ ccc-finish FAIL — 必须修复后重跑, 禁止宣告完成"
  exit 1
fi
echo ""
echo "✅ ccc-finish PASS — 任务可宣告完成, 4 文件契约闭环"
exit 0