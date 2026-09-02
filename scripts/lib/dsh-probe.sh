#!/bin/bash
# ── scripts/lib/dsh-probe.sh ──
# DSH 配额/通道探针统一配置源（P0-1）：URL/模型只在此定默认，禁止脚本各自硬编码。
#
# 优先级：环境变量 DSH_PROBE_URL / DSH_PROBE_MODEL
#        → CCC 配置 server/config/config.env（同名键）
#        → 默认 = 当前真实执行通道。
#
# 真实执行通道（2026-09-02 本机取证）：
#   DSH headless 默认走 ~/.dsh/settings.yaml provider `local-litellm`
#   baseURL=127.0.0.1:3456（经 m1-tunnel → M1 192.168.3.140 SCNet 中转），
#   apiKeyEnv=OPENCODE_GO_API_KEY，默认模型 claude-4-5-haiku；
#   DSH 基于 @anthropic-ai SDK，调用路径 /v1/messages（Anthropic 兼容）。
# 说明：若实际通道路径/模型不同，用 DSH_PROBE_URL / DSH_PROBE_MODEL 覆盖即可，
#   勿改本文件默认值（单一事实源）。
#
# 用法（source）：
#   source scripts/lib/dsh-probe.sh
#   dsh_probe_url    # 输出探针 URL
#   dsh_probe_model  # 输出探针模型
# 用法（脚本执行）：
#   scripts/lib/dsh-probe.sh print-url | print-model
set -uo pipefail

DSH_PROBE_URL_DEFAULT="http://127.0.0.1:3456/v1/messages"
DSH_PROBE_MODEL_DEFAULT="claude-4-5-haiku"

_dsh_probe_config_env_path() {
  local v="${CCC_CONFIG_ENV:-}" root
  if [[ -n "$v" && -f "$v" ]]; then
    printf '%s' "$v"
    return 0
  fi
  root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd 2>/dev/null || printf '')"
  if [[ -n "$root" && -f "$root/server/config/config.env" ]]; then
    printf '%s' "$root/server/config/config.env"
  fi
}

_dsh_probe_config_value() {
  local key="$1" cfg v=""
  cfg="$(_dsh_probe_config_env_path)"
  if [[ -n "$cfg" ]]; then
    v="$(grep -E "^[[:space:]]*${key}[[:space:]]*=" "$cfg" 2>/dev/null | tail -1 | cut -d= -f2- | tr -d '"' | tr -d "'" | xargs 2>/dev/null || true)"
  fi
  printf '%s' "$v"
}

dsh_probe_url() {
  local v="${DSH_PROBE_URL:-}"
  [[ -z "$v" ]] && v="$(_dsh_probe_config_value DSH_PROBE_URL)"
  printf '%s' "${v:-$DSH_PROBE_URL_DEFAULT}"
}

dsh_probe_model() {
  local v="${DSH_PROBE_MODEL:-}"
  [[ -z "$v" ]] && v="$(_dsh_probe_config_value DSH_PROBE_MODEL)"
  printf '%s' "${v:-$DSH_PROBE_MODEL_DEFAULT}"
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  case "${1:-}" in
    print-url) dsh_probe_url; echo ;;
    print-model) dsh_probe_model; echo ;;
    *)
      echo "usage: $0 print-url|print-model" >&2
      exit 2
      ;;
  esac
fi
