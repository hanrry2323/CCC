#!/usr/bin/env bash
# ── CCC 一键放行：部署 + 自动验证 + 放行报告 + 卡头关闭（T52 自动化基建 第 2 件） ──
#
# 生产模式（默认，在 2017 上对生产仓执行）：
#   0. stop_engine()：优雅停 Engine（launchctl bootout），等在途执行体退出（≤300s）
#   1. git fetch + checkout 目标 commit/tag（2017 pull）
#   2. start_engine() + launchctl kickstart 三常驻服务（web-server / engine / board-scheduler）
#   3. 自动验证：/health、/board/states、/projects、/session 或免登录直连、一次对话
#   4. 输出放行报告（stdout + 报告文件）
#   5. 卡头状态自动更新「已关闭」（验收席放行后；--card 指定或按 commit 自动识别）
#
# --no-pull / --simulate 跳过停/启 Engine（无 checkout 即无竞态窗口）。
#
# 模拟模式（--simulate，M1 模拟 / 临时目录测试）：
#   - 跳过 git pull 与 launchctl kickstart 与一次对话；
#   - 做 config.env 只读检查 + 看板可见性检查（board export 自 --dispatch-dir 导出，
#     验证目标卡在派生看板数据中） + 卡头关闭；不碰生产 docs/dispatch。
#
# 用法：
#   deploy/release.sh [<commit|tag>] [选项]
#
# 选项：
#   --repo <path>         目标仓路径（默认 $CCC_REPO_PATH → ~/program/CCC → 本仓根）
#   --dispatch-dir <dir>  任务卡目录（默认取 config.env DISPATCH_DIR → docs/dispatch）
#   --host <ip>           验证目标主机（默认 127.0.0.1）
#   --port <port>         Web 端口（默认取 config.env WEB_PORT → 7788）
#   --config <path>       config.env 路径（只读检查；默认 $REPO/server/config/config.env）
#   --card <T52>          放行后要关闭的卡编号（默认按目标 commit 在回写区自动识别）
#   --simulate            模拟模式（跳过 git/kickstart/对话；用于临时目录端到端测试）
#   --no-pull             跳过 git fetch/checkout（默认生产模式会 pull）
#   --no-kickstart        跳过 launchctl kickstart（模拟/本地测试）
#   --skip-conversation   跳过「一次对话」验证
#   --with-conversation   模拟模式下也强制跑一次对话（需 --host/--port 指向在线服务）
#   --password <明文>     鉴权开启时 /session 登录用密码（默认 $CCC_WEB_PASSWORD）
#   --json                放行报告输出 JSON 到 stdout
#   --report <path>       报告文件路径（默认 ./release-report-<ts>.md）
#   -h|--help             帮助

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# ── 默认值（环境变量可覆盖，零硬编码） ──
REPO_PATH="${CCC_REPO_PATH:-}"
DISPATCH_DIR_ARG="${CCC_DISPATCH_DIR:-}"
WEB_HOST="${CCC_WEB_HOST:-127.0.0.1}"
WEB_PORT_ARG="${CCC_WEB_PORT:-}"
CONFIG_ENV_ARG="${CCC_CONFIG_ENV:-}"
TARGET=""
CARD_ID_ARG="${CCC_RELEASE_CARD:-}"
SIMULATE=false
NO_PULL=false
NO_KICKSTART=false
SKIP_CONVERSATION=false
WITH_CONVERSATION=false
PASSWORD="${CCC_WEB_PASSWORD:-}"
JSON_OUTPUT=false
REPORT_PATH=""
PYTHON_BIN="${CCC_PYTHON_BIN:-}"

usage() {
  sed -n '2,40p' "$0" | sed 's/^# \{0,1\}//'
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo) REPO_PATH="$2"; shift 2 ;;
    --dispatch-dir) DISPATCH_DIR_ARG="$2"; shift 2 ;;
    --host) WEB_HOST="$2"; shift 2 ;;
    --port) WEB_PORT_ARG="$2"; shift 2 ;;
    --config) CONFIG_ENV_ARG="$2"; shift 2 ;;
    --card) CARD_ID_ARG="$2"; shift 2 ;;
    --password) PASSWORD="$2"; shift 2 ;;
    --report) REPORT_PATH="$2"; shift 2 ;;
    --simulate) SIMULATE=true; shift ;;
    --no-pull) NO_PULL=true; shift ;;
    --no-kickstart) NO_KICKSTART=true; shift ;;
    --skip-conversation) SKIP_CONVERSATION=true; shift ;;
    --with-conversation) WITH_CONVERSATION=true; shift ;;
    --json) JSON_OUTPUT=true; shift ;;
    -h|--help) usage; exit 0 ;;
    -*)
      echo "[ERROR] 未知参数: $1" >&2
      usage
      exit 2
      ;;
    *) TARGET="$1"; shift ;;
  esac
