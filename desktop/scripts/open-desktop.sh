#!/usr/bin/env bash
# 配好偏好 → 确保 sidecar → 打开 CCC Desktop
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
bash "$ROOT/desktop/scripts/configure-desktop.sh"
pkill -x CCCDesktop 2>/dev/null || true
sleep 0.3
# Prefer /Applications bundle
if [[ -d /Applications/CCCDesktop.app ]]; then
  open -a /Applications/CCCDesktop.app
else
  open -a CCCDesktop 2>/dev/null || open "$ROOT/desktop/.build/CCCDesktop.app"
fi
echo "已打开 CCC Desktop"
