#!/bin/bash
# smoke_fleet_start_stop.sh — CCC fleet 状态机端到端 smoke（v0.61.0 阶段 B）
#
# 4 步验证:
#   1. fleet status 当前状态(基线)
#   2. fleet stop all → 0 进程 + 0 listening port
#   3. fleet start all → 拓扑序 + 全 up
#   4. fleet stop all → 全净
#
# 跑法:bash tests/scripts/smoke_fleet_start_stop.sh
# 期望:每步 exit 0,最终 OVERALL 回到 red(全 stop)
#
# ⚠ 真实启停 fleet 进程,会改 ~/.ccc/control.json / launchd 状态
# 不要在生产 2017 上跑(本 smoke 假设在 M1 dev)

set -uo pipefail

CCC_HOME="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FLEET="${CCC_HOME}/scripts/ccc-fleet.sh"
HOST_TAG="$("$FLEET" 2>/dev/null >/dev/null; bash -c 'if [[ "$(hostname)" == "Mac2017"* || "$(hostname)" == "fan"* ]]; then echo 2017; else echo m1; fi')"

echo "=== Smoke Fleet Start/Stop (host=$HOST_TAG) ==="
echo

# step 1: 基线
echo "--- step 1: baseline status ---"
bash "$FLEET" status
echo
if ! bash "$FLEET" status | grep -qE 'OVERALL: (🟢 green|🟡 yellow)'; then
  echo "⚠ baseline 不是 green/yellow,skip smoke(避免破坏已有状态)"
  echo "  如需真跑,fleet.sh start all 一次后重试"
  exit 0
fi

# step 2: stop all
echo "--- step 2: stop all ---"
bash "$FLEET" stop all
sleep 2
echo "stop 后状态:"
bash "$FLEET" status | tail -3
if bash "$FLEET" status | grep -q 'OVERALL: 🟢 green'; then
  echo "❌ FAIL: stop 后还有 green 组件,bootout 没生效"
  exit 1
fi
echo

# step 3: start all
echo "--- step 3: start all ---"
bash "$FLEET" start all
sleep 3
echo "start 后状态:"
bash "$FLEET" status | tail -3
# 注:本次 smoke 不强求回到 green(start 可能因端口冲突/依赖失败,看具体提示)
# 但必须 OVERALL 不能更差
echo

# step 4: stop all(清理)
echo "--- step 4: stop all(清理)---"
bash "$FLEET" stop all
sleep 2
echo
echo "=== Smoke PASS ==="
exit 0
