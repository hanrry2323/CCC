#!/bin/bash
# ccc-fleet.sh — CCC fleet 统一状态机（v0.61.0 阶段 B · 2026-07-25）
#
# 子命令:
#   start <host|ui-tier|all>  拓扑序 bootstrap + 等就绪 HTTP 200
#   stop <host|ui-tier|all>   反向拓扑序 bootout
#   status [host|all]         三色:green / yellow / red
#   restart <host>            rolling 重启(预留,占位)
#   health [host]             调各端点 /health 等
#   diagnose                  整合 health + self-check(短) + dual-host
#   watchdog                  plist 30s 调一次,health != green → 告警
#
# 不动 Engine/Board 调度核心,只管进程与端口。

set -uo pipefail

CCC_HOME="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=_ccc_launchd.sh
source "${CCC_HOME}/scripts/_ccc_launchd.sh"

CCC_PLIST_ACTIVE="${HOME}/Library/LaunchAgents"
CCC_PLIST_STAGED="${HOME}/Library/LaunchAgents/disabled-ccc"

# ── 0. host 判别 + label 总表 ────────────────────────────
_host_tag() {
  if [[ "$(hostname)" == "Mac2017"* || "$(hostname)" == "fan"* ]]; then
    echo "2017"
  else
    echo "m1"
  fi
}
HOST_TAG="$(_host_tag)"

# 完整 label 表(2017 + M1 共 12 个;含老 batch2 / flywheel / loop-monitor / opencode-serve
# 保留作 backward-compat:disabled-ccc/ 里有这些 plist,bootout 时全收)
ALL_LABELS_2017=(
  "com.ccc.relay.2017"
  "com.ccc.board"
  "com.ccc.chat-server"
  "com.ccc.engine"
  "com.ccc.batch2-autonomy"
  "com.ccc.flywheel-scan"
  "com.ccc.loop-monitor"
  "com.ccc.opencode-serve"
)
ALL_LABELS_M1=(
  "com.ccc.relay.m1"
  "com.ccc.hub-tunnel"
  "com.ccc.agent-sidecar"
  "com.ccc.flywheel-scan"
  "com.ccc.loop-monitor"
  "com.opencode.serve"
)
ALL_LABELS=()
if [[ "$HOST_TAG" == "2017" ]]; then
  ALL_LABELS=("${ALL_LABELS_2017[@]}")
else
  ALL_LABELS=("${ALL_LABELS_M1[@]}")
fi

# ── 0.5 依赖拓扑(after 表示"必须先于本组件启动")───────
# 注释里 ui 表示仅在 ui-tier 模式启(m1 才有 ui)
# engine 依赖 relay + chat-server;chat-server 依赖 board;board 独立
# agent-sidecar 依赖 hub-tunnel(M1 专属)
# hub-tunnel 依赖 chat-server(M1 专属)
# flywheel-scan / loop-monitor 依赖 engine
# batch2-autonomy 依赖 engine(2017 专属)
# opencode-serve 独立(单独跑 dev session)
TIER_UI_M1=(
  "com.ccc.relay.m1"
  "com.ccc.hub-tunnel"
  "com.ccc.agent-sidecar"
)
TIER_ALL_2017=(
  "com.ccc.relay.2017"
  "com.ccc.board"
  "com.ccc.chat-server"
  "com.ccc.engine"
  "com.ccc.flywheel-scan"
  "com.ccc.loop-monitor"
  "com.ccc.batch2-autonomy"
  "com.ccc.opencode-serve"
)
TIER_ALL_M1=(
  "com.ccc.relay.m1"
  "com.ccc.hub-tunnel"
  "com.ccc.agent-sidecar"
)
# 反向序:用于 stop
TIER_ALL_2017_REV=(
  "com.ccc.batch2-autonomy"
  "com.ccc.opencode-serve"
  "com.ccc.loop-monitor"
  "com.ccc.flywheel-scan"
  "com.ccc.engine"
  "com.ccc.chat-server"
  "com.ccc.board"
  "com.ccc.relay.2017"
)

