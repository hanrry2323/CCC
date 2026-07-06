#!/bin/bash
# hello-ccc.sh — CCC 4-file contract 演示脚本
#
# 由 CCC Executor 在 hello-ccc-demo 任务 (phase=1) 下产出。
# 打印 4 文件契约路径 + 当前 phases.json 状态，用于冒烟测试。
#
# 红线遵循：
#   - 不修改 plan / verdict / phases.json（红线 6）
#   - --dry-run 模式下不写任何文件（防御性兜底）

set -euo pipefail

# ---- 常量 ----
CCC_DIR=".ccc"
PHASES_FILE="${CCC_DIR}/phases/hello-ccc-demo.phases.json"

# 全局状态
DRY_RUN=0

# ---- 函数 ----
print_ccc_paths() {
    local task="${1:-hello-ccc-demo}"
    cat <<EOF
${CCC_DIR}/plans/${task}.plan.md
${CCC_DIR}/phases/${task}.phases.json
${CCC_DIR}/reports/${task}.report.md
${CCC_DIR}/verdicts/${task}.verdict.md
EOF
}

print_phase_status() {
    local phases_file="${1:-${PHASES_FILE}}"

    if [[ ! -f "${phases_file}" ]]; then
        echo "WARN: phases file not found: ${phases_file}" >&2
        return 1
    fi

    # JSONL 容错: 文件可能是单行 multi-object 或每行一个对象。
    # 用 sed -n 全局匹配每个 phase 对象,逐行输出。
    # 策略: 先把 phase 对象从整文件提取出来,再按对象单独解析。
    local content
    content=$(cat "${phases_file}" || true)

    # 把相邻的 phase 对象切开(在 } 后面没有 , 但有 { 时补 \n)
    local normalized
    normalized=$(printf '%s' "${content}" | sed 's/}{/}\n{/g')

    while IFS= read -r line; do
        [[ -z "${line}" ]] && continue

        local phase_id status
        phase_id=$(printf '%s' "${line}" | sed -n 's/.*"phase_id"[[:space:]]*:[[:space:]]*\([0-9][0-9]*\).*/\1/p' || true)
        status=$(printf '%s' "${line}" | sed -n 's/.*"status"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' || true)

        if [[ -n "${phase_id}" && -n "${status}" ]]; then
            echo "phase ${phase_id}: ${status}"
        fi
    done <<< "${normalized}"
}

usage() {
    cat <<EOF
Usage: hello-ccc.sh [--dry-run]

Options:
  --dry-run    仅 echo 输出,不执行任何写操作（演示用）
  -h, --help   显示帮助

Environment:
  CCC_PHASES_FILE  覆盖 phases.json 路径（默认: ${PHASES_FILE}）
EOF
}

main() {
    # 参数解析
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --dry-run)
                DRY_RUN=1
                shift
                ;;
            -h|--help)
                usage
                exit 0
                ;;
            *)
                echo "ERROR: unknown argument: $1" >&2
                usage >&2
                exit 2
                ;;
        esac
    done

    local phases_file="${CCC_PHASES_FILE:-${PHASES_FILE}}"

    echo "[hello-ccc] DRY_RUN=${DRY_RUN}"
    echo "[hello-ccc] === CCC 4-file contract paths ==="
    print_ccc_paths "hello-ccc-demo"
    echo "[hello-ccc] === phase status ==="
    print_phase_status "${phases_file}"
    echo "CCC 4-file contract OK"
}

main "$@"