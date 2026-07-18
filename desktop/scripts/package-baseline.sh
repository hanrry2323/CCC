#!/usr/bin/env bash
# Desktop 打包基线（签名 / notarize 后置）
set -euo pipefail
cd "$(dirname "$0")/.."
swift build -c release
BIN=".build/release/CCCDesktop"
test -x "$BIN"
echo "OK release binary: $(pwd)/$BIN"
ls -lh "$BIN"
