#!/usr/bin/env bash
# ccc-dual-host-check.sh — 核对 M1 与 Mac2017 版本对齐 + 端点探活
#
# 用法：
#   bash scripts/ccc-dual-host-check.sh
#   CCC_SERVER=http://127.0.0.1:17777 bash scripts/ccc-dual-host-check.sh   # M1 隧道（默认）
#   CCC_SERVER=http://192.168.3.116:7777 …                                 # LAN 排障
#
#   --sync-only   只做版本/git 对齐（2017 start 门禁用；不依赖 Hub HTTP）
#   --m1 / --2017 强制主机视角
#
# 测试注入（跳过 HTTP）：
#   CCC_DUAL_HOST_MOCK_JSON='{"version":"v0.62.0","commit":"abc","hub_api_version":"v1"}' \
#     bash scripts/ccc-dual-host-check.sh
#
# 输出：
#   local: <ver> <commit>
#   hub|origin: …
#   aligned: yes|no
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

SYNC_ONLY=0
ENDPOINT_HOST=""
for arg in "$@"; do
  case "$arg" in
    --sync-only) SYNC_ONLY=1 ;;
    --m1)        ENDPOINT_HOST="m1" ;;
    --2017)      ENDPOINT_HOST="2017" ;;
  esac
done
if [[ -z "$ENDPOINT_HOST" ]]; then
  if [[ "$(hostname)" == "Mac2017"* || "$(hostname)" == "fan"* ]]; then
    ENDPOINT_HOST="2017"
  else
    ENDPOINT_HOST="m1"
  fi
fi

# M1 默认走 SSH 隧道；2017 本机 Hub；LAN 仅排障覆盖
if [[ -n "${CCC_SERVER:-}" ]]; then
  SERVER="$CCC_SERVER"
elif [[ "$ENDPOINT_HOST" == "2017" ]]; then
  SERVER="http://127.0.0.1:7777"
else
  SERVER="http://127.0.0.1:17777"
fi
USER="${CCC_CHAT_USER:-ccc}"
PASS="${CCC_CHAT_PASS:-ccc}"
SUPPORTED_HUB_API='["v1"]'

_endpoints() {
  local host_tag="$1"
  if [[ "$host_tag" == "m1" ]]; then
    # M1：本机对话栈 + 隧道 Hub（Board 不直暴露，经 Hub 反代）
    cat <<EOF
hub|${SERVER}/api/desktop/version
sidecar|http://127.0.0.1:7788/health
relay|http://127.0.0.1:4000/admin/status
EOF
  else
    cat <<EOF
hub|http://127.0.0.1:7777/api/desktop/version
relay|http://127.0.0.1:4000/admin/status
board|http://127.0.0.1:7775/health
EOF
  fi
}

_check_endpoint() {
  local label=$1 url=$2
  local code
  if [[ -n "${CCC_DUAL_HOST_MOCK_JSON:-}" ]]; then
    code=200
  else
    code=$(curl -sS -m 3 -o /dev/null -w '%{http_code}' -u "${USER}:${PASS}" "$url" 2>/dev/null || echo 000)
  fi
  if [[ "$code" =~ ^2 ]]; then
    printf "  endpoint: %-10s up   %s\n" "$label" "$url"
  else
    printf "  endpoint: %-10s down %s (http=%s)\n" "$label" "$url" "$code"
  fi
}

LOCAL_VERSION="$(tr -d '[:space:]' < VERSION 2>/dev/null || true)"
LOCAL_COMMIT="$(git rev-parse HEAD 2>/dev/null || true)"
LOCAL_SHORT="${LOCAL_COMMIT:0:7}"

echo "local: ${LOCAL_VERSION:-?} ${LOCAL_SHORT:-?} (host=${ENDPOINT_HOST})"

