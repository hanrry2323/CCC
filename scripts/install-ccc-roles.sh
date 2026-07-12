#!/bin/bash
# install-ccc-roles.sh — 安装 CCC Engine + 看板服务 (v0.20.1)
#
# v0.20.1 变更：替代 7 角色定时轮询，改为单一 Engine 常驻进程串行执行。
#
# 用法:
#   ./install-ccc-roles.sh                            # 安装到 CCC 自身
#   ./install-ccc-roles.sh --workspace ~/program/qxo  # 安装到 qxo 项目
#   ./install-ccc-roles.sh --upgrade                  # 先卸载旧角色，再装 engine
#   ./install-ccc-roles.sh --workspace ~/program/qxo --upgrade
set -uo pipefail

# ── 参数 ──
WORKSPACE=""
UPGRADE=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    --workspace) WORKSPACE="$2"; shift 2 ;;
    --workspace=*) WORKSPACE="${1#*=}"; shift ;;
    --upgrade) UPGRADE=true; shift ;;
    *) echo "未知参数: $1"; exit 1 ;;
  esac
done

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
  # source 项目配置
  if [ -f "$WORKSPACE/.ccc/config.sh" ]; then
    source "$WORKSPACE/.ccc/config.sh"
  fi
  # 初始化看板目录
  mkdir -p "${WORKSPACE}/.ccc/board/"{backlog,planned,in_progress,testing,verified,released,abnormal,events}
  if [ ! -f "${WORKSPACE}/.ccc/board/index.json" ]; then
    echo '{"backlog":0,"planned":0,"in_progress":0,"testing":0,"verified":0,"released":0,"abnormal":0}' \
      > "${WORKSPACE}/.ccc/board/index.json"
  fi
  echo "→ 项目: ${PROJECT_NAME} (${WORKSPACE})"
else
  WORKSPACE="$CCC_HOME"
  PROJECT_NAME="ccc"
  LABEL_PREFIX="com.ccc."
  echo "→ 项目: CCC (默认)"
fi

# ── --upgrade: 先卸载旧角色 ──
if $UPGRADE; then
  echo ""
  echo "=== 卸载旧角色 ==="
  # 卸载当前项目的旧角色 plist
  OLD_ROLES=("dev" "reviewer" "tester" "kb" "product" "ops" "regress")
  for role in "${OLD_ROLES[@]}"; do
    label="${LABEL_PREFIX}${role}"
    plist="${PLIST_DIR}/${label}.plist"
    if [ -f "$plist" ]; then
      echo -n "  卸载 ${label} ... "
      launchctl unload "$plist" 2>/dev/null && echo -n "unloaded "
      rm -f "$plist" && echo "removed" || echo "remove_fail"
    fi
  done

  # 卸载 CCC 自身的旧角色（跨项目）
  if [[ -n "$WORKSPACE" ]]; then
    echo "  (保留 CCC 自身的旧角色，单独对 CCC 跑 --upgrade 以清理)"
  fi
fi

# ── 安装 Engine plist（v0.28.1+ 统一引擎）──
# 不再按 workspace 安装多 engine，只有 com.ccc.engine 一个统一进程管理所有 workspace。
# 非 CCC 项目运行此脚本时跳过 engine（由 CCC 的统一引擎管辖）。
install_engine() {
  local label="com.ccc.engine"
  local plist="${PLIST_DIR}/${label}.plist"
  local script="${CCC_HOME}/scripts/ccc-engine.sh"
  local log="${LOG_DIR}/ccc-engine.log"

  # 非 CCC 项目跳过 engine 安装（统一引擎只装在 CCC 自身）
  if [[ "$PROJECT_NAME" != "ccc" ]]; then
    echo "  v0.28.1+ 统一引擎: 跳过（engine 由 CCC 统一管理）"
    return
  fi

  cat > "$plist" <<PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${label}</string>
  <key>ProgramArguments</key>
  <array>
    <string>${script}</string>
  </array>
  <key>WorkingDirectory</key>
  <string>${CCC_HOME}</string>
  <key>KeepAlive</key>
  <true/>
  <key>RunAtLoad</key>
  <true/>
  <key>StandardOutPath</key>
  <string>${log}</string>
  <key>StandardErrorPath</key>
  <string>${log}</string>
  <key>ProcessType</key>
  <string>Background</string>
  <key>ThrottleInterval</key>
  <integer>10</integer>
</dict>
</plist>
PLIST_EOF

  plutil -lint "$plist" >/dev/null || { echo "  ⚠ engine plist 不合法"; return 1; }
  launchctl unload "$plist" 2>/dev/null || true
  launchctl load -w "$plist"
  echo "  ✓ ${label}（统一引擎）"
}

# ── 安装/更新 board-server plist（如不存在）──
install_board() {
  local label="com.ccc.board"
  local plist="${PLIST_DIR}/${label}.plist"

  # 如果已存在且当前项目是 CCC 默认，跳过（避免覆盖）
  if [ -f "$plist" ] && [[ "$PROJECT_NAME" != "ccc" ]]; then
    echo "  跳过 board-server（仅 CCC 自身运行）"
    return
  fi
  if [ -f "$plist" ]; then
    echo "  board-server 已安装，跳过"
    return
  fi

  local log="${LOG_DIR}/ccc-board.log"
  cat > "$plist" <<PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${label}</string>
  <key>ProgramArguments</key>
  <array>
    <string>${CCC_HOME}/scripts/ccc-board-server.py</string>
    <string>--port</string>
    <string>7777</string>
    <string>--host</string>
    <string>127.0.0.1</string>
  </array>
  <key>WorkingDirectory</key>
  <string>${CCC_HOME}</string>
  <key>KeepAlive</key>
  <true/>
  <key>RunAtLoad</key>
  <true/>
  <key>StandardOutPath</key>
  <string>${log}</string>
  <key>StandardErrorPath</key>
  <string>${log}</string>
  <key>ProcessType</key>
  <string>Background</string>
  <key>ThrottleInterval</key>
  <integer>5</integer>
</dict>
</plist>
PLIST_EOF

  plutil -lint "$plist" >/dev/null || { echo "  ⚠ board plist 不合法"; return 1; }
  launchctl unload "$plist" 2>/dev/null || true
  launchctl load -w "$plist"
  echo "  ✓ ${label}"
}

echo ""
echo "=== 安装服务 ==="
install_engine
install_board

echo ""
echo "=== 状态 ==="
launchctl list | grep "${LABEL_PREFIX}" | sed 's/^/  /'
echo ""

if $UPGRADE; then
  echo "升级完成。旧角色 plist 已卸载。"
  echo "提示: 如 qxo 项目也需升级，运行:"
  echo "  $0 --workspace ~/program/qxo --upgrade"
fi
echo "Done. (prefix: ${LABEL_PREFIX}, workspace: ${WORKSPACE})"
