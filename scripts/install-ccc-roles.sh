#!/bin/bash
# install-ccc-roles.sh — 一键装 6 角色 launchd plist (v0.18)
#
# 用法:
#   ./install-ccc-roles.sh                          # 装到 CCC 自身
#   ./install-ccc-roles.sh --workspace ~/program/qxo  # 装到 qxo 项目
#
# 频率表 (老板指定):
#   product:  4h      = 14400s
#   dev:      30min   = 1800s
#   reviewer: 2h      = 7200s
#   tester:   4h      = 14400s
#   ops:      30min   = 1800s
#   kb:       23:00   (StartCalendarInterval)
set -uo pipefail

# ── 参数 ──
WORKSPACE=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --workspace) WORKSPACE="$2"; shift 2 ;;
    --workspace=*) WORKSPACE="${1#*=}"; shift ;;
    *) echo "未知参数: $1 (仅支持 --workspace <path>)"; exit 1 ;;
  esac
done

# ── 路径 ──
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CCC_HOME="$(cd "$SCRIPT_DIR/.." && pwd)"
PLIST_DIR="${HOME}/Library/LaunchAgents"
LOG_DIR="${HOME}/.ccc/logs"
mkdir -p "$LOG_DIR"

# ── 项目识别 ──
if [[ -n "$WORKSPACE" ]]; then
  WORKSPACE="$(cd "$WORKSPACE" 2>/dev/null && pwd)"  # 解析绝对路径
  PROJECT_NAME="$(basename "$WORKSPACE")"
  LABEL_PREFIX="com.ccc.${PROJECT_NAME}."
  PROJECT_TAG="${PROJECT_NAME}"

  # 初始化目标项目的看板
  mkdir -p "${WORKSPACE}/.ccc/board/"{backlog,planned,in_progress,testing,verified,released}
  if [ ! -f "${WORKSPACE}/.ccc/board/index.json" ]; then
    echo '{"backlog":0,"planned":0,"in_progress":0,"testing":0,"verified":0,"released":0}' \
      > "${WORKSPACE}/.ccc/board/index.json"
  fi
  echo "→ 项目: ${PROJECT_NAME} (${WORKSPACE})"
else
  WORKSPACE="$CCC_HOME"
  PROJECT_NAME="ccc"
  LABEL_PREFIX="com.ccc."
  PROJECT_TAG=""
  echo "→ 项目: CCC (默认)"
fi

ROLES=(product dev reviewer tester ops)
INTERVALS=(14400 1800 7200 14400 1800)

install_role() {
  local role=$1
  local plist="${PLIST_DIR}/${LABEL_PREFIX}${role}.plist"
  local script="${SCRIPT_DIR}/roles/${role}.sh"
  local out_log="${LOG_DIR}/${PROJECT_NAME}-role-${role}.out.log"
  local err_log="${LOG_DIR}/${PROJECT_NAME}-role-${role}.err.log"
  local interval=0
  for i in "${!ROLES[@]}"; do
    if [[ "${ROLES[$i]}" == "$role" ]]; then
      interval=${INTERVALS[$i]}
      break
    fi
  done

  # 环境变量段（仅非默认项目需要）
  local ENV_BLOCK=""
  if [[ -n "$PROJECT_TAG" ]]; then
    ENV_BLOCK='  <key>EnvironmentVariables</key>
  <dict>
    <key>CCC_WORKSPACE</key>
    <string>'"${WORKSPACE}"'</string>
  </dict>
'
  fi

  if [[ "$role" == "kb" ]]; then
    cat > "$plist" <<PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${LABEL_PREFIX}${role}</string>
  <key>ProgramArguments</key>
  <array>
    <string>${script}</string>
  </array>
${ENV_BLOCK}  <key>WorkingDirectory</key>
  <string>${WORKSPACE}</string>
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
  <string>${LABEL_PREFIX}${role}</string>
  <key>ProgramArguments</key>
  <array>
    <string>${script}</string>
  </array>
${ENV_BLOCK}  <key>WorkingDirectory</key>
  <string>${WORKSPACE}</string>
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

  plutil -lint "$plist" >/dev/null || { echo "  ⚠ plist 不合法: ${role}"; return 1; }
  launchctl unload "$plist" 2>/dev/null || true
  launchctl load -w "$plist"
  echo "  ✓ ${LABEL_PREFIX}${role}"
}

echo ""
echo "=== 安装 6 角色 ==="
for role in "${ROLES[@]}" kb; do
  install_role "$role"
done

echo ""
echo "=== 状态 ==="
launchctl list | grep "${LABEL_PREFIX}" | sed 's/^/  /'
echo ""
echo "Done. (prefix: ${LABEL_PREFIX}, workspace: ${WORKSPACE})"
