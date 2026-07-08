#!/bin/bash
# tests/e2e/test_pipeline_smoke.sh — CCC 完整流水线 E2E 测试 (v0.19)
#
# 在临时工作区跑一条完整流水线：
# 创建任务 → product 写 plan → dev mock → reviewer py_compile
#
# 退出码：0=全部通过  1=某个步骤失败

set -euo pipefail

echo "=== E2E: CCC 流水线集成测试 ==="

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WORKSPACE=$(mktemp -d)
trap "rm -rf '$WORKSPACE'" EXIT

# 初始化 workspace（模拟 .ccc 目录）
mkdir -p "$WORKSPACE/.ccc/board/"{backlog,planned,in_progress,testing,verified,released,abnormal,events}
mkdir -p "$WORKSPACE/.ccc/"{plans,phases,pids,reports,verdicts}
mkdir -p "$WORKSPACE/scripts"

# 写一个 dummy .py 文件供 reviewer 检查
echo "x = 1" > "$WORKSPACE/scripts/dummy.py"

# profile.md
cat > "$WORKSPACE/.ccc/profile.md" <<'EOF'
# E2E Test Project
项目名: e2e-test
主语言: Python
EOF

# state.md
cat > "$WORKSPACE/.ccc/state.md" <<'EOF'
# .ccc/state.md — E2E Test
当前版本: v0.19-test
EOF

export CCC_WORKSPACE="$WORKSPACE"
BOARD_PY="$SCRIPT_DIR/scripts/ccc-board.py"

echo ""
echo "1. 创建测试任务"
echo '{"action":"create","id":"e2e-smoke","title":"E2E Smoke Test","column":"backlog"}' | python3 "$BOARD_PY" --batch
RC=$?
if [[ $RC -ne 0 ]]; then echo "❌ Step 1 FAILED"; exit 1; fi
echo "✓"

echo ""
echo "2. 确认任务在 backlog"
python3 "$BOARD_PY" index 2>&1 | grep -q '"backlog": 1'
RC=$?
if [[ $RC -ne 0 ]]; then echo "❌ Step 2 FAILED (backlog count != 1)"; python3 "$BOARD_PY" index; exit 1; fi
echo "✓"

echo ""
echo "3. 写 plan.md + phases.json（模拟 product 角色）"
PLAN_FILE="$WORKSPACE/.ccc/plans/e2e-smoke.plan.md"
cat > "$PLAN_FILE" <<'EOF'
# e2e-smoke

## 目标
- E2E 测试

## 范围
- **只改文件**: scripts/dummy.py

## 验收
- py_compile 通过
- 无异常
EOF

PHASES_FILE="$WORKSPACE/.ccc/phases/e2e-smoke.phases.json"
cat > "$PHASES_FILE" <<'EOF'
{"schema_version": "1.0"}
{"phase": 1, "status": "done", "scope": ["scripts/dummy.py"], "commit_message": "e2e test", "commit": null, "subtasks": {"1.1": "done"}, "timeout": 60, "notes": "", "retry": 0, "retry_at": null}
EOF

# 挪到 planned
echo '{"action":"move","id":"e2e-smoke","from":"backlog","to":"planned"}' | python3 "$BOARD_PY" --batch
echo "✓"

echo ""
echo "4. 模拟 dev（写 report + 挪 to testing）"
mkdir -p "$WORKSPACE/.ccc/reports"
cat > "$WORKSPACE/.ccc/reports/e2e-smoke.report.md" <<'EOF'
# e2e-smoke 执行报告

## 信息
- 状态: 完成
EOF
echo '{"action":"move","id":"e2e-smoke","from":"planned","to":"in_progress"}' | python3 "$BOARD_PY" --batch
echo '{"action":"move","id":"e2e-smoke","from":"in_progress","to":"testing"}' | python3 "$BOARD_PY" --batch
echo "✓"

echo ""
echo "5. reviewer_role: py_compile"
# reviewer_role 会用 CCC_WORKSPACE 找文件
python3 "$BOARD_PY" reviewer
echo "✓"

echo ""
echo "6. 确认任务在 verified"
python3 "$BOARD_PY" index 2>&1 | grep -q '"verified": 1'
RC=$?
if [[ $RC -ne 0 ]]; then echo "❌ Step 6 FAILED (not in verified)"; python3 "$BOARD_PY" index; exit 1; fi
echo "✓"

echo ""
echo "7. 确认看板无异常"
python3 "$BOARD_PY" index 2>&1 | grep -q '"abnormal": 0'
RC=$?
if [[ $RC -ne 0 ]]; then echo "❌ Step 7 FAILED (abnormal != 0)"; exit 1; fi
echo "✓"

echo ""
echo "=============================="
echo "✅ E2E: 全部 7 步通过"
echo "=============================="
exit 0
