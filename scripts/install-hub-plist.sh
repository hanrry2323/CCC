#!/bin/bash
# install-hub-plist.sh — 安装 CCC Hub (Chat) launchd（v0.39.1 尊重控制面）
# 默认只 stage，不 load。要启动：--start（会 enable control）
set -uo pipefail

CCC_HOME="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=_ccc_launchd.sh
source "${CCC_HOME}/scripts/_ccc_launchd.sh"

DO_START=false
[[ "${1:-}" == "--start" ]] && DO_START=true

PLIST_STAGED="${CCC_PLIST_STAGED}/com.ccc.chat-server.plist"
SRC="${CCC_HOME}/scripts/com.ccc.chat-server.plist"

mkdir -p "$CCC_PLIST_STAGED"
cp "$SRC" "$PLIST_STAGED"
plutil -lint "$PLIST_STAGED" >/dev/null || { echo "plist 不合法"; exit 1; }

# 清端口占用（无论是否 start）
for port in 7777 8084 18084; do
  pids=$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)
  if [ -n "$pids" ]; then
    echo "清理 :$port → $pids"
    kill $pids 2>/dev/null || true
  fi
done

if $DO_START; then
  PYTHONPATH="${CCC_HOME}/scripts${PYTHONPATH:+:$PYTHONPATH}" \
    python3 "${CCC_HOME}/scripts/_ccc_control.py" enable "install-hub --start" >/dev/null
  ccc_launchd_finalize "com.ccc.chat-server" "$PLIST_STAGED" --start
  echo "✓ com.ccc.chat-server loaded"
else
  ccc_launchd_finalize "com.ccc.chat-server" "$PLIST_STAGED"
  echo "✓ com.ccc.chat-server staged only（未 load）"
  echo "  启动: $0 --start  或  bash scripts/ccc-autostart-guard.sh enable --start"
fi
echo "  Board API 应对齐: http://127.0.0.1:7775"
echo "  日志: /tmp/ccc-chat-server.{log,err}"
