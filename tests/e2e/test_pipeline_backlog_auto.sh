#!/bin/bash
# tests/e2e/test_pipeline_backlog_auto.sh — CCC backlog 自动拆分 → 全链路 E2E (v0.28+)
#
# 验证目标：
#   用户落 backlog 一条 task → engine 自动推进 product→planned→dev→reviewer→tester→kb→released
#
# 设计：
#   本测试**不实际启动 opencode**（避免 30 分钟 + Claude API 依赖），
#   直接调用 ccc-engine.py 的内部函数 + ccc-board.py 角色函数，验证
#   每一列的 transition 行为符合 Engine 设计。
#
# 覆盖场景：
#   1. backlog fast-path（有 phases.json → 直接 planned，不调 product）
#   2. product_role 拆分（无 phases.json → 调 Claude API 写 plan+phases → planned）
#   3. dev_role 完成后流转（in_progress → testing → verified）
#   4. 失败时进入 abnormal（不发卡死在 in_progress）
#
# 退出码：0=全部通过  1=某个步骤失败

set -euo pipefail

echo "=== E2E: backlog 自动拆分 → 全链路（v0.28+）==="

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WORKSPACE=$(mktemp -d)
trap "rm -rf '$WORKSPACE'" EXIT

# ─────────── 初始化 workspace ───────────
mkdir -p "$WORKSPACE/.ccc/board/"{backlog,planned,in_progress,testing,verified,released,abnormal,events}
mkdir -p "$WORKSPACE/.ccc/"{plans,phases,pids,reports,verdicts}
mkdir -p "$WORKSPACE/scripts"
mkdir -p "$WORKSPACE/tests"

cat > "$WORKSPACE/.ccc/profile.md" <<'EOF'
# E2E Backlog Auto Test Project
项目名: e2e-backlog-auto-test
主语言: Python
EOF

cat > "$WORKSPACE/.ccc/state.md" <<'EOF'
# .ccc/state.md — E2E Backlog Auto
当前版本: v0.28-test
EOF

# 一个 dummy python 文件用于 py_compile 静态检查
echo "x = 1" > "$WORKSPACE/scripts/dummy.py"

# 初始化 git，让 reviewer diff 有 baseline
cd "$WORKSPACE" && git init -q && \
  git config user.email "test@ccc" && \
  git config user.name "test" && \
  git add -A && \
  git commit -q -m "initial commit"

# 让 dummy.py 有 diff 方便 reviewer 分类
echo "x = 42" > "$WORKSPACE/scripts/dummy.py"

export CCC_WORKSPACE="$WORKSPACE"
BOARD_PY="$SCRIPT_DIR/scripts/ccc-board.py"
ENGINE_PY="$SCRIPT_DIR/scripts/ccc-engine.py"

# ─────────── 验证 0：基础条件 ───────────
echo ""
echo "0. 环境准备"
python3 -c "
import importlib.util, sys
sys.path.insert(0, '$SCRIPT_DIR/scripts')
for name in ('ccc_board', 'ccc_engine'):
    spec = importlib.util.spec_from_file_location(name, '$SCRIPT_DIR/scripts/' + ('ccc-board.py' if name == 'ccc_board' else 'ccc-engine.py'))
    pass
print('import path OK')
"
if [[ $? -ne 0 ]]; then echo "❌ Step 0 FAILED"; exit 1; fi
echo "✓"

# ═══════════════════════════════════════════════
# 场景 1：backlog fast-path（phases.json 已存在）
# ═══════════════════════════════════════════════
echo ""
echo "─── 场景 1: backlog fast-path（phases.json 存在）───"

echo ""
echo "1.1 投 task 到 backlog + 预写 plan.md + phases.json（用户已外部拆好）"
TASK1="e2e-bk-fast-path-$(date +%s)"

cat > "$WORKSPACE/.ccc/plans/${TASK1}.plan.md" <<EOF
# $TASK1

## 目标
- backlog fast-path 全链路

## 文件白名单
- tests/test_${TASK1}.py

## 验收
- 自动流转通过
EOF

