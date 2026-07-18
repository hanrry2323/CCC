#!/usr/bin/env bash
# Desktop 打包基线：release 二进制 + 最小 .app（签名 / notarize 后置）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

swift build -c release
BIN=".build/release/CCCDesktop"
test -x "$BIN"

APP_DIR="${CCC_DESKTOP_APP_OUT:-$ROOT/.build/CCCDesktop.app}"
rm -rf "$APP_DIR"
mkdir -p "$APP_DIR/Contents/MacOS" "$APP_DIR/Contents/Resources"

cp "$BIN" "$APP_DIR/Contents/MacOS/CCCDesktop"
chmod +x "$APP_DIR/Contents/MacOS/CCCDesktop"

cat > "$APP_DIR/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key>
  <string>CCC Desktop</string>
  <key>CFBundleDisplayName</key>
  <string>CCC Desktop</string>
  <key>CFBundleIdentifier</key>
  <string>com.ccc.desktop</string>
  <key>CFBundleVersion</key>
  <string>1</string>
  <key>CFBundleShortVersionString</key>
  <string>0.1.0</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleExecutable</key>
  <string>CCCDesktop</string>
  <key>LSMinimumSystemVersion</key>
  <string>13.0</string>
  <key>NSHighResolutionCapable</key>
  <true/>
  <key>NSPrincipalClass</key>
  <string>NSApplication</string>
</dict>
</plist>
PLIST

echo "OK release binary: $ROOT/$BIN"
echo "OK app bundle:     $APP_DIR"
ls -lh "$BIN" "$APP_DIR/Contents/MacOS/CCCDesktop"