# 组件健康探活 URL(按 host 决定)
_probe_url() {
  local label=$1
  case "$label" in
    com.ccc.relay.*)    echo "http://127.0.0.1:4000/admin/status" ;;
    com.ccc.board)      echo "http://127.0.0.1:7775/" ;;  # /health 会 302；根路径 200
    com.ccc.chat-server) echo "http://127.0.0.1:7777/api/desktop/projects" ;;
    com.ccc.engine)     echo "" ;;  # engine 无独立 health 端点,看 launchd 状态
    com.ccc.hub-tunnel) echo "" ;;  # 隧道无 HTTP,通过 launchd 看
    com.ccc.agent-sidecar) echo "http://127.0.0.1:7788/health" ;;
    *)                  echo "" ;;
  esac
}
# 鉴权(Hub 需要 basic auth)
_probe_auth() {
  local label=$1
  case "$label" in
    com.ccc.chat-server) echo "-u ccc:ccc" ;;
    *) echo "" ;;
  esac
}

# ── 1. 通用工具函数 ───────────────────────────────────
_log() { echo "[$(date +%H:%M:%S)] [fleet] $*" >&2; }

# launchd 状态检查:输出 "loaded" / "not-loaded" / "not-found"
_status_of() {
  local label=$1
  local line
  line=$(launchctl list 2>/dev/null | awk -v lbl="$label" '$3==lbl {print $1; exit}')
  if [[ -z "$line" ]]; then echo "not-found"; return; fi
  local pid exit_code
  pid="${line%%	*}"
  exit_code="${line##*	}"
  if [[ "$pid" != "-" && "$pid" -gt 0 ]] 2>/dev/null; then
    echo "loaded"
  else
    echo "exited"
  fi
}

# 探活 URL(GET + auth),返回 "up" / "down"
_probe_component() {
  local label=$1
  local url=$(_probe_url "$label")
  if [[ -z "$url" ]]; then echo "n/a"; return; fi
  local auth=$(_probe_auth "$label")
  local code
  # 不用 -f：Board 等可能 302；2xx/3xx 均算 up
  code=$(eval curl -sS -m 3 $auth -o /dev/null -w "%{http_code}" "$url" 2>/dev/null || echo 000)
  if [[ "$code" =~ ^[23] ]]; then echo "up"; else echo "down:$code"; fi
}

# 等就绪:最多 max_s 秒,每 1s 探一次
_wait_probe() {
  local label=$1 max_s=${2:-30}
  local url=$(_probe_url "$label") auth=$(_probe_auth "$label")
  if [[ -z "$url" ]]; then return 0; fi  # 无 URL,跳过
  for _ in $(seq 1 "$max_s"); do
    local code
    code=$(eval curl -sS -m 1 $auth -o /dev/null -w "%{http_code}" "$url" 2>/dev/null || echo 000)
    [[ "$code" =~ ^[23] ]] && return 0
    sleep 1
  done
  return 1
}

# 把 plist 从 disabled-ccc/ 恢复到 active/(如果不在)
_restore_plist() {
  local label=$1
  local active_plist="${CCC_PLIST_ACTIVE}/${label}.plist"
  local staged_plist="${CCC_PLIST_STAGED}/${label}.plist"
  if [[ ! -f "$active_plist" && -f "$staged_plist" ]]; then
    mv "$staged_plist" "$active_plist"
    _log "  restored $active_plist"
  fi
}

# 启动单个组件
_start_one() {
  local label=$1
  _restore_plist "$label"
  local plist="${CCC_PLIST_ACTIVE}/${label}.plist"
  if [[ ! -f "$plist" ]]; then
    _log "  WARN: $plist 不存在,跳过"
    return 0
  fi
  local uid
  uid=$(id -u)
  launchctl enable "gui/${uid}/${label}" 2>/dev/null || true
  launchctl bootstrap "gui/${uid}" "$plist" 2>/dev/null \
    || launchctl load -w "$plist" 2>/dev/null \
    || { _log "  ERROR: bootstrap $label 失败"; return 1; }
}