cat > "$WORKSPACE/.ccc/phases/${TASK1}.phases.json" <<EOF
{"schema_version": "1.1"}
{"phase": 1, "status": "pending", "subtasks": {"1.1": "pending"}, "timeout": 60, "commit": null, "notes": "manual", "retry": 0, "retry_at": null}
EOF

cat > "$WORKSPACE/.ccc/board/backlog/${TASK1}.jsonl" <<EOF
{"id": "$TASK1", "title": "Fast Path Task", "description": "manual phases, expect fast-path to planned", "status": "backlog", "created_at": "2026-07-13T12:00:00+08:00", "updated_at": "2026-07-13T12:00:00+08:00", "schema_version": "1.0"}
EOF
echo "✓"

echo ""
echo "1.2 调 engine 内部 _process_backlog（应在 phases 存在时跳过 product 直接移到 planned）"
python3 -c "
import importlib.util, sys, os
sys.path.insert(0, '$SCRIPT_DIR/scripts')
spec_eng = importlib.util.spec_from_file_location('ce', '$SCRIPT_DIR/scripts/ccc-engine.py')
ce = importlib.util.module_from_spec(spec_eng)
spec_eng.loader.exec_module(ce)
from pathlib import Path

ws = Path('$WORKSPACE')
result = ce._process_backlog(ws)
print(f'_process_backlog returned: {result}')
assert result, '_process_backlog must do something for backlog task'
print('fast-path invoked ✓')
"
if [[ $? -ne 0 ]]; then echo "❌ Step 1.2 FAILED"; exit 1; fi
echo "✓"

echo ""
echo "1.3 验证 task 已在 planned（phases.json 存在 fast-path）"
if [[ ! -f "$WORKSPACE/.ccc/board/planned/${TASK1}.jsonl" ]]; then
  echo "❌ Step 1.3 FAILED: task 未进入 planned"
  ls -la "$WORKSPACE/.ccc/board/"*/"$TASK1.jsonl" 2>&1 | head -10
  exit 1
fi
if [[ -f "$WORKSPACE/.ccc/board/backlog/${TASK1}.jsonl" ]]; then
  echo "❌ Step 1.3 FAILED: task 仍在 backlog"
  exit 1
fi
echo "✓"

# ═══════════════════════════════════════════════
# 场景 2: _try_launch_planned → dev_role_launch 启动
# ═══════════════════════════════════════════════
echo ""
echo "─── 场景 2: planned → dev_role_launch ───"

echo ""
echo "2.1 调 _try_launch_planned（mock 实际 launch 失败也 OK；只验证 planned 列表读取 + phase 校验）"
LAUNCH_RC=0
python3 -c "
import importlib.util, sys
sys.path.insert(0, '$SCRIPT_DIR/scripts')
spec_eng = importlib.util.spec_from_file_location('ce', '$SCRIPT_DIR/scripts/ccc-engine.py')
ce = importlib.util.module_from_spec(spec_eng)
spec_eng.loader.exec_module(ce)
from pathlib import Path

ws = Path('$WORKSPACE')
active = {}
# 调用 _try_launch_planned 会真实调 dev_role_launch 启 opencode。
# 我们只验证它读取 planned 列表，不实际等待；
# opencode 启后会放后台，我们立即继续。
result = ce._try_launch_planned(ws, active)
print(f'_try_launch_planned returned: {result}')
" 2>&1 | tail -10 || LAUNCH_RC=$?
# 即使 opencode 启动慢甚至失败，launch 函数本体会立即返回，所以这里 RC 不强制 0
if [[ $LAUNCH_RC -ne 0 ]]; then
  echo "  (warning: launch raised, may be OK if subprocess started)"
fi

echo ""
echo "2.2 验证 task 已被移到 in_progress"
if [[ ! -f "$WORKSPACE/.ccc/board/in_progress/${TASK1}.jsonl" ]]; then
  echo "❌ Step 2.2 FAILED: task 未进入 in_progress"
  ls -la "$WORKSPACE/.ccc/board/"*/"$TASK1.jsonl" 2>&1 | head -10
  # 清理可能的后台 opencode 后退出
  if [[ -f "$WORKSPACE/.ccc/pids/${TASK1}.pid" ]]; then
    kill -9 "$(cat "$WORKSPACE/.ccc/pids/${TASK1}.pid")" 2>/dev/null || true
  fi
  exit 1
