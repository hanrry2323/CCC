#!/bin/bash
# code 模式 headless 一次性执行器（DSH 实验专用）
# 从 web 的 launchctl plist 借环境变量（OPENCODE_GO_API_KEY 等，不打印密钥值），
# 以默认 agent preset "code" 跑一个 headless one-shot 任务。
#
# 用法: run-headless-code.sh "<任务文本>" [cwd]
#   cwd 默认 /Users/fan/qx-map（实验会话落盘 workspace）
set -u

DSH=/Users/fan/.npm/_npx/1e7f6d9597241db0/node_modules/.bin/dsh
PLIST=~/Library/LaunchAgents/com.deepseek.dsh-web.plist
CWD="${2:-/Users/fan/qx-map}"
TASK="$1"

# 从 plist 提取环境变量并注入（值不进 stdout，不出现在日志）
if [ -f "$PLIST" ]; then
  eval "$(python3 - <<'PYEOF'
import plistlib, os, shlex
p = os.path.expanduser("~/Library/LaunchAgents/com.deepseek.dsh-web.plist")
try:
    with open(p, "rb") as f:
        env = plistlib.load(f).get("EnvironmentVariables", {})
except Exception as e:
    env = {}
for k, v in env.items():
    print("export %s=%s" % (k, shlex.quote(str(v))))
PYEOF
)"
fi

# IPv6 防护（与生产 web 一致：opencode.ai 有 AAAA 但本机无 IPv6 路由）
export NODE_OPTIONS="--dns-result-order=ipv4first${NODE_OPTIONS:+ $NODE_OPTIONS}"

# Code Mode 进程级开关（DSH_TOOLS_MODE=native|code|both，默认 code）
# code-runtime 由 headless bundle 自带挂载；此开关把整个进程切成 code 模式
export DSH_TOOLS_MODE="${DSH_TOOLS_MODE:-code}"

cd "$CWD"
exec "$DSH" --profile headless "$TASK"
