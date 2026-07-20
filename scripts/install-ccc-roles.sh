#!/bin/bash
# install-ccc-roles.sh — 安装 CCC 看板服务 (v0.28.1+)
#
# v0.28.1 变更：Engine 5→1 合并，统一 com.ccc.engine 单进程管理所有 workspace，
# 不再按项目安装 per-workspace engine。非 CCC 项目运行此脚本将跳过 engine 安装。
# 保留 --workspace 参数仅用于初始化看板目录（backlog/planned 等 7 列 + index.json）。
#
# 用法:
#   ./install-ccc-roles.sh                                       # 仅写入 plist（默认不 load）
#   ./install-ccc-roles.sh --start                               # 写 control=enabled 并 bootstrap
#   ./install-ccc-roles.sh --workspace ~/program/qxo             # 初始化 qxo 项目看板目录（跳过 engine）
#   ./install-ccc-roles.sh --upgrade                             # 卸载旧角色 plist + 重装
#   ./install-ccc-roles.sh --workspace ~/program/qxo --upgrade   # 初始化项目目录 + 卸载旧角色
#
# v0.39.1: 默认绝不 launchctl load（根因：装完即 KeepAlive 复活）。
set -uo pipefail

# ── 参数 ──
WORKSPACE=""
UPGRADE=false
DO_START=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    --workspace) WORKSPACE="$2"; shift 2 ;;
    --workspace=*) WORKSPACE="${1#*=}"; shift ;;
    --upgrade) UPGRADE=true; shift ;;
    --start) DO_START=true; shift ;;
    *) echo "未知参数: $1"; exit 1 ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CCC_HOME="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck source=_ccc_launchd.sh
source "${SCRIPT_DIR}/_ccc_launchd.sh"
PLIST_DIR="${CCC_PLIST_STAGED}"
LOG_DIR="${HOME}/.ccc/logs"
mkdir -p "$LOG_DIR" "$CCC_PLIST_STAGED"

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
  <dict>
    <key>SuccessfulExit</key>
    <true/>
    <key>SuccessfulExitTimeout</key>
    <integer>30</integer>
    <key>Crashed</key>
    <true/>
  </dict>
  <key>RunAtLoad</key>
  <true/>
  <key>StandardOutPath</key>
  <string>${log}</string>
  <key>StandardErrorPath</key>
  <string>${log}</string>
  <key>ProcessType</key>
  <string>Interactive</string>
  <key>ThrottleInterval</key>
  <integer>60</integer>
  <key>WatchPaths</key>
  <array>
    <string>${HOME}/.ccc/control.json</string>
  </array>
  <key>SoftResourceLimits</key>
  <dict>
    <key>NumberOfFiles</key>
    <integer>4096</integer>
  </dict>
</dict>
</plist>
PLIST_EOF

  plutil -lint "$plist" >/dev/null || { echo "  ⚠ engine plist 不合法"; return 1; }
  if $DO_START; then
    PYTHONPATH="${CCC_HOME}/scripts${PYTHONPATH:+:$PYTHONPATH}" \
      python3 "${CCC_HOME}/scripts/_ccc_control.py" enable "install --start" >/dev/null
    ccc_launchd_finalize "$label" "$plist" --start --engine
  else
    ccc_launchd_finalize "$label" "$plist" --engine
  fi
}

# ── 安装/更新 board-server plist（如不存在）──
# 注意：board/hub 与 Engine 解耦。本脚本只 stage board，永不因 --start 拉起 UI KeepAlive。
# 前端开发: bash scripts/ccc-hub-dev.sh ；UI 常驻: guard ui --start
install_board() {
  local label="com.ccc.board"
  local plist="${PLIST_DIR}/${label}.plist"

  # 如果已存在且当前项目是 CCC 默认，跳过（避免覆盖）
  if [ -f "$plist" ] && [[ "$PROJECT_NAME" != "ccc" ]]; then
    echo "  跳过 board-server（仅 CCC 自身运行）"
    return
  fi
  if [ -f "$plist" ]; then
    echo "  board-server 已 staged，跳过"
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
    <string>7775</string>
    <string>--host</string>
    <string>127.0.0.1</string>
  </array>
  <key>WorkingDirectory</key>
  <string>${CCC_HOME}</string>
  <key>KeepAlive</key>
  <dict>
    <key>SuccessfulExit</key>
    <true/>
    <key>SuccessfulExitTimeout</key>
    <integer>30</integer>
    <key>Crashed</key>
    <true/>
  </dict>
  <key>RunAtLoad</key>
  <true/>
  <key>StandardOutPath</key>
  <string>${log}</string>
  <key>StandardErrorPath</key>
  <string>${log}</string>
  <key>ProcessType</key>
  <string>Interactive</string>
  <key>ThrottleInterval</key>
  <integer>60</integer>
  <key>SoftResourceLimits</key>
  <dict>
    <key>NumberOfFiles</key>
    <integer>4096</integer>
  </dict>
</dict>
</plist>
PLIST_EOF

  plutil -lint "$plist" >/dev/null || { echo "  ⚠ board plist 不合法"; return 1; }
  # 始终只 stage — 避免装 Engine 时把 Board KeepAlive 一并拉起
  ccc_launchd_finalize "$label" "$plist" --ui
}

echo ""
echo "=== 安装服务 ==="
install_engine
install_board

echo ""
echo "=== 状态 ==="
launchctl list 2>/dev/null | grep "${LABEL_PREFIX}" | sed 's/^/  /' || echo "  (no loaded agents)"
echo ""

if $UPGRADE; then
  echo "升级完成。旧角色 plist 已卸载。"
  echo "提示: 如 qxo 项目也需升级，运行:"
  echo "  $0 --workspace ~/program/qxo --upgrade"
fi
echo ""
if $DO_START; then
  echo "已 --start：control=enabled 且已尝试 bootstrap。"
else
  # 确保不会因历史 active plist 残留而复活
  bash "${CCC_HOME}/scripts/ccc-autostart-guard.sh" disable >/dev/null 2>&1 || \
    PYTHONPATH="${CCC_HOME}/scripts${PYTHONPATH:+:$PYTHONPATH}" \
      python3 "${CCC_HOME}/scripts/_ccc_control.py" disable "post-install safe default" >/dev/null 2>&1 || true
  echo "⚠ v0.39.1：plist 仅 staged，未 load。启用："
  echo "  bash ${CCC_HOME}/scripts/ccc-autostart-guard.sh enable --start"
fi
echo "  文档: ${CCC_HOME}/docs/CONTROL.md"
echo "Done. (prefix: ${LABEL_PREFIX}, workspace: ${WORKSPACE})"
