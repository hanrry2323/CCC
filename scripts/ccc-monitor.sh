#!/bin/bash
# ccc-monitor.sh — 自动开 tmux monitor 窗口（如果已开就跳过）
#
# 职责：检测当前 session 是否已有名为 "monitor" 的窗口；
#       - 已有 → 打印 "[monitor] 已存在" 并 exit 0（幂等）
#       - 没有 → 新建 monitor 窗口，每 10s 清屏打印所有窗口摘要
#
# 用法：
#   ccc-monitor.sh [SESSION]              # SESSION 默认 claude-code
#
# 退出码：0 = 窗口已存在或新建成功；非 0 = tmux 调用失败
#
# v0.7d-prime 红线 14 配套脚本

set -uo pipefail

SESSION="${1:-claude-code}"

# 幂等检测：tmux 中是否已存在名为 monitor 的窗口
if tmux list-windows -t "$SESSION" 2>/dev/null | grep -q "monitor"; then
  echo "[monitor] 已存在"
  exit 0
fi

# 新建 monitor 窗口（双引号让外层 bash 展开 $SESSION，符合红线 20 v3 portability）
tmux new-window -t "$SESSION" -n monitor "bash -c 'while true; do clear; echo \"=== \$(date) monitor ===\"; tmux list-windows -t $SESSION; echo; for w in \$(tmux list-windows -t $SESSION -F \"#I\" 2>/dev/null); do echo \"--- window \$w ---\"; tmux capture-pane -t $SESSION:\$w -p 2>/dev/null | tail -5; done; sleep 10; done'"

echo "[monitor] 已开"
