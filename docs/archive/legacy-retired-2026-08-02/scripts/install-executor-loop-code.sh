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
HOST_ARCH="$(uname -m)"
BIN_INFO="$(file "$DEST/cli" 2>/dev/null || true)"
case "$HOST_ARCH" in
  arm64|aarch64)
    if echo "$BIN_INFO" | grep -qi 'x86_64' && ! echo "$BIN_INFO" | grep -qi 'arm64\|aarch64'; then
      echo "WARN: host is $HOST_ARCH but cli looks x86_64: $BIN_INFO"
    fi
    ;;
  x86_64|i386|i686)
    if echo "$BIN_INFO" | grep -qi 'arm64\|aarch64' && ! echo "$BIN_INFO" | grep -qi 'x86_64'; then
      echo "FAIL: host is $HOST_ARCH but cli is arm64 (Errno 86). Install arch-matching binary."
      exit 1
    fi
    ;;
esac
# smoke: binary must at least be exec-format for this host
if ! "$DEST/cli" --version >/dev/null 2>&1; then
  # some CLIs need network for --version; still reject obvious arch mismatch already
  if echo "$BIN_INFO" | grep -qi 'arm64' && [[ "$HOST_ARCH" == "x86_64" ]]; then
    echo "FAIL: cannot run arm64 cli on x86_64"
    exit 1
  fi
fi
shasum -a 256 "$DEST/cli" | awk '{print $1}' > "$DEST/SHA256"
date -u +%Y-%m-%dT%H:%M:%SZ > "$DEST/VERSION"
cat > "$DEST/README.md" <<EOF
loop-code private Claude-compatible CLI for CCC (SSOT 方案 Agent).
host_arch: ${HOST_ARCH}
source: ${SRC}
Do not commit \`cli\` (see .gitignore). Install via scripts/install-executor-loop-code.sh.
EOF
echo "OK → $DEST/cli ($BIN_INFO)"
cat "$DEST/SHA256"