done

# ── 解析 python 解释器 ──
if [[ -z "$PYTHON_BIN" ]]; then
  for cand in /usr/local/bin/python3 python3 python; do
    if command -v "$cand" >/dev/null 2>&1; then PYTHON_BIN="$cand"; break; fi
  done
fi
if [[ -z "$PYTHON_BIN" ]]; then
  echo "[ERROR] 未找到 python3（设置 CCC_PYTHON_BIN 指定）" >&2
  exit 2
fi

# ── 仓库路径 ──
if [[ -z "$REPO_PATH" ]]; then
  if [[ -d "$HOME/program/CCC" ]]; then
    REPO_PATH="$HOME/program/CCC"
  else
    REPO_PATH="$PROJECT_ROOT"
  fi
fi
REPO_PATH="$(cd "$REPO_PATH" 2>/dev/null && pwd)" || {
  echo "[ERROR] 仓库路径不存在: $REPO_PATH" >&2
  exit 2
}

# ── config.env（只读检查 + 提取运行参数） ──
CONFIG_ENV="${CONFIG_ENV_ARG:-$REPO_PATH/server/config/config.env}"
CONFIG_READ_ONLY=""
if [[ -f "$CONFIG_ENV" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$CONFIG_ENV"
  set +a
  CONFIG_READ_ONLY="ok"
fi

WEB_PORT="${WEB_PORT_ARG:-${WEB_PORT:-7788}}"
DISPATCH_DIR="${DISPATCH_DIR_ARG:-${DISPATCH_DIR:-docs/dispatch}}"
# dispatch-dir 相对路径按仓库根解析
case "$DISPATCH_DIR" in
  /*) RESOLVED_DISPATCH_DIR="$DISPATCH_DIR" ;;
  *)  RESOLVED_DISPATCH_DIR="$REPO_PATH/$DISPATCH_DIR" ;;
esac

# ── 验证结果收集 ──
declare -a RESULT_LINES=()
PASS_COUNT=0
FAIL_COUNT=0
SKIP_COUNT=0
RELEASE_PASSED=true

record() { # <status: PASS|FAIL|SKIP|WARN> <step> <detail>
  local status="$1" step="$2" detail="${3:-}"
  RESULT_LINES+=("$status|$step|$detail")
  case "$status" in
    PASS) PASS_COUNT=$((PASS_COUNT + 1)) ;;
    FAIL) FAIL_COUNT=$((FAIL_COUNT + 1)); RELEASE_PASSED=false ;;
    SKIP) SKIP_COUNT=$((SKIP_COUNT + 1)) ;;
  esac
  if [[ "$JSON_OUTPUT" != true ]]; then
    printf '[%s] %-28s %s\n' "$status" "$step" "$detail"
  fi
}

http_get() { # <path> → 输出 body 到 stdout，返回 curl 退出码
  curl -sf --max-time 15 "http://${WEB_HOST}:${WEB_PORT}$1"
}

json_field() { # <json> <key> → 输出字段值
  "$PYTHON_BIN" -c "import sys,json; d=json.load(sys.stdin); print(d.get(sys.argv[1],''))" "$1"
}

# ── T67 部署窗口防线：优雅停/启 Engine，杜绝 checkout 窗口误扫 + kickstart 杀在途执行体 ──
ENGINE_LABEL="com.ccc.engine"
INFLIGHT_PATTERN="${CCC_INFLIGHT_PATTERN:-claude -p}"
INFLIGHT_WAIT_SECONDS="${CCC_INFLIGHT_WAIT_SECONDS:-300}"
INFLIGHT_POLL_INTERVAL="${CCC_INFLIGHT_POLL_INTERVAL:-10}"

in_flight_executors() { # → 0=无在途执行体, 1=有
  pgrep -f "$INFLIGHT_PATTERN" >/dev/null 2>&1
}

stop_engine() { # 生产模式：checkout 前优雅停 Engine，等待在途执行体退出（≤300s，超时警告继续）
  if launchctl bootout "gui/$(id -u)/$ENGINE_LABEL" 2>/dev/null; then
    record PASS "停 Engine" "launchctl bootout $ENGINE_LABEL"
  else
    record WARN "停 Engine" "launchctl bootout 失败（服务未注册?）— 继续部署"
  fi
  local waited=0
  while in_flight_executors; do
    if [[ "$waited" -ge "$INFLIGHT_WAIT_SECONDS" ]]; then
      record WARN "在途执行体" "等待 ${waited}s 仍有在途（${INFLIGHT_PATTERN}），超时继续部署（不阻塞）"
      return 0
    fi
    waited=$((waited + INFLIGHT_POLL_INTERVAL))
    if [[ "$JSON_OUTPUT" != true ]]; then
      printf '[WAIT] 在途执行体等待退出… %ss/%ss\n' "$waited" "$INFLIGHT_WAIT_SECONDS"
    fi
    sleep "$INFLIGHT_POLL_INTERVAL"
  done
  record PASS "在途执行体" "无在途（${INFLIGHT_PATTERN}）"
}

start_engine() { # 生产模式：checkout 后恢复 Engine（bootout 已卸载 → bootstrap；未卸载 → kickstart -k）→ 0/1
  local domain="gui/$(id -u)/$ENGINE_LABEL"
  local plist="$HOME/Library/LaunchAgents/$ENGINE_LABEL.plist"
  if launchctl print "$domain" >/dev/null 2>&1; then
    if launchctl kickstart -k "$domain" >/dev/null 2>&1; then
      record PASS "启 Engine" "launchctl kickstart $ENGINE_LABEL"
      return 0
    fi
  elif [[ -f "$plist" ]] && launchctl bootstrap "gui/$(id -u)" "$plist" >/dev/null 2>&1; then
    record PASS "启 Engine" "launchctl bootstrap $ENGINE_LABEL"
    return 0
  fi
  record WARN "启 Engine" "launchctl 恢复失败（服务未注册/plist 缺失）"
  return 1
}

# ── 1. git pull / checkout ──
GIT_SHA=""
if [[ "$SIMULATE" == true || "$NO_PULL" == true ]]; then
  GIT_SHA="$(git -C "$REPO_PATH" rev-parse --short HEAD 2>/dev/null || echo "unknown")"
  record PASS "git 定位" "跳过 pull（${SIMULATE:+模拟}${NO_PULL:+--no-pull}）；当前 HEAD=$GIT_SHA"
else
  # T67 防线：checkout 前优雅停 Engine，避免部署窗口误扫 + kickstart 杀在途执行体
  stop_engine
  if [[ -z "$TARGET" ]]; then
    TARGET="$(git -C "$REPO_PATH" rev-parse --abbrev-ref HEAD 2>/dev/null || echo HEAD)"
  fi
  if git -C "$REPO_PATH" fetch origin --quiet 2>/dev/null && git -C "$REPO_PATH" checkout "$TARGET" --quiet 2>/dev/null; then
    GIT_SHA="$(git -C "$REPO_PATH" rev-parse --short HEAD)"
    record PASS "2017 pull" "${REPO_PATH} → ${TARGET} (${GIT_SHA})"
  else
    record FAIL "2017 pull" "git fetch/checkout 失败: $TARGET"
    GIT_SHA="$(git -C "$REPO_PATH" rev-parse --short HEAD 2>/dev/null || echo "unknown")"
  fi
fi

# ── 2. 三服务 kickstart ──
if [[ "$SIMULATE" == true || "$NO_KICKSTART" == true ]]; then
  record SKIP "三服务 kickstart" "跳过（${SIMULATE:+模拟}${NO_KICKSTART:+--no-kickstart}）"
else
  KICK_OK=true
  if ! start_engine; then KICK_OK=false; fi
  for svc in com.ccc.web-server com.ccc.board-scheduler; do
    if ! launchctl kickstart -k "gui/$(id -u)/$svc" 2>/dev/null; then
      KICK_OK=false
      record WARN "kickstart $svc" "launchctl 失败（服务未注册?）"
    fi
  done
  if [[ "$KICK_OK" == true ]]; then
    record PASS "三服务 kickstart" "web-server/engine/board-scheduler 已重启"
    # 等待服务就绪
    for _ in $(seq 1 30); do
      if curl -sf --max-time 3 "http://${WEB_HOST}:${WEB_PORT}/health" >/dev/null 2>&1; then break; fi
      sleep 1
    done
  fi
fi

# ── 3. 自动验证段 ──
# 3.1 /health（模拟模式不连在线服务，全在线检查统一 SKIP）
AUTH_REQ=""
if [[ "$SIMULATE" == true ]]; then
  record SKIP "/health" "模拟模式不连在线服务"
else
  HEALTH_BODY="$(curl -sf --max-time 10 "http://${WEB_HOST}:${WEB_PORT}/health" 2>/dev/null || true)"
  if [[ -n "$HEALTH_BODY" ]]; then
    AUTH_REQ="$(printf '%s' "$HEALTH_BODY" | "$PYTHON_BIN" -c "import sys,json; print(json.load(sys.stdin).get('auth_required',''))")"
    record PASS "/health" "status ok（auth_required=${AUTH_REQ:-unknown}）"
  else
    AUTH_REQ=""
    record FAIL "/health" "无法连接 http://${WEB_HOST}:${WEB_PORT}/health"
  fi
fi

# 3.2 /session 或免登录直连
if [[ "$SIMULATE" == true ]]; then
  record SKIP "/session 或免登录直连" "模拟模式不连在线服务"
elif [[ "$AUTH_REQ" == "True" || "$AUTH_REQ" == "true" ]]; then
  if [[ -n "$PASSWORD" ]]; then
    SESSION_BODY="$(curl -sf --max-time 10 -X POST "http://${WEB_HOST}:${WEB_PORT}/session" \
      -H 'Content-Type: application/json' \
      -d "{\"username\":\"${CCC_WEB_USERNAME:-}\",\"password\":\"$PASSWORD\"}" 2>/dev/null || true)"
    if printf '%s' "$SESSION_BODY" | grep -q '"token"'; then
      record PASS "/session" "token 获取成功"
    else
      record FAIL "/session" "登录失败（用户名/密码不匹配?）"
    fi
  else
    record SKIP "/session" "鉴权开启但未提供 --password，跳过"
  fi
else
  record PASS "免登录直连" "auth_required=false，直连可用"
fi

# 3.3 /board/states
if [[ "$SIMULATE" == true ]]; then
  record SKIP "/board/states" "模拟模式改走看板导出检查"
else
  STATES_BODY="$(http_get "/board/states" || true)"
  if [[ -n "$STATES_BODY" ]] && printf '%s' "$STATES_BODY" | grep -q '"'; then
    record PASS "/board/states" "$(printf '%s' "$STATES_BODY" | head -c 80)"
  else
    record FAIL "/board/states" "接口异常或返回空"
  fi
fi

# 3.4 /projects
if [[ "$SIMULATE" == true ]]; then
  record SKIP "/projects" "模拟模式不连在线服务"
else
  PROJECTS_BODY="$(http_get "/projects" || true)"
  if [[ -n "$PROJECTS_BODY" ]] && printf '%s' "$PROJECTS_BODY" | grep -q 'projects'; then
    record PASS "/projects" "项目清单返回"
  else
    record FAIL "/projects" "接口异常或返回空"
  fi
fi

# 3.5 一次对话（SSE 流式：收到 done 完整回复，或流式已通超时未完成 → 视为在线可用）
RUN_CONVERSATION=false
if [[ "$SIMULATE" == true && "$WITH_CONVERSATION" != true ]]; then
  record SKIP "一次对话" "模拟模式跳过（--with-conversation 强制开启）"
elif [[ "$SKIP_CONVERSATION" == true ]]; then
  record SKIP "一次对话" "--skip-conversation"
else
  RUN_CONVERSATION=true
fi
if [[ "$RUN_CONVERSATION" == true ]]; then
  CONV_TIMEOUT="${CCC_RELEASE_CONV_TIMEOUT:-120}"
  CONV_TMP="$(mktemp -d)"
  curl -sS -N --max-time "$CONV_TIMEOUT" -X POST \
    "http://${WEB_HOST}:${WEB_PORT}/conversation" \
    -H 'Content-Type: application/json' \
    -d '{"message":"ping（release.sh 自动验证）","stream":true}' \
    > "$CONV_TMP/stream.txt" 2> "$CONV_TMP/curl.err"
  CURL_RC=$?
  CONV_RESULT="$( "$PYTHON_BIN" -c '
import sys, json
text_len = 0
done = None
meta_seen = False
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    if line.startswith("event:"):
        continue
    if line.startswith("data:"):
        try:
            payload = json.loads(line[5:].strip())
        except Exception:
            continue
        if "model" in payload and "tools" in payload:
            meta_seen = True
        if payload.get("text"):
            text_len += len(payload["text"])
        if payload.get("is_error") is not None:
            done = payload
if done is None:
    if text_len > 0 or meta_seen:
        print("FLOWING textlen=%d（超时未收到 done，流式已通，视在线可用）" % text_len)
    else:
        print("FAIL no-events")
elif done.get("is_error"):
    print("FAIL brain-error:" + str(done.get("error", "")))
elif text_len > 0:
    print("OK textlen=%d（完整回复）" % text_len)
else:
    print("FAIL empty-text")
' < "$CONV_TMP/stream.txt" )"
  rm -rf "$CONV_TMP"
  case "$CONV_RESULT" in
    OK*)    record PASS "一次对话" "$CONV_RESULT" ;;
    FLOWING*) record PASS "一次对话" "$CONV_RESULT" ;;
    *)      record FAIL "一次对话" "$CONV_RESULT（curl rc=${CURL_RC}）" ;;
  esac
fi

# 3.6 config.env 只读检查（两种模式都做）
if [[ -n "$CONFIG_READ_ONLY" ]]; then
  record PASS "config.env 只读检查" "${CONFIG_ENV}（未写入）"
else
  record WARN "config.env 只读检查" "未找到 config.env（${CONFIG_ENV}）"
fi

# ── 4. 看板可见性检查（模拟模式：board export 自 --dispatch-dir 导出并检索目标卡） ──
BOARD_VISIBLE=false
if [[ -n "$CARD_ID_ARG" ]]; then
  EXPORT_TMP="$(mktemp -d)/board.js"
  if ( cd "$REPO_PATH" && "$PYTHON_BIN" -m server.board.export \
      --dispatch-dir "$RESOLVED_DISPATCH_DIR" --output "$EXPORT_TMP" ) >/dev/null 2>&1 \
     && grep -q "$CARD_ID_ARG" "$EXPORT_TMP"; then
    BOARD_VISIBLE=true
    record PASS "看板可见性" "$CARD_ID_ARG 在派生看板数据中可见（${RESOLVED_DISPATCH_DIR}）"
  else
    record FAIL "看板可见性" "$CARD_ID_ARG 未在派生看板数据中找到（${RESOLVED_DISPATCH_DIR}）"
  fi
  rm -rf "$(dirname "$EXPORT_TMP")"
else
  record SKIP "看板可见性" "未指定 --card，跳过"
fi

# ── 5. 卡头状态更新「已关闭」（仅验证通过后执行） ──
CARD_PATH=""
CARD_UPDATED=false
if [[ "$RELEASE_PASSED" == true ]]; then
  if [[ -n "$CARD_ID_ARG" ]]; then
    CARD_FILE="$(find "$RESOLVED_DISPATCH_DIR" -maxdepth 1 -name "T*.md" -type f | xargs -I{} basename "{}" .md 2>/dev/null | grep -x "$CARD_ID_ARG" || true)"
    CARD_PATH=""
    for f in "$RESOLVED_DISPATCH_DIR"/"${CARD_ID_ARG}"-*.md; do
      [[ -e "$f" ]] && CARD_PATH="$f" && break
    done
    if [[ -z "$CARD_PATH" ]]; then
      # 支持精确文件名（如 T90-test-x.md 的 id 不带 slug）
      for f in "$RESOLVED_DISPATCH_DIR"/T*.md; do
        if [[ "$(basename "$f" .md)" == "$CARD_ID_ARG" ]]; then CARD_PATH="$f"; break; fi
      done
    fi
  elif [[ -n "$GIT_SHA" && "$GIT_SHA" != "unknown" ]]; then
    # 自动识别：在回写区含该 commit 的卡
    CARD_PATH="$(grep -l "$GIT_SHA" "$RESOLVED_DISPATCH_DIR"/T*.md 2>/dev/null | head -1 || true)"
  fi

  if [[ -n "$CARD_PATH" && -f "$CARD_PATH" ]]; then
    if "$PYTHON_BIN" - "$CARD_PATH" <<'PYEOF'
import os, re, sys
path = sys.argv[1]
text = open(path, encoding="utf-8").read()
new = re.sub(r"(状态\s*[:：]\s*)([^\n·]+?)(?=\s*·|\s*$)", r"\1已关闭", text, count=1)
if new != text:
    tmp = path + ".tmp"
    open(tmp, "w", encoding="utf-8").write(new)
    os.replace(tmp, path)
    print("updated")
else:
    print("unchanged")
PYEOF
    then
      CARD_UPDATED=true
      record PASS "卡头关闭" "$(basename "$CARD_PATH") → 状态：已关闭"
    else
      record FAIL "卡头关闭" "$CARD_PATH 状态更新失败"
    fi
  else
    record SKIP "卡头关闭" "未识别目标卡（--card 或 commit 自动识别）"
  fi
else
  record SKIP "卡头关闭" "验证未全通过，不放行不关闭"
fi

# ── 6. 放行报告 ──
TS="$(date +%Y%m%d-%H%M%S)"
REPORT_PATH="${REPORT_PATH:-release-report-$TS.md}"
CONCLUSION="❌ 放行未通过（$FAIL_COUNT FAIL / $PASS_COUNT PASS / $SKIP_COUNT SKIP）"
if [[ "$RELEASE_PASSED" == true ]]; then
  CONCLUSION="✅ 放行通过（$PASS_COUNT PASS / $SKIP_COUNT SKIP / 0 FAIL）"
fi

build_report() {
  local mode="生产"
  [[ "$SIMULATE" == true ]] && mode="模拟"
  cat <<EOF
# CCC 一键放行报告

- 时间：$(date '+%Y-%m-%d %H:%M:%S')
- 模式：${mode}
- 目标：${TARGET:-（当前 HEAD）}（${GIT_SHA}）
- 仓库：${REPO_PATH}
- 任务卡目录：${RESOLVED_DISPATCH_DIR}
- 目标卡：${CARD_ID_ARG:-（自动识别）}
- config.env：${CONFIG_READ_ONLY:-未找到}（只读检查）

## 验证明细

$(printf '%s\n' "${RESULT_LINES[@]}" | awk -F'|' '{printf "- **%s** %s：%s\n", $1, $2, $3}')

## 结论

${CONCLUSION}
EOF
}

if [[ "$JSON_OUTPUT" == true ]]; then
  export RELEASE_TS="$TS" RELEASE_TARGET="${TARGET:-}" RELEASE_SHA="$GIT_SHA" \
         RELEASE_REPO="$REPO_PATH" RELEASE_DISPATCH_DIR="$RESOLVED_DISPATCH_DIR" \
         RELEASE_CARD="$CARD_ID_ARG" RELEASE_CONFIG="$CONFIG_READ_ONLY" \
         RELEASE_SIMULATE="$SIMULATE" RELEASE_PASSED="$RELEASE_PASSED"
  printf '%s\n' "${RESULT_LINES[@]}" | \
    "$PYTHON_BIN" -c '
import json, os, sys
lines = [l.split("|", 2) for l in sys.stdin.read().splitlines() if l]
report = {
    "release": {
        "ts": os.environ["RELEASE_TS"],
        "simulate": os.environ["RELEASE_SIMULATE"] == "true",
        "target": os.environ["RELEASE_TARGET"] or None,
        "sha": os.environ["RELEASE_SHA"],
        "repo": os.environ["RELEASE_REPO"],
        "dispatch_dir": os.environ["RELEASE_DISPATCH_DIR"],
        "card": os.environ["RELEASE_CARD"] or None,
        "config_read_only": os.environ["RELEASE_CONFIG"] or None,
    },
    "steps": [{"status": s, "step": st, "detail": d} for s, st, d in lines],
    "passed": os.environ["RELEASE_PASSED"] == "true",
}
print(json.dumps(report, ensure_ascii=False, indent=2))
'
else
  build_report | tee "$REPORT_PATH"
  echo
  echo "报告已保存：$REPORT_PATH"
fi

[[ "$RELEASE_PASSED" == true ]] && exit 0 || exit 1
