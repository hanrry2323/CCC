#!/usr/bin/env bash
# install-hk-egress-tunnel.sh — 香港出口：HK CONNECT 代理 + 2017 SSH 本地转发
#
# 拓扑：
#   Relay(2017) → http://127.0.0.1:18080 → ssh -L → HK:18080 CONNECT → OpenCode
#
# 用法（在 Mac2017 上跑）：
#   bash scripts/install-hk-egress-tunnel.sh --start
#   bash scripts/install-hk-egress-tunnel.sh --status
#   bash scripts/install-hk-egress-tunnel.sh --stop
#
# 环境：
#   CCC_HK_SSH=ccc-hk          SSH Host（默认写 ~/.ssh/config）
#   CCC_HK_HOST=124.156.166.72
#   CCC_HK_USER=ubuntu
#   CCC_HK_IDENTITY=~/.ssh/ccc-hk.pem
set -euo pipefail

CCC_HOME="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LABEL="com.ccc.hk-egress-tunnel"
LOCAL_PORT="${CCC_HK_LOCAL_PORT:-18080}"
HK_SSH="${CCC_HK_SSH:-ccc-hk}"
HK_HOST="${CCC_HK_HOST:-124.156.166.72}"
HK_USER="${CCC_HK_USER:-ubuntu}"
HK_IDENTITY="${CCC_HK_IDENTITY:-$HOME/.ssh/ccc-hk.pem}"
PLIST="$HOME/Library/LaunchAgents/${LABEL}.plist"
LOG_DIR="${HOME}/.ccc/logs"
BIN_DIR="${HOME}/.ccc/bin"
WRAPPER="${BIN_DIR}/ccc-hk-egress-tunnel.sh"
PROXY_SRC="${CCC_HOME}/relay/scripts/hk-connect-proxy.py"

mkdir -p "$LOG_DIR" "$BIN_DIR" "$HOME/Library/LaunchAgents"

_cmd="${1:-}"

_ssh() {
  ssh -o BatchMode=yes -o ConnectTimeout=12 -o IdentitiesOnly=yes \
    -i "$HK_IDENTITY" "${HK_USER}@${HK_HOST}" "$@"
}

_ensure_ssh_config() {
  if [[ ! -f "$HK_IDENTITY" ]]; then
    echo "❌ 缺少私钥: $HK_IDENTITY" >&2
    echo "   从 M1 拷贝: scp ~/.ssh/uxo.pem mac2017:~/.ssh/ccc-hk.pem && chmod 600 ~/.ssh/ccc-hk.pem" >&2
    exit 1
  fi
  chmod 600 "$HK_IDENTITY" 2>/dev/null || true
  local cfg="$HOME/.ssh/config"
  mkdir -p "$HOME/.ssh"
  touch "$cfg"
  if ! grep -qE "^Host[[:space:]]+${HK_SSH}\$" "$cfg" 2>/dev/null; then
    cat >> "$cfg" <<EOF

Host ${HK_SSH}
    HostName ${HK_HOST}
    User ${HK_USER}
    IdentityFile ${HK_IDENTITY}
    IdentitiesOnly yes
    ServerAliveInterval 30
    ServerAliveCountMax 3
    ExitOnForwardFailure yes
EOF
    echo "✓ 写入 SSH Host ${HK_SSH}"
  fi
}

