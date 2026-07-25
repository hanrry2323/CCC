#!/bin/bash
# test_reviewer_bg.sh — ccc-reviewer-bg.sh 静态/单元测试(v0.62.0 阶段 1)
#
# 测 3 项:
#   1. syntax(脚本不依赖运行时也能 bash -n 过)
#   2. 参数解析(不传参报错;少参报错;6 参 + 选参正确)
#   3. 函数入口验证(nohup ... & 启动模式;session_id 文件预期路径)
#
# 不真调 claude — 真 E2E 由 smoke_v0.62.0.sh(阶段 5)覆盖。

set -uo pipefail

CCC_HOME="$(cd "$(dirname "$0")/../.." && pwd)"
SCRIPT="$CCC_HOME/scripts/ccc-reviewer-bg.sh"
FAILED=0
_log_pass() { printf "\033[32m✓ %s\033[0m\n" "$1"; }
_log_fail() { printf "\033[31m✗ %s\033[0m\n" "$1"; FAILED=$((FAILED + 1)); }

# ── Case 1: syntax ─────────────────────────────────────
if bash -n "$SCRIPT" 2>/dev/null; then
  _log_pass "case 1: syntax OK"
else
  _log_fail "case 1: bash -n 失败"
fi

# ── Case 2: 参数解析(不调 claude,只验 usage 错 + 参数赋值)──
# 用 dry-run 模式:ccc-reviewer-bg.sh 第 1 行 `${1:?usage:}` 报缺参错
TESTDIR="$(mktemp -d)"
rc1=0; rc2=0; rc3=0
bash "$SCRIPT" 2>"$TESTDIR/err1" 1>/dev/null || rc1=$?
bash "$SCRIPT" "only-task-id" 2>"$TESTDIR/err2" 1>/dev/null || rc2=$?
bash "$SCRIPT" "t1" "p1" "ws" "model" "/dev/null" 2>"$TESTDIR/err3" 1>/dev/null || rc3=$?
[[ $rc1 -ne 0 && $rc2 -ne 0 && $rc3 -ne 0 ]] \
  && _log_pass "case 2: 参数缺失均 exit 非 0 (rc1=$rc1 rc2=$rc2 rc3=$rc3)" \
  || _log_fail "case 2: 缺参未拒(rc1=$rc1 rc2=$rc2 rc3=$rc3)"

# 验证 6 参 + 选参完整时,nohup 启动后立刻检查文件被建
OUT="$TESTDIR/case3"
mkdir -p "$OUT"
HOME="$TESTDIR" bash "$SCRIPT" \
  "test-task" "reviewer" "/tmp" "flash" "/dev/null" "$OUT" \
  --hard-kill-after 2 2>"$TESTDIR/err4" 1>/dev/null &
BG_PID=$!
# 等 4s 让 ccc-reviewer-bg.sh 启动后台 + mock sleep 跑完
sleep 4
# 验证 <task>.reviewer.out 文件被建(via nohup stdout 捕获)
if [[ -s "$OUT/test-task.reviewer.out" ]]; then
  _log_pass "case 3: 6 参启动后 <task>.reviewer.out 文件被建"
else
  _log_fail "case 3: out 文件未建 (err: $(cat $TESTDIR/err4 2>/dev/null | head -3))"
fi
# 收尾
kill $BG_PID 2>/dev/null
pkill -f "ccc-reviewer-bg.sh" 2>/dev/null
wait 2>/dev/null

rm -rf "$TESTDIR"

if [[ $FAILED -eq 0 ]]; then
  echo "✓ test_reviewer_bg.sh 3/3 全过"
  exit 0
fi
echo "✗ test_reviewer_bg.sh $FAILED case fail"
exit 1
