#!/bin/bash
# install-hub-plist.sh — 安装 CCC Hub (Chat) launchd（v0.39.1 尊重控制面）
# 默认只 stage，不 load。要启动：--start（会 enable control）
# 路径按 CCC_HOME / HOME 生成，禁止写死 /Users/apple。
set -uo pipefail

CCC_HOME="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=_ccc_launchd.sh
source "${CCC_HOME}/scripts/_ccc_launchd.sh"

DO_START=false
[[ "${1:-}" == "--start" ]] && DO_START=true

HUB_PY="${CCC_HOME}/.venv-hub/bin/python"
if [[ ! -x "$HUB_PY" ]]; then
  echo "Hub 需要 .venv-hub（claude-agent-sdk 持续会话）:"
  echo "  python3 -m venv ${CCC_HOME}/.venv-hub"
  echo "  ${CCC_HOME}/.venv-hub/bin/pip install -r ${CCC_HOME}/requirements-hub.txt"
  exit 1
fi

PLIST_STAGED="${CCC_PLIST_STAGED}/com.ccc.chat-server.plist"
mkdir -p "$CCC_PLIST_STAGED" "${HOME}/.ccc/logs"

PATH_EXTRA="${HOME}/.local/bin:${HOME}/.npm-global/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
LOG_OUT="${HOME}/.ccc/logs/ccc-chat-server.log"
LOG_ERR="${HOME}/.ccc/logs/ccc-chat-server.err"
MINIMAX_KEY_FILE="${HOME}/.ccc/minimax-api-key"
# Hub 扇出 Claude：默认直连 MiniMax；CCC_HUB_ROUTER=http://127.0.0.1:4000 可回退中转
if [[ -n "${CCC_HUB_ROUTER:-}" ]]; then
  HUB_ANTHROPIC_BASE="${CCC_HUB_ROUTER}"
  HUB_ANTHROPIC_TOKEN="${ANTHROPIC_AUTH_TOKEN:-sk-trae-real-token-not-needed}"
  HUB_ANTHROPIC_MODEL="${ANTHROPIC_MODEL:-flash}"
else
  HUB_ANTHROPIC_BASE="${ANTHROPIC_BASE_URL:-https://api.minimaxi.com/anthropic}"
  if [[ -n "${ANTHROPIC_AUTH_TOKEN:-}" ]]; then
    HUB_ANTHROPIC_TOKEN="$ANTHROPIC_AUTH_TOKEN"
  elif [[ -f "$MINIMAX_KEY_FILE" ]]; then
    HUB_ANTHROPIC_TOKEN="$(tr -d '[:space:]' < "$MINIMAX_KEY_FILE")"
  else
    echo "缺少 ${MINIMAX_KEY_FILE}；或设 CCC_HUB_ROUTER=http://127.0.0.1:4000 回退中转" >&2
    exit 1
  fi
  HUB_ANTHROPIC_MODEL="${ANTHROPIC_MODEL:-MiniMax-M3}"
fi

DESKTOP_AGENT_URL="${CCC_DESKTOP_AGENT_URL:-http://192.168.3.140:7788}"
AGENT_TOKEN_VALUE="${CCC_AGENT_TOKEN:-}"
if [[ -z "$AGENT_TOKEN_VALUE" && -f "${HOME}/.ccc/agent-token" ]]; then
  AGENT_TOKEN_VALUE="$(tr -d '[:space:]' < "${HOME}/.ccc/agent-token")"
fi
if [[ -z "$AGENT_TOKEN_VALUE" ]]; then
  echo "提示: 未设 CCC_AGENT_TOKEN；遗留 /api/agent 探针需与 M1 ~/.ccc/agent-token 相同（产品聊不经此反代）" >&2
fi

