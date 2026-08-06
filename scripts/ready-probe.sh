#!/usr/bin/env bash
# ── CCC：查询 ready_for_merge 队列卡片数 ──
#
# 用法：
#   scripts/ready-probe.sh
#
# 环境：
#   CCC_BOARD_URL  默认 http://192.168.3.116:7788

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHON_BIN="${CCC_PYTHON_BIN:-python3}"
BOARD_URL="${CCC_BOARD_URL:-http://192.168.3.116:7788}"

# Fetch and extract ready count
if output=$(curl -sf --max-time 10 "${BOARD_URL}/board/ready_for_merge" 2>/dev/null); then
  count=$(echo "$output" | "$PYTHON_BIN" -c "import json,sys; d=json.load(sys.stdin); print(d.get('count', 0))" 2>/dev/null || echo "0")
else
  # Fallback to 0 if the request fails
  count=0
fi

echo "ready_count=${count}"