# ── --sync-only：2017 start 门禁 — 对齐 origin/main，不依赖 Hub HTTP ──
if [[ "$SYNC_ONLY" -eq 1 ]]; then
  if [[ -n "${CCC_DUAL_HOST_MOCK_JSON:-}" ]]; then
    echo "origin: mock"
    echo "aligned: yes"
    exit 0
  fi
  git fetch -q origin 2>/dev/null || true
  ORIGIN_COMMIT="$(git rev-parse origin/main 2>/dev/null || true)"
  ORIGIN_SHORT="${ORIGIN_COMMIT:0:7}"
  echo "origin/main: ${ORIGIN_SHORT:-?}"
  if [[ -z "$LOCAL_COMMIT" || -z "$ORIGIN_COMMIT" ]]; then
    echo "aligned: no"
    echo "mismatch: missing local or origin/main commit"
    exit 1
  fi
  if [[ "${LOCAL_COMMIT:0:7}" != "${ORIGIN_COMMIT:0:7}" ]]; then
    echo "aligned: no"
    echo "mismatch: commit local=${LOCAL_SHORT} origin/main=${ORIGIN_SHORT}"
    echo "hint: git merge --ff-only origin/main"
    exit 1
  fi
  echo "aligned: yes"
  exit 0
fi

fetch_hub() {
  if [[ -n "${CCC_DUAL_HOST_MOCK_JSON:-}" ]]; then
    printf '%s\n' "${CCC_DUAL_HOST_MOCK_JSON}"
    return 0
  fi
  local out err code http
  out="$(mktemp)"
  err="$(mktemp)"
  set +e
  http="$(curl -sS --connect-timeout 5 --max-time 15 \
      -u "${USER}:${PASS}" \
      -o "${out}" -w '%{http_code}' \
      "${SERVER}/api/desktop/version" 2>"${err}")"
  code=$?
  set -e
  if [[ "${code}" -ne 0 || -z "${http}" || "${http}" == "000" ]]; then
    echo "ERROR: Hub unreachable at ${SERVER}/api/desktop/version (curl exit ${code}, http=${http:-?})" >&2
    if [[ -s "${err}" ]]; then
      cat "${err}" >&2 || true
    fi
    rm -f "${out}" "${err}"
    return 2
  fi
  if [[ "${http}" != "200" ]]; then
    echo "ERROR: Hub version endpoint HTTP ${http} at ${SERVER}/api/desktop/version" >&2
    if [[ -s "${out}" ]]; then
      head -c 400 "${out}" >&2 || true
      echo >&2
    fi
    rm -f "${out}" "${err}"
    return 2
  fi
  cat "${out}"
  rm -f "${out}" "${err}"
  return 0
}

HUB_JSON="$(fetch_hub)" || exit 2

while IFS='|' read -r label url; do
  [[ -z "$label" ]] && continue
  _check_endpoint "$label" "$url"
done < <(_endpoints "$ENDPOINT_HOST")

set +e
EVAL="$(
  LOCAL_VERSION="${LOCAL_VERSION}" LOCAL_COMMIT="${LOCAL_COMMIT}" \
  SUPPORTED_HUB_API="${SUPPORTED_HUB_API}" \
  HUB_JSON="${HUB_JSON}" \
  python3 - <<'PY'
import json, os, sys

local_ver = (os.environ.get("LOCAL_VERSION") or "").strip()
local_commit = (os.environ.get("LOCAL_COMMIT") or "").strip()
supported = json.loads(os.environ.get("SUPPORTED_HUB_API") or '["v1"]')
raw = os.environ.get("HUB_JSON") or ""
try:
    d = json.loads(raw)
except json.JSONDecodeError as e:
    print(f"ERROR: invalid Hub version JSON: {e}", file=sys.stderr)
    sys.exit(2)

h_ver = str(d.get("version") or "").strip()
h_commit = str(d.get("commit") or "").strip()
h_api = str(d.get("hub_api_version") or "").strip()
h_short = h_commit[:7] if h_commit else "?"
local_short = local_commit[:7] if local_commit else "?"

print(f"hub: {h_ver or '?'} {h_short} {h_api or '?'}")

mismatches = []
if not h_ver or not local_ver or h_ver != local_ver:
    mismatches.append(f"version local={local_ver or '?'} hub={h_ver or '?'}")
if not h_commit or not local_commit or h_commit[:7] != local_commit[:7]:
    mismatches.append(f"commit local={local_short} hub={h_short}")
if h_api not in supported:
    mismatches.append(
        f"hub_api_version={h_api or '?'} not in supported={supported}"
    )

if mismatches:
    print("aligned: no")
    for m in mismatches:
        print(f"mismatch: {m}")
    sys.exit(1)

print("aligned: yes")
sys.exit(0)
PY
)"
rc=$?
set -e
printf '%s\n' "${EVAL}"
exit "${rc}"
