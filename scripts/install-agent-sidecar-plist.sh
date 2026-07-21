#!/usr/bin/env bash
# install-agent-sidecar-plist.sh — Desktop 本机 Agent Sidecar launchd 常驻
# 与 Engine 控制面无关：Hub 抖不影响聊天；KeepAlive 崩溃自拉。
#
# 用法：
#   bash scripts/install-agent-sidecar-plist.sh           # 只写 plist + load
#   bash scripts/install-agent-sidecar-plist.sh --start   # 同上并 kickstart
#   bash scripts/install-agent-sidecar-plist.sh --stop
#   bash scripts/install-agent-sidecar-plist.sh --status
set -euo pipefail

CCC_HOME="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LABEL="com.ccc.agent-sidecar"
PLIST="${HOME}/Library/LaunchAgents/${LABEL}.plist"
UID_NUM="$(id -u)"
DOMAIN="gui/${UID_NUM}"

AGENT_PY="${CCC_HOME}/.venv-hub/bin/python"
if [[ ! -x "$AGENT_PY" ]]; then
  echo "需要 .venv-hub:"
  echo "  python3 -m venv ${CCC_HOME}/.venv-hub"
  echo "  ${CCC_HOME}/.venv-hub/bin/pip install -r ${CCC_HOME}/requirements-hub.txt"
  exit 1
fi

PORT="${CCC_AGENT_PORT:-7788}"
HOST="${CCC_AGENT_HOST:-127.0.0.1}"
LOG_DIR="${HOME}/Library/Logs/CCC"
LOG_OUT="${LOG_DIR}/agent-sidecar.log"
LOG_ERR="${LOG_DIR}/agent-sidecar.err"
PATH_EXTRA="${HOME}/.local/bin:${HOME}/.npm-global/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
TOKEN_FILE="${HOME}/.ccc/agent-token"
MINIMAX_KEY_FILE="${HOME}/.ccc/minimax-api-key"

mkdir -p "$LOG_DIR" "${HOME}/Library/LaunchAgents" "${HOME}/.ccc"

# 本机共享密钥（Desktop ↔ sidecar）；已有则复用
if [[ -n "${CCC_AGENT_TOKEN:-}" ]]; then
  AGENT_TOKEN="$CCC_AGENT_TOKEN"
elif [[ -f "$TOKEN_FILE" ]]; then
  AGENT_TOKEN="$(tr -d '[:space:]' < "$TOKEN_FILE")"
else
  AGENT_TOKEN="$(openssl rand -hex 32)"
fi
(umask 077; printf '%s\n' "$AGENT_TOKEN" > "$TOKEN_FILE")
chmod 600 "$TOKEN_FILE"

cmd="${1:-}"
case "$cmd" in
  --stop|stop)
    launchctl bootout "${DOMAIN}/${LABEL}" 2>/dev/null || true
    launchctl unload -w "$PLIST" 2>/dev/null || true
    # 清掉误起的 nohup 孤儿
    pkill -f "ccc-agent-sidecar.py" 2>/dev/null || true
    echo "✓ ${LABEL} stopped"
    exit 0
    ;;
  --status|status)
    echo "plist: $PLIST"
    if [[ -f "$PLIST" ]]; then
      echo "plist: present"
    else
      echo "plist: missing"
    fi
    launchctl print "${DOMAIN}/${LABEL}" 2>&1 | head -25 || echo "launchd: not loaded"
    curl -fsS --max-time 2 "http://${HOST}:${PORT}/health" 2>&1 | head -c 200 || echo "health: down"
    echo
    exit 0
    ;;
esac

# 默认直连 MiniMax Anthropic（对话更稳）。
# 可选上游（按优先级，互斥）：
#   1) CCC_AGENT_UPSTREAM_118INK=1 → Anthropic 兼容中转（默认模型 claude-opus-4-8）
#   2) CCC_AGENT_ROUTER=http://...   → 2017 旧中转（兼容保留，默认模型 flash）
#   3) 直连 MiniMax（默认）
# 不继承 shell 里的 ANTHROPIC_BASE_URL，避免误指本机旧 :4000
if [[ -n "${CCC_AGENT_UPSTREAM_118INK:-}" ]]; then
  # 118.ink 中转：Anthropic 兼容 /v1/messages；key 默认取 CCC_AGENT_118INK_KEY（写在 secrets.env）
  ROUTER="https://118.ink/v1"
  AUTH_TOKEN_VALUE="${CCC_AGENT_118INK_KEY:-${ANTHROPIC_AUTH_TOKEN:-}}"
  if [[ -z "$AUTH_TOKEN_VALUE" ]]; then
    echo "缺少 118.ink key：请设置 CCC_AGENT_118INK_KEY（或 ANTHROPIC_AUTH_TOKEN）" >&2
    echo "回退默认：unset CCC_AGENT_UPSTREAM_118INK 后重新安装" >&2
    exit 1
  fi
  AGENT_MODEL="${ANTHROPIC_MODEL:-claude-opus-4-8}"
elif [[ -n "${CCC_AGENT_ROUTER:-}" ]]; then
  ROUTER="${CCC_AGENT_ROUTER}"
  AUTH_TOKEN_VALUE="${ANTHROPIC_AUTH_TOKEN:-sk-trae-real-token-not-needed}"
  AGENT_MODEL="${ANTHROPIC_MODEL:-flash}"
