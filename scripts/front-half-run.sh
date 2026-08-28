#!/bin/bash
# ── scripts/front-half-run.sh ── 前半段自动化编排（rebuild/phase2）
#
# 链路：方案 → 出卡（plan-to-cards.sh 机械拆卡）→ [Engine 常驻自动派发 → DSH 自动开发 → 已回写]
#
# 用法：
#   scripts/front-half-run.sh --plan <方案文件> [--dispatch-dir <dir>] [--dry-run]
#                              [--wait-written] [--timeout N] [--json]
#
# 说明：
# - 出卡 = plan-to-cards.sh（机械，无需 LLM）；卡落 docs/dispatch/<prefix>/ 待分派。
# - 自动开发 = Engine 常驻时自动消费待分派卡（executors.json → dsh-executor.sh）。
# - --wait-written：轮询直到全部卡「已回写」或超时（供前后半段总验收编排；LLM 配额阻塞时超时退出）。
# - 产出：每张卡的路径 + 状态时间线。
set -uo pipefail
SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SELF/.." && pwd)"
PYTHON_BIN="${CCC_PYTHON_BIN:-$ROOT/.venv-hub/bin/python}"
DISPATCH_DIR="docs/dispatch"
PLAN_FILE=""
WAIT_WRITTEN=false
TIMEOUT=600
DRY_RUN=false
JSON=false

usage() { sed -n '2,14p' "$0" | sed 's/^# \{0,1\}//'; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --plan) PLAN_FILE="${2:?--plan 需要方案文件}"; shift 2 ;;
    --dispatch-dir) DISPATCH_DIR="$2"; shift 2 ;;
    --wait-written) WAIT_WRITTEN=true; shift ;;
    --timeout) TIMEOUT="$2"; shift 2 ;;
    --dry-run) DRY_RUN=true; shift ;;
    --json) JSON=true; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "[ERROR] 未知参数: $1" >&2; usage; exit 2 ;;
  esac
done

[[ -z "$PLAN_FILE" ]] && { echo "[ERROR] 缺 --plan" >&2; exit 2; }
[[ -f "$PLAN_FILE" ]] || { echo "[ERROR] 方案文件不存在: $PLAN_FILE" >&2; exit 2; }

echo "[front-half] $(date '+%H:%M:%S') 方案=$PLAN_FILE dispatch=$DISPATCH_DIR"

# 密钥单源 + 配额预检（DSH 侧将执行开发；429 提前告警不阻断出卡）
# shellcheck source=scripts/dsh-key.sh
source "$SELF/dsh-key.sh" 2>/dev/null || true
"$SELF/dsh-key-check.sh" --quiet || echo "[warn] DSH 网关配额耗尽（429）—— 出卡仍执行，自动开发将失败（见 ledger dsh_quota_alert）" >&2

if [[ "$DRY_RUN" == true ]]; then
  "$SELF/plan-to-cards.sh" --plan "$PLAN_FILE" --dispatch-dir "$DISPATCH_DIR" --dry-run || exit $?
  exit 0
fi

OUT="$("$SELF/plan-to-cards.sh" --plan "$PLAN_FILE" --dispatch-dir "$DISPATCH_DIR" 2>&1)"
RC=$?
echo "$OUT"
[[ $RC -ne 0 ]] && { echo "[ERROR] 出卡失败 rc=$RC" >&2; exit $RC; }

# 收集出卡路径（[OK] card: <path>）
CARDS=($(echo "$OUT" | sed -n 's/^\[OK\] card: //p' | sort -u))
echo "[front-half] 出卡 ${#CARDS[@]} 张：${CARDS[*]:-无}"

if [[ "$WAIT_WRITTEN" == true ]]; then
  echo "[front-half] 等待全部卡「已回写」（超时 ${TIMEOUT}s）..."
  DEADLINE=$(( $(date +%s) + TIMEOUT ))
  while (( $(date +%s) < DEADLINE )); do
    # 卡状态读取（分支信封 + 工作区双源）
    STATES="$("$PYTHON_BIN" -c "
import json, sys
sys.path.insert(0, '$ROOT')
from server.board.card_header import CardHeader
from server.board.models import base_state
import subprocess
want = {p.split('/')[-1].split('.')[0] for p in sys.argv[1:]}
states = {}
for p in sys.argv[1:]:
    try:
        t = open(p, encoding='utf-8').read()
        h = CardHeader.from_text(t, fallback_id=p.split('/')[-1].split('.')[0])
        states[p] = h.state
    except Exception as e:
        states[p] = 'ERR'
print(json.dumps(states, ensure_ascii=False))
" "${CARDS[@]}" 2>/dev/null)"
    DONE=0
    for c in "${CARDS[@]}"; do
      ST="$(echo "$STATES" | "$PYTHON_BIN" -c "import json,sys; print(json.load(sys.stdin).get('$c',''))" 2>/dev/null)"
      if [[ "$ST" == *"已回写"* ]]; then DONE=$((DONE+1)); fi
    done
    echo "[front-half] $(date '+%H:%M:%S') 已回写 $DONE/${#CARDS[@]}"
    [[ $DONE -eq ${#CARDS[@]} ]] && break
    sleep 10
  done
  [[ $DONE -eq ${#CARDS[@]} ]] || { echo "[ERROR] 超时未全部已回写（LLM 配额或引擎未在跑？）" >&2; exit 3; }
fi

if [[ "$JSON" == true ]]; then
  printf '{"cards": [%s]}\n' "$(printf '%s\n' "${CARDS[@]}" | sed 's/.*/"&"/' | paste -sd, -)"
fi
echo "[front-half] 完成"
