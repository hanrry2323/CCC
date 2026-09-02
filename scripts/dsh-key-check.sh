#!/bin/bash
# ── scripts/dsh-key-check.sh ──
# DSH 配额/通道预检（P0-1：三态收紧 + 对齐真实执行通道）。
#   探测目标默认 = 真实执行通道（local-litellm 127.0.0.1:3456，见 scripts/lib/dsh-probe.sh）；
#   HTTP/连接结果统一映射为显式状态，任何异常不得伪装成 PASS。
#
# 退出码协议（调用方必须按此判定，禁止把非 0 当 PASS）：
#   0 = PASS              2xx 且响应满足协议（非空 + 含模型响应标记）
#   2 = QUOTA_EXHAUSTED   429（写 ledger dsh_quota_alert）
#   3 = AUTH_ERROR        401/403
#   4 = UPSTREAM_ERROR    5xx
#   5 = PROBE_UNAVAILABLE 000/超时/DNS/TLS/连接失败/空响应/解析失败/未分类 HTTP
#   6 = NO_KEY            无 OPENCODE_GO_API_KEY（调用方决定是否阻断）
#   7 = ERROR             其他未分类错误
# 用法：scripts/dsh-key-check.sh [--quiet]
set -uo pipefail
SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/dsh-key.sh
source "$SELF/dsh-key.sh"
# shellcheck source=scripts/lib/dsh-probe.sh
source "$SELF/lib/dsh-probe.sh"

QUIET=false
[[ "${1:-}" == "--quiet" ]] && QUIET=true
say() { [[ $QUIET == false ]] && echo "$@" >&2; }

# NO_KEY：返回显式状态由调用方决定是否阻断，不再用 exit 0 伪装跳过
if [[ -z "${OPENCODE_GO_API_KEY:-}" ]]; then
  say "[error] dsh-key-check: 无 OPENCODE_GO_API_KEY（NO_KEY）—— 预检不通过"
  exit 6
fi

URL="$(dsh_probe_url)"
MODEL="$(dsh_probe_model)"
TIMEOUT="${DSH_PROBE_TIMEOUT:-20}"
TMP="$(mktemp -t dsh-key-check.XXXXXX 2>/dev/null)" || { say "[error] dsh-key-check: 无法创建临时文件（ERROR）"; exit 7; }
trap 'rm -f "$TMP"' EXIT

# 最小请求（Anthropic 兼容：x-api-key + anthropic-version，与真实执行通道 local-litellm 对齐）
code="$(curl -sS -o "$TMP" -w '%{http_code}' -m "$TIMEOUT" \
  -H "x-api-key: $OPENCODE_GO_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "Content-Type: application/json" \
  -d "{\"model\":\"$MODEL\",\"max_tokens\":1,\"messages\":[{\"role\":\"user\",\"content\":\"ping\"}]}" \
  "$URL" 2>/dev/null)"
curl_rc=$?

# 000 / curl 失败（超时28 / DNS6 / 连接7 / TLS35,60 等）一律 PROBE_UNAVAILABLE，绝不 PASS
if [[ "$code" == "000" || $curl_rc -ne 0 ]]; then
  say "[error] dsh-key-check: 探针不可达（PROBE_UNAVAILABLE http=$code curl_rc=$curl_rc url=${URL}）"
  exit 5
fi

case "$code" in
  429)
    ROOT="$(cd "$SELF/.." && pwd)"
    (cd "$ROOT" && .venv-hub/bin/python -c "
import sys
sys.path.insert(0, '.')
from server.board.audit_ledger import record_action
record_action('dsh_quota_alert', 'gateway', source='dsh-key-check',
              detail='DSH 网关 429 配额耗尽（派发/审核将失败，需等配额重置或充值）')
" >/dev/null 2>&1 || true)
    say "[error] dsh-key-check: 429 配额耗尽（QUOTA_EXHAUSTED，已 ledger 告警 dsh_quota_alert）"
    exit 2
    ;;
  401|403)
    say "[error] dsh-key-check: 认证失败（AUTH_ERROR http=${code}）"
    exit 3
    ;;
  2??)
    # 2xx：非空响应 + 含模型响应标记才 PASS；空/无法解析一律 PROBE_UNAVAILABLE
    if [[ ! -s "$TMP" ]]; then
      say "[error] dsh-key-check: 空响应（PROBE_UNAVAILABLE http=${code}）"
      exit 5
    fi
    if ! grep -qE '"content"|"model"|"choices"' "$TMP" 2>/dev/null; then
      say "[error] dsh-key-check: 响应无法解析/无模型响应标记（PROBE_UNAVAILABLE http=${code}）"
      exit 5
    fi
    say "[ok] dsh-key-check: PASS（http=${code}）"
    exit 0
    ;;
  5??)
    say "[error] dsh-key-check: 上游错误（UPSTREAM_ERROR http=${code}）"
    exit 4
    ;;
  *)
    say "[error] dsh-key-check: 未分类 HTTP 状态（ERROR http=${code}）"
    exit 7
    ;;
esac
