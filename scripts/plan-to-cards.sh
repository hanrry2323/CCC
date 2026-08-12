#!/usr/bin/env bash
# ── CCC：ccc-plan → 多卡一次 commit+push（北星 W1）──
#
# 用法：
#   scripts/plan-to-cards.sh <plan.md|-> [--dry-run] [--no-push] [--dispatch-dir DIR]
#
# 输入：含 ```ccc-plan 围栏的 Markdown，或纯 JSON / YAML plan 正文。
# 非法前缀 / 空验收点 → 非 0（不静默出卡）。

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHON_BIN="${CCC_PYTHON_BIN:-python3}"
DISPATCH_DIR="${CCC_DISPATCH_DIR:-docs/dispatch}"
DRY_RUN=false
NO_PUSH=false
PLAN_FILE=""

usage() {
  sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=true; shift ;;
    --no-push) NO_PUSH=true; shift ;;
    --dispatch-dir) DISPATCH_DIR="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    -) PLAN_FILE="-"; shift ;;
    *)
      if [[ -z "$PLAN_FILE" ]]; then PLAN_FILE="$1"; shift
      else echo "[ERROR] 多余参数: $1" >&2; exit 2; fi
      ;;
  esac
done

if [[ -z "$PLAN_FILE" ]]; then
  echo "[ERROR] 需要 plan 文件路径或 -（stdin）" >&2
  usage
  exit 2
fi

TMP_PLAN="$(mktemp)"
trap 'rm -f "$TMP_PLAN"' EXIT
if [[ "$PLAN_FILE" == "-" ]]; then
  cat > "$TMP_PLAN"
else
  if [[ ! -f "$PLAN_FILE" ]]; then
    echo "[ERROR] 找不到 plan：$PLAN_FILE" >&2
    exit 2
  fi
  cat "$PLAN_FILE" > "$TMP_PLAN"
fi

export CCC_PROJECT_ROOT="$PROJECT_ROOT"
MAP_JSON="$(
  cd "$PROJECT_ROOT" && "$PYTHON_BIN" -c "
import json, os, sys
from pathlib import Path
sys.path.insert(0, os.environ['CCC_PROJECT_ROOT'])
from server.board.ccc_plan import parse_ccc_plan, PlanError
try:
    plan = parse_ccc_plan(Path(sys.argv[1]).read_text(encoding='utf-8'))
except PlanError as e:
    print(f'[ERROR] {e}', file=sys.stderr)
    sys.exit(2)
except Exception as e:
    print(f'[ERROR] parse failed: {e}', file=sys.stderr)
    sys.exit(2)
print(json.dumps({
    'title': plan.title,
    'project': plan.project,
    'slices': [{
        'title': s.title,
        'slug': s.slug,
        'acceptance': s.acceptance,
        'whitelist': s.whitelist,
        'executor': s.executor,
    } for s in plan.slices],
}, ensure_ascii=False))
" "$TMP_PLAN"
)" || exit $?

PLAN_TITLE="$(
  "$PYTHON_BIN" -c "import json,sys; print(json.load(sys.stdin)['title'])" <<<"$MAP_JSON"
)"
PROJECT="$(
  "$PYTHON_BIN" -c "import json,sys; print(json.load(sys.stdin)['project'])" <<<"$MAP_JSON"
)"
# 方案编号（A1 修复 2026-08-10）：关联字段用 <prefix>-plan-<NNN> 而非标题，对齐 Doc-Gate Q1
PLAN_NUM="$(basename "$PLAN_FILE" .md | cut -d- -f1 | grep -E '^[0-9]{3}$' || echo "")"
SLICE_COUNT="$(
  "$PYTHON_BIN" -c "import json,sys; print(len(json.load(sys.stdin)['slices']))" <<<"$MAP_JSON"
)"

if [[ "$DRY_RUN" == true ]]; then
  echo "[dry-run] plan=$PLAN_TITLE project=$PROJECT slices=$SLICE_COUNT"
  echo "$MAP_JSON" | "$PYTHON_BIN" -m json.tool
  exit 0
fi

CREATED=()
cd "$PROJECT_ROOT"

while IFS= read -r row; do
  [[ -z "$row" ]] && continue
  stitle="$("$PYTHON_BIN" -c "import json,sys; print(json.load(sys.stdin)['title'])" <<<"$row")"
  slug="$("$PYTHON_BIN" -c "import json,sys; print(json.load(sys.stdin)['slug'])" <<<"$row")"
  executor="$("$PYTHON_BIN" -c "import json,sys; print(json.load(sys.stdin)['executor'])" <<<"$row")"
  acc_json="$("$PYTHON_BIN" -c "import json,sys; print(json.dumps(json.load(sys.stdin)['acceptance'], ensure_ascii=False))" <<<"$row")"
  wl_json="$("$PYTHON_BIN" -c "import json,sys; print(json.dumps(json.load(sys.stdin)['whitelist'], ensure_ascii=False))" <<<"$row")"

  CARD_PATH="$(
    "$SCRIPT_DIR/new-card.sh" \
      --title "$stitle" \
      --project "$PROJECT" \
      --slug "$slug" \
      --executor "$executor" \
      --dispatch-dir "$DISPATCH_DIR" \
      --related "${PROJECT}-plan-${PLAN_NUM}" \
      --quiet \
    | sed -n 's/^CARD_PATH=//p'
  )"
  if [[ -z "$CARD_PATH" || ! -f "$CARD_PATH" ]]; then
    # 兜底：new-card 未吐 CARD_PATH 时回退旧扫描（不依赖仅 head -1，先精确 glob）
    CARD_PATH="$(find "$DISPATCH_DIR/$PROJECT" -maxdepth 1 -type f -name "${PROJECT}[0-9][0-9][0-9]-${slug}.md" | head -1)"
  fi
  if [[ -z "$CARD_PATH" || ! -f "$CARD_PATH" ]]; then
    echo "[ERROR] 出卡后找不到 ${PROJECT}*-${slug}.md" >&2
    # 回滚：删除已生成的临时卡
    for c in "${CREATED[@]}"; do rm -f "$c"; done
    exit 1
  fi

  "$PYTHON_BIN" -c "
