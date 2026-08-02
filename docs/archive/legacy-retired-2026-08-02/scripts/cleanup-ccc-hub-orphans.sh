#!/bin/bash
# cleanup-ccc-hub-orphans.sh — 清理旧 Chat/Board 残留进程与错误端口
set -uo pipefail

echo "=== 清理 CCC Hub 残留 ==="

# 杀掉明确的临时测试 chat 进程（保留 launchd 管理的正式 Hub）
# 注意：并行 Claude/pytest 会话会反复拉起 :18084，需整组杀掉
pkill -9 -f 'pytest tests/scripts' 2>/dev/null || true
pkill -9 -f 'ccc-chat-server.py --port 18084' 2>/dev/null || true

for port in 8084 18084; do
  for _ in 1 2 3; do
    pids=$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)
    if [ -z "${pids:-}" ]; then
      break
    fi
    echo "kill -9 :$port → $pids"
    kill -9 $pids 2>/dev/null || true
    sleep 0.5
  done
  pids=$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)
  if [ -z "${pids:-}" ]; then
    echo "ok  :$port 无监听"
  else
    echo "WARN :$port 仍被占用 → $pids（可能有外部会话在重拉测试）"
  fi
done

sleep 1
echo "=== 当前相关监听 ==="
lsof -nP -iTCP:7775 -iTCP:7777 -iTCP:8084 -iTCP:18084 -sTCP:LISTEN 2>/dev/null || echo "(无 8084/18084)"
echo "完成"
