#!/bin/bash
# register-qxo.sh — 在 qx-observer 项目注册 6 角色 (v0.18)
#
# 为 ~/program/qx-observer 安装 6 个 launchd plist：
#   com.ccc.qxo.{product,dev,reviewer,tester,ops,kb}
#
# 各 plist 设置 CCC_WORKSPACE=/Users/apple/program/qx-observer
# 角色脚本和 skill 仍在 CCC_HOME 下。
set -uo pipefail

QXO_HOME="$HOME/program/qx-observer"
CCC_HOME="$HOME/program/CCC"
PLIST_DIR="${HOME}/Library/LaunchAgents"
SCRIPT_DIR="${CCC_HOME}/scripts/roles"
LOG_DIR="${HOME}/.ccc/logs"
mkdir -p "$LOG_DIR"

# 角色配置
ROLES=(product dev reviewer tester ops)
INTERVALS=(14400 1800 7200 14400 1800)  # 4h / 30min / 2h / 4h / 30min

install_qxo_role() {
  local role=$1
  local plist="${PLIST_DIR}/com.ccc.qxo.${role}.plist"
  local script="${SCRIPT_DIR}/${role}.sh"
  local out_log="${LOG_DIR}/qxo-role-${role}.out.log"
  local err_log="${LOG_DIR}/qxo-role-${role}.err.log"
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
  <string>com.ccc.qxo.${role}</string>
  <key>ProgramArguments</key>
  <array>
    <string>${script}</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>CCC_WORKSPACE</key>
    <string>${QXO_HOME}</string>
  </dict>
  <key>WorkingDirectory</key>
  <string>${QXO_HOME}</string>
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
  <string>com.ccc.qxo.${role}</string>
  <key>ProgramArguments</key>
  <array>
    <string>${script}</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>CCC_WORKSPACE</key>
    <string>${QXO_HOME}</string>
  </dict>
  <key>WorkingDirectory</key>
  <string>${QXO_HOME}</string>
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

  plutil -lint "$plist" >/dev/null 2>&1 || {
    echo "ERROR: plutil failed for ${plist}"
    return 1
  }
  launchctl unload "$plist" 2>/dev/null || true
  launchctl load -w "$plist"
  echo "✓ com.ccc.qxo.${role}  (interval=${interval}s)"
}

echo "=== 注册 qxo 6 角色 ==="
echo "  QXO_HOME=${QXO_HOME}"
echo "  CCC_HOME=${CCC_HOME}"
echo ""

# 先初始化 qxo 看板
mkdir -p "${QXO_HOME}/.ccc/board/"{backlog,planned,in_progress,testing,verified,released}
if [ ! -f "${QXO_HOME}/.ccc/board/index.json" ]; then
  echo '{"backlog":0,"planned":0,"in_progress":0,"testing":0,"verified":0,"released":0}' > "${QXO_HOME}/.ccc/board/index.json"
fi
echo "✓ 看板初始化"

# 装 plist
for role in "${ROLES[@]}" kb; do
  install_qxo_role "$role"
done

echo ""
echo "=== launchctl 状态 ==="
launchctl list | grep com.ccc.qxo
