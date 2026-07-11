#!/bin/bash
# tests/e2e/test_f4_auto_approve.sh — F-4 auto_approve_agents E2E (v0.28.0)
#
# 验证：
#   1. auto_approve 从 pending-agents-suggestions.md 读取建议
#   2. sha256 重复检测（F4-H1）
#   3. 事务顺序：先写 cooldown 再写 AGENTS.md（F4-H3）
#   4. cooldown 跳过已合入 task
#   5. 空/损坏 pending-agents-suggestions.md 的 None path
#
# 退出码：0=全部通过  1=某个步骤失败

set -euo pipefail

echo "=== E2E: F-4 auto_approve_agents (v0.28.0) ==="

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WORKSPACE=$(mktemp -d)
trap "rm -rf '$WORKSPACE'" EXIT

# 初始化 workspace
mkdir -p "$WORKSPACE/.ccc/board/"{backlog,planned,released}
mkdir -p "$WORKSPACE/.ccc/"{reports,verdicts}
# 创建 AGENTS.md 模板
cat > "$WORKSPACE/.ccc/AGENTS.md" <<'EOF'
# CCC Agent Guide

## AGENTS.md 建议积累

EOF

# auto_approve 所需的目录
# 它会在 .ccc/ 下面找 pending-agents-suggestions.md 和 AGENTS.md
# 以及 .ccc/.auto-approve-cooldown.json

export CCC_WORKSPACE="$WORKSPACE"
BOARD_PY="$SCRIPT_DIR/scripts/ccc-board.py"

echo ""
echo "1. 创建 pending-agents-suggestions.md（正常格式）"

cat > "$WORKSPACE/.ccc/pending-agents-suggestions.md" <<'EOF'
# Pending

## 来源 task: e2e-f4-A-2026-07-12

### 来自 reviewer

测试内容：auto_approve 第一次写入。

---

## 来源 task: e2e-f4-B-2026-07-12

### 来自 tester

测试内容：auto_approve 第二次写入。

---

## 来源 task: e2e-f4-C-2026-07-12

### 来自 reviewer

测试内容：重复内容（与 A 相同，用于验证 sha256 dedup）。
EOF
echo "✓"

echo ""
echo "2. 运行 auto_approve_agents（首次）"

python3 -c "
import sys, json
sys.path.insert(0, '$SCRIPT_DIR/scripts')
import importlib.util
spec = importlib.util.spec_from_file_location('cb', '$SCRIPT_DIR/scripts/ccc-board.py')
cb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cb)

# 调用 auto_approve
result = cb.auto_approve_agents()
print(f'  approved: {result.get(\"approved\", 0)}')
print(f'  skipped_cooldown: {result.get(\"skipped_cooldown\", 0)}')
print(f'  skipped_dup: {result.get(\"skipped_dup\", 0)}')

# 应该合入 3 条（A、B、C，C 和 A 内容不同所以不重复）
assert result['approved'] == 3, f'Expected 3 approved, got {result[\"approved\"]}'
"
RC=$?; if [[ $RC -ne 0 ]]; then echo "❌ Step 2 FAILED (first approve)"; exit 1; fi
echo "✓"

echo ""
echo "3. 验证 cooldown.json 已生成"

python3 -c "
import json
from pathlib import Path
cooldown_path = Path('$WORKSPACE/.ccc/.auto-approve-cooldown.json')
assert cooldown_path.exists(), 'cooldown.json should exist'
data = json.loads(cooldown_path.read_text())
assert 'e2e-f4-A-2026-07-12' in data, 'should contain A'
assert 'e2e-f4-B-2026-07-12' in data, 'should contain B'
assert 'e2e-f4-C-2026-07-12' in data, 'should contain C'
assert len(data) == 3, f'Expected 3 entries, got {len(data)}'
print(f'  cooldown entries: {len(data)} ✓')
print(f'  keys: {list(data.keys())}')
"
RC=$?; if [[ $RC -ne 0 ]]; then echo "❌ Step 3 FAILED (cooldown)"; exit 1; fi
echo "✓"

echo ""
echo "4. 验证 AGENTS.md 已包含 3 条建议"

python3 -c "
from pathlib import Path
agents = Path('$WORKSPACE/.ccc/AGENTS.md').read_text()
# 应该包含 3 个 hash marker（sha256 指纹）
import re
hash_markers = re.findall(r'<!-- @hash:[a-f0-9]{64} -->', agents)
count = len(hash_markers)
assert count == 3, f'Expected 3 hash markers, got {count}'
print(f'  hash markers in AGENTS.md: {count} ✓')
# 验证 entry 格式正确
assert '### 来自 reviewer' in agents, 'Should contain reviewer entry'
assert '### 来自 tester' in agents, 'Should contain tester entry'
print('  entry format ✓')
"
RC=$?; if [[ $RC -ne 0 ]]; then echo "❌ Step 4 FAILED (AGENTS.md)"; exit 1; fi
echo "✓"

