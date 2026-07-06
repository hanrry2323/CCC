#!/bin/bash
# ccc-cost.sh — 单任务成本核算
#
# 根据 .ccc/reports/<task>.report.md 与 git log 中的 ccc-task-id=<task>
# commit 信息,输出 commits 数 / 涉及文件数 / report 路径。
#
# 用法:
#   bash scripts/ccc-cost.sh --task <name>
#
# 退出码:
#   0  成功
#   2  参数缺失或 report 缺失

set -euo pipefail

WORKSPACE="${CCC_WORKSPACE:-$(pwd)}"
CCC_DIR="$WORKSPACE/.ccc"
REPORTS_DIR="$CCC_DIR/reports"

usage() {
  cat <<'EOF'
ccc-cost.sh — 单任务成本核算

用法:
  bash scripts/ccc-cost.sh --task <name>

示例:
  bash scripts/ccc-cost.sh --task hello-ccc-demo
EOF
}

TASK=""
for arg in "$@"; do
  case "$arg" in
    --task)
      shift
      TASK="${1:-}"
      ;;
    --task=*)
      TASK="${arg#--task=}"
      ;;
    -h|--help)
      usage
      exit 0
      ;;
  esac
done

if [[ -z "$TASK" ]]; then
  echo "ERROR: --task <name> is required" >&2
  usage >&2
  exit 2
fi

REPORT_PATH="$REPORTS_DIR/$TASK.report.md"
if [[ ! -f "$REPORT_PATH" ]]; then
  echo "ERROR: report not found: $REPORT_PATH" >&2
  exit 2
fi

# 统计该 task 的 commit 数
COMMIT_COUNT=$(git -C "$WORKSPACE" log --oneline --grep "ccc-task-id=$TASK" | wc -l | tr -d ' ')

# 收集所有相关 commit 涉及的文件 (去重)
FILES_TMP=$(mktemp)
trap 'rm -f "$FILES_TMP"' EXIT

COMMITS=$(git -C "$WORKSPACE" log --format=%H --grep "ccc-task-id=$TASK")
if [[ -n "$COMMITS" ]]; then
  while IFS= read -r sha; do
    [[ -z "$sha" ]] && continue
    git -C "$WORKSPACE" show --name-only --format= "$sha" >> "$FILES_TMP" || true
  done <<< "$COMMITS"
fi

# 去重 + 去掉空行
FILE_COUNT=$(grep -v '^$' "$FILES_TMP" 2>/dev/null | sort -u | wc -l | tr -d ' ')

cat <<EOF
task: $TASK
commits: $COMMIT_COUNT
files: $FILE_COUNT
report: $REPORT_PATH
EOF

exit 0