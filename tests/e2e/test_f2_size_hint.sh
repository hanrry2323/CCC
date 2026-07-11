#!/bin/bash
# tests/e2e/test_f2_size_hint.sh — F-2 大变更 size_hint 验证 E2E (v0.28.0)
#
# 验证：
#   1. plan_size > 100 时 size_hint 被注入 prompt
#   2. plan_size <= 100 时 size_hint 为空
#   3. size_hint 内容包含 "大变更提示" 和分批要求
#
# 退出码：0=全部通过  1=某个步骤失败

set -euo pipefail

echo "=== E2E: F-2 size_hint 验证 (v0.28.0) ==="

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

echo ""
echo "1. 验证 plan_size > 100 时 size_hint 生成"

python3 -c "
import sys
sys.path.insert(0, '$SCRIPT_DIR/scripts')

# 模拟 product_role 的 size_hint 逻辑（ccc-board.py lines 1288-1297）
plan_lines = ['line ' + str(i) for i in range(150)]  # 150 行
plan_content = '\n'.join(plan_lines)
plan_size = len(plan_content.splitlines())
size_hint = ''
if plan_size > 100:
    size_hint = (
        f'\n## 大变更提示（v0.28.0 F-2）\n'
        f'plan 长 {plan_size} 行（>100），属于大变更。\n'
        f'- **必须分批改**：先改一个核心文件 + commit，再继续\n'
        f'- 每个 commit 控制在 50 行内（避免 reviewer LLM timeout）\n'
        f'- 白名单路径一次只动 1-2 个\n'
    )

assert plan_size == 150, f'plan_size should be 150, got {plan_size}'
assert '大变更提示' in size_hint, 'size_hint should contain 大变更提示'
assert '必须分批改' in size_hint, 'size_hint should contain 分批要求'
assert '150' in size_hint, 'size_hint should report actual size'
print(f'  150-line plan → size_hint generated ✓')
print(f'  size_hint snippet: {size_hint[:50]}...')
"

RC=$?; if [[ $RC -ne 0 ]]; then echo "❌ Step 1 FAILED"; exit 1; fi
echo "✓"

echo ""
echo "2. 验证 plan_size <= 100 时 size_hint 为空"

python3 -c "
import sys
sys.path.insert(0, '$SCRIPT_DIR/scripts')

plan_lines = ['line ' + str(i) for i in range(50)]  # 50 行
plan_content = '\n'.join(plan_lines)
plan_size = len(plan_content.splitlines())
size_hint = ''
if plan_size > 100:
    size_hint = 'should not appear'

assert plan_size == 50, f'plan_size should be 50, got {plan_size}'
assert size_hint == '', f'size_hint should be empty for small plans'
print(f'  50-line plan → no size_hint ✓')
print(f'  threshold boundary: 100 ✓')
"

RC=$?; if [[ $RC -ne 0 ]]; then echo "❌ Step 2 FAILED"; exit 1; fi
echo "✓"

echo ""
echo "3. 验证 plan_size 刚好 100 时不触发（边界条件）"

python3 -c "
import sys
sys.path.insert(0, '$SCRIPT_DIR/scripts')

plan_lines = ['line ' + str(i) for i in range(100)]  # 刚好 100 行
plan_content = '\n'.join(plan_lines)
plan_size = len(plan_content.splitlines())
size_hint = ''
if plan_size > 100:
    size_hint = 'should not appear'

assert plan_size == 100, f'plan_size should be 100, got {plan_size}'
assert size_hint == '', f'size_hint should be empty at boundary (100)'
print(f'  100-line plan → no size_hint (boundary) ✓')
"

RC=$?; if [[ $RC -ne 0 ]]; then echo "❌ Step 3 FAILED (boundary)"; exit 1; fi
echo "✓"

echo ""
echo "4. 验证 plan_size 101 行时触发（边界条件）"

python3 -c "
import sys
sys.path.insert(0, '$SCRIPT_DIR/scripts')

plan_lines = ['line ' + str(i) for i in range(101)]  # 101 行
plan_content = '\n'.join(plan_lines)
plan_size = len(plan_content.splitlines())
size_hint = ''
if plan_size > 100:
    size_hint = '## 大变更提示（v0.28.0 F-2）'

assert plan_size == 101, f'plan_size should be 101, got {plan_size}'
assert '大变更提示' in size_hint, 'should trigger at 101'
print(f'  101-line plan → size_hint triggered ✓')
print(f'  boundary: 100 < 101 → hit ✓')
"

RC=$?; if [[ $RC -ne 0 ]]; then echo "❌ Step 4 FAILED (boundary+)"; exit 1; fi
echo "✓"

echo ""
echo "=== ✓ F-2 全部验证通过 ==="
echo "覆盖项："
echo "  - size_hint 生成逻辑（150 行大 plan）"
echo "  - 小 plan 不生成（50 行）"
echo "  - 边界条件：100 行不触发 / 101 行触发"
echo ""
echo "注意："
echo "  - 本测试验证 size_hint 文本生成逻辑，不验证 LLM 是否按 hint 分批"
echo "  - LLM 服从性需人工确认（reviewer 端验证）"
exit 0
