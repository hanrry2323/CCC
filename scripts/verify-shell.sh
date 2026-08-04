#!/usr/bin/env bash
# ── CCC 壳 headless 复验一键跑（T52 自动化基建 第 3 件） ──
#
# 固化六场景复验：免登录直进 / 流式 / 思考折叠无空占位 / 切界面不断流 /
# 左栏业务项目 / 零 console error。API 级断言（零第三方依赖），
# 浏览器 DOM 层（折叠渲染/console 具体报错）依赖 Playwright（M1 环境）。
#
# 两种模式：
#   verify-shell.sh                    默认连 127.0.0.1:7788（已部署壳的复验）
#   verify-shell.sh --local            起本地测试服务（随机端口）后复验；
#                                      本地服务无大脑配置，默认跳过对话类场景
#
# 用法：
#   scripts/verify-shell.sh [--host H] [--port P] [--local]
#                           [--skip-conversation] [--with-conversation]
#                           [--conv-timeout N] [--report <path>]
#
# 返回码：0 = 全场景通过；1 = 有 FAIL；2 = 用法错误。

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

PYTHON_BIN="${CCC_PYTHON_BIN:-}"
for cand in /usr/local/bin/python3 python3 python; do
  [[ -n "$PYTHON_BIN" ]] && break
  command -v "$cand" >/dev/null 2>&1 && PYTHON_BIN="$cand" && break
done
if [[ -z "$PYTHON_BIN" ]]; then
  echo "[ERROR] 未找到 python3（设置 CCC_PYTHON_BIN 指定）" >&2
  exit 2
fi

HOST="127.0.0.1"
PORT="7788"
LOCAL=false
SKIP_CONV=false
WITH_CONV=false
CONV_TIMEOUT=120
REPORT_PATH=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host) HOST="$2"; shift 2 ;;
    --port) PORT="$2"; shift 2 ;;
    --local) LOCAL=true; shift ;;
    --skip-conversation) SKIP_CONV=true; shift ;;
    --with-conversation) WITH_CONV=true; shift ;;
    --conv-timeout) CONV_TIMEOUT="$2"; shift 2 ;;
    --report) REPORT_PATH="$2"; shift 2 ;;
    -h|--help) sed -n '2,24p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "[ERROR] 未知参数: $1" >&2; exit 2 ;;
  esac
done

LOCAL_PID=""
cleanup() {
  if [[ -n "$LOCAL_PID" ]] && kill -0 "$LOCAL_PID" 2>/dev/null; then
    kill "$LOCAL_PID" 2>/dev/null || true
    echo "[INFO] 已停止本地测试服务 (pid ${LOCAL_PID})"
  fi
}
trap cleanup EXIT

# ── 本地模式：起测试服务（随机端口） ──
if [[ "$LOCAL" == true ]]; then
  PORT="$("$PYTHON_BIN" - <<'PYEOF'
import socket
s = socket.socket()
s.bind(("127.0.0.1", 0))
print(s.getsockname()[1])
s.close()
PYEOF
)"
  ( cd "$PROJECT_ROOT" && "$PYTHON_BIN" -m server.web.server --host 127.0.0.1 --port "$PORT" \
      >/tmp/ccc-verify-shell.log 2>&1 ) &
  LOCAL_PID=$!
  # 等就绪
  for _ in $(seq 1 30); do
    if curl -sf "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then break; fi
    sleep 1
  done
  echo "[INFO] 本地测试服务 http://127.0.0.1:${PORT}（pid ${LOCAL_PID}）"
fi

# 跳过对话类场景的两种情形：显式 --skip-conversation；本地模式且未 --with-conversation
# （本地测试服务无大脑配置，对话类场景无意义）
CHECK_ARGS=("--base" "http://${HOST}:${PORT}" "--conv-timeout" "$CONV_TIMEOUT")
if [[ "$SKIP_CONV" == true || ( "$LOCAL" == true && "$WITH_CONV" != true ) ]]; then
  CHECK_ARGS+=("--skip-conversation")
  echo "[INFO] 跳过对话类场景（--skip-conversation 或本地模式无大脑）"
fi

# ── 跑复验 ──
if "$PYTHON_BIN" "$SCRIPT_DIR/verify_shell_checks.py" "${CHECK_ARGS[@]}"; then
  if [[ -n "$REPORT_PATH" ]]; then
    echo "shell verify PASS" > "$REPORT_PATH"
  fi
  exit 0
else
  if [[ -n "$REPORT_PATH" ]]; then
    echo "shell verify FAIL" > "$REPORT_PATH"
  fi
  exit 1
fi
