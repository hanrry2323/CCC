#!/bin/bash
# ccc-exec-launcher.sh — 三件套整合：monitor + Executor + poll
#
# 职责：一键起一个 Executor 任务所需的全部套件
#   1. 调用 ccc-monitor.sh 开/复用 monitor 窗口（幂等）
#   2. send-keys 到目标窗口触发 Executor（cat prompt | claude --bare）
#   3. 后台 nohup 启动 ccc-poll.sh，PID 写 /tmp/poll-<WINDOW>.pid
#
# 用法：
#   ccc-exec-launcher.sh <window> <prompt-file>
#     window     tmux 窗口号（数字）
#     prompt-file  包含 Executor prompt 的文件路径
#
# 前置：
#   - 已在 session "claude-code" 中（默认）；可用 SESSION=xxx 覆盖
#   - claude binary 在 PATH 中
#
# 退出码：0 = 三件套全部就位；非 0 = 参数错误或关键步骤失败
#
# v0.7d-prime 红线 14 配套脚本（强制配套 monitor + 5min 轮询）

set -uo pipefail

WINDOW="${1:?usage: ccc-exec-launcher.sh <window> <prompt-file>}"
PROMPT_FILE="${2:?usage: ccc-exec-launcher.sh <window> <prompt-file>}"
SESSION="${SESSION:-claude-code}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 1. 开 monitor（如果没开）—— 幂等
bash "$SCRIPT_DIR/ccc-monitor.sh" "$SESSION"

# 2. 启动 Executor（cat prompt-file | claude --bare）
tmux send-keys -t "$SESSION:$WINDOW" "cat $PROMPT_FILE | claude --bare --model deepseek-v4-flash" Enter

# 3. 后台启动 poll（自动检测完成 → 自动终止）
LOG_FILE="/tmp/poll-$WINDOW-$(date +%s).log"
nohup bash "$SCRIPT_DIR/ccc-poll.sh" "$WINDOW" "$SESSION" 300 > "$LOG_FILE" 2>&1 &
POLL_PID=$!
echo "$POLL_PID" > "/tmp/poll-$WINDOW.pid"

echo "[launcher] poll PID=$POLL_PID window=$WINDOW log=$LOG_FILE"
echo "[launcher] monitor=$SESSION:monitor (复用或新建)"
