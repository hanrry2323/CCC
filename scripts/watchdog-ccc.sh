#!/usr/bin/env bash
# ── scripts/watchdog-ccc.sh ──
# CCC 看门狗守护脚本（P5 灭：服务防死锁与 <60s 快速自愈）
#
# 用法：
#   ./scripts/watchdog-ccc.sh
#
# 机制：
#   1. 检查 com.ccc.engine (server.engine.main) 进程是否存在
#   2. 检查 com.ccc.web-server 进程是否存在
#   3. 检查日志 ~/.ccc/logs/engine.stderr.log 的最近心跳修改时间 (mtime < 120s)
#   4. 如果任何一项异常，只重启对应服务（不连带重启其他服务）
#
# 2026-08-21 修复：分离服务健康检查，避免 engine 故障时连带重启 web-server

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="${HOME}/.ccc/logs"
mkdir -p "${LOG_DIR}"

HEARTBEAT_LOG="${LOG_DIR}/engine.stderr.log"
# 槽位心跳（run_once 每轮写 engine-metrics.jsonl）——真实心跳源，优先于 stderr.log
SLOT_METRICS="${LOG_DIR}/exec/engine-metrics.jsonl"
WATCHDOG_LOG="${LOG_DIR}/watchdog.log"

ENGINE_PNAME="${CCC_WATCHDOG_ENGINE_PNAME:-server.engine.main}"
WEB_PNAME="${CCC_WATCHDOG_WEB_PNAME:-server.web.server}"

# 心跳宽限（秒）：engine 心跳默认 60s，但 run_once 偶发阻塞（子进程/SSH）可达 10-40min，
# 固定 120s 会误杀。默认 300s，可经 CCC_WATCHDOG_HEARTBEAT_GRACE 覆盖。
HEARTBEAT_GRACE="${CCC_WATCHDOG_HEARTBEAT_GRACE:-300}"

# ── ccc083 防旋自愈（2026-08-25）：连续观测确认 + kickstart 冷却 + 风暴升级告警 ──
# 背景（取证结论）：2026-08-24 14:49–15:46 机审/开发会话把本脚本当「门禁实跑」反复执行，
# 单次观测即触发 kickstart --engine-only；重启窗口内 pgrep 竞态又判「进程不存在」，
# 形成 47 次连环重启 → 在飞执行体被杀(exit 137) → 引擎回待分派重派 → 新会话再实跑本脚本的
# 自持风暴。修复四件套：
#   1) 连续确认：故障需连续 MIN_FAULT_STREAK 轮观测（默认 2）才动手；孤立单次观测只记录；
#   2) 冷却：同服务两次 kickstart 最小间隔 KICK_COOLDOWN 秒（默认 300），冷却期内只观测不动手；
#   3) 升级告警：连续 FLAP_ALERT_STREAK 轮仍故障 → 写 alerts 文件转人工（每小时至多一次）；
#   4) DRY-RUN：CCC_WATCHDOG_DRY_RUN=1 只记录意图不执行 kickstart（测试/演练）。
WATCHDOG_STATE_DIR="${CCC_WATCHDOG_STATE_DIR:-${LOG_DIR}/watchdog-state}"
MIN_FAULT_STREAK="${CCC_WATCHDOG_MIN_FAULT_STREAK:-2}"
KICK_COOLDOWN="${CCC_WATCHDOG_KICKSTART_COOLDOWN:-300}"
FLAP_ALERT_STREAK="${CCC_WATCHDOG_FLAP_ALERT_STREAK:-10}"
ALERT_REPEAT_SEC="${CCC_WATCHDOG_ALERT_REPEAT_SEC:-3600}"
DRY_RUN="${CCC_WATCHDOG_DRY_RUN:-0}"

# 读单服务状态（bash 3.2 兼容：经全局变量返回）
WD_STREAK=0; WD_LAST_KICK=0; WD_LAST_ALERT=0
wd_load_state() {
  local svc="$1" f k v
  WD_STREAK=0; WD_LAST_KICK=0; WD_LAST_ALERT=0
  f="${WATCHDOG_STATE_DIR}/${svc}.state"
  [[ -f "$f" ]] || return 0
  while IFS='=' read -r k v; do
    case "$k" in
      streak)     WD_STREAK="$(printf '%s' "$v" | tr -cd '0-9')"; WD_STREAK="${WD_STREAK:-0}";;
      last_kick)  WD_LAST_KICK="$(printf '%s' "$v" | tr -cd '0-9')"; WD_LAST_KICK="${WD_LAST_KICK:-0}";;
      last_alert) WD_LAST_ALERT="$(printf '%s' "$v" | tr -cd '0-9')"; WD_LAST_ALERT="${WD_LAST_ALERT:-0}";;
    esac
  done < "$f"
}

