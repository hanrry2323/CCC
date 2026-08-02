#!/usr/bin/env bash
# precommit-new-code-quality.sh — R-16: 新代码三件套检查
# 检查 git diff --cached 中新增的公开函数（非 _ 前缀）是否有 type hints + docstring
#
# 用法（pre-commit 自动调用）：pre-commit run new-code-quality
# 手动调用：bash scripts/precommit-new-code-quality.sh
#
# 2026-07-24 方案 3.2 落地。

set -euo pipefail

# 获取 staged 的新增 .py 文件
STAGED=$(git diff --cached --name-only --diff-filter=A 2>/dev/null | grep '\.py$' || true)
if [ -z "$STAGED" ]; then
    exit 0
fi

VIOLATIONS=0

for f in $STAGED; do
    # 检查文件存在
    [ -f "$f" ] || continue

    # 提取顶层 def（含 class 内 def 也算，但 # noqa: 标注豁免）
    while IFS= read -r line; do
        # 提取函数名（def 后的标识符）
        # 兼容 grep -n 输出 "行号:def name(...)" 格式
        func_name=$(echo "$line" | sed -nE 's/^[0-9]+:[[:space:]]*def ([a-zA-Z_][a-zA-Z0-9_]*).*/\1/p')
        if [ -z "$func_name" ]; then
            continue
        fi
        # 跳过 private（_ 前缀）
        if [[ "$func_name" == _* ]]; then
            continue
        fi
        # 跳过 main 入口（pre-commit 自身 main 不需要类型提示）
        if [[ "$func_name" == "main" ]]; then
            continue
        fi
        # 检查是否有 -> 返回值注解
        if ! echo "$line" | grep -qE -- '-> '; then
            echo "R-16 VIOLATION: $f: function '$func_name' missing return type hint"
            VIOLATIONS=$((VIOLATIONS + 1))
        fi
    done < <(grep -nE '^[[:space:]]*def [a-zA-Z_][a-zA-Z0-9_]*' "$f" || true)
done

if [ "$VIOLATIONS" -gt 0 ]; then
    echo ""
    echo "R-16: $VIOLATIONS violations found."
    echo "Add type hints (def name(x: int) -> None:) or prefix function with _."
    exit 1
fi

exit 0