# 停止单个组件(bootout + 等进程退出)
_stop_one() {
  local label=$1 timeout=${2:-10}
  local uid
  uid=$(id -u)
  launchctl bootout "gui/${uid}/${label}" 2>/dev/null || true
  launchctl disable "gui/${uid}/${label}" 2>/dev/null || true
  for _ in $(seq 1 "$timeout"); do
    local st
    st=$(_status_of "$label")
    [[ "$st" == "not-found" || "$st" == "exited" ]] && return 0
    sleep 1
  done
  _log "  WARN: $label 进程未在 ${timeout}s 内退出,可能 leak"
  return 0
}

# 端口是否被占
_port_in_use() {
  local port=$1
  command -v lsof >/dev/null 2>&1 && lsof -i:"$port" 2>/dev/null | grep -q LISTEN
}

# ── 2. 子命令:start ────────────────────────────────────
# 用法:start <host|ui-tier|all>
start() {
  local target="${1:-all}"
  if [[ "$target" == "ui-tier" ]]; then
    # M1 专属:relay.m1 + hub-tunnel + agent-sidecar（永不含 Hub/Board/Engine）
    local tier=("${TIER_UI_M1[@]}")
    if [[ "$HOST_TAG" != "m1" ]]; then
      _log "❌ ui-tier 仅 M1 模式,当前 $HOST_TAG"; return 1
    fi
  elif [[ "$target" == "all" ]]; then
    if [[ "$HOST_TAG" == "2017" ]]; then
      local tier=("${TIER_ALL_2017[@]}")
    else
      local tier=("${TIER_ALL_M1[@]}")
    fi
  else
    _log "❌ 未知 target: $target (可选: ui-tier / all / 2017 / m1)"
    return 1
  fi

  # 端口预检(避免双实例抢端口)
  if [[ "$HOST_TAG" == "2017" ]]; then
    for port in 4000 4002 7775 7777; do
      if _port_in_use "$port"; then
        _log "WARN: 端口 $port 已被占,可能存在旧实例"
      fi
    done
  else
    for port in 4000 7788 17777; do
      if _port_in_use "$port"; then
        _log "WARN: 端口 $port 已被占,可能存在旧实例"
      fi
    done
    for port in 7775 7777; do
      if _port_in_use "$port"; then
        _log "❌ M1 不应监听 Hub/Board 端口 $port — 先停本机 Hub 再 start"
        return 1
      fi
    done
  fi

  _log "→ start tier (${#tier[@]} 组件),拓扑序: ${tier[*]}"

  # v0.61.0 阶段 C:启动前 self-check 强门禁(仅 HARD 项:1-7 + 9-10)
  # 端口(8)+ dual-host(11)是运行时检查,不在 fleet 启动门禁里
  if ! bash "${CCC_HOME}/scripts/ccc-self-check.sh" --preflight; then
    _log "❌ preflight 未通过 → 拒绝启动"
    _log "  跑 bash scripts/ccc-self-check.sh 单独看哪项 FAIL"
    return 2
  fi

  # v0.61.0 阶段 E:2017 start 前核对仓内 VERSION 与 origin/main（Hub 可能未起，不用 HTTP）
  if [[ "$target" == "all" && "$HOST_TAG" == "2017" ]]; then
    if ! bash "${CCC_HOME}/scripts/ccc-dual-host-check.sh" --sync-only --2017; then
      _log "❌ 2017 仓未与 origin/main 对齐 → 拒绝启 fleet"
      _log "  跑: git fetch && git merge --ff-only origin/main"
      return 1
    fi
  fi

  local started=()
  for label in "${tier[@]}"; do
    _log "  [start] $label"
    if _start_one "$label"; then
      # 等就绪(只对有 URL 的)
      if _wait_probe "$label" 30; then
        _log "  [ok] $label 探活通过"
      else
        _log "  [WARN] $label bootstrap 但 30s 内探活不通过"
      fi
      started+=("$label")
    else
      _log "  [FATAL] $label 启动失败 → 回滚已启组件"
      for rev in "${started[@]}"; do
        _stop_one "$rev" 5
      done
      return 1
    fi
  done
  _log "✓ tier start 完成"
  status
}

