#!/bin/bash
# ── scripts/dsh-key-check.sh ──
# DSH 网关配额预检（rebuild/phase2 · 修 429 双源无监控）：
#   用密钥探测 opencode.ai/zen/go 最小 messages 请求；
#   429=周配额耗尽 → ledger 告警（dsh_quota_alert）+ exit 2（阻断派发，防无声 429 循环）。
# 用法：scripts/dsh-key-check.sh [--quiet]
set -uo pipefail
SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/dsh-key.sh
source "$SELF/dsh-key.sh"
QUIET=false
[[ "${1:-}" == "--quiet" ]] && QUIET=true

if [[ -z "${OPENCODE_GO_API_KEY:-}" ]]; then
  [[ $QUIET == false ]] && echo "[warn] dsh-key-check: 无 OPENCODE_GO_API_KEY，跳过预检" >&2
  exit 0
fi

# 探针：最小 messages 请求（Anthropic 兼容网关：x-api-key + anthropic-version，非 Bearer）
code="$(curl -s -o /dev/null -w '%{http_code}' -m 20 \
  -H "x-api-key: $OPENCODE_GO_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "Content-Type: application/json" \
  -d '{"model":"deepseek-v4-flash","max_tokens":1,"messages":[{"role":"user","content":"ping"}]}' \
  https://opencode.ai/zen/go/v1/messages 2>/dev/null || echo 000)"

if [[ "$code" == "429" ]]; then
  ROOT="$(cd "$SELF/.." && pwd)"
  (cd "$ROOT" && .venv-hub/bin/python -c "
import os, sys
sys.path.insert(0, '.')
from server.board.audit_ledger import record_action
record_action('dsh_quota_alert', 'gateway', source='dsh-key-check',
              detail='opencode.ai 429 周配额耗尽（DSH 派发/审核将失败，需等配额重置或充值）')
" >/dev/null 2>&1 || true)
  [[ $QUIET == false ]] && echo "[ERROR] dsh-key-check: 429 周配额耗尽（已 ledger 告警 dsh_quota_alert）" >&2
  exit 2
fi
[[ $QUIET == false ]] && echo "[ok] dsh-key-check: gateway http=$code" >&2
exit 0
