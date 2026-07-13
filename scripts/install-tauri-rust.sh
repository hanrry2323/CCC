#!/usr/bin/env bash
# install-tauri-rust.sh — 安装 Rust 工具链（Tauri 依赖）
set -euo pipefail
if command -v rustc &>/dev/null; then
  echo " Rust 已安装: $(rustc --version)"
  exit 0
fi
echo " 安装 Rust 工具链..."
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
source "$HOME/.cargo/env"
echo " Rust $(rustc --version) 安装完成"
# 添加 macOS 目标
rustup target add aarch64-apple-darwin x86_64-apple-darwin
