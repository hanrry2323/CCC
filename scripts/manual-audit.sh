#!/usr/bin/env bash
# ── CCC：手动机审节点（老板手动转发卡片 → 机审）──
#
# 流程开发阶段：开发/机审均为手动环节。本脚本让老板把一张已回写的卡
# 手动转发去机审（复用引擎 `_run_machine_audit_after_writeback`，与 `--audit` 同链路）。
#
# 用法：
#   scripts/manual-audit.sh <card-id> [<card-id>...] [--severity 轻|中|重] [--force]
#
# 选项：
#   --severity 轻|中|重   覆盖机审 v4 severity 判定（重度 → fresh agent 零上下文）
#   --force               已有机审通过证据时强制重审
#
# 参照：scripts/redispatch-card.sh（web API 薄客户端）。

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BOARD_URL="${CCC_BOARD_URL:-http://192.168.3.116:7788}"

IDS=()
SEVERITY=""
FORCE=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help) sed -n '2,14p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    --severity) SEVERITY="$2"; shift 2 ;;
    --force) FORCE=true; shift ;;
    *) IDS+=("$1"); shift ;;
  esac
done

if [[ ${#IDS[@]} -eq 0 ]]; then
  echo "[ERROR] 缺少卡 ID（用法：scripts/manual-audit.sh <card-id> [--severity 轻|中|重] [--force]）" >&2
  exit 2
fi
if [[ -n "$SEVERITY" ]] && [[ "$SEVERITY" != "轻" && "$SEVERITY" != "中" && "$SEVERITY" != "重" ]]; then
  echo "[ERROR] --severity 须为 轻/中/重（当前: $SEVERITY）" >&2
  exit 2
fi

rc=0
for cid in "${IDS[@]}"; do
  body="{}"
  if [[ -n "$SEVERITY" ]]; then
    body=$(printf '{"severity":"%s"}' "$SEVERITY")
  fi
  if [[ "$FORCE" == true ]]; then
    if [[ "$body" == "{}" ]]; then
      body='{"force":true}'
    else
      body=$(printf '{"severity":"%s","force":true}' "$SEVERITY")
    fi
  fi
  if out="$(curl -sf --max-time 3600 -X POST "${BOARD_URL}/tasks/${cid}/audit" \
      -H 'Content-Type: application/json' -d "$body" 2>&1)"; then
    echo "[OK] ${cid}: ${out}"
  else
    echo "[ERROR] ${cid}: ${out}" >&2
    rc=1
  fi
done
exit "$rc"