import json, re, sys
from pathlib import Path
path = Path(sys.argv[1])
acc = json.loads(sys.argv[2])
wl = json.loads(sys.argv[3])
goal = sys.argv[4]
text = path.read_text(encoding='utf-8')
text = re.sub(
    r'(## 目标\n\n)（一句话，可验收。）',
    lambda m: m.group(1) + goal + '（ccc-plan 切片）。',
    text,
    count=1,
)
wl_block = '\n'.join(f'- \`{w}\`' for w in wl) if wl else '（本切片白名单见验收点；未列路径勿改。）'
text = re.sub(
    r'(## 范围\n\n)（明确本卡改动范围，白名单式列出。）',
    lambda m: m.group(1) + wl_block,
    text,
    count=1,
)
acc_block = '\n'.join(f'{i}. {a}' for i, a in enumerate(acc, 1))
text = re.sub(
    r'(## 验收标准\n\n)1\. （可执行的验收点，附命令/可观察结果）',
    lambda m: m.group(1) + acc_block,
    text,
    count=1,
)
text = text.replace('老板「验收看板」终验', '老板「合入批准」')
text = text.replace('听「验收看板」后写', '听「合入批准」后写')
path.write_text(text, encoding='utf-8')
" "$CARD_PATH" "$acc_json" "$wl_json" "$stitle"

  CREATED+=("$CARD_PATH")
  echo "[OK] card: $CARD_PATH"
done < <(
  "$PYTHON_BIN" -c "
import json,sys
plan=json.load(sys.stdin)
for s in plan['slices']:
    print(json.dumps(s, ensure_ascii=False))
" <<<"$MAP_JSON"
)

if [[ ${#CREATED[@]} -eq 0 ]]; then
  echo "[ERROR] 未生成任何卡" >&2
  exit 1
fi

# ── Phase 2: 全量校验（一次 validate_cards 全树扫描，O(N) 而非逐卡 O(N²)）──
if ! ( cd "$PROJECT_ROOT" && "$PYTHON_BIN" -c "
import sys
sys.path.insert(0, '.')
from server.board.validate import validate_cards
issues = validate_cards('$DISPATCH_DIR')
errs = [i for i in issues if i.severity == 'error' and i.card_id.startswith('$PROJECT')]
if errs:
    print(f'卡头校验发现 {len(errs)} 个本项目 error：', file=sys.stderr)
    for e in errs:
        print(f'  [{e.card_id}] {e.path}: {e.reason}', file=sys.stderr)
    sys.exit(1)
print('[OK] 本项目卡头校验通过')
" ); then
  echo "[ERROR] 全量校验未通过，回滚所有临时卡" >&2
  for c in "${CREATED[@]}"; do rm -f "$c"; done
  exit 1
fi

echo "[OK] 全量校验通过（${#CREATED[@]} 张卡）"

# 相对仓库根的路径；dispatch-dir 在仓外时只出卡不 git
REL_CREATED=()
OUTSIDE=false
for c in "${CREATED[@]}"; do
  abs="$(cd "$(dirname "$c")" && pwd)/$(basename "$c")"
  case "$abs" in
    "$PROJECT_ROOT"/*)
      REL_CREATED+=("${abs#"$PROJECT_ROOT"/}")
      ;;
    *)
      OUTSIDE=true
      ;;
  esac
done

if [[ "$OUTSIDE" == true ]]; then
  echo "[OK] generated ${#CREATED[@]} cards under external dispatch-dir (skip git)"
  printf '%s\n' "${CREATED[@]}"
  exit 0
fi

git add -- "${REL_CREATED[@]}"
if git diff --cached --quiet; then
  echo "[WARN] 无暂存变更（卡可能已存在）" >&2
  exit 1
fi
git commit -m "$(cat <<EOF
cards: plan-to-cards ${PLAN_TITLE} (${#CREATED[@]} slices)

EOF
)"

if [[ "$NO_PUSH" == true ]]; then
  echo "[OK] committed ${#CREATED[@]} cards (no push)"
  exit 0
fi

git push
echo "[OK] pushed ${#CREATED[@]} cards from plan: $PLAN_TITLE"
