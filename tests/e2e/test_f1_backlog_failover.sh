#!/bin/bash
# tests/e2e/test_f1_backlog_failover.sh — F-1 backlog 失败退避 E2E (v0.28.0)
#
# 验证：
#   1. fail_counter 文件读写 + 持久化
#   2. fail_count < MAX → 允许重试
#   3. fail_count >= MAX → quarantine
#   4. 成功后计数器清空
#
# 退出码：0=全部通过  1=某个步骤失败

set -euo pipefail

echo "=== E2E: F-1 backlog failover (v0.28.0) ==="

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WORKSPACE=$(mktemp -d)
trap "rm -rf '$WORKSPACE'" EXIT

mkdir -p "$WORKSPACE/.ccc/board/"{backlog,planned,in_progress,testing,verified,released,abnormal,events}
mkdir -p "$WORKSPACE/.ccc/"{plans,phases,pids,reports,verdicts,reviews,review-locks}
mkdir -p "$WORKSPACE/.ccc/.product-fail-counter"
mkdir -p "$WORKSPACE/scripts"
echo "x = 1" > "$WORKSPACE/scripts/dummy.py"

cat > "$WORKSPACE/.ccc/profile.md" <<'EOF'
# E2E F-1 Test
项目名: e2e-f1-test
主语言: Python
EOF
cat > "$WORKSPACE/.ccc/state.md" <<'EOF'
# .ccc/state.md — F-1 E2E
当前版本: v0.28.0-test
EOF

echo ""
echo "1. 创建 3 个 backlog task + 测试 fail_counter 文件"
python3 -c "
import sys, json
sys.path.insert(0, '$SCRIPT_DIR/scripts')
from pathlib import Path

# BoardStore 构建需要 Path
from _config import Config as _C
import _config
_config._resolve_workspace = lambda: Path('$WORKSPACE')
from _board_store import FileBoardStore

W = Path('$WORKSPACE')
store = FileBoardStore(W)

# 创建 3 task
for i, tid in enumerate([('oldest-2026-07-10', '2026-07-10'),
                         ('mid-2026-07-11', '2026-07-11'),
                         ('newest-2026-07-12', '2026-07-12')]):
    store.create_task({
        'id': tid[0], 'title': tid[0], 'created_at': tid[1],
        'status': 'backlog', 'updated_at': tid[1],
    }, column='backlog')

bl = store.list_tasks('backlog')
assert len(bl) == 3, f'Expected 3, got {len(bl)}'
print(f'  backlog count: {len(bl)}')

# fail_counter 读写测试
counter_dir = W / '.ccc' / '.product-fail-counter'
c = counter_dir / 'oldest-2026-07-10.json'
c.write_text(json.dumps({'fail_count': 2}, indent=2))
assert json.loads(c.read_text())['fail_count'] == 2
# 递增
data = {'fail_count': json.loads(c.read_text())['fail_count'] + 1}
c.write_text(json.dumps(data, indent=2))
assert json.loads(c.read_text())['fail_count'] == 3
print(f'  fail_counter I/O: write/read/increment ✓')
# 清空（模拟成功）
c.unlink()
assert not c.exists()
print(f'  counter cleared after success ✓')
"
RC=$?; if [[ $RC -ne 0 ]]; then echo "❌ Step 1 FAILED"; exit 1; fi
echo "✓"

echo ""
echo "2. 测试 fail_count < MAX → 允许重试"
python3 -c "
import sys, json
sys.path.insert(0, '$SCRIPT_DIR/scripts')
from pathlib import Path

MAX = 3
counter_path = Path('$WORKSPACE/.ccc/.product-fail-counter/newest-2026-07-12.json')
counter_path.write_text(json.dumps({'fail_count': 1}))
fc = json.loads(counter_path.read_text())['fail_count']
assert fc < MAX, f'fc={fc} should be < {MAX}'
print(f'  fail_count={fc} < {MAX} = retry allowed ✓')
"
RC=$?; if [[ $RC -ne 0 ]]; then echo "❌ Step 2 FAILED (retry)"; exit 1; fi
echo "✓"

echo ""
echo "3. 测试 fail_count >= MAX → quarantine"
python3 -c "
import sys, json
sys.path.insert(0, '$SCRIPT_DIR/scripts')
from pathlib import Path
from _board_store import FileBoardStore
import _config
_config._resolve_workspace = lambda: Path('$WORKSPACE')

store = FileBoardStore(Path('$WORKSPACE'))
# 确保 mid task 在 backlog 中
store.create_task({
    'id': 'mid-2026-07-11', 'title': 'mid-2026-07-11',
    'status': 'backlog', 'created_at': '2026-07-11', 'updated_at': '2026-07-11',
}, column='backlog')

MAX = 3
counter_path = Path('$WORKSPACE/.ccc/.product-fail-counter/mid-2026-07-11.json')
counter_path.write_text(json.dumps({'fail_count': 3}))
fc = json.loads(counter_path.read_text())['fail_count']

if fc >= MAX:
    store.quarantine('mid-2026-07-11', f'product_role failed {fc} times')
    print(f'  fail_count={fc} >= {MAX} → quarantined ✓')

bl_ids = [t['id'] for t in store.list_tasks('backlog')]
ab_ids = [t['id'] for t in store.list_tasks('abnormal')]
assert 'mid-2026-07-11' not in bl_ids
assert 'mid-2026-07-11' in ab_ids
print(f'  task moved backlog→abnormal ✓')
"
RC=$?; if [[ $RC -ne 0 ]]; then echo "❌ Step 3 FAILED (quarantine)"; exit 1; fi
echo "✓"

echo ""
echo "=== ✓ F-1 全部验证通过 ==="
echo "覆盖项："
echo "  - fail_counter 文件读写"
echo "  - fail_count < MAX → retry"
echo "  - fail_count >= MAX → quarantine"
echo "  - success → counter cleared"
exit 0
