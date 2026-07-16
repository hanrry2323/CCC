#!/usr/bin/env bash
# ccc-hub-dev.sh — 前端/Hub 开发前台入口（v0.39.2）
#
# 设计目标：改 UI / 调路由 / 验看板时，**绝不**经 launchd KeepAlive，
# **绝不** enable Engine，**绝不**改 control.json 为 enabled。
#
# 用法:
#   bash scripts/ccc-hub-dev.sh          # 前台起 Board(:7775) + Hub(:7777)
#   bash scripts/ccc-hub-dev.sh stop     # 杀掉本脚本拉起的前台进程（按端口）
#
# 需要常驻（开机自启）时才用：
#   bash scripts/ccc-autostart-guard.sh ui --start
# 全流水线：
#   bash scripts/ccc-autostart-guard.sh enable --start

set -euo pipefail

CCC_HOME="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$CCC_HOME"

BOARD_PORT="${BOARD_PORT:-7775}"
HUB_PORT="${CCC_CHAT_PORT:-7777}"
LOG_DIR="${HOME}/.ccc/logs"
mkdir -p "$LOG_DIR"

# 前台旁路：board/chat 入口见此变量则跳过 control idle hold
export CCC_FOREGROUND=1
export CCC_CHAT_PORT="$HUB_PORT"
export CCC_CHAT_HOST="${CCC_CHAT_HOST:-127.0.0.1}"
export CCC_CHAT_USER="${CCC_CHAT_USER:-ccc}"
export CCC_CHAT_PASS="${CCC_CHAT_PASS:-ccc}"
export CCC_BOARD_URL="${CCC_BOARD_URL:-http://127.0.0.1:${BOARD_PORT}}"
export BOARD_PORT
export BOARD_HOST="${BOARD_HOST:-127.0.0.1}"
export CCC_CHAT_NO_OPEN="${CCC_CHAT_NO_OPEN:-1}"

_stop_ports() {
  for port in "$BOARD_PORT" "$HUB_PORT"; do
    pids=$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)
    if [[ -n "${pids:-}" ]]; then
      echo "stop :$port → $pids"
      # shellcheck disable=SC2086
      kill $pids 2>/dev/null || true
    fi
  done
}

if [[ "${1:-}" == "stop" ]]; then
  _stop_ports
  exit 0
fi

# 若 launchd 已占端口，提示改用前台（先卸 agent）
if launchctl list 2>/dev/null | grep -qE 'com\.ccc\.(board|chat-server)'; then
  echo "WARN: launchd 仍挂着 com.ccc.board/chat-server。"
  echo "  开发请先: bash scripts/ccc-autostart-guard.sh disable"
  echo "  再跑本脚本。继续将尝试占用端口…"
fi

_stop_ports
sleep 0.5

BOARD_LOG="${LOG_DIR}/hub-dev-board.log"
HUB_LOG="${LOG_DIR}/hub-dev-hub.log"

echo "CCC Hub DEV (foreground, no launchd, no engine)"
echo "  Board API  http://127.0.0.1:${BOARD_PORT}"
echo "  Hub UI     http://127.0.0.1:${HUB_PORT}  (ccc/ccc)"
echo "  control    untouched (still $(python3 -c "import sys; sys.path.insert(0,'scripts'); from _ccc_control import get_mode; print(get_mode())" 2>/dev/null || echo '?'))"
echo "  stop       bash scripts/ccc-hub-dev.sh stop   or Ctrl-C"
echo ""

python3 scripts/ccc-board-server.py --host 127.0.0.1 --port "$BOARD_PORT" \
  >"$BOARD_LOG" 2>&1 &
BOARD_PID=$!

cleanup() {
  echo ""
  echo "shutting down hub-dev…"
  kill "$BOARD_PID" 2>/dev/null || true
  _stop_ports
}
trap cleanup EXIT INT TERM

# 等 board 起来
for _ in 1 2 3 4 5 6 7 8 9 10; do
  if curl -sf -o /dev/null --max-time 1 "http://127.0.0.1:${BOARD_PORT}/api/health" 2>/dev/null \
     || curl -sf -o /dev/null --max-time 1 "http://127.0.0.1:${BOARD_PORT}/" 2>/dev/null; then
    break
  fi
  sleep 0.3
done

# Hub 前台（阻塞）
exec python3 scripts/ccc-chat-server.py --host "$CCC_CHAT_HOST" --port "$HUB_PORT" --no-open
