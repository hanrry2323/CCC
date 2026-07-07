#!/bin/bash
# install-ccc-roles.sh — 一键装 6 角色 launchd plist (v0.18)
#
# 用法:
#   ./install-ccc-roles.sh                          # 装到 CCC 自身
#   ./install-ccc-roles.sh --workspace ~/program/qxo  # 装到 qxo 项目
#
# 频率表 (老板指定):
#   product:  4h      = 14400s
#   dev:      10min   = 600s
#   reviewer: 2h      = 7200s
#   tester:   4h      = 14400s
#   ops:      30min   = 1800s
#   kb:       23:00   (StartCalendarInterval)
#   regress:  23:30   (StartCalendarInterval, 每日回测)
set -uo pipefail

# ── 默认配置（source 前先有铺垫变量，防 errexit）──
DEFAULT_CONFIG="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/templates/ccc-config.sh"
if [ -f "$DEFAULT_CONFIG" ]; then
  source "$DEFAULT_CONFIG"
fi
# ROLES 必须是数组；source 后仍是空则 fallback
if [[ ${#ROLES[@]} -eq 0 ]]; then
  ROLES=(product dev reviewer tester ops kb regress)
fi

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
  # source 项目内配置
  if [ -f "$WORKSPACE/.ccc/config.sh" ]; then
    source "$WORKSPACE/.ccc/config.sh"
  fi

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

# ── 从配置获取间隔 ──
get_interval() {
  local role=$1
  case "$role" in
    product) echo "${PRODUCT_INTERVAL:-14400}" ;;
    dev) echo "${DEV_INTERVAL:-600}" ;;
    reviewer) echo "${REVIEWER_INTERVAL:-7200}" ;;
    tester) echo "${TESTER_INTERVAL:-14400}" ;;
    ops) echo "${OPS_INTERVAL:-1800}" ;;
    kb|regress) echo "" ;;  # calendar-based
    *) echo "" ;;
  esac
}

install_role() {
  local role=$1
  local plist="${PLIST_DIR}/${LABEL_PREFIX}${role}.plist"
  local script="${SCRIPT_DIR}/roles/${role}.sh"
  local out_log="${LOG_DIR}/${PROJECT_NAME}-role-${role}.out.log"
  local err_log="${LOG_DIR}/${PROJECT_NAME}-role-${role}.err.log"
  local interval=$(get_interval "$role")

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

  if [[ "$role" == "kb" ]] || [[ "$role" == "regress" ]]; then
    local cb_hour="${KB_HOUR:-23}"
    local cb_min="${KB_MINUTE:-0}"
    [[ "$role" == "regress" ]] && cb_min="${REGRESS_MINUTE:-30}" && cb_hour="${REGRESS_HOUR:-23}"
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
    <integer>${cb_hour}</integer>
    <key>Minute</key>
    <integer>${cb_min}</integer>
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
echo "=== 安装角色 ==="
for role in "${ROLES[@]}"; do
  install_role "$role"
done

echo ""
echo "=== 状态 ==="
launchctl list | grep "${LABEL_PREFIX}" | sed 's/^/  /'
echo ""
echo "Done. (prefix: ${LABEL_PREFIX}, workspace: ${WORKSPACE})"
