#!/usr/bin/env bash
# 一键配好 CCC Desktop：Server / 本机 Agent / 平台仓映射，并确保 sidecar
# 2026-07-21：M1 不保留业务源码第二树；勿再 rsync/clone 业务仓到本机。
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DOMAIN="${CCC_DESKTOP_DOMAIN:-com.ccc.desktop}"
SERVER="${CCC_SERVER:-http://127.0.0.1:17777}"
AGENT="${CCC_AGENT:-http://127.0.0.1:7788}"

echo "== configure Desktop ($DOMAIN) =="
# Hub 稳定性：先确保 SSH 隧道（LAN :7777 偶发卡死；隧道探活满绿）
if [[ "${CCC_SKIP_HUB_TUNNEL:-0}" != "1" ]]; then
  bash "$ROOT/scripts/install-hub-tunnel-plist.sh" --start || true
fi
defaults write "$DOMAIN" "ccc.server" -string "$SERVER"
defaults write "$DOMAIN" "ccc.user" -string "${CCC_CHAT_USER:-ccc}"
defaults write "$DOMAIN" "ccc.pass" -string "${CCC_CHAT_PASS:-ccc}"
defaults write "$DOMAIN" "ccc.agent" -string "$AGENT"
defaults write "$DOMAIN" "ccc.home" -string "$ROOT"
defaults write "$DOMAIN" "ccc.selectedProject" -string "ccc-demo"
defaults write "$DOMAIN" "ccc.localWorkspace" -string "$ROOT"

# 仅平台仓可映射；业务仓事实走 Hub baseline（2017）
MAP_JSON=$(python3 - <<PY
import json
print(json.dumps({"ccc": "$ROOT"}, ensure_ascii=False))
PY
)
defaults write "$DOMAIN" "ccc.localWorkspaceMap" -string "$MAP_JSON"

# 确保 sidecar（launchd KeepAlive；不再依赖 nohup）
echo "ensure sidecar launchd…"
bash "$ROOT/scripts/install-agent-sidecar-plist.sh" --start || true
for i in 1 2 3 4 5 6 7 8 9 10 11 12; do
  curl -sf -m 1 "${AGENT%/}/health" >/dev/null 2>&1 && break
  sleep 0.5
done

if curl -sf -m 2 "${AGENT%/}/health" >/dev/null 2>&1; then
  echo "sidecar: OK $AGENT"
else
  echo "sidecar: FAIL（Desktop 会显示「本机 Agent 未就绪」）"
fi

_HUB="${SERVER:-http://127.0.0.1:17777}"
if curl -sf -m 4 -u "${CCC_CHAT_USER:-ccc}:${CCC_CHAT_PASS:-ccc}" "${_HUB%/}/api/desktop/config" >/dev/null 2>&1; then
  echo "hub: OK ${_HUB}"
else
  echo "hub: FAIL (${_HUB})（先查 bash scripts/install-hub-tunnel-plist.sh --status）"
fi

echo "prefs:"
defaults read "$DOMAIN" | grep -E 'ccc\.(server|agent|home|selected|local)' || true
echo "note: 业务仓无本机 map；对齐基线只信 Hub /api/projects/{id}/baseline"
echo "note: Hub 默认走本机 SSH 隧道 :17777（勿再依赖 LAN :7777 直连）"
echo "done. 重开 Desktop: bash desktop/scripts/open-desktop.sh"