cat > "$PLIST_STAGED" <<PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.ccc.chat-server</string>
  <key>ProgramArguments</key>
  <array>
    <string>${HUB_PY}</string>
    <string>${CCC_HOME}/scripts/ccc-chat-server.py</string>
    <string>--no-open</string>
  </array>
  <key>WorkingDirectory</key>
  <string>${CCC_HOME}</string>
  <key>KeepAlive</key>
  <dict>
    <key>SuccessfulExit</key>
    <true/>
    <key>SuccessfulExitTimeout</key>
    <integer>10</integer>
  </dict>
  <key>RunAtLoad</key>
  <true/>
  <key>ProcessType</key>
  <string>Background</string>
  <key>ThrottleInterval</key>
  <integer>30</integer>
  <key>EnvironmentVariables</key>
  <dict>
    <key>CCC_CHAT_HOST</key>
    <string>0.0.0.0</string>
    <key>CCC_CHAT_PORT</key>
    <string>7777</string>
    <key>CCC_CHAT_USER</key>
    <string>ccc</string>
    <key>CCC_CHAT_PASS</key>
    <string>ccc</string>
    <key>CCC_BOARD_URL</key>
    <string>http://127.0.0.1:7775</string>
    <key>CCC_DESKTOP_AGENT_URL</key>
    <string>${DESKTOP_AGENT_URL}</string>
    <key>CCC_AGENT_TOKEN</key>
    <string>${AGENT_TOKEN_VALUE}</string>
    <key>CCC_CHAT_NO_OPEN</key>
    <string>1</string>
    <key>ANTHROPIC_BASE_URL</key>
    <string>${HUB_ANTHROPIC_BASE}</string>
    <key>ANTHROPIC_AUTH_TOKEN</key>
    <string>${HUB_ANTHROPIC_TOKEN}</string>
    <key>ANTHROPIC_MODEL</key>
    <string>${HUB_ANTHROPIC_MODEL}</string>
    <key>PATH</key>
    <string>${PATH_EXTRA}</string>
  </dict>
  <key>StandardOutPath</key>
  <string>${LOG_OUT}</string>
  <key>StandardErrorPath</key>
  <string>${LOG_ERR}</string>
</dict>
</plist>
PLIST_EOF

plutil -lint "$PLIST_STAGED" >/dev/null || { echo "plist 不合法"; exit 1; }

for port in 7777 8084 18084; do
  pids=$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)
  if [ -n "$pids" ]; then
    echo "清理 :$port → $pids"
    kill $pids 2>/dev/null || true
  fi
done

if $DO_START; then
  PYTHONPATH="${CCC_HOME}/scripts${PYTHONPATH:+:$PYTHONPATH}" \
    python3 "${CCC_HOME}/scripts/_ccc_control.py" ui "install-hub --start" >/dev/null
  ccc_launchd_finalize "com.ccc.chat-server" "$PLIST_STAGED" --start --ui
  echo "✓ com.ccc.chat-server loaded"
  # kickstart 后有短暂不可达窗口：轮询至 200 或超时
  HUB_PORT="${CCC_CHAT_PORT:-7777}"
  HUB_USER="${CCC_CHAT_USER:-ccc}"
  HUB_PASS="${CCC_CHAT_PASS:-ccc}"
  ready=false
  for _i in $(seq 1 30); do
    code=$(curl -sS -m 1 -o /dev/null -w "%{http_code}" \
      -u "${HUB_USER}:${HUB_PASS}" \
      "http://127.0.0.1:${HUB_PORT}/api/desktop/projects" 2>/dev/null || echo 000)
    if [[ "$code" == "200" ]]; then
      ready=true
      echo "✓ Hub ready http://127.0.0.1:${HUB_PORT} (${_i}s)"
      break
    fi
    sleep 1
  done
  if ! $ready; then
    echo "WARN: Hub 未在 30s 内就绪（最后 http=${code:-?}），请查 ${LOG_ERR}" >&2
  fi
else
  ccc_launchd_finalize "com.ccc.chat-server" "$PLIST_STAGED" --ui
  echo "✓ com.ccc.chat-server staged only（未 load）"
  echo "  前台开发: bash ${CCC_HOME}/scripts/ccc-hub-dev.sh"
  echo "  常驻 UI:  bash ${CCC_HOME}/scripts/ccc-autostart-guard.sh ui --start"
fi
echo "  Board API 应对齐: http://127.0.0.1:7775"
echo "  日志: ${LOG_OUT} / ${LOG_ERR}"
echo "  对话主入口 = M1 Desktop + sidecar :7788（Hub /api/chat 已删；不再需要 CCC_EXECUTOR）"