# ── 3. 子命令:stop ─────────────────────────────────────
# 用法:stop <host|ui-tier|all>
stop() {
  local target="${1:-all}"
  local tier
  if [[ "$target" == "all" ]]; then
    if [[ "$HOST_TAG" == "2017" ]]; then
      tier=("${TIER_ALL_2017_REV[@]}")
    else
      # M1 反向:agent-sidecar → hub-tunnel → relay
      tier=("com.ccc.agent-sidecar" "com.ccc.hub-tunnel" "com.ccc.relay.m1")
    fi
  elif [[ "$target" == "ui-tier" ]]; then
    if [[ "$HOST_TAG" != "m1" ]]; then
      _log "❌ ui-tier 仅 M1 模式"; return 1
    fi
    tier=("com.ccc.agent-sidecar" "com.ccc.hub-tunnel" "com.ccc.relay.m1")
  elif [[ "$target" == "engine" ]]; then
    tier=("com.ccc.engine")
  else
    _log "❌ 未知 target: $target"
    return 1
  fi
  _log "→ stop tier (反向序),${#tier[@]} 组件: ${tier[*]}"
  for label in "${tier[@]}"; do
    _log "  [stop] $label"
    _stop_one "$label" 10
  done
  _log "✓ tier stop 完成"

  # v0.62.0(P1-1):stop 时一并清 claude --bg 真进程(不只是 wrapper)
  # - wrapper 进程(cc-reviewer-bg.sh):pgrep -f ccc-reviewer-bg.sh
  # - 实际在跑的 claude --bg 子进程:pgrep -f "claude.*--bg"
  # - bg session 状态文件 ~/.ccc/bg-sessions/state.json 删(下次启动 rebuild)
  # 否则 Engine 下一启动 register_bg_session 重注,会泄漏旧 session
  if [[ "$target" == "all" || "$target" == "engine" ]]; then
    local bg_pids
    bg_pids=$(pgrep -f 'ccc-reviewer-bg\.sh' 2>/dev/null || true)
    if [[ -n "$bg_pids" ]]; then
      _log "  [stop] 清 claude --bg wrappers: $bg_pids"
      # shellcheck disable=SC2086  # word-split 故意
      kill -TERM $bg_pids 2>/dev/null || true
      sleep 1
      kill -KILL $bg_pids 2>/dev/null || true
    fi
    # v0.62.0(P1-1):同时杀真正在跑的 claude --bg 子进程(orphan 泄漏)
    local bg_claude_pids
    bg_claude_pids=$(pgrep -f 'claude.*--bg' 2>/dev/null || true)
    if [[ -n "$bg_claude_pids" ]]; then
      _log "  [stop] 清 claude --bg 子进程: $bg_claude_pids"
      # shellcheck disable=SC2086  # word-split 故意
      kill -TERM $bg_claude_pids 2>/dev/null || true
      sleep 1
      kill -KILL $bg_claude_pids 2>/dev/null || true
    fi
    # v0.62.0(P0-A.2):清持久化文件,下次 Engine tick 重建
    local bg_state="${HOME}/.ccc/bg-sessions/state.json"
    if [[ -f "$bg_state" ]]; then
      rm -f "$bg_state"
      _log "  [stop] 清 bg session state.json"
    fi
  fi
}

