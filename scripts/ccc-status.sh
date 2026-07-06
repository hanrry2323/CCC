#!/bin/bash
# ccc-status.sh — CCC 4 文件契约健康检查
#
# 检查 .ccc/ 下 4 个契约文件的状态:
#   - profile.md          (项目档案)
#   - state.md            (跨会话状态接力)
#   - plans/*.plan.md     (任务计划)
#   - reports/*.report.md (执行报告)
#
# 用法:
#   bash scripts/ccc-status.sh                # 人类可读文本输出
#   bash scripts/ccc-status.sh --json         # JSON 输出

set -euo pipefail

WORKSPACE="${CCC_WORKSPACE:-$(pwd)}"
CCC_DIR="$WORKSPACE/.ccc"
JSON_MODE=0

for arg in "$@"; do
  case "$arg" in
    --json) JSON_MODE=1 ;;
    -h|--help)
      cat <<'EOF'
ccc-status.sh — CCC 4 文件契约健康检查

用法:
  bash scripts/ccc-status.sh                # 文本输出
  bash scripts/ccc-status.sh --json         # JSON 输出
  CCC_WORKSPACE=/path bash scripts/ccc-status.sh
EOF
      exit 0 ;;
  esac
done

# 文件存在性标记: "ok" 或 "missing"
status_of() {
  if [[ -f "$1" ]] && [[ -s "$1" ]]; then echo "ok"; else echo "missing"; fi
}

check_ccc_files() {
  local profile_state state_state plans_count tasks_state

  profile_state=$(status_of "$CCC_DIR/profile.md")
  state_state=$(status_of "$CCC_DIR/state.md")

  plans_count=0
  tasks_state="missing"
  if [[ -d "$CCC_DIR/plans" ]]; then
    plans_count=$(find "$CCC_DIR/plans" -maxdepth 1 -type f -name '*.plan.md' | wc -l | tr -d ' ')
  fi
  if [[ -d "$CCC_DIR/reports" ]]; then
    local report_count
    report_count=$(find "$CCC_DIR/reports" -maxdepth 1 -type f -name '*.report.md' | wc -l | tr -d ' ')
    if [[ "$report_count" -gt 0 ]]; then
      tasks_state="ok"
    fi
  fi

  echo "=== CCC 4-file contract check ==="
  echo "  workspace:     $WORKSPACE"
  echo "  .ccc/profile.md: $profile_state  → $CCC_DIR/profile.md"
  echo "  .ccc/state.md:   $state_state    → $CCC_DIR/state.md"
  echo "  .ccc/plans/*.plan.md:  $plans_count 个"
  echo "  .ccc/reports/*.report.md: $tasks_state"
  echo ""
  echo "Tasks 状态: profile=$profile_state, state=$state_state, plans=$plans_count, tasks=$tasks_state"
}

print_summary() {
  echo "=== CCC 4-file contract check ==="
  echo "完成 — 见上方 4 文件契约健康状态"
}

emit_json() {
  local profile_state state_state plans_count tasks_state

  profile_state=$(status_of "$CCC_DIR/profile.md")
  state_state=$(status_of "$CCC_DIR/state.md")

  plans_count=0
  tasks_state="missing"
  if [[ -d "$CCC_DIR/plans" ]]; then
    plans_count=$(find "$CCC_DIR/plans" -maxdepth 1 -type f -name '*.plan.md' | wc -l | tr -d ' ')
  fi
  if [[ -d "$CCC_DIR/reports" ]]; then
    local report_count
    report_count=$(find "$CCC_DIR/reports" -maxdepth 1 -type f -name '*.report.md' | wc -l | tr -d ' ')
    if [[ "$report_count" -gt 0 ]]; then tasks_state="ok"; fi
  fi

  printf '{"profile": "%s", "state": "%s", "plans": "%s", "tasks": "%s"}\n' \
    "$profile_state" "$state_state" "$plans_count" "$tasks_state"
}

main() {
  if [[ $JSON_MODE -eq 1 ]]; then
    emit_json
  else
    check_ccc_files
    print_summary
  fi
}

main
exit 0