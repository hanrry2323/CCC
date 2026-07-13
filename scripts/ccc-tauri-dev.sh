#!/usr/bin/env bash
# ccc-tauri-dev.sh — 快速启动 CCC Cockpit 开发模式 (轻量包装)
#
# 区别于 cockpit-desktop.sh:
#   - 不做端口预检（sidecar 启动时会自动处理）
#   - 不做 Rust 工具链预检
#   - 直接 forward 到 npx tauri dev
#
# 适用于：已经知道环境就绪，只想快速启动 GUI 调试
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

exec npx @tauri-apps/cli dev "$@"
