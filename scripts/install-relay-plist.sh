#!/bin/bash
# install-relay-plist.sh — 装 CCC Relay 启动脚本（v0.60+ 接入控制面）
# 2026-07-25 共识:中转站回归,CCC 编排面 CLI 集中经 relay 调度;M1 与 2017 各跑独立实例
# 默认只 stage,未 load。要启动:--start
# 用法:bash install-relay-plist.sh [--start] [--host m1|2017]
set -uo pipefail

CCC_HOME="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=_ccc_launchd.sh
source "${CCC_HOME}/scripts/_ccc_launchd.sh"

DO_START=false
HOST_TAG=""
for arg in "$@"; do
  case "$arg" in
    --start) DO_START=true ;;
    --host)  shift; HOST_TAG="${1:-}" ;;
  esac
done

# 主机识别:M1 / 2017(可显式 --host 覆盖,缺省按本机 host 名判)
if [[ -z "$HOST_TAG" ]]; then
  if [[ "$(hostname)" == "Mac2017"* || "$(hostname)" == "fan"* ]]; then
    HOST_TAG="2017"
  else
    HOST_TAG="m1"
  fi
fi
case "$HOST_TAG" in
  m1|2017) ;;
  *) echo "❌ --host 必须是 m1 或 2017,不是 '$HOST_TAG'"; exit 1 ;;
esac
LABEL="com.ccc.relay.${HOST_TAG}"
echo "→ CCC Relay 安装目标: ${LABEL} (host=${HOST_TAG})"

LOG_DIR="${HOME}/.ccc/logs"
RELAY_DIR="${CCC_HOME}/relay"
RELAY_HOME="${HOME}/.ccc/relay"
PLIST="${CCC_PLIST_STAGED}/${LABEL}.plist"

# 端口默认 4000(anthropic)+ 4002(openai-chat)由 src/server.ts 内部同进程
# 状态目录按主机隔离
mkdir -p "$LOG_DIR" "$RELAY_HOME" "$CCC_PLIST_STAGED"
chmod 700 "$RELAY_HOME"

# 检测构建产物
if [[ ! -f "${RELAY_DIR}/dist/proxy.js" ]]; then
  echo "⚠️  ${RELAY_DIR}/dist/proxy.js 不存在(未构建)"
  echo "   先: cd ${RELAY_DIR} && npm ci && npm run build"
  if ! $DO_START; then
    echo "   当前 stage-only 不强制要求构建产物;--start 时会再检查"
  fi
fi

# 检测 node
if ! command -v node >/dev/null 2>&1; then
  echo "❌ 缺 node(>=18);装:brew install node@22"
  exit 1
fi

# 检测 upstreams.json(必须 0600,且三档 flash/Pro/code 必填)
if [[ ! -f "${RELAY_HOME}/upstreams.json" ]]; then
  if [[ -f "${CCC_HOME}/templates/relay-upstreams.example.json" ]]; then
    cp "${CCC_HOME}/templates/relay-upstreams.example.json" "${RELAY_HOME}/upstreams.json"
    chmod 600 "${RELAY_HOME}/upstreams.json"
    echo "→ 已拷 ${RELAY_HOME}/upstreams.json(脱敏),请填 key 后启动"
  fi
fi

# 三档契约检查(只校验结构,不读 key 明文)
# 兼容两种格式:① 顶层 JSON 数组(实际 relay 期望,config.ts:133)② 嵌套 tiers{} 字典
if command -v python3 >/dev/null 2>&1; then
  python3 -c "
