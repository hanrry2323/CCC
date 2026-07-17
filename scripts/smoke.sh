#!/usr/bin/env bash
# 冒烟测试运行器 — 用于 CCC tester/Engine 快速验证
# 选定子集：test_cli.py + test_sau_bridge.py
# 使用方式: bash scripts/smoke.sh

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "=== xianyu 冒烟测试 ==="
echo "子集: tests/test_cli.py tests/bridge/test_sau_bridge.py"
echo "工作目录: $ROOT"
echo ""

# 运行冒烟子集
python -m pytest tests/test_cli.py tests/bridge/test_sau_bridge.py -q --tb=short

EXIT_CODE=$?
if [ $EXIT_CODE -eq 0 ]; then
    echo ""
    echo "=== SMOKE PASSED ==="
else
    echo ""
    echo "=== SMOKE FAILED (exit=$EXIT_CODE) ==="
fi
exit $EXIT_CODE