# ── 4. 子命令:status ───────────────────────────────────
# 三色:green=loaded+probe OK;yellow=loaded+probe fail;red=not loaded
status() {
  local target="${1:-all}"
  local labels=()
  if [[ "$target" == "all" || "$target" == "$HOST_TAG" ]]; then
    labels=("${ALL_LABELS[@]}")
  else
    _log "❌ 未知 status target: $target"; return 1
  fi
  local overall="green"
  printf "%-32s %-12s %-12s %s\n" "LABEL" "LOAD" "PROBE" "DETAIL"
  for label in "${labels[@]}"; do
    local st probe
    st=$(_status_of "$label")
    probe=$(_probe_component "$label" 2>/dev/null || echo down)
    # 实际调 probe(避免上面 _probe_component subshell 问题)
    local url=$(_probe_url "$label")
    local probe_status="n/a"
    if [[ -n "$url" ]]; then
      local auth=$(_probe_auth "$label")
      local code
      code=$(eval curl -fsS -m 3 $auth -o /dev/null -w "%{http_code}" "$url" 2>/dev/null || echo 000)
      if [[ "$code" =~ ^2 ]]; then
        probe_status="up"
      else
        probe_status="down:$code"
        [[ "$st" == "loaded" ]] && overall="yellow"
      fi
    fi
    if [[ "$st" != "loaded" && "$st" != "exited" ]]; then
      overall="red"
    fi
    printf "%-32s %-12s %-12s %s\n" "$label" "$st" "$probe_status" ""
  done
  echo
  case "$overall" in
    green) echo "OVERALL: 🟢 green" ;;
    yellow) echo "OVERALL: 🟡 yellow" ;;
    red) echo "OVERALL: 🔴 red" ;;
  esac
}

# ── 5. 子命令:health ───────────────────────────────────
# 调各端点的 /health(或 /admin/status)返回状态
health() {
  local target="${1:-all}"
  if [[ "$target" == "all" || "$target" == "$HOST_TAG" ]]; then
    :
  fi
  echo "=== CCC Fleet Health ($HOST_TAG @ $(hostname)) ==="
  for label in "${ALL_LABELS[@]}"; do
    local url=$(_probe_url "$label")
    if [[ -z "$url" ]]; then continue; fi
    local auth=$(_probe_auth "$label")
    local code latency=-1 body=""
    local start_ms end_ms
    # macOS BSD date 不支持 %3N,fallback 到 Python 毫秒
    start_ms=$(python3 -c 'import time; print(int(time.time()*1000))' 2>/dev/null || date +%s)
    body=$(eval curl -fsS -m 5 $auth "$url" 2>/dev/null | head -c 200)
    end_ms=$(python3 -c 'import time; print(int(time.time()*1000))' 2>/dev/null || date +%s)
    code=$?
    latency=$((end_ms - start_ms))
    if [[ -z "$body" ]]; then
      printf "  %-32s down\n" "$label"
    else
      printf "  %-32s up (%dms) %s\n" "$label" "$latency" "$url"
    fi
  done
}

# ── 6. 子命令:diagnose ─────────────────────────────────
# 整合:status + self-check 短 + dual-host(check 仅 2017 上跑)
diagnose() {
  echo "=== Diagnose ($HOST_TAG) ==="
  status
  echo
  echo "--- self-check (HARD 7 项) ---"
  bash "${CCC_HOME}/scripts/ccc-self-check.sh" 2>&1 | tail -10
  echo
  if [[ -f "${CCC_HOME}/scripts/ccc-dual-host-check.sh" ]]; then
    echo "--- dual-host ---"
    bash "${CCC_HOME}/scripts/ccc-dual-host-check.sh" 2>&1 | head -10
  fi
}

# ── 7. 子命令:restart(占位,v0.61.0 阶段 B)──────────────
restart() {
  local target="${1:-all}"
  _log "restart $target(rolling 等 active_tasks ≤ 1 暂未实现,本阶段做硬重启)"
  stop "$target"
  sleep 2
  start "$target"
}

# ── 8. 子命令:watchdog(plist 30s 调一次)────────────
# 状态非 green → 写告警(目前用 stderr,后续接 desktop 通知)
watchdog() {
  local st=$(status 2>&1 | grep -E '^OVERALL' | head -1)
  if [[ "$st" != *"green"* ]]; then
    _log "WATCHDOG ALERT: $st"
    return 1
  fi
  return 0
}

# ── 9. main ────────────────────────────────────────────
case "${1:-status}" in
  start)    shift; start "$@" ;;
  stop)     shift; stop "$@" ;;
  status)   shift; status "$@" ;;
  restart)  shift; restart "$@" ;;
  health)   shift; health "$@" ;;
  diagnose) shift; diagnose "$@" ;;
  watchdog) shift; watchdog "$@" ;;
  *)        status ;;
esac