import json, sys
try:
    with open('${RELAY_HOME}/upstreams.json') as f:
        cfg = json.load(f)
    # 格式 ①:顶层 JSON 数组
    if isinstance(cfg, list):
        tiers = {u.get('tier'): u for u in cfg if isinstance(u, dict) and u.get('tier')}
    # 格式 ②:嵌套 tiers{} 字典
    elif isinstance(cfg, dict):
        tiers = cfg.get('tiers') or cfg
    else:
        print('❌ upstreams.json 必须是 dict 或 list'); sys.exit(2)
    if not isinstance(tiers, dict):
        print('❌ tiers 必须是 dict'); sys.exit(2)
    missing = [t for t in ('flash','Pro','code') if t not in tiers]
    if missing:
        print(f'❌ upstreams.json 缺三档必填: {missing}'); sys.exit(2)
    for t, v in tiers.items():
        if not isinstance(v, dict):
            print(f'❌ tier {t} 必须是 dict'); sys.exit(2)
        if isinstance(cfg, list):
            # 数组格式每项本身就是 upstream
            ups = [v]
        else:
            ups = v.get('upstreams') or v.get('providers') or []
        if not isinstance(ups, list) or not ups:
            print(f'❌ tier {t} 缺 upstreams[]'); sys.exit(2)
except FileNotFoundError:
    print('❌ upstreams.json 不存在'); sys.exit(2)
" || { echo '❌ upstreams.json 校验失败,见上'; exit 1; }
fi

cat > "$PLIST" <<PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>$(command -v node)</string>
    <string>${RELAY_DIR}/dist/proxy.js</string>
  </array>
  <key>WorkingDirectory</key>
  <string>${RELAY_DIR}</string>
  <key>KeepAlive</key>
  <dict>
    <key>SuccessfulExit</key>
    <true/>
    <key>SuccessfulExitTimeout</key>
    <integer>10</integer>
  </dict>
  <key>RunAtLoad</key>
  <true/>
  <key>ProcessType</key>
  <string>Background</string>
  <key>ThrottleInterval</key>
  <integer>30</integer>
  <key>EnvironmentVariables</key>
  <dict>
    <key>LOOP_UPSTREAMS_FILE</key>
    <string>${RELAY_HOME}/upstreams.json</string>
    <key>LOOP_USAGE_FILE</key>
    <string>${RELAY_HOME}/usage.json</string>
    <key>LOOP_SCORES_FILE</key>
    <string>${RELAY_HOME}/scores.json</string>
    <key>LOOP_CACHE_STATS_FILE</key>
    <string>${RELAY_HOME}/cache-stats.json</string>
    <key>LOOP_CLIENTS_FILE</key>
    <string>${RELAY_HOME}/clients.json</string>
    <key>LOOP_HOST_TAG</key>
    <string>${HOST_TAG}</string>
  </dict>
  <key>StandardOutPath</key>
  <string>${LOG_DIR}/ccc-relay-${HOST_TAG}.out.log</string>
  <key>StandardErrorPath</key>
  <string>${LOG_DIR}/ccc-relay-${HOST_TAG}.err.log</string>
</dict>
</plist>
PLIST_EOF

plutil -lint "$PLIST" >/dev/null || { echo "❌ plist 不合法"; exit 1; }

if $DO_START; then
  # 端口预检:防双实例抢 4000
  if command -v lsof >/dev/null 2>&1 && lsof -i:4000 >/dev/null 2>&1; then
    echo "❌ 4000 已被占用,先停旧实例或清残骸(disabled-relay-20260718)"
    lsof -i:4000 | head -5
    exit 1
  fi
  ccc_launchd_finalize "$LABEL" "$PLIST" --start --ui
  echo "✓ ${LABEL} loaded → http://127.0.0.1:4000/dashboard  :4002 (openai)"
  echo "  三档契约: flash / Pro / code(见 upstreams.json)"
  echo "  logs: ${LOG_DIR}/ccc-relay-${HOST_TAG}.{out,err}.log"
else
  ccc_launchd_finalize "$LABEL" "$PLIST" --ui
  echo "✓ ${LABEL} staged only(未 load)"
  echo "  启动: bash ${CCC_HOME}/scripts/install-relay-plist.sh --start [--host m1|2017]"
fi
