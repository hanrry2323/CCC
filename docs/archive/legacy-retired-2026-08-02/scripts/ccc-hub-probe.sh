#!/usr/bin/env bash
# ccc-hub-probe.sh — Hub / sidecar 探活契约（P-E）
#
# 权威口径（禁止用错 path 判死）：
#   - Hub **无** GET /api/health（404 = 预期，不是挂了）
#   - Hub 可达性 = GET /api/desktop/projects（或 /api/desktop/version）+ Bearer 会话 token（换发失败回退 Basic）
#   - 无 auth → 401 = 预期（Hub 开鉴权；sidecar /health 默认无 auth —— 设计差异）
#   - 对话口 = M1 GET :7788/health（与 Hub 分离）
#
# 用法：
#   bash scripts/ccc-hub-probe.sh
#   CCC_SERVER=http://127.0.0.1:17777 bash scripts/ccc-hub-probe.sh   # M1 隧道
#   CCC_SERVER=http://192.168.3.116:7777 …                            # LAN 排障
#
# 退出：0 全绿；1 契约失败（错判或真挂）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

SERVER="${CCC_SERVER:-http://127.0.0.1:17777}"
USER="${CCC_CHAT_USER:-ccc}"
PASS="${CCC_CHAT_PASS:-ccc}"
AGENT="${CCC_AGENT:-http://127.0.0.1:7788}"
# 统一走 Bearer 会话 token（窗口 G）；换发失败回退 Basic（开关 off 不断链）
HUB_TOKEN="$(bash "${ROOT}/scripts/ccc-hub-token.sh" "$SERVER" "$USER" "$PASS" 2>/dev/null || true)"
if [[ -n "$HUB_TOKEN" ]]; then
  AUTH=(-H "Authorization: Bearer $HUB_TOKEN")
else
  AUTH=(-u "${USER}:${PASS}")
fi

fail=0
note() { echo "[probe] $*"; }
bad() { echo "[probe] FAIL: $*" >&2; fail=1; }
ok() { echo "[probe] ok: $*"; }

# 1) Hub /api/health 必须 404（契约：勿当可达性探针）
code=$(curl -sS -m 5 -o /tmp/ccc-hub-health.body -w '%{http_code}' \
  "${AUTH[@]}" "${SERVER}/api/health" 2>/dev/null || echo 000)
if [[ "$code" == "404" ]]; then
  ok "Hub /api/health → 404 (expected; not a liveness probe)"
else
  bad "Hub /api/health expected 404, got ${code} (do not invent /api/health as product API)"
fi

# 2) 无 auth → projects 401（契约）
code=$(curl -sS -m 5 -o /tmp/ccc-hub-projects-na.body -w '%{http_code}' \
  "${SERVER}/api/desktop/projects" 2>/dev/null || echo 000)
if [[ "$code" == "401" ]]; then
  ok "Hub /api/desktop/projects no-auth → 401 (expected)"
else
  # 若本机关了 auth，放宽为 200 并注明
  if [[ "$code" == "200" ]]; then
    note "WARN: projects no-auth returned 200 (AUTH may be disabled); still prefer Bearer for probes"
  else
    bad "Hub projects no-auth expected 401 (or 200 if auth off), got ${code}"
  fi
fi

# 3) 带 auth → projects 200
code=$(curl -sS -m 8 -o /tmp/ccc-hub-projects.body -w '%{http_code}' \
  "${AUTH[@]}" "${SERVER}/api/desktop/projects" 2>/dev/null || echo 000)
if [[ "$code" == "200" ]]; then
  ok "Hub /api/desktop/projects + auth → 200"
else
  bad "Hub /api/desktop/projects + auth expected 200, got ${code} — tunnel/Hub down?"
fi

# 4) version（可选同契约）
code=$(curl -sS -m 5 -o /tmp/ccc-hub-ver.body -w '%{http_code}' \
  "${AUTH[@]}" "${SERVER}/api/desktop/version" 2>/dev/null || echo 000)
if [[ "$code" == "200" ]]; then
  ok "Hub /api/desktop/version + auth → 200"
else
  bad "Hub /api/desktop/version + auth expected 200, got ${code}"
fi

# 5) sidecar /health（默认无 auth）
if curl -sf --connect-timeout 5 -m 5 "${AGENT}/health" -o /tmp/ccc-sidecar-health.json; then
  ok "sidecar ${AGENT}/health → ok (default no Agent Token)"
else
  bad "sidecar ${AGENT}/health unreachable"
fi

if [[ "$fail" -ne 0 ]]; then
  echo "[probe] OVERALL fail" >&2
  exit 1
fi
echo "[probe] OVERALL pass — use desktop/projects(+auth) or desktop/version(+auth); never /api/health for Hub liveness"
exit 0
