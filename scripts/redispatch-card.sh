#!/usr/bin/env bash
# ── CCC：打回卡人工重新分派（运行时指令，主树卡文件只读）──
#
# 用法：
#   scripts/redispatch-card.sh <card-id> [<card-id>...]
#   scripts/redispatch-card.sh --renew-auth <card-id> ...   # 强制重新登录换 token
#
# 前置：老板修订指示先写进卡 `## 人工批注` 并 commit+push 到 main
#       （执行体 worktree 从 main 建，天然读到批注）。
# 动作：调用看板 API POST /tasks/<id>/transition（status=待分派）→ 写运行时
#       sidecar（state=待分派、retry_count=0、redispatch=ts），engine 每轮重派。
#       不直接改任何卡文件（主树保持 main 镜像）。
#
# 鉴权（2026-09-07 P4.2 增强）：
#   - CCC_BOARD_TOKEN env 优先；无 env 时自动从 ~/.ccc/web-auth.txt 登录取 token；
#   - transition 返回 401 → 自动走 POST /session 换新 token 并重试一次；
#   - --renew-auth 强制本地重新登录（供轮换后手动换发）。
#   红线：token/密码不落盘、不进日志、不进 git；token 只在内存中传递。

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BOARD_URL="${CCC_BOARD_URL:-http://192.168.3.116:7788}"
WEB_AUTH_FILE="${CCC_WEB_AUTH_FILE:-${HOME}/.ccc/web-auth.txt}"

BOARD_TOKEN="${CCC_BOARD_TOKEN:-}"       # 可被 _fetch_token 更新；绝不落盘/打印
AUTH_HEADERS=()
if [[ -n "${BOARD_TOKEN}" ]]; then
  AUTH_HEADERS=(-H "Authorization: Bearer ${BOARD_TOKEN}")
fi

RENEW_AUTH=0
IDS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help) sed -n '2,26p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    --renew-auth) RENEW_AUTH=1; shift ;;
    *) IDS+=("$1"); shift ;;
  esac
done

if [[ ${#IDS[@]} -eq 0 ]]; then
  echo "[ERROR] 缺少卡 ID（用法：scripts/redispatch-card.sh <card-id>）" >&2
  exit 2
fi

cd "$PROJECT_ROOT"

# ── 解析 ~/.ccc/web-auth.txt（现网格式：标题 + `账号: xxx` + `口令: xxx`）──
# 兼容单行 user:pass 与单行口令（账号固定 ccc）。失败返回 1。
# 成功设 _AUTH_USER / _AUTH_PASS（内存态）。
_parse_auth_file() {
  local line key val first
  _AUTH_USER=""; _AUTH_PASS=""
  [[ -f "${WEB_AUTH_FILE}" ]] || return 1
  while IFS= read -r line; do
    line="${line#"${line%%[![:space:]]*}"}"
    [[ -n "$line" ]] || continue
    case "$line" in \#*) continue ;; esac
    key="${line%%[:：]*}"
    val="${line#*[:：]}"
    val="${val#"${val%%[![:space:]]*}"}"
    case "${key}" in
      账号|用户|账号名|user|username) [[ -n "$val" ]] && _AUTH_USER="$val" ;;
      口令|密码|password|pass)       [[ -n "$val" ]] && _AUTH_PASS="$val" ;;
    esac
  done < "${WEB_AUTH_FILE}"
  if [[ -n "${_AUTH_USER}" && -n "${_AUTH_PASS}" ]]; then
    return 0
  fi
  first="$(grep -m1 -v '^[[:space:]]*#' "${WEB_AUTH_FILE}" 2>/dev/null | head -1 || true)"
  first="${first#"${first%%[![:space:]]*}"}"
  [[ -n "$first" ]] || return 1
  if [[ "$first" == *":"* ]]; then
    _AUTH_USER="${first%%:**}"
    _AUTH_PASS="${first#*:}"
    _AUTH_PASS="${_AUTH_PASS#"${_AUTH_PASS%%[![:space:]]*}"}"
  else
    _AUTH_USER="ccc"
    _AUTH_PASS="$first"
  fi
  [[ -n "${_AUTH_USER}" && -n "${_AUTH_PASS}" ]]
}

# ── POST /session 换 token（内存态，绝不落盘/打印 token）──
# 同轮只允许换发一次（TOKEN_RENEWED=1），避免 401 死循环反复登录。
_fetch_token() {
  local body tmpfile code
  if [[ "${TOKEN_RENEWED:-0}" == "1" ]]; then
    echo "[WARN] 本轮已换发过 token，拒绝再次登录（401 重复可人工用 CCC_BOARD_TOKEN 注入）" >&2
    return 1
  fi
  if ! _parse_auth_file; then
    echo "[ERROR] 凭据文件不可读或格式不支持: ${WEB_AUTH_FILE}" >&2
    return 1
  fi
  # JSON 序列化经 python3（避免口令含引号破坏 JSON）；无 python3 时退化为短口令直拼。
  body="$(python3 -c '
import json, sys
print(json.dumps({"username": sys.argv[1], "password": sys.argv[2]}))
' "${_AUTH_USER}" "${_AUTH_PASS}" 2>/dev/null || printf '{"username":"%s","password":"%s"}\n' "${_AUTH_USER}" "${_AUTH_PASS}")"
  tmpfile="$(mktemp 2>/dev/null || echo "${TMPDIR:-/tmp}/ccc-redispatch-body.$$")"
  code="$(curl -s --max-time 10 -X POST "${BOARD_URL}/session" \
      -H 'Content-Type: application/json' -d "${body}" \
      -o "${tmpfile}" -w '%{http_code}' 2>/dev/null || true)"
  if [[ "${code}" != "200" ]]; then
    rm -f "${tmpfile}" 2>/dev/null || true
    # 失败不打印 token/口令，只给状态
    echo "[WARN] POST /session 登录失败 (HTTP ${code:-连接失败})，无法换发 token" >&2
    return 1
  fi
  BOARD_TOKEN="$(python3 -c '
import json, sys
try:
    d = json.load(open(sys.argv[1], encoding="utf-8"))
    print(d.get("token", ""))
except Exception:
    print("")
' "${tmpfile}" 2>/dev/null || sed -n 's/.*"token"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "${tmpfile}" | head -1)"
  rm -f "${tmpfile}" 2>/dev/null || true
  if [[ -z "${BOARD_TOKEN}" ]]; then
    echo "[WARN] /session 响应未含 token（可能账号不匹配）；已中止" >&2
    return 1
  fi
  TOKEN_RENEWED=1
  AUTH_HEADERS=(-H "Authorization: Bearer ${BOARD_TOKEN}")
  return 0
}

