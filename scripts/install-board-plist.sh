#!/bin/bash
# install-board-plist.sh — 装 CCC 看板 HTTP 服务器 launchd（v0.39.1 尊重控制面）
# 默认只 stage，不 load。要启动：--start
set -uo pipefail

CCC_HOME="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=_ccc_launchd.sh
source "${CCC_HOME}/scripts/_ccc_launchd.sh"

DO_START=false
[[ "${1:-}" == "--start" ]] && DO_START=true

# ── 加载配置（BOARD_PORT / BOARD_HOST）──
DEFAULT_CONFIG="${CCC_HOME}/templates/ccc-config.sh"
if [ -f "$DEFAULT_CONFIG" ]; then
  # shellcheck source=/dev/null
  source "$DEFAULT_CONFIG"
fi

LOG_DIR="${HOME}/.ccc/logs"
mkdir -p "$LOG_DIR" "$CCC_PLIST_STAGED"

PLIST="${CCC_PLIST_STAGED}/com.ccc.board.plist"

cat > "$PLIST" <<PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.ccc.board</string>
  <key>ProgramArguments</key>
  <array>
    <string>${CCC_HOME}/scripts/ccc-board-server.py</string>
    <string>--port</string>
    <string>${BOARD_PORT:-7775}</string>
    <string>--host</string>
    <string>${BOARD_HOST:-127.0.0.1}</string>
  </array>
  <key>WorkingDirectory</key>
  <string>${CCC_HOME}</string>
  <key>KeepAlive</key>
  <true/>
  <key>RunAtLoad</key>
  <true/>
  <key>StandardOutPath</key>
  <string>${LOG_DIR}/ccc-board.out.log</string>
  <key>StandardErrorPath</key>
  <string>${LOG_DIR}/ccc-board.err.log</string>
  <key>ProcessType</key>
  <string>Background</string>
  <key>ThrottleInterval</key>
  <integer>5</integer>
</dict>
</plist>
PLIST_EOF

plutil -lint "$PLIST" >/dev/null || { echo "plist 不合法"; exit 1; }

if $DO_START; then
  PYTHONPATH="${CCC_HOME}/scripts${PYTHONPATH:+:$PYTHONPATH}" \
    python3 "${CCC_HOME}/scripts/_ccc_control.py" enable "install-board --start" >/dev/null
  ccc_launchd_finalize "com.ccc.board" "$PLIST" --start
  echo "✓ com.ccc.board loaded → http://127.0.0.1:${BOARD_PORT:-7775}"
else
  ccc_launchd_finalize "com.ccc.board" "$PLIST"
  echo "✓ com.ccc.board staged only（未 load）"
  echo "  启动: $0 --start"
fi
echo "  Hub UI → http://localhost:7777"
echo "  日志: ${LOG_DIR}/ccc-board.{out,err}.log"