wd_save_state() {
  local svc="$1" f
  mkdir -p "${WATCHDOG_STATE_DIR}" 2>/dev/null || true
  f="${WATCHDOG_STATE_DIR}/${svc}.state"
  { printf 'streak=%s\nlast_kick=%s\nlast_alert=%s\n' "${WD_STREAK}" "${WD_LAST_KICK}" "${WD_LAST_ALERT}" \
      > "$f" 2>/dev/null; } || true
}

# 故障观测记账 + 自愈判定。返回 0=应当触发 kickstart；1=观察/冷却跳过。
wd_fault_observed() {
  local svc="$1" label="$2" now alert_file
  now="$(date +%s)"
  wd_load_state "$svc"
  WD_STREAK=$((WD_STREAK + 1))
  wd_save_state "$svc"
  if (( WD_STREAK >= FLAP_ALERT_STREAK )) && (( now - WD_LAST_ALERT >= ALERT_REPEAT_SEC )); then
    mkdir -p "${LOG_DIR}/alerts" 2>/dev/null || true
    alert_file="${LOG_DIR}/alerts/watchdog-flap-${svc}.alert"
    printf '[%s] %s 连续 %d 轮观测到故障且自愈无效——疑似环境级故障或自愈配置过紧，需人工介入\n' \
      "$(date '+%Y-%m-%d %H:%M:%S')" "$label" "$WD_STREAK" > "$alert_file" 2>/dev/null || true
    WD_LAST_ALERT="$now"
    wd_save_state "$svc"
    log_watchdog "ALERT: 自愈风暴升级告警（${svc} streak=${WD_STREAK}）→ ${alert_file}"
    echo "[ALERT] watchdog flap escalation: ${svc} streak=${WD_STREAK}" >&2
  fi
  if (( now - WD_LAST_KICK < KICK_COOLDOWN )); then
    log_watchdog "自愈冷却中（${svc}：距上次 kickstart $((now - WD_LAST_KICK))s < ${KICK_COOLDOWN}s），本轮只观测不动手（streak=${WD_STREAK}）"
    return 1
  fi
  if (( WD_STREAK < MIN_FAULT_STREAK )); then
    log_watchdog "故障首次/未连任观测（${svc} streak=${WD_STREAK}/${MIN_FAULT_STREAK}），观察一轮不动手"
    return 1
  fi
  WD_LAST_KICK="$now"
  WD_STREAK=0
  wd_save_state "$svc"
  return 0
}

# 健康回见：清零该服务故障连击（保留 kick/alert 时间戳）
wd_healthy_observed() {
  local svc="$1"
  wd_load_state "$svc"
  (( WD_STREAK == 0 )) && return 0
  WD_STREAK=0
  wd_save_state "$svc"
}


log_watchdog() {
  local msg="$1"
  local ts
  ts="$(date '+%Y-%m-%d %H:%M:%S')"
  echo "[${ts}] ${msg}" >> "${WATCHDOG_LOG}"
}

# 1. 检查 engine 进程是否存在
is_engine_alive() {
  pgrep -f "${ENGINE_PNAME}" >/dev/null 2>&1
}

# 2. 检查 web-server 进程是否存在
is_web_alive() {
  pgrep -f "${WEB_PNAME}" >/dev/null 2>&1
}

# 3. 检查 engine 心跳新鲜度：优先 slot 心跳 engine-metrics.jsonl（run_once 每轮写），
#    缺失/不可读回退 stderr.log。宽限 HEARTBEAT_GRACE（默认 300s，2026-08-22 硬化）。
is_engine_heartbeat_healthy() {
  local source=""
  local last_mod=""

  if [[ -f "${SLOT_METRICS}" ]]; then
    source="${SLOT_METRICS}"
  elif [[ -f "${HEARTBEAT_LOG}" ]]; then
    source="${HEARTBEAT_LOG}"
  else
    return 1
  fi

  if [[ "$OSTYPE" == "darwin"* ]]; then
    last_mod=$(stat -f "%m" "${source}")
  else
    last_mod=$(stat -c "%Y" "${source}")
  fi

  local now
  now=$(date +%s)
  local diff=$((now - last_mod))

  if [[ $diff -lt ${HEARTBEAT_GRACE} ]]; then
    return 0
  else
    return 1
  fi
}

