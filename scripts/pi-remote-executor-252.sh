#!/bin/bash
# scripts/pi-remote-executor-252.sh — PI@252 目标机映射垫片
# 共享实现=scripts/pi-remote-executor.sh（win 形态实证：cmd + -p < promptfile + scp 正斜杠回传）。
# 新增目标机只加本垫片 + executors 槽位，不改共享实现（提案 §一 A 线「每机一脚本」口径）。
export PI_SSH_USER="win"
export PI_SSH_HOST="192.168.3.252"
export PI_REMOTE_FORM="win"
export PI_REMOTE_PROMPT_DIR="C:\Users\win"
export PI_REMOTE_PS="C:/Users/win/ccc-pi-run.ps1"
exec bash "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/pi-remote-executor.sh" "$@"
