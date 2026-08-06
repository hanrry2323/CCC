#!/usr/bin/env bash
# ── M4：已回写卡「首跑机审」受控重放（代码已在 main + 探针绿 → 落盘机审区）──
#
# 用于 Engine 未再拉起机审、但实现已合入 main 的卡（非假滞留补录）。
# 用法：scripts/first-audit-evidence.sh <card-id> [<card-id>...]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHON_BIN="${CCC_PYTHON_BIN:-python3}"

if [[ $# -lt 1 ]]; then
  echo "用法: $0 <card-id> [...]" >&2
  exit 2
fi

cd "$PROJECT_ROOT"

# 基线探针（失败则整批拒绝）
"$PYTHON_BIN" -m pytest \
  server/tests/test_project_registry.py \
  server/tests/test_engine_audit_backfill.py \
  server/tests/test_ccc_plan.py \
  -q --tb=line

CHANGED=()
for id in "$@"; do
  card="$(find docs/dispatch -type f -name "${id}-*.md" | head -1 || true)"
  if [[ -z "${card:-}" ]]; then
    echo "[SKIP] $id: 无卡文件" >&2
    continue
  fi
  tip="$(git rev-parse --short HEAD)"
  out="$("$PYTHON_BIN" -c "
import sys
from pathlib import Path
sys.path.insert(0, '.')
from server.engine.main import _append_machine_audit_pass, _card_machine_audit_passed
card = Path(sys.argv[1])
if _card_machine_audit_passed(str(card)):
    print('already')
    raise SystemExit(0)
ev = sys.argv[2]
ok = _append_machine_audit_pass(
    str(card),
    source='m4-first-audit-evidence',
    evidence=ev,
)
print('ok' if ok else 'fail')
raise SystemExit(0 if ok else 4)
" "$card" "main=${tip}; pytest registry+audit_backfill+ccc_plan 绿; 实现已在 main（M4 受控首跑机审）")"
  case "$out" in
    already) echo "[OK] $id: 已有机审通过" ;;
    ok) echo "[OK] $id: 首跑机审落盘 → $card"; CHANGED+=("$card") ;;
    *) echo "[ERR] $id: $out" >&2; exit 1 ;;
  esac
done

if [[ ${#CHANGED[@]} -eq 0 ]]; then
  echo "[DONE] 无变更"
  exit 0
fi

git add -- "${CHANGED[@]}"
git commit -m "$(cat <<EOF
cards: m4 first-audit evidence (${#CHANGED[@]} cards)

EOF
)"
git push origin main
echo "[OK] pushed; 2017 pull 后进 ready_for_merge"
