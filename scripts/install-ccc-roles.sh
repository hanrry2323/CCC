#!/bin/bash
# install-ccc-roles.sh — 一键装 6 角色 launchd plist (v0.18)
#
# 频率表 (老板指定):
#   product:  4h      = 14400s
#   dev:      30min   = 1800s
#   reviewer: 2h      = 7200s
#   tester:   4h      = 14400s
#   ops:      30min   = 1800s
#   kb:       23:00   (StartCalendarInterval)
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CCC_HOME="$(cd "$SCRIPT_DIR/.." && pwd)"
PLIST_DIR="${HOME}/Library/LaunchAgents"
LOG_DIR="${CCC_HOME}/.ccc/logs"
mkdir -p "$LOG_DIR"

ROLES=(product dev reviewer tester ops)
INTERVALS=(14400 1800 7200 14400 1800)

install_role() {
  local role=$1
  local plist="${PLIST_DIR}/com.ccc.${role}.plist"
  local script="${SCRIPT_DIR}/roles/${role}.sh"
  local out_log="${LOG_DIR}/role-${role}.out.log"
  local err_log="${LOG_DIR}/role-${role}.err.log"
  local interval=0
  for i in "${!ROLES[@]}"; do
    if [[ "${ROLES[$i]}" == "$role" ]]; then
      interval=${INTERVALS[$i]}
      break
    fi
  done

  if [[ "$role" == "kb" ]]; then
    cat > "$plist" <<PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.ccc.${role}</string>
  <key>ProgramArguments</key>
  <array>
    <string>${script}</string>
  </array>
  <key>WorkingDirectory</key>
  <string>${CCC_HOME}</string>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key>
    <integer>23</integer>
    <key>Minute</key>
    <integer>0</integer>
  </dict>
  <key>RunAtLoad</key>
  <true/>
  <key>StandardOutPath</key>
  <string>${out_log}</string>
  <key>StandardErrorPath</key>
  <string>${err_log}</string>
  <key>ProcessType</key>
  <string>Background</string>
</dict>
</plist>
PLIST_EOF
  else
    cat > "$plist" <<PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.ccc.${role}</string>
  <key>ProgramArguments</key>
  <array>
    <string>${script}</string>
  </array>
  <key>WorkingDirectory</key>
  <string>${CCC_HOME}</string>
  <key>StartInterval</key>
  <integer>${interval}</integer>
  <key>RunAtLoad</key>
  <true/>
  <key>StandardOutPath</key>
  <string>${out_log}</string>
  <key>StandardErrorPath</key>
  <string>${err_log}</string>
  <key>ProcessType</key>
  <string>Background</string>
</dict>
</plist>
PLIST_EOF
  fi

  plutil -lint "$plist" >/dev/null
  launchctl unload "$plist" 2>/dev/null || true
  launchctl load -w "$plist"
  echo "Installed: com.ccc.${role} (interval=${interval}s, daily 23:00 for kb)"
}

for role in "${ROLES[@]}" kb; do
  install_role "$role"
done

echo ""
echo "=== launchctl 状态 ==="
launchctl list | grep com.ccc