# 4. 检查 web-server HTTP 健康
is_web_http_healthy() {
  local http_code
  http_code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 3 http://localhost:7788/health 2>/dev/null || echo "000")
  if [[ "$http_code" == "200" ]]; then
    return 0
  else
    return 1
  fi
}

# ── P0-2a 预设变更监控（2026-08-23）：preset hash 基线校验 ──
# 基线文件落 LOG_DIR（fan 可写），预设本身 root:444 只读防 DSH 自改。
# 变更→写告警（watchdog.log + stderr），不重启服务（由人审定是否回滚）。
check_preset_hash() {
  local preset_root="${HOME}/.dsh/.agent-presets"
  local baseline="${LOG_DIR}/preset-hash.baseline"
  local current
  current="$(find "${preset_root}" -type f \( -name '*.yml' -o -name '*.yaml' \) 2>/dev/null | sort | xargs shasum -a 256 2>/dev/null | shasum -a 256 2>/dev/null | awk '{print $1}')"
  if [[ -z "$current" ]]; then
    return 0
  fi
  if [[ ! -f "$baseline" ]]; then
    echo "$current  baseline" > "$baseline" 2>/dev/null || true
    log_watchdog "preset 基线已登记: ${current:0:12}..."
    return 0
  fi
  local expect
  expect="$(awk '{print $1}' "$baseline" 2>/dev/null)"
  if [[ "$current" != "$expect" ]]; then
    local msg="preset 变更告警：当前 ${current:0:12}... 期望 ${expect:0:12}...（~/.dsh/.agent-presets 已变，需人工核对是否为授权变更）"
    log_watchdog "ALERT: $msg"
    echo "[ALERT] $msg" >&2
  fi
}
check_preset_hash || true

# ── 清道夫巡检（2026-08-24 · ccc078）：陈旧 worktree / 可删分支 / 遗留预检服务 ──
# 只上报不删除；输出进既有 watchdog 日志管道（log_watchdog）。
# 同类告警 24h 内不重复（阈值防刷屏，状态文件落 LOG_DIR/janitor/）。
# 纯增量段：不触碰下方健康检查/自愈逻辑与退出码；调用处一律 `|| true`，
# 巡检自身失败只影响本段，绝不改变健康结论。
# 锚定 CCC 主仓（而非脚本所在 checkout）：worktree 里运行时经 git-common-dir 回溯主仓根。
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
_janitor_common_dir="$(git -C "${SCRIPT_DIR}" rev-parse --path-format=absolute --git-common-dir 2>/dev/null || true)"
if [[ -n "${_janitor_common_dir}" && -d "${_janitor_common_dir}" ]]; then
  REPO_ROOT="$(dirname "${_janitor_common_dir}")"
fi
DISPATCH_ROOT="${REPO_ROOT}/docs/dispatch"
CCC_REGISTRY="${REPO_ROOT}/docs/projects/registry.yaml"
JANITOR_STATE_DIR="${LOG_DIR}/janitor"
JANITOR_REPEAT_SEC="${CCC_JANITOR_REPEAT_SEC:-86400}"        # 同类告警去重窗口：24h
JANITOR_TMP_MIN_AGE_SEC="${CCC_JANITOR_TMP_MIN_AGE_SEC:-86400}"  # /tmp/ccc-* 判「残留」的最小年龄

janitor_path_mtime() {
  if [[ "$OSTYPE" == "darwin"* ]]; then
    stat -f "%m" "$1" 2>/dev/null || echo 0
  else
    stat -c "%Y" "$1" 2>/dev/null || echo 0
  fi
}

# 同类告警 24h 去重：返回 0 = 应上报（并登记时间戳）
janitor_should_report() {
  local key="$1" state_file now last
  state_file="${JANITOR_STATE_DIR}/${key}"
  mkdir -p "${JANITOR_STATE_DIR}" 2>/dev/null || true
  now="$(date +%s)"
  last="$(cat "${state_file}" 2>/dev/null || true)"
  last="${last//[^0-9]/}"
  last="${last:-0}"
  if (( now - last >= JANITOR_REPEAT_SEC )); then
    echo "${now}" > "${state_file}" 2>/dev/null || true
    return 0
  fi
  return 1
}