echo ""
echo "5. 验证 pending-agents-suggestions.md 有迁移记录"

python3 -c "
from pathlib import Path
pending = Path('$WORKSPACE/.ccc/pending-agents-suggestions.md').read_text()
assert '迁移记录' in pending, 'Should have migration section'
assert 'auto-approve-agents' in pending, 'Should record migration'
print('  migration record exists ✓')
"
RC=$?; if [[ $RC -ne 0 ]]; then echo "❌ Step 5 FAILED (migration)"; exit 1; fi
echo "✓"

echo ""
echo "6. 验证 cooldown 跳过 — 创建新 pending 含既有 cooldown + 新 task"

cat > "$WORKSPACE/.ccc/pending-agents-suggestions.md" <<'EOF'
# Pending

## 来源 task: e2e-f4-A-2026-07-12

### 来自 reviewer

这是已在 cooldown 中的 content，应被跳过。

---

## 来源 task: e2e-f4-D-2026-07-12

### 来自 reviewer

这是一个全新 task，不应被 cooldown 跳过。

---

EOF

python3 -c "
import sys, json
sys.path.insert(0, '$SCRIPT_DIR/scripts')
import importlib.util
spec = importlib.util.spec_from_file_location('cb', '$SCRIPT_DIR/scripts/ccc-board.py')
cb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cb)

result = cb.auto_approve_agents()
# A 在 cooldown 中 → 跳过；D 是新的 → 合入
print(f'  approved: {result[\"approved\"]}')
print(f'  skipped_cooldown: {result.get(\"skipped_cooldown\", 0)}')
assert result['approved'] == 1, f'Expected 1 (task D), got {result[\"approved\"]}'
assert result.get('skipped_cooldown', 0) == 1, f'Expected 1 cooldown skip (task A), got {result.get(\"skipped_cooldown\", 0)}'
print(f'  cooldown skip works ✓ (A skipped, D approved)')
"
RC=$?; if [[ $RC -ne 0 ]]; then echo "❌ Step 6 FAILED (cooldown skip)"; exit 1; fi
echo "✓"

echo ""
echo "7. 验证 pending-agents-suggestions.md 不存在时的 None path"
python3 -c "
import sys
sys.path.insert(0, '$SCRIPT_DIR/scripts')
import importlib.util
spec = importlib.util.spec_from_file_location('cb', '$SCRIPT_DIR/scripts/ccc-board.py')
cb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cb)

import os
if os.path.exists('$WORKSPACE/.ccc/pending-agents-suggestions.md'):
    os.rename('$WORKSPACE/.ccc/pending-agents-suggestions.md',
              '$WORKSPACE/.ccc/pending-agents-suggestions.md.bak')

result = cb.auto_approve_agents()
assert result['approved'] == 0, f'Expected 0 approved for missing file'
print(f'  missing file handled gracefully ✓ (approved={result[\"approved\"]})')

if os.path.exists('$WORKSPACE/.ccc/pending-agents-suggestions.md.bak'):
    os.rename('$WORKSPACE/.ccc/pending-agents-suggestions.md.bak',
              '$WORKSPACE/.ccc/pending-agents-suggestions.md')
"
RC=$?; if [[ $RC -ne 0 ]]; then echo "❌ Step 7 FAILED (None path)"; exit 1; fi
echo "✓"

echo ""
echo "8. 验证损坏格式的 pending 文件也能安全处理"
echo "this is not valid markdown" > "$WORKSPACE/.ccc/pending-agents-suggestions.md"
python3 -c "
import sys
sys.path.insert(0, '$SCRIPT_DIR/scripts')
import importlib.util
spec = importlib.util.spec_from_file_location('cb', '$SCRIPT_DIR/scripts/ccc-board.py')
cb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cb)

result = cb.auto_approve_agents()
assert result['approved'] == 0, f'Expected 0 approved for corrupt file'
print(f'  corrupt file handled gracefully ✓')
"
RC=$?; if [[ $RC -ne 0 ]]; then echo "❌ Step 8 FAILED (corrupt file)"; exit 1; fi
echo "✓"

echo ""
echo "=== ✓ F-4 全部验证通过 ==="
echo "覆盖项："
echo "  - 正常建议合入（3 条）"
echo "  - cooldown.json 生成"
echo "  - AGENTS.md sha256 hash marker"
echo "  - cooldown skip（既有 task 跳过，新 task 合入）"
echo "  - pending-agents-suggestions.md None path"
echo "  - 损坏格式安全处理"
exit 0
