#!/usr/bin/env bash
# Desktop 打包基线：release 二进制 + 最小 .app（签名 / notarize 后置）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REPO="$(cd "$ROOT/.." && pwd)"
cd "$ROOT"

VER_RAW="$(tr -d '[:space:]' < "$REPO/VERSION" 2>/dev/null || echo "0.0.0")"
VER="${VER_RAW#v}"
BUILD="${CCC_DESKTOP_BUILD:-1}"

swift build -c release
BIN=".build/release/CCCDesktop"
test -x "$BIN"

APP_DIR="${CCC_DESKTOP_APP_OUT:-$ROOT/.build/CCCDesktop.app}"
rm -rf "$APP_DIR"
mkdir -p "$APP_DIR/Contents/MacOS" "$APP_DIR/Contents/Resources"

cp "$BIN" "$APP_DIR/Contents/MacOS/CCCDesktop"
chmod +x "$APP_DIR/Contents/MacOS/CCCDesktop"

cat > "$APP_DIR/Contents/Info.plist" <<PLIST
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
  <string>${BUILD}</string>
  <key>CFBundleShortVersionString</key>
  <string>${VER}</string>
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
  <key>NSLocalNetworkUsageDescription</key>
  <string>CCC Desktop 需要访问局域网中的 Hub（编排）与模型中转站，以加载项目、转任务并显示调用次数。</string>
  <key>NSBonjourServices</key>
  <array>
    <string>_http._tcp</string>
  </array>
  <key>NSAppTransportSecurity</key>
  <dict>
    <key>NSAllowsLocalNetworking</key>
    <true/>
  </dict>
</dict>
</plist>
PLIST

echo "OK release binary: $ROOT/$BIN"
echo "OK app bundle:     $APP_DIR (version ${VER} build ${BUILD})"
ls -lh "$BIN" "$APP_DIR/Contents/MacOS/CCCDesktop"
/usr/libexec/PlistBuddy -c 'Print CFBundleShortVersionString' "$APP_DIR/Contents/Info.plist"

# 绑定 Info.plist（局域网权限文案等）到 adhoc 签名，否则 TCC 不认
codesign --force --deep --sign - \
  --identifier "com.ccc.desktop" \
  "$APP_DIR" 2>/dev/null || codesign --force --sign - "$APP_DIR/Contents/MacOS/CCCDesktop"
codesign -dv --verbose=2 "$APP_DIR" 2>&1 | head -20 || true
