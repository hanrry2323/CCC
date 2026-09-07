#!/usr/bin/env bash
# 安装 reaper launchd 配置（不自动加载；加载/重启由运维确认）。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TEMPLATE="${ROOT}/server/deploy/com.ccc.reaper.plist"
TARGET="${HOME}/Library/LaunchAgents/com.ccc.reaper.plist"
PYTHON_BIN="${CCC_REAPER_PYTHON:-${ROOT}/.venv-hub/bin/python3}"
LOG_DIR="${CCC_REAPER_LOG_DIR:-${HOME}/.ccc/logs}"
USERNAME="$(id -un)"

[[ -f "$TEMPLATE" ]] || { echo "missing template: $TEMPLATE" >&2; exit 2; }
mkdir -p "$(dirname "$TARGET")" "$LOG_DIR"
python3 - "$TEMPLATE" "$TARGET" "$ROOT" "$PYTHON_BIN" "$LOG_DIR" "$USERNAME" <<'PY'
from pathlib import Path
import sys
src = Path(sys.argv[1])
dst = Path(sys.argv[2])
root = Path(sys.argv[3])
py = Path(sys.argv[4])
log = Path(sys.argv[5])
user = sys.argv[6]
text = src.read_text(encoding="utf-8")
repls = {
    "$PROJECT_ROOT": str(root),
    "$PYTHON_BIN": str(py),
    "$LOG_DIR": str(log),
    "$USERNAME": user,
    "$HOME": str(Path.home()),
}
for old, new in repls.items():
    text = text.replace(old, new)
dst.write_text(text, encoding="utf-8")
PY
/usr/bin/plutil -lint "$TARGET"
printf 'installed %s\n' "$TARGET"
printf 'not loaded; run launchctl bootstrap/bootout explicitly after review\n'
