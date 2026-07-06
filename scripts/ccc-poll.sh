#!/bin/bash
# ccc-poll.sh — 5 分钟轮询指定窗口 + 完成检测 + 自动终止
#
# 职责：每 INTERVAL 秒捕获一次 pane 内容，检测是否出现 prompt "❯"
#       且不再有 "esc to interrupt"（表示 Executor 已完成，回到待命态）
#       一旦命中完成信号 → 写最终 pane 到 /tmp/poll-final-<ts>.txt → break
#
# 用法：
#   ccc-poll.sh [WINDOW] [SESSION] [INTERVAL]
#     WINDOW   默认 1
#     SESSION  默认 claude-code
#     INTERVAL 默认 300（5 分钟）；手测可用 5
#
# 退出码：0 = 完成信号命中；非 0 = 参数错误或 tmux 调用失败
#
# v0.7d-prime 红线 14/15 配套脚本（红线 15：完成自动终止）

set -uo pipefail

WINDOW="${1:-1}"
SESSION="${2:-claude-code}"
INTERVAL="${3:-300}"

START=$(date +%s)
echo "[poll] start window=$SESSION:$WINDOW interval=${INTERVAL}s"

while true; do
  sleep "$INTERVAL"
  PANE=$(tmux capture-pane -t "$SESSION:$WINDOW" -p 2>/dev/null | tail -5)
  NOW=$(date +%s)
  ELAPSED=$((NOW - START))

  # 完成信号：单独 prompt "❯" + 无 "esc to interrupt"
  if echo "$PANE" | grep -q "❯" && ! echo "$PANE" | grep -q "esc to interrupt"; then
    echo "[poll] 完成检测 elapsed=${ELAPSED}s"
    echo "$PANE" > "/tmp/poll-final-$(date +%s).txt"
    break
  fi
  echo "[poll] elapsed=${ELAPSED}s"
done
echo "[poll] 退出"
