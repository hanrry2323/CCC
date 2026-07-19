#!/usr/bin/env bash
# 一键配好 CCC Desktop：Server / 本机 Agent / 项目 / 工作区，并确保 sidecar
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DOMAIN="${CCC_DESKTOP_DOMAIN:-com.ccc.desktop}"
SERVER="${CCC_SERVER:-http://192.168.3.116:7777}"
AGENT="${CCC_AGENT:-http://127.0.0.1:7788}"
DEMO_LOCAL="${CCC_DEMO_LOCAL:-$HOME/program/apps/ccc-demo}"
DEMO_REMOTE="${CCC_DEMO_REMOTE:-fan@192.168.3.116:/Users/fan/program/apps/ccc-demo/}"

echo "== configure Desktop ($DOMAIN) =="
defaults write "$DOMAIN" "ccc.server" -string "$SERVER"
defaults write "$DOMAIN" "ccc.user" -string "${CCC_CHAT_USER:-ccc}"
defaults write "$DOMAIN" "ccc.pass" -string "${CCC_CHAT_PASS:-ccc}"
defaults write "$DOMAIN" "ccc.agent" -string "$AGENT"
defaults write "$DOMAIN" "ccc.home" -string "$ROOT"
defaults write "$DOMAIN" "ccc.selectedProject" -string "ccc-demo"
defaults write "$DOMAIN" "ccc.localWorkspace" -string "$ROOT"

# 同步业务仓（小仓）到本机
if [[ ! -d "$DEMO_LOCAL/.git" && ! -f "$DEMO_LOCAL/README.md" ]]; then
  echo "sync ccc-demo → $DEMO_LOCAL"
  mkdir -p "$DEMO_LOCAL"
  if rsync -az --delete "$DEMO_REMOTE" "$DEMO_LOCAL/" 2>/dev/null; then
    echo "  rsync OK"
  else
    echo "  WARN: rsync 失败，工作区 map 仍写入路径（可稍后手动同步）"
  fi
fi

MAP_JSON=$(python3 - <<PY
import json
print(json.dumps({
  "ccc": "$ROOT",
  "ccc-demo": "$DEMO_LOCAL",
}, ensure_ascii=False))
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

_HUB="${SERVER:-http://192.168.3.116:7777}"
if curl -sf -m 4 -u "${CCC_CHAT_USER:-ccc}:${CCC_CHAT_PASS:-ccc}" "${_HUB%/}/api/desktop/config" >/dev/null 2>&1; then
  echo "hub: OK ${_HUB}"
else
  echo "hub: FAIL (${_HUB})（检查 Mac2017 Hub）"
fi

echo "prefs:"
defaults read "$DOMAIN" | grep -E 'ccc\.(server|agent|home|selected|local)' || true
echo "done. 重开 Desktop: bash desktop/scripts/open-desktop.sh"
