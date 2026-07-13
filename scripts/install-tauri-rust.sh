#!/usr/bin/env bash
# install-tauri-rust.sh — 安装 Rust 工具链（Tauri 依赖）
# 用法: bash scripts/install-tauri-rust.sh
# 幂等：已安装则跳过

set -euo pipefail

if command -v rustc &>/dev/null && command -v cargo &>/dev/null; then
  echo " Rust 已安装: rustc $(rustc --version | awk '{print $2}') / cargo $(cargo --version | awk '{print $2}')"
  exit 0
fi

if [[ ! -t 0 ]]; then
  echo " ERROR: 非交互终端拒绝自动安装 Rust。请在终端手动运行:" >&2
  echo "   curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y" >&2
  exit 1
fi

echo " 安装 Rust 工具链..."
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
# shellcheck disable=SC1091
source "$HOME/.cargo/env"

echo " Rust $(rustc --version | awk '{print $2}') 安装完成"

ARCH="$(uname -m)"
case "$ARCH" in
  arm64|aarch64)
    rustup target add aarch64-apple-darwin
    ;;
  x86_64)
    rustup target add x86_64-apple-darwin
    ;;
  *)
    echo "WARN: 未识别架构 $ARCH，跳过 darwin target 安装" >&2
    ;;
esac

echo " Tauri Rust 工具链就绪"