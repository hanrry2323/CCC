#!/usr/bin/env bash
# ── M3：滞留机审清账 — audit.log 已通过但卡无机审区 → 补落盘 ──
#
# 用法：
#   scripts/backfill-stale-audit.sh <card-id> [<card-id>...]
#   scripts/backfill-stale-audit.sh --from-board   # 拉 2017 机审列
#
# 环境：
#   CCC_BOARD_URL     默认 http://192.168.3.116:7788
#   CCC_EXEC_LOG_DIR  本地 audit 目录；空则 scp 自 2017 ~/.ccc/logs/exec
#   CCC_SSH           默认 fan@192.168.3.116

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHON_BIN="${CCC_PYTHON_BIN:-python3}"
BOARD_URL="${CCC_BOARD_URL:-http://192.168.3.116:7788}"
SSH_HOST="${CCC_SSH:-fan@192.168.3.116}"
LOG_DIR="${CCC_EXEC_LOG_DIR:-}"
FROM_BOARD=false
IDS=()

usage() { sed -n '2,14p' "$0" | sed 's/^# \{0,1\}//'; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --from-board) FROM_BOARD=true; shift ;;
    -h|--help) usage; exit 0 ;;
    *) IDS+=("$1"); shift ;;
  esac
done

cd "$PROJECT_ROOT"

if [[ "$FROM_BOARD" == true ]]; then
  IDS=()
  while IFS= read -r line; do
    [[ -n "$line" ]] && IDS+=("$line")
  done < <(
    curl -sf --max-time 10 "${BOARD_URL}/board/snapshot" \
      | "$PYTHON_BIN" -c "
import json,sys
d=json.load(sys.stdin)
for c in (d.get('columns') or {}).get('机审') or []:
    print(c['id'] if isinstance(c,dict) else c)
"
  )
fi

if [[ ${#IDS[@]} -eq 0 ]]; then
  echo "[ERROR] 需要 <card-id> 或 --from-board" >&2
  exit 2
fi

TMPDIR_BF="$(mktemp -d)"
trap 'rm -rf "$TMPDIR_BF"' EXIT

resolve_card() {
  local id="$1"
  find docs/dispatch -type f -name "${id}-*.md" 2>/dev/null | head -1
}

fetch_audit_log() {
  local id="$1"
  local dest="$TMPDIR_BF/${id}.audit.log"
  if [[ -n "$LOG_DIR" && -f "${LOG_DIR}/${id}.audit.log" ]]; then
    cp "${LOG_DIR}/${id}.audit.log" "$dest"
    echo "$dest"
    return 0
  fi
  if scp -q "${SSH_HOST}:.ccc/logs/exec/${id}.audit.log" "$dest" 2>/dev/null; then
    echo "$dest"
    return 0
  fi
  return 1
}

CHANGED=()
SKIPPED=0
for id in "${IDS[@]}"; do
  card="$(resolve_card "$id" || true)"
  if [[ -z "${card:-}" ]]; then
    echo "[SKIP] $id: 本地无卡文件"
    SKIPPED=$((SKIPPED + 1))
    continue
  fi
  if ! audit="$(fetch_audit_log "$id")"; then
    echo "[SKIP] $id: 无 audit.log（非「假滞留」）"
    SKIPPED=$((SKIPPED + 1))
    continue
  fi
  set +e
  out="$("$PYTHON_BIN" -c "
import sys
from pathlib import Path
sys.path.insert(0, '.')
from server.engine.main import (
    _append_machine_audit_pass,
    _audit_output_indicates_pass,
    _card_machine_audit_passed,
)
card = Path(sys.argv[1])
audit = Path(sys.argv[2]).read_text(encoding='utf-8', errors='replace')
if _card_machine_audit_passed(str(card)):
    print('already_passed')
    raise SystemExit(0)
if not _audit_output_indicates_pass(audit):
    print('log_not_pass')
    raise SystemExit(3)
ok = _append_machine_audit_pass(str(card), source='m3-backfill-stale-audit', evidence=audit[-800:])
print('ok' if ok else 'fail')
raise SystemExit(0 if ok else 4)
" "$card" "$audit" 2>&1)"
  rc=$?
  set -e
  case "$out" in
    already_passed) echo "[OK] $id: 已有机审通过" ;;
    log_not_pass) echo "[SKIP] $id: audit.log 未判定通过"; SKIPPED=$((SKIPPED+1)) ;;
    ok) echo "[OK] $id: 已补落盘 → $card"; CHANGED+=("$card") ;;
    *) echo "[ERR] $id (rc=$rc): $out"; SKIPPED=$((SKIPPED+1)) ;;
  esac
done

if [[ ${#CHANGED[@]} -eq 0 ]]; then
  echo "[DONE] 无卡文件变更（skipped=$SKIPPED）"
  exit 0
fi

git add -- "${CHANGED[@]}"
git commit -m "$(cat <<EOF
cards: m3 backfill 机审区 from audit.log (${#CHANGED[@]} cards)

EOF
)"
git push origin main
echo "[OK] pushed ${#CHANGED[@]} cards; 请 2017 pull"