_deploy_hk_proxy() {
  echo "→ 部署香港 CONNECT 代理 (python3)"
  _ssh "mkdir -p ~/ccc-egress && command -v python3 >/dev/null"
  scp -o BatchMode=yes -o IdentitiesOnly=yes -i "$HK_IDENTITY" \
    "$PROXY_SRC" "${HK_USER}@${HK_HOST}:ccc-egress/hk-connect-proxy.py"
  _ssh 'bash -s' <<'REMOTE'
set -euo pipefail
mkdir -p ~/.config/systemd/user ~/ccc-egress
chmod +x ~/ccc-egress/hk-connect-proxy.py
cat > ~/.config/systemd/user/ccc-hk-connect-proxy.service <<'UNIT'
[Unit]
Description=CCC HK HTTP CONNECT egress proxy
After=network.target

[Service]
Type=simple
WorkingDirectory=%h/ccc-egress
ExecStart=/usr/bin/python3 %h/ccc-egress/hk-connect-proxy.py
Restart=always
RestartSec=3
Environment=CCC_HK_PROXY_HOST=127.0.0.1
Environment=CCC_HK_PROXY_PORT=18080

[Install]
WantedBy=default.target
UNIT
pkill -f 'hk-connect-proxy.py' 2>/dev/null || true
if command -v systemctl >/dev/null && systemctl --user list-unit-files >/dev/null 2>&1; then
  # linger so user services survive logout
  loginctl enable-linger "$USER" 2>/dev/null || true
  systemctl --user daemon-reload
  systemctl --user enable --now ccc-hk-connect-proxy.service
  sleep 1
  systemctl --user is-active ccc-hk-connect-proxy.service
else
  nohup python3 ~/ccc-egress/hk-connect-proxy.py >>~/ccc-egress/proxy.log 2>&1 &
  sleep 1
fi
ss -lntp 2>/dev/null | grep 18080 || netstat -lntp 2>/dev/null | grep 18080 || true
REMOTE
  echo "✓ 香港代理已启动 (127.0.0.1:18080)"
}

_write_wrapper() {
  cat > "$WRAPPER" <<EOF
#!/usr/bin/env bash
# Auto-generated: SSH local forward → HK CONNECT proxy
exec /usr/bin/ssh -N \\
  -o ExitOnForwardFailure=yes \\
  -o ServerAliveInterval=30 \\
  -o ServerAliveCountMax=3 \\
  -o IdentitiesOnly=yes \\
  -i "${HK_IDENTITY}" \\
  -L 127.0.0.1:${LOCAL_PORT}:127.0.0.1:18080 \\
  ${HK_USER}@${HK_HOST}
EOF
  chmod +x "$WRAPPER"
}

_write_plist() {
  cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>${WRAPPER}</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>ThrottleInterval</key>
  <integer>10</integer>
  <key>StandardOutPath</key>
  <string>${LOG_DIR}/hk-egress-tunnel.out.log</string>
  <key>StandardErrorPath</key>
  <string>${LOG_DIR}/hk-egress-tunnel.err.log</string>
</dict>
</plist>
EOF
}

_start() {
  # 仅编排机
  if [[ "$(hostname)" != "Mac2017"* && "$(hostname)" != "fan"* ]]; then
    echo "❌ 本脚本应在 Mac2017 上运行（编排面出口）" >&2
    exit 1
  fi
  _ensure_ssh_config
  _deploy_hk_proxy
  _write_wrapper
  _write_plist
  local uid; uid=$(id -u)
  launchctl bootout "gui/${uid}/${LABEL}" 2>/dev/null || true
  launchctl bootstrap "gui/${uid}" "$PLIST"
  launchctl enable "gui/${uid}/${LABEL}" 2>/dev/null || true
  launchctl kickstart -k "gui/${uid}/${LABEL}" 2>/dev/null || true
  sleep 2
  _status
}

_stop() {
  local uid; uid=$(id -u)
  launchctl bootout "gui/${uid}/${LABEL}" 2>/dev/null || true
  echo "✓ tunnel stopped"
}

_status() {
  echo "=== ${LABEL} ==="
  launchctl list "${LABEL}" 2>/dev/null || echo "(not loaded)"
  if nc -z 127.0.0.1 "$LOCAL_PORT" 2>/dev/null; then
    echo "✓ local :${LOCAL_PORT} listening"
  else
    echo "✗ local :${LOCAL_PORT} not listening"
  fi
  # 经隧道探香港代理（CONNECT 探不通用 TCP）
  if curl -sS -m 8 -x "http://127.0.0.1:${LOCAL_PORT}" https://ifconfig.me 2>/dev/null | head -c 40; then
    echo
    echo "✓ egress via HK OK"
  else
    echo "✗ egress probe failed — 看 ${LOG_DIR}/hk-egress-tunnel.err.log"
  fi
}

case "$_cmd" in
  --start)  _start ;;
  --stop)   _stop ;;
  --status) _status ;;
  --deploy-hk-only)
    _ensure_ssh_config
    _deploy_hk_proxy
    ;;
  *)
    echo "用法: $0 --start|--stop|--status|--deploy-hk-only"
    exit 1
    ;;
esac
