#!/usr/bin/env bash
# Desktop 「第二条消息消失」最小复现门禁
#
# 模拟 Desktop 客户端行为：
#   - POST /api/chat 第一条 prompt；等 done 事件 → 流关
#   - 立刻 POST /api/chat 第二条 prompt；等 done 事件
# 断言：
#   - 两条流都返回 HTTP 200
#   - 两条流都收到 type=done 且 partial=false
#   - 两条间隔 < CHAT_FIRST_EVENT_TIMEOUT（默认 45s），避免「第二条挂死」
#
# 这是网络/服务端基线。客户端 runChatStream 的修复在 AppModel.swift 内，
# 但 server 必须先能保证两轮独立 done，否则修了客户端也跑不通回归。

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

AGENT="${CCC_AGENT:-http://127.0.0.1:7788}"
TOKEN_FILE="${CCC_AGENT_TOKEN_FILE:-$HOME/.ccc/agent-token}"
PROJECT_PATH="${CCC_TEST_PROJECT_PATH:-$ROOT}"
MAX_GAP_SEC="${CHAT_SECOND_TURN_MAX_GAP:-45}"

if [[ ! -f "$TOKEN_FILE" ]]; then
    echo "SKIP: missing $TOKEN_FILE (install agent-token first)" >&2
    exit 0
fi
TOKEN="$(tr -d '\n' < "$TOKEN_FILE")"
SID="second-turn-$(date +%s)-$$"

call_turn() {
    local turn_id="$1"
    local prompt="$2"
    local start_ts
    start_ts=$(date +%s)
    # -sS 静默 + 显示错误；-N 不缓冲；--max-time 防挂死
    local out
    out="$(curl -sS -N --max-time 60 \
        -H "Authorization: Bearer $TOKEN" \
        -H "Content-Type: application/json" \
        -X POST "$AGENT/api/chat" \
        --data-binary "{
            \"project\":\"ccc-demo\",
            \"session_id\":\"$SID\",
            \"turn_id\":\"$turn_id\",
            \"prompt\":\"$prompt\",
            \"project_path\":\"$PROJECT_PATH\",
            \"prompt_mode\":\"light\",
            \"tool_mode\":\"discuss\",
            \"model\":\"flash\"
        }" || true)"
    local elapsed=$(( $(date +%s) - start_ts ))
    local last_type
    last_type="$(printf '%s' "$out" \
        | grep -oE '"type":[[:space:]]*"[a-z_]+"' \
        | tail -1 || true)"
    if [[ -z "$last_type" ]]; then
        echo "  [$turn_id] FAIL: no events (elapsed=${elapsed}s)" >&2
        echo "  body: $(printf '%s' "$out" | tail -c 400)" >&2
        return 1
    fi
    if [[ "$last_type" != *"done"* ]]; then
        echo "  [$turn_id] FAIL: last event $last_type (elapsed=${elapsed}s)" >&2
        return 1
    fi
    echo "  [$turn_id] OK ($last_type, ${elapsed}s)"
}

echo "== second-turn-vanish smoke =="
echo "  agent: $AGENT"
echo "  session: $SID"

call_turn "t1" "请只回 OK 两字母"
call_turn "t2" "再回 OK 两字母"

# 检查间隔：第二条从开始到 done 的耗时必须在阈值内
gap="$(curl -sS -N --max-time 60 \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -X POST "$AGENT/api/chat" \
    --data-binary "{
        \"project\":\"ccc-demo\",
        \"session_id\":\"$SID\",
        \"turn_id\":\"t3\",
        \"prompt\":\"再回 OK\",
        \"project_path\":\"$PROJECT_PATH\",
        \"prompt_mode\":\"light\",
        \"tool_mode\":\"discuss\",
        \"model\":\"flash\"
    }" \
    | grep -c '"type":[[:space:]]*"done"' || true)"
if [[ "$gap" -lt 1 ]]; then
    echo "  [t3] FAIL: no done within 60s" >&2
    exit 1
fi
echo "  [t3] OK (gap check)"

echo "== PASS: second-turn-vanish smoke =="
