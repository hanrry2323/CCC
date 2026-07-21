#!/usr/bin/env bash
# ccc-ingest-ci-failure.sh — F4-3：CI/hook JSON → POST /api/desktop/proactive-epic
#
# 用法：
#   echo '{"title":"CI 失败","goal":"修 pytest","payload":{"run_id":"1"}}' \
#     | CCC_PROJECT_ID=ccc-demo bash scripts/ccc-ingest-ci-failure.sh
#   bash scripts/ccc-ingest-ci-failure.sh /path/to/fail.json
#
# 环境：
#   CCC_SERVER       默认 http://127.0.0.1:7777
#   CCC_CHAT_USER    默认 ccc
#   CCC_CHAT_PASS    默认 ccc
#   CCC_PROJECT_ID   JSON 缺 project_id 时补全
#   CCC_PROACTIVE_DRY_RUN=1  只打印将 POST 的 JSON，不发 HTTP
#
# 退出：0 成功（含幂等 replay）；非 0 失败。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

SERVER="${CCC_SERVER:-http://127.0.0.1:7777}"
USER="${CCC_CHAT_USER:-ccc}"
PASS="${CCC_CHAT_PASS:-ccc}"
PROJECT_ID="${CCC_PROJECT_ID:-}"

INPUT_FILE="${1:-}"
if [[ -n "${INPUT_FILE}" ]]; then
  if [[ ! -f "${INPUT_FILE}" ]]; then
    echo "ERROR: file not found: ${INPUT_FILE}" >&2
    exit 2
  fi
  RAW="$(cat "${INPUT_FILE}")"
else
  RAW="$(cat)"
fi

if [[ -z "${RAW//[[:space:]]/}" ]]; then
  echo "ERROR: empty JSON input" >&2
  exit 2
fi

# 规范化：补 source/project_id；缺字段由 Hub 返回 400
BODY="$(
  RAW="${RAW}" PROJECT_ID="${PROJECT_ID}" python3 - <<'PY'
import json, os, sys
raw = os.environ.get("RAW") or ""
try:
    data = json.loads(raw)
except json.JSONDecodeError as e:
    print(f"ERROR: invalid JSON: {e}", file=sys.stderr)
    sys.exit(2)
if not isinstance(data, dict):
    print("ERROR: JSON object required", file=sys.stderr)
    sys.exit(2)
pid = (data.get("project_id") or data.get("project") or os.environ.get("PROJECT_ID") or "").strip()
if pid:
    data["project_id"] = pid
if not str(data.get("source") or "").strip():
    data["source"] = "ci"
# CLI 便捷：允许只有 message/log → goal
if not str(data.get("goal") or "").strip():
    for k in ("message", "error", "log", "summary"):
        v = data.get(k)
        if v:
            data["goal"] = str(v)[:2000]
            break
if not str(data.get("title") or "").strip():
    data["title"] = "CI 失败"
# 若顶层没有 payload，把未知键塞进 payload（保留 project/source/title/goal/acceptance）
known = {
    "project_id", "project", "source", "title", "goal", "acceptance",
    "payload", "pipeline", "plan_md", "thread_id", "client_request_id",
    "complexity", "epic_id",
}
if "payload" not in data:
    extra = {k: v for k, v in data.items() if k not in known}
    if extra:
        data["payload"] = extra
print(json.dumps(data, ensure_ascii=False))
PY
)"

if [[ "${CCC_PROACTIVE_DRY_RUN:-}" == "1" ]]; then
  printf '%s\n' "${BODY}"
  exit 0
fi

OUT="$(mktemp)"
ERR="$(mktemp)"
trap 'rm -f "${OUT}" "${ERR}"' EXIT

set +e
HTTP="$(curl -sS --connect-timeout 5 --max-time 30 \
  -u "${USER}:${PASS}" \
  -H 'Content-Type: application/json' \
  -d "${BODY}" \
  -o "${OUT}" -w '%{http_code}' \
  "${SERVER}/api/desktop/proactive-epic" 2>"${ERR}")"
RC=$?
set -e

if [[ "${RC}" -ne 0 || -z "${HTTP}" || "${HTTP}" == "000" ]]; then
  echo "ERROR: Hub unreachable at ${SERVER}/api/desktop/proactive-epic (curl exit ${RC})" >&2
  [[ -s "${ERR}" ]] && cat "${ERR}" >&2 || true
  exit 2
fi

if [[ "${HTTP}" != "200" ]]; then
  echo "ERROR: HTTP ${HTTP}" >&2
  head -c 800 "${OUT}" >&2 || true
  echo >&2
  exit 1
fi

cat "${OUT}"
echo