# 上报一类明细（key, 类别名, 明细多行文本）；去重窗口内完全静默
janitor_emit() {
  local key="$1" label="$2" detail="$3" line
  [[ -n "${detail//[[:space:]]/}" ]] || return 1
  janitor_should_report "${key}" || return 1
  log_watchdog "JANITOR[${label}] 发现待处置项（同类 24h 防刷屏窗口内首次上报）："
  while IFS= read -r line; do
    [[ -n "$line" ]] && log_watchdog "JANITOR[${label}]   - ${line}"
  done <<< "${detail}"
  return 0
}

# 卡是否终态：头部「状态：已关闭/作废」或「历史卡/历史标记」标注
janitor_card_is_terminal() {
  local f="$1" h
  h="$(head -12 "$f" 2>/dev/null || true)"
  if printf '%s\n' "${h}" | grep -qE '状态：.*(已关闭|作废)'; then return 0; fi
  if printf '%s\n' "${h}" | grep -qE '^> .*历史(卡|标记)'; then return 0; fi
  return 1
}

# 扫一仓的 worktree：①卡已终态的注册 worktree；②worktree_root 下未注册的孤儿目录
janitor_scan_repo_worktrees() {
  local repo="$1" wt_root="$2"
  [[ -d "$repo" ]] || return 0
  git -C "$repo" rev-parse --git-dir >/dev/null 2>&1 || return 0
  local reg first p name cardf cardid d
  reg="$(git -C "$repo" worktree list --porcelain 2>/dev/null | awk '/^worktree /{print $2}' || true)"
  first=1
  while IFS= read -r p; do
    [[ -n "$p" ]] || continue
    if (( first )); then first=0; continue; fi   # 首条=主 checkout，跳过
    name="${p##*/}"
    [[ "$name" =~ ^[a-z]+[0-9]+$ ]] || continue  # 仅识别 <prefix><NNN> 形态
    cardf="$(ls "${DISPATCH_ROOT}"/*/"${name}"-*.md 2>/dev/null | head -1 || true)"
    [[ -n "$cardf" && -f "$cardf" ]] || continue  # 定位不到对应卡 → 不误报
    cardid="$(basename "${cardf}" .md)"
    if janitor_card_is_terminal "${cardf}"; then
      RECYCLE_DETAIL+="worktree ${p} · 卡 ${cardid} 已终态 → 建议: 核对该目录无未提交改动后执行 git worktree remove \"${p}\""$'\n'
    fi
  done <<< "${reg}"
  if [[ -n "$wt_root" && -d "$wt_root" ]]; then
    for d in "${wt_root}"/*/; do
      [[ -d "$d" ]] || continue
      d="${d%/}"
      if printf '%s\n' "${reg}" | grep -qxF "${d}"; then continue; fi
      RECYCLE_DETAIL+="孤儿目录 ${d} · git worktree list 未注册 → 建议: 确认无用后删除该目录（必要时 git worktree prune）"$'\n'
    done
  fi
  return 0
}

# 扫一仓本地分支：已合入 origin/main(master) 仍存在的非豁免分支
janitor_scan_repo_branches() {
  local repo="$1" base="" busy br is_busy
  [[ -d "$repo" ]] || return 0
  git -C "$repo" rev-parse --git-dir >/dev/null 2>&1 || return 0
  if git -C "$repo" rev-parse -q --verify refs/remotes/origin/main >/dev/null 2>&1; then
    base="origin/main"
  elif git -C "$repo" rev-parse -q --verify refs/remotes/origin/master >/dev/null 2>&1; then
    base="origin/master"
  else
    return 0  # 无远程 main/master 引用的仓跳过（不做 fetch，基于本地引用保守判定）
  fi
  busy="$(git -C "$repo" worktree list --porcelain 2>/dev/null | awk '/^branch /{sub("^refs/heads/", "", $2); print $2}' || true)"
  while IFS= read -r br; do
    [[ -n "$br" ]] || continue
    case "${br}" in main|master|develop|HEAD) continue;; esac  # 豁免主干分支
    is_busy=0
    if printf '%s\n' "${busy}" | grep -qxF "${br}"; then is_busy=1; fi
    if git -C "$repo" merge-base --is-ancestor "${br}" "${base}" >/dev/null 2>&1; then
      if (( is_busy )); then
        BRANCH_DETAIL+="${repo} :: ${br} · 已合入 ${base}（正被 worktree 占用）→ 建议: 先移除占用它的 worktree，再 git branch -d ${br}"$'\n'
      else
        BRANCH_DETAIL+="${repo} :: ${br} · 已合入 ${base} → 建议: git branch -d ${br}"$'\n'
      fi
    fi
  done < <(git -C "$repo" branch --format='%(refname:short)' 2>/dev/null || true)
  return 0
}

# 扫遗留预检服务：7898/7899 监听 + /tmp/ccc-* 残留（按最小年龄过滤，防误伤活跃预检）
janitor_scan_stale_services() {
  local port lst row pid cmd p mt age total=0 old=0 samples=""
  for port in 7898 7899; do
    lst="$(lsof -nP -iTCP:"${port}" -sTCP:LISTEN 2>/dev/null | tail -n +2 || true)"
    while IFS= read -r row; do
      [[ -n "$row" ]] || continue
      pid="$(printf '%s\n' "${row}" | awk '{print $2}')"
      cmd="$(printf '%s\n' "${row}" | awk '{print $1}')"
      STALE_DETAIL+="端口 ${port} 预检监听残留: pid=${pid} cmd=${cmd} → 建议: 核实非现役服务后执行 kill ${pid}"$'\n'
    done <<< "${lst}"
  done
  for p in /tmp/ccc-*; do
    [[ -e "$p" ]] || continue
    total=$((total + 1))
    mt="$(janitor_path_mtime "$p")"
    mt="${mt:-0}"
    age=$(( $(date +%s) - mt ))
    if (( age >= JANITOR_TMP_MIN_AGE_SEC )); then
      old=$((old + 1))
      if (( old <= 5 )); then samples+=" ${p##*/}"; fi
    fi
  done
  if (( total > 0 )); then
    STALE_DETAIL+="/tmp/ccc-* 预检残留共 ${total} 项（mtime≥${JANITOR_TMP_MIN_AGE_SEC}s 的 ${old} 项；样例:${samples} ）→ 建议: 核实无活跃预检引用后批量清理 /tmp/ccc-*"$'\n'
  fi
  return 0
}