# 确保有可用 token：显式 --renew-auth，或未注入 env token。
# 若当前为 FORCE（--renew-auth）则无视现有 token 重新登录一次。
ensure_token() {
  if [[ "${RENEW_AUTH}" == "1" || -z "${BOARD_TOKEN}" ]]; then
    _fetch_token || { return 1; }
  fi
}

# ── 发起带 code 的 board 请求：board_req METHOD PATH [DATA] ──
# 返回：设 B_REQ_CODE / B_REQ_BODY（内存态 body）
board_req() {
  local method="$1" path="$2" data="${3:-}"
  local args=(-s --max-time 10 -X "${method}")
  local n="${#AUTH_HEADERS[@]}"
  [[ -n "${BOARD_TOKEN}" ]] && args+=("${AUTH_HEADERS[@]}")
  [[ -z "${data}" ]] || args+=(-H 'Content-Type: application/json' -d "${data}")
  local tmpfile
  tmpfile="$(mktemp 2>/dev/null || echo "${TMPDIR:-/tmp}/ccc-redispatch-body.$$")"
  B_REQ_CODE="$(curl "${args[@]}" "${BOARD_URL}${path}" -o "${tmpfile}" -w '%{http_code}' 2>/dev/null || true)"
  B_REQ_BODY="$(cat "${tmpfile}" 2>/dev/null || true)"
  rm -f "${tmpfile}" 2>/dev/null || true
  [[ -n "${B_REQ_CODE}" && "${B_REQ_CODE}" =~ ^[0-9]+$ ]]
}

# 401（或 token 相关 403）时换发 token 并重试一次。成功返回 0。
retry_on_unauthorized() {
  local method="$1" path="$2" data="${3:-}"
  if [[ "${B_REQ_CODE}" == "401" || "${B_REQ_CODE}" == "403" ]]; then
    if _fetch_token; then
      board_req "${method}" "${path}" "${data}" && [[ "${B_REQ_CODE}" != "401" && "${B_REQ_CODE}" != "403" ]]
      return $?
    fi
  fi
  return 1
}

rc=0
for cid in "${IDS[@]}"; do
  # 读任务详情（预算耗尽提示）——失败静默降级（非核心）
  board_req GET "/tasks/${cid}" || true
  if [[ "${B_REQ_CODE}" == "200" ]]; then
    if [[ "${B_REQ_BODY}" == *'"awaiting_human":true'* || "${B_REQ_BODY}" == *'"reject_budget_exhausted":true'* ]]; then
      exhausted_class="$(printf '%s' "${B_REQ_BODY}" | sed -n 's/.*"exhausted_class":"\([^"]*\)".*/\1/p' | head -1)"
      exhausted_class="${exhausted_class:-business}"
      echo "[WARN] ${cid}: 此卡预算耗尽（${exhausted_class}），确认后重派将清零计数" >&2
    fi
  elif [[ "${B_REQ_CODE}" == "401" || "${B_REQ_CODE}" == "403" ]]; then
    # 详情读 401：自动换 token 再读
    retry_on_unauthorized GET "/tasks/${cid}" >/dev/null || true
  fi

  # 发起 transition；401 → 自动换发 → 重试一次
  if ! board_req POST "/tasks/${cid}/transition" '{"status":"待分派"}'; then
    echo "[ERROR] ${cid}: 请求失败（HTTP ${B_REQ_CODE:-未知}）" >&2
    rc=1
    continue
  fi
  if [[ "${B_REQ_CODE}" == "401" || "${B_REQ_CODE}" == "403" ]]; then
    if retry_on_unauthorized POST "/tasks/${cid}/transition" '{"status":"待分派"}'; then
      echo "[OK] ${cid}: ${B_REQ_BODY}"
    else
      echo "[ERROR] ${cid}: transition 401 且换发后仍失败（${B_REQ_CODE}）" >&2
      rc=1
    fi
  elif [[ "${B_REQ_CODE}" == "200" ]]; then
    echo "[OK] ${cid}: ${B_REQ_BODY}"
  else
    echo "[ERROR] ${cid}: transition HTTP ${B_REQ_CODE}: ${B_REQ_BODY}" >&2
    rc=1
  fi
done

exit "$rc"