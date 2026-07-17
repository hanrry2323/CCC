#!/usr/bin/env bash
# 冒烟测试运行器 — 用于 CCC tester/Engine 快速验证
# 选定子集: tests/scripts/test_ccc_status_smoke.py
# 使用方式: bash scripts/smoke.sh

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "=== CCC 冒烟测试 ==="
echo "子集: tests/scripts/test_ccc_status_smoke.py"
echo "工作目录: $ROOT"
echo ""

# 运行冒烟子集
python3 -m pytest tests/scripts/test_ccc_status_smoke.py -q --tb=short

EXIT_CODE=$?
if [ $EXIT_CODE -eq 0 ]; then
    echo ""
    echo "=== SMOKE PASSED ==="
else
    echo ""
    echo "=== SMOKE FAILED (exit=$EXIT_CODE) ==="
fi
exit $EXIT_CODE