# 清道夫主入口：只上报，不删除，不改健康检查结论
janitor_sweep() {
  local pairs seen mac wtr n_r n_b n_s
  RECYCLE_DETAIL=""
  BRANCH_DETAIL=""
  STALE_DETAIL=""
  # 受管仓清单 = CCC 主仓 + registry.yaml（唯一事实源）中本地存在的仓
  pairs=""
  if [[ -f "${CCC_REGISTRY}" ]]; then
    while IFS= read -r pair; do
      [[ -n "$pair" ]] || continue
      mac="${pair%%$'\t'*}"
      wtr="${pair#*$'\t'}"
      [[ -n "$mac" && "$mac" != "null" && -d "$mac" ]] || continue
      [[ "$mac" != "${REPO_ROOT}" ]] || continue   # 主仓统一由追加行提供（registry 中 ccc 项目无 worktree_root，若先入列会以空 wt_root 占住去重位）
      pairs+="${pair}"$'\n'
    done < <(awk '
      /^  - / { if (mac != "" && mac != "null") print mac "\t" wtr; mac=""; wtr=""; next }
      /^      mac2017:/      { mac=$2 }
      /^      worktree_root:/ { wtr=$2 }
      END { if (mac != "" && mac != "null") print mac "\t" wtr }
    ' "${CCC_REGISTRY}" 2>/dev/null || true)
  fi
  pairs+="${REPO_ROOT}"$'\t'"${REPO_ROOT}-wt"$'\n'
  seen="|"
  while IFS=$'\t' read -r mac wtr; do
    [[ -n "$mac" ]] || continue
    case "${seen}" in *"|${mac}|"*) continue;; esac   # 同仓只扫一次（registry 与追加主仓行可能重合）
    seen+="|${mac}|"
    janitor_scan_repo_worktrees "${mac}" "${wtr}" || true
    janitor_scan_repo_branches "${mac}" || true
  done <<< "${pairs}"
  janitor_scan_stale_services || true

  n_r="$(printf '%s' "${RECYCLE_DETAIL}" | grep -c . || true)"
  n_b="$(printf '%s' "${BRANCH_DETAIL}" | grep -c . || true)"
  n_s="$(printf '%s' "${STALE_DETAIL}" | grep -c . || true)"
  janitor_emit "janitor-recyclable-worktrees" "可回收worktree" "${RECYCLE_DETAIL}" || true
  janitor_emit "janitor-prunable-branches" "可删分支" "${BRANCH_DETAIL}" || true
  janitor_emit "janitor-stale-services" "遗留服务" "${STALE_DETAIL}" || true
  echo "[JANITOR] 清道夫巡检: 可回收worktree=${n_r} 可删分支=${n_b} 遗留服务=${n_s}（明细入 ${WATCHDOG_LOG}，同类告警 24h 防刷屏）"
  return 0
}

