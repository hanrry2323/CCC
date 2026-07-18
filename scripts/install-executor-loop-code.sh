#!/bin/bash
# Copy a Claude-compatible CLI into CCC/vendor/loop-code/ (no symlink).
set -euo pipefail
CCC_HOME="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="${CCC_HOME}/vendor/loop-code"
SRC="${1:-}"
if [[ -z "$SRC" || ! -f "$SRC" ]]; then
  echo "用法: $0 /path/to/cli-or-cli-dev"
  exit 1
fi
mkdir -p "$DEST"
cp -f "$SRC" "$DEST/cli"
chmod +x "$DEST/cli"
shasum -a 256 "$DEST/cli" | awk '{print $1}' > "$DEST/SHA256"
date -u +%Y-%m-%dT%H:%M:%SZ > "$DEST/VERSION"
cat > "$DEST/README.md" <<'EOF'
Optional private Claude-compatible CLI for CCC.
Do not commit `cli` (see .gitignore). Install via scripts/install-executor-loop-code.sh.
EOF
echo "OK → $DEST/cli"
cat "$DEST/SHA256"
