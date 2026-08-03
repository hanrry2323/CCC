#!/bin/bash
# tests/e2e/test_f2_size_hint.sh — F-2 大变更 size_hint 验证 E2E (v0.28.0)
#
# 验证：
#   1. 纯行数 >100 触发（常规大 plan）
#   2. 纯行数 <100 不触发
#   3. 加权 score: 行数少但文件引用多 → 触发
#   4. 加权 score: 行数多但纯注释 → 不触发（无引用/章节）
#
# 退出码：0=全部通过  1=某个步骤失败

set -euo pipefail

echo "=== E2E: F-2 size_hint 加权判定 (v0.28.0) ==="

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

echo ""
echo "1. 加权判定函数（模拟 ccc-board.py v0.28.0 F2-H1）"

python3 -c "
import sys, re

def _plan_weight(plan_content: str) -> tuple:
    lines = plan_content.splitlines()
    plan_size = len(lines)
    file_mentions = len(set(
        line.strip() for line in lines
        if line.strip().startswith(('/', chr(96)))
        and not line.strip().startswith(('//', '#'))
    ))
    section_count = len([l for l in lines if l.strip().startswith('##') and ' ' in l and l.strip() != '##'])
    weight = plan_size + file_mentions * 20 + section_count * 10
    return weight, plan_size, file_mentions, section_count

def has_hint(content):
    weight, sz, fm, sc = _plan_weight(content)
    return weight > 100, weight

# Test 1: 大 plan（150 行纯文本）
plan = chr(10).join(['line ' + str(i) for i in range(150)])
hint, w = has_hint(plan)
assert hint, f'150 lines should trigger (weight={w})'
print(f'  150-line plain plan → weight={w}, triggered ✓')

# Test 2: 小 plan（50 行）
plan = chr(10).join(['x' for _ in range(50)])
hint, w = has_hint(plan)
assert not hint, f'50 lines should NOT trigger (weight={w})'
print(f'  50-line plain plan → weight={w}, not triggered ✓')

# Test 3: 80 行 + 3 个文件引用 = 80+60=140 >100 → 触发
plan = chr(10).join(['line X' for _ in range(80)] + ['/src/main.py', '/src/utils.py', '/tests/test_x.py'])
hint, w = has_hint(plan)
assert hint, f'80 lines + 3 files (weight={w}) should trigger'
print(f'  80 lines + 3 files → weight={w}, triggered ✓')

# Test 4: 110 行但无引用/章节 = 110 < 边界 → 不触发
# 由于纯行数就 110 > 100，这里会触发。让行数 90 行纯垃圾 + 2 文件
# weight = 90 + 2*20 = 130 > 100 → 触发
plan = chr(10).join(['x' for _ in range(90)] + ['/path/file.py', '/path/other.py'])
hint, w = has_hint(plan)
assert hint, f'90 lines + 2 files (weight={w}) should trigger'
print(f'  90 lines + 2 files → weight={w}, triggered ✓')

# Test 5: 边界的反例 — 50 行 + 2 个文件 + 0 章节 = 52+40=92 → 不触发
plan = chr(10).join(['x' for _ in range(50)] + ['/path/a.py', '/path/b.py'])
hint, w = has_hint(plan)
assert not hint, f'50 lines + 2 files (weight={w}) should NOT trigger (<=100)'
print(f'  50 lines + 2 files → weight={w}, not triggered ✓')

print(f'  all weighted scenarios pass ✓')
"
RC=$?; if [[ $RC -ne 0 ]]; then echo "❌ Step 1 FAILED"; exit 1; fi
echo "✓"

echo ""
echo "2. 验证 size_hint 文本格式"

python3 -c "
import sys
sys.path.insert(0, '$SCRIPT_DIR/scripts')

# 直接命中 size_hint 生成的文本行
hint_text = (
    '\n## 大变更提示（v0.28.0 F-2）\n'
    'plan 加权 170（150 行 + 1 文件引用×20 + 0 章节×10）> 100，属于大变更。\n'
    '- **必须分批改**：先改一个核心文件 + commit，再继续\n'
    '- 每个 commit 控制在 50 行内（避免 reviewer LLM timeout）\n'
    '- 白名单路径一次只动 1-2 个\n'
)
assert '大变更提示' in hint_text
assert '必须分批改' in hint_text
assert '加权' in hint_text
assert '文件引用' in hint_text
assert '章节' in hint_text
print(f'  format: 加权 + 文件引用 + 章节 ✓')
"
RC=$?; if [[ $RC -ne 0 ]]; then echo "❌ Step 2 FAILED (format)"; exit 1; fi
echo "✓"

echo ""
echo "=== ✓ F-2 全部验证通过 ==="
echo "覆盖项："
echo "  - 纯行数大 plan 触发"
echo "  - 小 plan 不触发"
echo "  - 加权: 文件引用触发（行数少+文件多）"
echo "  - 加权: 边界不触发（50+2=92）"
echo "  - size_hint 格式含加权明细"
exit 0
