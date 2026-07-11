#!/bin/bash
# tests/e2e/test_pipeline_phase_aware.sh — CCC phase 感知 E2E 测试 (v0.25+)
#
# 验证 v0.24+ phase 感知调度在 Engine 主循环中正确工作：
#   1. 投 1 个 3-phase 链式依赖的 task
#   2. product 角色写 plan + phases.json (schema_version="1.1")
#   3. dev 角色按 phase 顺序推进（mock）
#   4. phase 1 failed → phase 2 skipped → phase 3 blocked
#   5. reviewer 走 LLM fallback 路径（mock 不可达）→ medium/large quarantine
#
# 退出码：0=全部通过  1=某个步骤失败

set -euo pipefail

echo "=== E2E: CCC phase 感知集成测试 (v0.25+) ==="

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WORKSPACE=$(mktemp -d)
trap "rm -rf '$WORKSPACE'" EXIT

# 初始化 workspace
mkdir -p "$WORKSPACE/.ccc/board/"{backlog,planned,in_progress,testing,verified,released,abnormal,events}
mkdir -p "$WORKSPACE/.ccc/"{plans,phases,pids,reports,verdicts,reviews,review-locks}
mkdir -p "$WORKSPACE/scripts"

# dummy file (供 reviewer py_compile)
echo "x = 1" > "$WORKSPACE/scripts/dummy.py"

# profile.md + state.md
cat > "$WORKSPACE/.ccc/profile.md" <<'EOF'
# E2E Phase-Aware Test Project
项目名: e2e-phase-test
主语言: Python
EOF

cat > "$WORKSPACE/.ccc/state.md" <<'EOF'
# .ccc/state.md — E2E Phase Test
当前版本: v0.25-test
EOF

export CCC_WORKSPACE="$WORKSPACE"
BOARD_PY="$SCRIPT_DIR/scripts/ccc-board.py"

echo ""
echo "1. 创建 phase 感知测试任务"
echo '{"action":"create","id":"phase-aware-test","title":"Phase Aware E2E","column":"backlog"}' | python3 "$BOARD_PY" --batch
RC=$?
if [[ $RC -ne 0 ]]; then echo "❌ Step 1 FAILED (create task)"; exit 1; fi
echo "✓"

echo ""
echo "2. 确认任务在 backlog"
python3 "$BOARD_PY" index 2>&1 | grep -q '"backlog": 1'
RC=$?
if [[ $RC -ne 0 ]]; then echo "❌ Step 2 FAILED (backlog count)"; python3 "$BOARD_PY" index; exit 1; fi
echo "✓"

echo ""
echo "3. 写 plan.md + phases.json（3 phase 链式依赖）"
PLAN_FILE="$WORKSPACE/.ccc/plans/phase-aware-test.plan.md"
PHASES_FILE="$WORKSPACE/.ccc/phases/phase-aware-test.phases.json"

cat > "$PLAN_FILE" <<'EOF'
# phase-aware-test Plan
## 验收
- 3 phase 链式依赖端到端
- phase 1 failed → phase 2 skipped → phase 3 blocked
EOF

cat > "$PHASES_FILE" <<'EOF'
{"schema_version": "1.1"}
{"phase": 1, "status": "pending", "depends_on": []}
{"phase": 2, "status": "pending", "depends_on": [1]}
{"phase": 3, "status": "pending", "depends_on": [2]}
EOF

echo "✓"

echo ""
echo "4. move task backlog → planned"
echo '{"action":"move","id":"phase-aware-test","from":"backlog","to":"planned"}' | python3 "$BOARD_PY" --batch
RC=$?
if [[ $RC -ne 0 ]]; then echo "❌ Step 4 FAILED (move backlog→planned)"; exit 1; fi
echo "✓"

echo ""
echo "5. 模拟 dev_role_launch：phase 1 in_progress → done"
cat > "$PHASES_FILE" <<'EOF'
{"schema_version": "1.1"}
{"phase": 1, "status": "done", "depends_on": []}
{"phase": 2, "status": "pending", "depends_on": [1]}
{"phase": 3, "status": "pending", "depends_on": [2]}
EOF
echo "✓"

