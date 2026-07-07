#!/bin/bash
# install-board-plist.sh — 装 CCC 看板 HTTP 服务器 launchd plist (v0.18)
#
# 绑定 :6666（0.0.0.0，局域网可访问），随用户登录自动启动。
set -uo pipefail

CCC_HOME="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLIST_DIR="${HOME}/Library/LaunchAgents"
PLIST="${PLIST_DIR}/com.ccc.board.plist"
LOG_DIR="${HOME}/.ccc/logs"
mkdir -p "$LOG_DIR"

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
    <string>6666</string>
    <string>--host</string>
    <string>0.0.0.0</string>
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

# 先停旧版
launchctl unload "$PLIST" 2>/dev/null || true
sleep 1
launchctl load -w "$PLIST"

echo "✓ com.ccc.board 已装 → http://localhost:6666"
echo "  局域网: http://192.168.3.140:6666"
echo "  日志: ${LOG_DIR}/ccc-board.{out,err}.log"