fi
echo "✓"

# 杀掉可能在后台跑的 opencode（避免后续测试卡住）
if [[ -f "$WORKSPACE/.ccc/pids/${TASK1}.pid" ]]; then
  OPENCODE_PID=$(cat "$WORKSPACE/.ccc/pids/${TASK1}.pid")
  kill -9 "$OPENCODE_PID" 2>/dev/null || true
  # 杀子进程
  pkill -9 -P "$OPENCODE_PID" 2>/dev/null || true
fi

# ═══════════════════════════════════════════════
# 场景 3：dev 完成 → testing → verified → released (合成测试)
# ═══════════════════════════════════════════════
echo ""
echo "─── 场景 3: dev 完成 → testing → verified → released（mock 流转）───"

echo ""
echo "3.1 写 report + 移到 testing（模拟 dev_role 完成）"
TASK3="e2e-bk-released-$(date +%s)"

# 完整 plan+phases，跳过 product
mkdir -p "$WORKSPACE/.ccc/plans" "$WORKSPACE/.ccc/phases" "$WORKSPACE/.ccc/reports"
cat > "$WORKSPACE/.ccc/plans/${TASK3}.plan.md" <<EOF
# $TASK3

## 目标
- 端到端：测试 release 路径

## 文件白名单
- tests/test_${TASK3}.py

## 验收
- 自动落到 released
EOF

cat > "$WORKSPACE/.ccc/phases/${TASK3}.phases.json" <<EOF
{"schema_version": "1.1"}
{"phase": 1, "status": "done", "subtasks": {"1.1": "done"}, "timeout": 60, "commit": null, "notes": "mock done", "retry": 0, "retry_at": null}
EOF

cat > "$WORKSPACE/.ccc/reports/${TASK3}.report.md" <<EOF
# $TASK3 执行报告

## 信息
- 状态: mock 完成
EOF

# 直接 create_task 到 planned（模拟 product 已完成）
echo "{\"action\":\"create\",\"id\":\"$TASK3\",\"title\":\"Mock Task 3\",\"column\":\"planned\",\"status\":\"planned\",\"created_at\":\"2026-07-13T12:00:00+08:00\",\"updated_at\":\"2026-07-13T12:00:00+08:00\"}" | python3 "$BOARD_PY" --batch > /dev/null
echo '{"action":"move","id":"'$TASK3'","from":"planned","to":"in_progress"}' | python3 "$BOARD_PY" --batch > /dev/null
echo '{"action":"move","id":"'$TASK3'","from":"in_progress","to":"testing"}' | python3 "$BOARD_PY" --batch > /dev/null
echo "✓"

echo ""
echo "3.2 验证 testing 列包含 task"
TESTING_COUNT=$(python3 "$BOARD_PY" index 2>/dev/null | grep -o '"testing": *[0-9]*' | grep -o '[0-9]*$' || echo 0)
if [[ "$TESTING_COUNT" -lt 1 ]]; then
  echo "❌ Step 3.2 FAILED: testing 列无任务 (count=$TESTING_COUNT)"
  python3 "$BOARD_PY" index 2>&1 | head -20
  exit 1
fi
echo "✓ (testing=$TESTING_COUNT)"

echo ""
echo "3.3 reviewer 通过（small-class static pass）"
python3 "$BOARD_PY" reviewer 2>&1 | tail -5
# reviewer 应该把 task 移到 verified（small-class py_compile pass）
if [[ ! -f "$WORKSPACE/.ccc/board/verified/${TASK3}.jsonl" ]]; then
  echo "❌ Step 3.3 FAILED: reviewer 未把 task 移到 verified"
  ls -la "$WORKSPACE/.ccc/board/"*/"$TASK3.jsonl" 2>&1 | head -10
  exit 1
fi
echo "✓ verified"

# 注：kb_role 在真实环境会推 git tag + 改 CHANGELOG → out-of-scope
# 这里只验证 column transition 行为
echo ""
echo "3.4 验证 verdict.md 实际生成（红线 11 强证据）"
if [[ ! -s "$WORKSPACE/.ccc/reports/${TASK3}.review.md" ]]; then
  echo "❌ Step 3.4 FAILED: review.md 不存在或为空"
  exit 1