# 检查各服务状态
ENGINE_ISSUES=()
WEB_ISSUES=()

# Engine 检查
if ! is_engine_alive; then
  ENGINE_ISSUES+=("进程不存在")
elif ! is_engine_heartbeat_healthy; then
  ENGINE_ISSUES+=("日志心跳超时")
fi

# Web Server 检查
if ! is_web_alive; then
  WEB_ISSUES+=("进程不存在")
elif ! is_web_http_healthy; then
  WEB_ISSUES+=("HTTP 健康检查失败")
fi

_janitor_sweep_maybe() {
  if [[ "${CCC_JANITOR_OFF:-0}" == "1" ]]; then
    return 0
  fi
  janitor_sweep || true   # ccc078：巡检失败不影响「健康」结论与退出码
}

# 如果都没问题：清零故障连击（ccc083 防旋），跑清道夫巡检后照常退出
if [[ ${#ENGINE_ISSUES[@]} -eq 0 ]] && [[ ${#WEB_ISSUES[@]} -eq 0 ]]; then
  wd_healthy_observed "engine"
  wd_healthy_observed "web"
  _janitor_sweep_maybe
  echo "健康"
  exit 0
fi

# 只重启有问题的服务，不连带重启；触发前过 ccc083 防旋闸（连续确认 + 冷却）
FAILED=0

if [[ ${#ENGINE_ISSUES[@]} -gt 0 ]]; then
  REASON="Engine: ${ENGINE_ISSUES[*]}"
  log_watchdog "发现故障 [${REASON}]"
  echo "[WARN] 发现故障: ${REASON}" >&2
  if ! wd_fault_observed "engine" "Engine"; then
    log_watchdog "防旋闸拦截：本轮不对 Engine 执行自愈（只观测）"
  elif [[ "$DRY_RUN" == "1" ]]; then
    log_watchdog "[DRY-RUN] 将触发 kickstart --engine-only（未执行）"
    echo "[DRY-RUN] watchdog: 将自愈 Engine（未执行）"
  else
    if "${SCRIPT_DIR}/kickstart-ccc.sh" --engine-only >/dev/null 2>&1; then
      log_watchdog "自愈成功：engine 重启完毕"
      echo "Engine 已拉起"
    else
      log_watchdog "ERROR：engine 自愈失败"
      echo "Engine 重启失败"
      FAILED=$((FAILED + 1))
    fi
  fi
fi

if [[ ${#WEB_ISSUES[@]} -gt 0 ]]; then
  REASON="Web Server: ${WEB_ISSUES[*]}"
  log_watchdog "发现故障 [${REASON}]"
  echo "[WARN] 发现故障: ${REASON}" >&2
  if ! wd_fault_observed "web" "Web Server"; then
    log_watchdog "防旋闸拦截：本轮不对 Web Server 执行自愈（只观测）"
  elif [[ "$DRY_RUN" == "1" ]]; then
    log_watchdog "[DRY-RUN] 将触发 kickstart --web-only（未执行）"
    echo "[DRY-RUN] watchdog: 将自愈 Web Server（未执行）"
  else
    if "${SCRIPT_DIR}/kickstart-ccc.sh" --web-only >/dev/null 2>&1; then
      log_watchdog "自愈成功：web-server 重启完毕"
      echo "Web Server 已拉起"
    else
      log_watchdog "ERROR：web-server 自愈失败"
      echo "Web Server 重启失败"
      FAILED=$((FAILED + 1))
    fi
  fi
fi

if [[ $FAILED -gt 0 ]]; then
  exit 1
fi

_janitor_sweep_maybe   # ccc078/ccc083：自愈成功路径同样巡检；失败不影响退出码

exit 0
