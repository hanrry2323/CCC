#!/bin/bash
# ── scripts/dsh-key.sh ──
# DSH 密钥单源解析（rebuild/phase2 · 修 429 双源问题）：
#   优先级：env OPENCODE_GO_API_KEY → 现役 com.deepseek.dsh-web.plist → 禁用 com.ccc.engine.plist
#   背景：旧 run_audit.sh 读 com.ccc.engine.plist（08-26 已禁用移入 disabled-ccc/），
#   密钥源失效 → 派发无 key。现役 key 在 dsh-web plist（含 OPENCODE_GO_API_KEY / LOOP_PROXY_KEY）。
# 用法：source scripts/dsh-key.sh   # 解析到则导出 OPENCODE_GO_API_KEY
resolve_dsh_key() {
  if [[ -n "${OPENCODE_GO_API_KEY:-}" ]]; then
    printf '%s' "$OPENCODE_GO_API_KEY"
    return 0
  fi
  for plist in \
    "$HOME/Library/LaunchAgents/com.deepseek.dsh-web.plist" \
    "$HOME/Library/LaunchAgents/disabled-ccc/com.ccc.engine.plist"; do
    [[ -f "$plist" ]] || continue
    v="$(/usr/libexec/PlistBuddy -c "Print :EnvironmentVariables:OPENCODE_GO_API_KEY" "$plist" 2>/dev/null || true)"
    if [[ -n "$v" ]]; then
      printf '%s' "$v"
      return 0
    fi
  done
  return 1
}

K="$(resolve_dsh_key || true)"
if [[ -n "$K" ]]; then
  export OPENCODE_GO_API_KEY="$K"
fi
