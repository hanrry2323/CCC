#!/usr/bin/env bash
# install-hub-tunnel-plist.sh — M1→Mac2017 Hub SSH 本地转发（稳定性主路径）
#
# 证据（2026-07-22）：LAN http://192.168.3.116:7777 可 TCP 通但 HTTP 偶发/整段超时
# （远端 Send-Q 积压）；ssh -L 127.0.0.1:17777:127.0.0.1:7777 连续探活满绿。
# 因此 Desktop / sidecar 默认走本机隧道，不再赌 Wi‑Fi/交换机对 7777 的直连。
#
# 用法：
#   bash scripts/install-hub-tunnel-plist.sh           # 写 plist + load
#   bash scripts/install-hub-tunnel-plist.sh --start   # 同上并 kickstart
#   bash scripts/install-hub-tunnel-plist.sh --stop
#   bash scripts/install-hub-tunnel-plist.sh --status
#   bash scripts/install-hub-tunnel-plist.sh --smoke   # 30 次探活
#
# 环境：
#   CCC_HUB_TUNNEL_PORT   本地端口，默认 17777
#   CCC_HUB_SSH_HOST      SSH Host，默认 mac2017（可用 tb-mac2017）
#   CCC_HUB_REMOTE        远端 Hub，默认 127.0.0.1:7777
set -euo pipefail

CCC_HOME="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LABEL="com.ccc.hub-tunnel"
PLIST="${HOME}/Library/LaunchAgents/${LABEL}.plist"
UID_NUM="$(id -u)"
DOMAIN="gui/${UID_NUM}"
LOG_DIR="${HOME}/Library/Logs/CCC"
LOG_OUT="${LOG_DIR}/hub-tunnel.log"
LOG_ERR="${LOG_DIR}/hub-tunnel.err"
LOCAL_PORT="${CCC_HUB_TUNNEL_PORT:-17777}"
SSH_HOST="${CCC_HUB_SSH_HOST:-mac2017}"
REMOTE="${CCC_HUB_REMOTE:-127.0.0.1:7777}"
WRAP="${HOME}/.ccc/bin/ccc-hub-tunnel.sh"
TUNNEL_URL="http://127.0.0.1:${LOCAL_PORT}"

mkdir -p "$LOG_DIR" "${HOME}/Library/LaunchAgents" "${HOME}/.ccc/bin"

ACTION="${1:-}"
case "$ACTION" in
  --stop)
    launchctl bootout "${DOMAIN}/${LABEL}" 2>/dev/null || true
    # 清掉手启残留
    pkill -f "ssh .*${LOCAL_PORT}:${REMOTE}" 2>/dev/null || true
    echo "stopped ${LABEL}"
    exit 0
    ;;
  --status)
    launchctl print "${DOMAIN}/${LABEL}" 2>&1 | grep -E "state |pid |last exit|runs =|program =" | head -20 || echo "not loaded"
    lsof -nP -iTCP:"${LOCAL_PORT}" -sTCP:LISTEN 2>/dev/null || echo "port ${LOCAL_PORT}: not listening"
    curl -sS -m 3 -u "${CCC_CHAT_USER:-ccc}:${CCC_CHAT_PASS:-ccc}" \
      -o /dev/null -w "tunnel_config %{http_code} %{time_total}\n" \
      "${TUNNEL_URL}/api/desktop/config" || echo "tunnel_config FAIL"
    exit 0
    ;;
  --smoke)
    ok=0; fail=0
    for i in $(seq 1 30); do
      code=$(curl -sS -m 2 -u "${CCC_CHAT_USER:-ccc}:${CCC_CHAT_PASS:-ccc}" \
        -o /dev/null -w "%{http_code}" "${TUNNEL_URL}/api/desktop/config" 2>/dev/null || echo 000)
      if [[ "$code" == "200" ]]; then ok=$((ok+1)); else fail=$((fail+1)); echo "fail#$i $code"; fi
    done
    echo "smoke tunnel ${TUNNEL_URL} ok=$ok fail=$fail"
    [[ "$fail" -eq 0 ]]
    exit $?
    ;;
  ""|--start) ;;
  *)
    echo "usage: $0 [--start|--stop|--status|--smoke]"
    exit 2
    ;;
esac

# 包装脚本：ExitOnForwardFailure + KeepAlive；前台跑，交给 launchd 守护
cat > "$WRAP" <<EOF
#!/usr/bin/env bash
set -euo pipefail
exec /usr/bin/ssh -N \\
  -o BatchMode=yes \\
  -o ExitOnForwardFailure=yes \\
  -o ServerAliveInterval=15 \\
  -o ServerAliveCountMax=4 \\
  -o TCPKeepAlive=yes \\
  -o StrictHostKeyChecking=accept-new \\
  -L 127.0.0.1:${LOCAL_PORT}:${REMOTE} \\
  ${SSH_HOST}
EOF
chmod +x "$WRAP"

# 先清手启/旧进程，避免端口占用导致 launchd 起不来
pkill -f "ssh .*${LOCAL_PORT}:${REMOTE}" 2>/dev/null || true
if command -v lsof >/dev/null 2>&1; then
  for p in $(lsof -nP -iTCP:"${LOCAL_PORT}" -sTCP:LISTEN -t 2>/dev/null || true); do
    kill "$p" 2>/dev/null || true
  done
fi
sleep 0.4

cat > "$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>${WRAP}</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>ThrottleInterval</key>
  <integer>5</integer>
  <key>StandardOutPath</key>
  <string>${LOG_OUT}</string>
  <key>StandardErrorPath</key>
  <string>${LOG_ERR}</string>
</dict>
</plist>
PLIST

launchctl bootout "${DOMAIN}/${LABEL}" 2>/dev/null || true
launchctl bootstrap "$DOMAIN" "$PLIST"
launchctl enable "${DOMAIN}/${LABEL}" 2>/dev/null || true

if [[ "$ACTION" == "--start" || "$ACTION" == "" ]]; then
  launchctl kickstart -k "${DOMAIN}/${LABEL}" 2>/dev/null || true
fi

# 等转发就绪
for i in $(seq 1 20); do
  if curl -sf -m 1 -u "${CCC_CHAT_USER:-ccc}:${CCC_CHAT_PASS:-ccc}" \
    "${TUNNEL_URL}/api/desktop/config" >/dev/null 2>&1; then
    echo "OK hub-tunnel ${TUNNEL_URL} via ssh ${SSH_HOST} → ${REMOTE}"
    echo "  Desktop: defaults write com.ccc.desktop ccc.server -string '${TUNNEL_URL}'"
    echo "  sidecar: CCC_HUB_URL=${TUNNEL_URL} bash scripts/install-agent-sidecar-plist.sh --start"
    exit 0
  fi
  sleep 0.5
done

echo "FAIL: tunnel port ${LOCAL_PORT} not serving Hub yet"
echo "  ssh host=${SSH_HOST} remote=${REMOTE}"
echo "  logs: ${LOG_ERR}"
tail -20 "$LOG_ERR" 2>/dev/null || true
exit 1
