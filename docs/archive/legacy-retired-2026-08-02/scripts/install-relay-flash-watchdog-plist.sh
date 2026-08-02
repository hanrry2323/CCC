#!/usr/bin/env bash
# 安装 com.ccc.relay.flash-watchdog（60s StartInterval）— 探 M1 ai-loop-router
set -euo pipefail

CCC_HOME="${CCC_HOME:-$(cd "$(dirname "$0")/.." && pwd)}"
LABEL="com.ccc.relay.flash-watchdog"
PLIST="$HOME/Library/LaunchAgents/${LABEL}.plist"
SCRIPT="$CCC_HOME/scripts/ccc-relay-flash-watchdog.sh"
LOG_DIR="$HOME/.ccc/logs"

mkdir -p "$LOG_DIR" "$(dirname "$PLIST")"
chmod +x "$SCRIPT"

cat > "$PLIST" <<PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>${SCRIPT}</string>
  </array>
  <key>StartInterval</key>
  <integer>60</integer>
  <key>RunAtLoad</key>
  <true/>
  <key>StandardOutPath</key>
  <string>${LOG_DIR}/ccc-relay-flash-watchdog.out.log</string>
  <key>StandardErrorPath</key>
  <string>${LOG_DIR}/ccc-relay-flash-watchdog.err.log</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>CCC_RELAY_URL</key>
    <string>http://192.168.3.140:4100</string>
    <key>CCC_RELAY_LABEL</key>
    <string>com.ai-loop-router</string>
  </dict>
</dict>
</plist>
PLIST_EOF

plutil -lint "$PLIST" >/dev/null
launchctl bootout "gui/$(id -u)/${LABEL}" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
launchctl kickstart -k "gui/$(id -u)/${LABEL}" 2>/dev/null || true
echo "✓ ${LABEL} installed (60s flash probe → kickstart com.ai-loop-router on M1 after 3 fails)"
echo "  log: ${LOG_DIR}/ccc-relay-flash-watchdog.log"
