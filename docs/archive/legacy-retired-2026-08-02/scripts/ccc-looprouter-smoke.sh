#!/usr/bin/env bash
# ccc-looprouter-smoke.sh — M1 ai-loop-router 代理链路冒烟（chat / 流式 / 工具调用）
# 2026-08-01 迁移回归：CCC 模型出口统一走 M1 ai-loop-router（:4100 Anthropic 协议 / :4102 openai-chat）。
# 本脚本打 :4100 /v1/messages 三连探：
#   1) chat 非流式  → 200 + text block
#   2) 流式(SSE)   → 200 + content_block_delta
#   3) 工具调用    → 200 + tool_use(get_weather)
# 用法：
#   bash scripts/ccc-looprouter-smoke.sh               # 本机 :4100
#   CCC_RELAY_URL=http://192.168.3.140:4100 bash scripts/ccc-looprouter-smoke.sh   # 跨机验证
set -euo pipefail

RELAY_URL="${CCC_RELAY_URL:-http://127.0.0.1:4100}"
TIMEOUT_S="${CCC_RELAY_SMOKE_TIMEOUT:-30}"
FAIL=0
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# post $1=json body → 输出 "<http_code>|<body>"
post() {
  local code
  code="$(curl -sS -m "$TIMEOUT_S" -N -o "$TMP/body" -w '%{http_code}' \
    "$RELAY_URL/v1/messages" -H 'content-type: application/json' -d "$1" 2>/dev/null)" \
    && printf '%s|' "$code" && cat "$TMP/body" || echo '000|'
}

echo "== ccc-looprouter-smoke =="
echo "RELAY_URL=$RELAY_URL"

# 1) chat 非流式（上游可能先吐 redacted_thinking 占满小 max_tokens，判 200+message 包装）
out="$(post '{"model":"flash","max_tokens":16,"messages":[{"role":"user","content":"Reply with the single word: ok"}]}')"
code="${out%%|*}"; body="${out#*|}"
if [[ "$code" == "200" && "$body" == *'"type":"message"'* ]]; then
  echo "OK  chat (non-stream) → 200 + message"
else
  echo "FAIL chat code=$code body=$(printf '%s' "$body" | head -c 200)"
  FAIL=1
fi

# 2) 流式(SSE)
out="$(post '{"model":"flash","max_tokens":8,"stream":true,"messages":[{"role":"user","content":"Reply with the single word: ok"}]}')"
code="${out%%|*}"; body="${out#*|}"
if [[ "$code" == "200" && "$body" == *'content_block_delta'* ]]; then
  echo "OK  stream (SSE) → 200 + content_block_delta"
else
  echo "FAIL stream code=$code body=$(printf '%s' "$body" | head -c 200)"
  FAIL=1
fi

# 3) 工具调用
out="$(post '{"model":"flash","max_tokens":64,"tools":[{"name":"get_weather","description":"Get weather for a city","input_schema":{"type":"object","properties":{"city":{"type":"string"}},"required":["city"]}}],"messages":[{"role":"user","content":"What is the weather in Tokyo? Use the get_weather tool."}]}')"
code="${out%%|*}"; body="${out#*|}"
if [[ "$code" == "200" && "$body" == *'"type":"tool_use"'* && "$body" == *'get_weather'* ]]; then
  echo "OK  tool_use → 200 + tool_use(get_weather)"
else
  echo "FAIL tool code=$code body=$(printf '%s' "$body" | head -c 200)"
  FAIL=1
fi

if [[ "$FAIL" -ne 0 ]]; then
  echo "RESULT: FAIL"
  exit 1
fi
echo "RESULT: PASS"
exit 0