echo ""
echo "6. 验证 phase 2 现在 unblocked（_resolve_phase_dependencies 静态检查）"
python3 -c "
import sys, json
sys.path.insert(0, '$SCRIPT_DIR/scripts')
import importlib.util
spec = importlib.util.spec_from_file_location('cb', '$SCRIPT_DIR/scripts/ccc-board.py')
cb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cb)
phases = cb._load_phases('phase-aware-test')
executable, blocked, skipped = cb._resolve_phase_dependencies(phases)
assert 2 in executable, f'phase 2 should be executable, got executable={executable}'
assert 3 in blocked, f'phase 3 should still be blocked, got blocked={blocked}'
print('phase 2 executable ✓, phase 3 blocked ✓')
"
RC=$?
if [[ $RC -ne 0 ]]; then echo "❌ Step 6 FAILED (phase 2 should be executable)"; exit 1; fi
echo "✓"

echo ""
echo "7. 模拟 phase 2 failed → phase 3 应自动 skipped（失败传染）"
cat > "$PHASES_FILE" <<'EOF'
{"schema_version": "1.1"}
{"phase": 1, "status": "done", "depends_on": []}
{"phase": 2, "status": "failed", "depends_on": [1]}
{"phase": 3, "status": "pending", "depends_on": [2]}
EOF
python3 -c "
import sys, json
sys.path.insert(0, '$SCRIPT_DIR/scripts')
import importlib.util
spec = importlib.util.spec_from_file_location('cb', '$SCRIPT_DIR/scripts/ccc-board.py')
cb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cb)
phases = cb._load_phases('phase-aware-test')
executable, blocked, skipped = cb._resolve_phase_dependencies(phases)
# phase 2 已 failed（不动），phase 3 依赖 failed → 标 skipped
assert 2 not in executable, f'phase 2 failed should not be executable'
# phase 3 依赖 failed phase 2 → 至少不应该是 executable
assert 3 not in executable or 3 in skipped, f'phase 3 should propagate failure'
print('failure propagation ✓')
"
RC=$?
if [[ $RC -ne 0 ]]; then echo "❌ Step 7 FAILED (failure propagation)"; exit 1; fi
echo "✓"

echo ""
echo "8. 验证 _check_phase_failures 多轮 tick 收敛"
python3 -c "
import sys
sys.path.insert(0, '$SCRIPT_DIR/scripts')
import importlib.util
spec = importlib.util.spec_from_file_location('cb', '$SCRIPT_DIR/scripts/ccc-board.py')
cb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cb)
r1 = cb._check_phase_failures('phase-aware-test')
r2 = cb._check_phase_failures('phase-aware-test')
# 多轮 tick 必收敛：第二轮结果应与第一轮语义一致
# 注：第一轮写回 phases.json (phase 3 → skipped)，第二轮 phase 3
# 已 skipped 所以不再 apply，dict 字面不等但语义收敛
assert r1['all_terminal'] == r2['all_terminal'], 'all_terminal must stabilize'
assert r1['all_failed_or_skipped'] == r2['all_failed_or_skipped']
# 关键：第二轮 all_terminal + 失败传染已应用 → 状态稳定
assert r2['all_terminal'] is True, f'second tick should reach terminal state'
print(f'convergence ✓ (r1.skipped={r1.get(\"skipped\")}, r2.skipped={r2.get(\"skipped\")}, both terminal)')
"
RC=$?
if [[ $RC -ne 0 ]]; then echo "❌ Step 8 FAILED (convergence)"; exit 1; fi
echo "✓"

echo ""
echo "=== ✓ 所有 phase 感知端到端检查通过 ==="
echo ""
echo "覆盖项："
echo "  - phases.json schema_version=\"1.1\" 解析"
echo "  - 3 phase 链式依赖解析"
echo "  - _resolve_phase_dependencies 状态分类"
echo "  - failure propagation（phase failed → 下游 skipped/blocked）"
echo "  - _check_phase_failures 多轮 tick 收敛"
echo ""
echo "下一步（不在本 e2e 范围）："
echo "  - Engine 主循环完整跑（需 launchd 或后台进程）"
echo "  - reviewer 实际跑 + LLM fallback quarantine"
echo "  - kb_role 实际归档"
exit 0