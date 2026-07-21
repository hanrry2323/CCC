#!/usr/bin/env bash
# ccc-dual-host-check.sh — F2-2 一键核对 M1 与 Mac2017 Hub 版本对齐
#
# 用法：
#   bash scripts/ccc-dual-host-check.sh
#   CCC_SERVER=http://192.168.3.116:7777 bash scripts/ccc-dual-host-check.sh
#
# 测试注入（跳过 HTTP）：
#   CCC_DUAL_HOST_MOCK_JSON='{"version":"v0.52.2","commit":"abc","hub_api_version":"v1"}' \
#     bash scripts/ccc-dual-host-check.sh
#
# 输出三行：
#   M1: <ver> <commit>
#   2017: <ver> <commit> <hub_api>
#   aligned: yes|no
# 不一致时追加 mismatch: … 行；非零退出。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

SERVER="${CCC_SERVER:-http://192.168.3.116:7777}"
USER="${CCC_CHAT_USER:-ccc}"
PASS="${CCC_CHAT_PASS:-ccc}"
# 客户端支持的 hub_api_version 集（硬编码；未来 v2 再扩）
SUPPORTED_HUB_API='["v1"]'

M1_VERSION="$(tr -d '[:space:]' < VERSION 2>/dev/null || true)"
M1_COMMIT="$(git rev-parse HEAD 2>/dev/null || true)"
M1_SHORT="${M1_COMMIT:0:7}"

echo "M1: ${M1_VERSION:-?} ${M1_SHORT:-?}"

fetch_2017() {
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

HUB_JSON="$(fetch_2017)" || exit 2

set +e
EVAL="$(
  M1_VERSION="${M1_VERSION}" M1_COMMIT="${M1_COMMIT}" \
  SUPPORTED_HUB_API="${SUPPORTED_HUB_API}" \
  HUB_JSON="${HUB_JSON}" \
  python3 - <<'PY'
import json, os, sys

m1_ver = (os.environ.get("M1_VERSION") or "").strip()
m1_commit = (os.environ.get("M1_COMMIT") or "").strip()
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
m1_short = m1_commit[:7] if m1_commit else "?"

print(f"2017: {h_ver or '?'} {h_short} {h_api or '?'}")

mismatches = []
if not h_ver or not m1_ver or h_ver != m1_ver:
    mismatches.append(f"version M1={m1_ver or '?'} 2017={h_ver or '?'}")
# commit：短 sha 对齐（允许一侧给 full）
if not h_commit or not m1_commit or h_commit[:7] != m1_commit[:7]:
    mismatches.append(f"commit M1={m1_short} 2017={h_short}")
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
