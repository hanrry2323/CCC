#!/usr/bin/env bash
# cockpit-desktop.sh — CCC Cockpit 桌面端开发入口
#
# 用法:
#   bash scripts/cockpit-desktop.sh         # 启动开发模式
#   bash scripts/cockpit-desktop.sh build    # 编译 release
#   bash scripts/cockpit-desktop.sh debug    # 编译 debug bundle
#   bash scripts/cockpit-desktop.sh stop     # 停止运行中的 chat-server sidecar
#
# 行为:
#   - 检查 Rust 工具链（缺则提示安装）
#   - 检查 chat-server 是否在 8084 运行（避免重复启动）
#   - 调 npx tauri dev / build 启动桌面应用
#   - 子进程 Tauri 自动 spawn chat-server sidecar（见 src-tauri/src/server.rs）
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

PORT="${CCC_CHAT_PORT:-8084}"

red()   { printf '\033[31m%s\033[0m\n' "$*"; }
green() { printf '\033[32m%s\033[0m\n' "$*"; }
yellow(){ printf '\033[33m%s\033[0m\n' "$*"; }

check_rust() {
  if ! command -v cargo &>/dev/null; then
    red " 未检测到 Rust 工具链。请先运行："
    echo "    bash scripts/install-tauri-rust.sh"
    exit 1
  fi
}

check_chat_server() {
  if curl -s -o /dev/null -w "%{http_code}" --max-time 1 "http://127.0.0.1:$PORT/" 2>/dev/null | grep -qE "^[12345]"; then
    yellow "  chat-server 已在 $PORT 端口运行 — 桌面端将复用现有实例"
    return 1  # 1 表示"已运行"
  fi
  return 0  # 0 表示"未运行"
}

case "${1:-dev}" in
  dev)
    check_rust
    if check_chat_server; then
      green "  启动 CCC Cockpit (dev) — Tauri 会在内部 spawn chat-server sidecar"
    fi
    npx @tauri-apps/cli dev
    ;;
  build)
    check_rust
    green "  编译 CCC Cockpit release .app/.dmg"
    npx @tauri-apps/cli build
    ;;
  debug)
    check_rust
    green "  编译 CCC Cockpit debug .app (快速验证)"
    npx @tauri-apps/cli build --debug
    ;;
  stop)
    yellow "  停止 chat-server (port $PORT)"
    pids=$(lsof -ti:"$PORT" 2>/dev/null || true)
    if [[ -n "$pids" ]]; then
      echo "$pids" | xargs kill 2>/dev/null || true
      green "  已停止"
    else
      yellow "  port $PORT 上无进程"
    fi
    ;;
  *)
    echo "用法: $0 {dev|build|debug|stop}" >&2
    exit 1
    ;;
esac
