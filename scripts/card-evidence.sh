#!/usr/bin/env bash
# ── CCC：卡分支 tip 取证（北星真值单轨 · W2）──
#
# 进度 UI/API 只认 2017 :7788；本脚本只认 origin/codex/<stem>。
# 禁止 /tmp merge 考古。
#
# 用法：
#   scripts/card-evidence.sh <card-id>           # 如 ccc123
#   scripts/card-evidence.sh --stem <file-stem>  # 如 ccc123-my-slug
#
# 环境：
#   CCC_BOARD_URL  默认 http://192.168.3.116:7788

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BOARD_URL="${CCC_BOARD_URL:-http://192.168.3.116:7788}"
STEM=""
CARD_ID=""

usage() {
  sed -n '2,14p' "$0" | sed 's/^# \{0,1\}//'
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --stem) STEM="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *)
      if [[ -z "$CARD_ID" ]]; then CARD_ID="$1"; shift
      else echo "[ERROR] 多余参数: $1" >&2; exit 2; fi
      ;;
  esac
done

cd "$PROJECT_ROOT"

resolve_stem() {
  local id="$1"
  local hit
  hit="$(find docs/dispatch -type f -name "${id}-*.md" 2>/dev/null | head -1 || true)"
  if [[ -z "$hit" ]]; then
    # 允许传入完整 stem
    if [[ -f "docs/dispatch/"*"/${id}.md" ]]; then
      basename "$(ls docs/dispatch/*/"${id}.md" 2>/dev/null | head -1)" .md
      return
    fi
    echo "[ERROR] 找不到卡文件：${id}" >&2
    return 1
  fi
  basename "$hit" .md
}

if [[ -n "$STEM" ]]; then
  :
elif [[ -n "$CARD_ID" ]]; then
  STEM="$(resolve_stem "$CARD_ID")" || exit 2
else
  echo "[ERROR] 需要 <card-id> 或 --stem" >&2
  usage
  exit 2
fi

BRANCH="codex/${STEM}"
echo "== board (2017) =="
if curl -sf --max-time 5 "${BOARD_URL}/board/ready_for_merge" >/tmp/ccc-ready-$$.json 2>/dev/null; then
  python3 -c "
import json,sys
d=json.load(open(sys.argv[1]))
stem=sys.argv[2]
rid=stem.split('-')[0] if '-' in stem else stem
# id is prefix+NNN before first slug dash — e.g. ccc123-foo → ccc123
import re
m=re.match(r'^([a-z]{2,4}\d{3})', stem)
cid=m.group(1) if m else rid
print('ready_count', d.get('count'))
for c in d.get('cards') or []:
    if c.get('id')==cid:
        print('ready', c.get('id'), c.get('board_column'), 'audit', c.get('machine_audit_passed'))
        break
else:
    print('not_in_ready_queue', cid)
" /tmp/ccc-ready-$$.json "$STEM" || true
  rm -f /tmp/ccc-ready-$$.json
else
  echo "[WARN] 无法访问 ${BOARD_URL}/board/ready_for_merge（进度仍以该 API 为准，勿用本地卡头）"
fi

echo "== fetch ${BRANCH} =="
git fetch origin "$BRANCH" 2>&1 || {
  echo "[ERROR] origin/${BRANCH} 不存在或 fetch 失败" >&2
  exit 1
}

echo "== log origin/main..origin/${BRANCH} =="
git log --oneline "origin/main..origin/${BRANCH}" || true

echo "== diff --stat =="
git diff --stat "origin/main...origin/${BRANCH}" || true

echo "== tip =="
git rev-parse --short "origin/${BRANCH}"
echo "[OK] evidence stem=${STEM} branch=${BRANCH}"
