#!/bin/bash
# ccc-self-check.sh — CCC 项目自检（v1.0）
#
# 每条修复配套一个不可逆验证，全部通过才算干净。
# 在 commit 前或 CI 中运行。
#
# 用法: bash scripts/ccc-self-check.sh
# 返回: 0 = 全部通过, 1 = 有失败

set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FAILED=0

green() { printf "\033[32m✓ %s\033[0m\n" "$1"; }
red()   { printf "\033[31m✗ %s\033[0m\n" "$1"; }

# ── 1. 所有 Popen 入口已使用 _sanitized_env() ──────────────────────
check_sanitized_env() {
    local file="$ROOT/scripts/ccc-board.py"
    local remaining
    remaining=$(grep -c 'os\.environ\.copy()' "$file" 2>/dev/null || true)
    if [ "$remaining" -ne 0 ]; then
        red "board.py: 仍有 $remaining 处 os.environ.copy() 未替换"
        grep -n 'os.environ.copy()' "$file"
        return 1
    fi
    return 0
}

# ── 2. 模块级变量无重复声明 ─────────────────────────────────────────
check_no_duplicate_vars() {
    local file="$ROOT/scripts/ccc-engine.py"
    local errors=0
    for var in "_engine_start_ts" "_restart_log_written" "_RESTART_LOG_PATH"; do
        local count
        count=$(grep -c "^${var}" "$file" 2>/dev/null || true)
        if [ "$count" -gt 1 ]; then
            red "engine.py: ${var} 声明了 ${count} 次（应为 1 次）"
            errors=1
        fi
    done
    return $errors
}

# ── 3. Shell 脚本语法 ──────────────────────────────────────────────
check_shell_syntax() {
    local errors=0
    for shfile in "$ROOT/scripts/"*.sh; do
        if [ -f "$shfile" ]; then
            if ! bash -n "$shfile" 2>/dev/null; then
                red "$(basename "$shfile") 语法错误"
                bash -n "$shfile" 2>&1
                errors=1
            fi
        fi
    done
    return $errors
}

# ── 4. 所有 CCC 工作区有 templates/ ────────────────────────────────
check_templates_exist() {
    local errors=0
    for wsdir in "$HOME/program/"*/; do
        if [ -d "$wsdir/.ccc" ] && [ ! -d "$wsdir/templates" ]; then
            red "$(basename "$wsdir") 是 CCC 工作区但缺少 templates/"
            errors=1
        fi
    done
    return $errors
}

# ── 5. 测试中无已删除项目 ──────────────────────────────────────────
check_no_expired_projects_in_tests() {
    local file="$ROOT/tests/scripts/test_chat_server.py"
    if [ -f "$file" ]; then
        if grep -q '"hp"' "$file"; then
            red "test_chat_server.py 仍引用了已删除项目 'hp'"
            return 1
        fi
    fi
    return 0
}

# ── 6. Python 编译 ────────────────────────────────────────────
check_python_compile() {
    if ! python3 -m compileall -q "$ROOT/scripts" 2>/dev/null; then
        red "Python 编译错误"
        python3 -m compileall "$ROOT/scripts" 2>&1
        return 1
    fi
    return 0
}

# ── 7. Prompt injection 防护 — 所有用户输入插入 prompt 处已 sanitize ──
check_prompt_injection_guards() {
    local file="$ROOT/scripts/ccc-board.py"
    # 所有 f"- title: {task.get('title' 必须经过 _sanitize_prompt_input
    local unguarded
    unguarded=$(grep -cE "f\"- title:.*\{task\.get\('title'" "$file" 2>/dev/null || true)
    if [ "$unguarded" -gt 0 ]; then
        red "board.py: $unguarded 处 title 注入点未经 _sanitize_prompt_input 防护"
        grep -nE "f\"- title:.*\{task\.get\('title'" "$file"
        return 1
    fi
    return 0
}

# ── 执行 ──────────────────────────────────────────────────────────
echo "=== CCC 自检 ==="
echo ""

echo "── 1. Popen 环境变量过滤 ──"
if check_sanitized_env; then green "所有 Popen 均已使用 _sanitized_env()"; else FAILED=1; fi

echo "── 2. 模块级变量不重复 ──"
if check_no_duplicate_vars; then green "无重复模块级变量"; else FAILED=1; fi

echo "── 3. Shell 脚本语法 ──"
if check_shell_syntax; then green "Shell 语法全部通过"; else FAILED=1; fi

echo "── 4. 工作区 templates/ 目录 ──"
if check_templates_exist; then green "所有工作区 templates/ 完整"; else FAILED=1; fi

echo "── 5. 测试无过期项目引用 ──"
if check_no_expired_projects_in_tests; then green "测试项目引用有效"; else FAILED=1; fi

echo "── 6. Python 编译 ──"
if check_python_compile; then green "Python 编译通过"; else FAILED=1; fi

echo "── 7. Prompt injection 防护 ──"
if check_prompt_injection_guards; then green "所有注入点已防护"; else FAILED=1; fi

echo ""
if [ "$FAILED" -eq 0 ]; then
    echo "✓ 自检全部通过"
else
    echo "✗ 自检未通过，请修复上述问题"
fi
exit "$FAILED"