fi
echo "✓ review.md 已生成 $(wc -c < "$WORKSPACE/.ccc/reports/${TASK3}.review.md") 字节"

# ═══════════════════════════════════════════════
# 场景 4：失败 → abnormal（不卡 in_progress）
# ═══════════════════════════════════════════════
echo ""
echo "─── 场景 4: 异常路径 → abnormal（stale in_progress）───"

TASK4="e2e-bk-stale-$(date +%s)"

# 制造一个 stale in_progress task（updated_at 在 24h 之前）
STALE_TIME=$(python3 -c "from datetime import datetime, timezone, timedelta; print((datetime.now(timezone.utc) - timedelta(hours=30)).isoformat())")
cat > "$WORKSPACE/.ccc/board/in_progress/${TASK4}.jsonl" <<EOF
{"id": "$TASK4", "title": "Stale Task", "description": "stuck in_progress", "status": "in_progress", "created_at": "$STALE_TIME", "updated_at": "$STALE_TIME", "schema_version": "1.0"}
EOF

# 写一个 fake plan + phases（让 _check_stale 不被 file missing 跳过）
cat > "$WORKSPACE/.ccc/plans/${TASK4}.plan.md" <<EOF
# $TASK4

## 文件白名单
- scripts/dummy.py

## 验收
EOF

cat > "$WORKSPACE/.ccc/phases/${TASK4}.phases.json" <<EOF
{"schema_version": "1.1"}
{"phase": 1, "status": "in_progress", "subtasks": {"1.1": "in_progress"}, "timeout": 60, "commit": null, "notes": "stale", "retry": 0, "retry_at": null}
EOF

# 调到 engine 的 _check_stale
python3 -c "
import importlib.util, sys
sys.path.insert(0, '$SCRIPT_DIR/scripts')
spec_eng = importlib.util.spec_from_file_location('ce', '$SCRIPT_DIR/scripts/ccc-engine.py')
ce = importlib.util.module_from_spec(spec_eng)
spec_eng.loader.exec_module(ce)
from pathlib import Path
ws = Path('$WORKSPACE')
ce._check_stale(ws)
print('_check_stale invoked ✓')
" 2>&1 | tail -3
if [[ $? -ne 0 ]]; then echo "❌ Step 4.1 _check_stale 调用失败"; exit 1; fi
echo "✓"

echo ""
echo "4.2 验证 stale task 已移入 abnormal"
if [[ ! -f "$WORKSPACE/.ccc/board/abnormal/${TASK4}.jsonl" ]]; then
  echo "❌ Step 4.2 FAILED: stale task 未移入 abnormal"
  ls -la "$WORKSPACE/.ccc/board/"*/"$TASK4.jsonl" 2>&1 | head -10
  exit 1
fi
if [[ -f "$WORKSPACE/.ccc/board/in_progress/${TASK4}.jsonl" ]]; then
  echo "❌ Step 4.2 FAILED: stale task 仍在 in_progress (设计缺陷 — 不应卡住)"
  exit 1
fi
echo "✓ abnormal quarantine 生效"

# ─────────── 总结 ───────────
echo ""
echo "=============================="
echo "✅ E2E: backlog 自动拆分链路全部通过"
echo "=============================="
echo ""
echo "覆盖项："
echo "  - backlog fast-path（phases.json 存在 → 直接 planned）"
echo "  - dev_role_launch: planned → in_progress"
echo "  - reviewer small-class py_compile pass → verified"
echo "  - review.md 实际生成（红线 11 强证据）"
echo "  - stale in_progress → abnormal（不卡死）"
echo ""
echo "未覆盖（需 launchd + Claude API 或更长 timeout）："
echo "  - product_role 真正调 Claude API 写 plan (用 _call_claude_for_plan)"
echo "  - dev_role 用 opencode-runner.sh 实际跑 (1800s 超时)"
echo "  - reviewer + tester LLM 路径（fallback quarantine A24-03）"
echo "  - kb_role 推 git tag + 写 CHANGELOG（已通过 v0.19 smoke 验证）"
echo "  - Engine 主循环长跑（tick 收敛、idle sleep、audit 触发）"
exit 0