else
  ROUTER="${CCC_ANTHROPIC_BASE_URL:-https://api.minimaxi.com/anthropic}"
  # 忽略 shell 里残留的中转假 token，避免「BASE=minimax + AUTH=trae」401
  _tok="${ANTHROPIC_AUTH_TOKEN:-}"
  if [[ -z "$_tok" || "$_tok" == "sk-trae-real-token-not-needed" ]]; then
    if [[ -f "$MINIMAX_KEY_FILE" ]]; then
      AUTH_TOKEN_VALUE="$(tr -d '[:space:]' < "$MINIMAX_KEY_FILE")"
    else
      echo "缺少 MiniMax key：请写入 ${MINIMAX_KEY_FILE}（chmod 600）或设置 ANTHROPIC_AUTH_TOKEN" >&2
      echo "也可临时回退中转：CCC_AGENT_ROUTER=http://192.168.3.116:4000 $0 --start" >&2
      exit 1
    fi
  else
    AUTH_TOKEN_VALUE="$_tok"
  fi
  AGENT_MODEL="${ANTHROPIC_MODEL:-MiniMax-M3}"
  # 若 ANTHROPIC_MODEL 仍是 flash/code 逻辑名，直连时改成上游 id
  if [[ "$AGENT_MODEL" == "flash" || "$AGENT_MODEL" == "code" ]]; then
    AGENT_MODEL="MiniMax-M3"
  fi
fi

# MiniMax / 中转鉴权
AUTH_TOKEN_BLOCK="    <key>ANTHROPIC_AUTH_TOKEN</key>
    <string>${AUTH_TOKEN_VALUE}</string>"

cat > "$PLIST" <<PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>${AGENT_PY}</string>
    <string>${CCC_HOME}/scripts/ccc-agent-sidecar.py</string>
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
  <!-- 防 live slot / SSE 堆积打满默认 256 FD（Too many open files → 对话假死） -->
  <key>SoftResourceLimits</key>
  <dict>
    <key>NumberOfFiles</key>
    <integer>8192</integer>
  </dict>
  <key>HardResourceLimits</key>
  <dict>
    <key>NumberOfFiles</key>
    <integer>8192</integer>
  </dict>
  <key>EnvironmentVariables</key>
  <dict>
    <key>CCC_HOME</key>
    <string>${CCC_HOME}</string>
    <key>CCC_EXECUTOR</key>
    <string>loop-code</string>
    <key>CCC_AGENT_HOST</key>
    <string>${HOST}</string>
    <key>CCC_AGENT_PORT</key>
    <string>${PORT}</string>
    <key>CCC_AGENT_CWD</key>
    <string>${CCC_HOME}</string>
    <key>CCC_AGENT_TOKEN</key>
    <string>${AGENT_TOKEN}</string>
    <key>CCC_AGENT_ALLOWED_ROOTS</key>
    <string>${HOME}/program:${CCC_HOME}</string>
    <key>ANTHROPIC_BASE_URL</key>
    <string>${ROUTER}</string>
${AUTH_TOKEN_BLOCK}
    <key>ANTHROPIC_MODEL</key>
    <string>${AGENT_MODEL}</string>
    <key>CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC</key>
    <string>1</string>
    <key>DISABLE_AUTOUPDATER</key>
    <string>1</string>
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

plutil -lint "$PLIST" >/dev/null

# 释放端口上的旧 nohup / 旧实例
pids=$(lsof -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null || true)
if [[ -n "${pids}" ]]; then
  echo "清理 :${PORT} → ${pids}"
  # shellcheck disable=SC2086
  kill $pids 2>/dev/null || true
  sleep 0.4
fi
pkill -f "ccc-agent-sidecar.py" 2>/dev/null || true
sleep 0.2

launchctl bootout "${DOMAIN}/${LABEL}" 2>/dev/null || true
launchctl enable "${DOMAIN}/${LABEL}" 2>/dev/null || true
launchctl bootstrap "${DOMAIN}" "$PLIST" 2>/dev/null \
  || launchctl load -w "$PLIST" 2>/dev/null \
  || true

if [[ "$cmd" == "--start" || "$cmd" == "start" || -z "$cmd" ]]; then
  launchctl kickstart -k "${DOMAIN}/${LABEL}" 2>/dev/null || true
fi

# 等健康
ok=0
for _ in 1 2 3 4 5 6 7 8 9 10 12 14 16; do
  if curl -fsS --max-time 1 "http://${HOST}:${PORT}/health" >/dev/null 2>&1; then
    ok=1
    break
  fi
  sleep 0.4
done

if [[ "$ok" == "1" ]]; then
  echo "✓ ${LABEL} loaded · http://${HOST}:${PORT} healthy"
else
  echo "⚠ ${LABEL} loaded but health not ready yet — 见 ${LOG_ERR}"
fi
echo "  plist: ${PLIST}"
echo "  token: ${TOKEN_FILE} (Desktop 自动读取；chmod 600)"
echo "  logs:  ${LOG_OUT} / ${LOG_ERR}"
echo "  stop:  bash ${CCC_HOME}/scripts/install-agent-sidecar-plist.sh --stop"
