#!/usr/bin/env bash
# ── CCC：合入批准（北星 W2 · 人审 diff 后唯一常规动作）──
#
# 用法：
#   scripts/approve-merge.sh <card-id> [<card-id>...]
#   scripts/approve-merge.sh --ready              # 批处理 2017 ready_for_merge 队列
#   scripts/approve-merge.sh --close-only <id>    # 分支已分叉/已合入时仅关卡（ready 必需）
#
# 校验：机审通过（本地卡或 API）+ origin/codex/<stem> 存在。
# 动作：能 ff 则 ff-merge；否则 --close-only / 分支已在 main → 只关卡。
# 合入前 main 卡头允许滞后；本脚本写关闭态。

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHON_BIN="${CCC_PYTHON_BIN:-python3}"
BOARD_URL="${CCC_BOARD_URL:-http://192.168.3.116:7788}"
USE_READY=false
CLOSE_ONLY=false
IDS=()

usage() {
  sed -n '2,16p' "$0" | sed 's/^# \{0,1\}//'
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --ready) USE_READY=true; shift ;;
    --close-only) CLOSE_ONLY=true; shift ;;
    -h|--help) usage; exit 0 ;;
    *) IDS+=("$1"); shift ;;
  esac
done

cd "$PROJECT_ROOT"

if [[ "$USE_READY" == true ]]; then
  IDS=()
  while IFS= read -r line; do
    [[ -n "$line" ]] && IDS+=("$line")
  done < <(
    curl -sf --max-time 10 "${BOARD_URL}/board/ready_for_merge" \
      | "$PYTHON_BIN" -c "import json,sys; d=json.load(sys.stdin); print('\n'.join(c['id'] for c in d.get('cards') or []))"
  )
  if [[ ${#IDS[@]} -eq 0 ]]; then
    echo "[OK] ready_for_merge 队列为空"
    exit 0
  fi
fi

if [[ ${#IDS[@]} -eq 0 ]]; then
  echo "[ERROR] 需要 <card-id> 或 --ready" >&2
  usage
  exit 2
fi

resolve_card() {
  local id="$1"
  local hit
  hit="$(find docs/dispatch -type f -name "${id}-*.md" 2>/dev/null | head -1 || true)"
  if [[ -z "$hit" ]]; then
    echo "[ERROR] 找不到卡：${id}" >&2
    return 1
  fi
  echo "$hit"
}

check_audit() {
  local path="$1"
  "$PYTHON_BIN" -c "
from pathlib import Path
import sys
sys.path.insert(0, '.')
from server.board.models import machine_audit_passed_text
text = Path(sys.argv[1]).read_text(encoding='utf-8')
# 也接受分支 tip 已写机审：先查本地；不足则提示用 API
ok = machine_audit_passed_text(text)
sys.exit(0 if ok else 1)
" "$path"
}

# 外仓提示：registry.mac2017 非 CCC 本仓时打印分支/HEAD/是否已在业务 main（不自动 push）
print_external_repo_hint() {
  local path="$1" branch="$2"
  "$PYTHON_BIN" - "$path" "$branch" <<'PY' || true
import re, subprocess, sys
from pathlib import Path

sys.path.insert(0, ".")
from server.board.registry import load_projects

card = Path(sys.argv[1])
branch = sys.argv[2]
text = card.read_text(encoding="utf-8")
m = re.search(r"项目：([^·\n]+)", text)
prefix = m.group(1).strip() if m else ""
if not prefix:
    sys.exit(0)
projects = load_projects()
by_prefix = {p.prefix: p for p in projects if p.prefix}
entry = by_prefix.get(prefix)
ccc = by_prefix.get("ccc")
if entry is None or not entry.path_mac2017:
    sys.exit(0)
if ccc and entry.path_mac2017 == ccc.path_mac2017:
    sys.exit(0)
repo = entry.path_mac2017
if not repo.startswith("/") or ".." in repo:
    print(f"[外仓] project={prefix} path={repo} (路径非法，跳过探测)")
    sys.exit(0)
remote = "origin/" + branch
cmd = (
    f"git -C {repo} fetch -q origin >/dev/null 2>&1; "
    f"h=$(git -C {repo} rev-parse --short {remote} 2>/dev/null || echo missing); "
    f"in_main=$(git -C {repo} merge-base --is-ancestor {remote} origin/main >/dev/null 2>&1 && echo yes || echo no); "
    'echo "$h $in_main"'
)
try:
    out = subprocess.check_output(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", "fan@192.168.3.116", cmd],
        text=True,
        stderr=subprocess.DEVNULL,
        timeout=25,
    ).strip()
except (subprocess.SubprocessError, OSError):
    print(f"[外仓] project={prefix} path={repo} branch={branch} (ssh 不可达，请人工核对)")
    sys.exit(0)
parts = out.split()
head = parts[0] if parts else "missing"
in_main = parts[1] if len(parts) > 1 else "?"
print(f"[外仓] project={prefix} path={repo} branch={branch} HEAD={head} in_main={in_main}")
PY
}

close_card() {
  local path="$1"
  local today
  today="$(date +%Y-%m-%d)"
  "$PYTHON_BIN" -c "
import re, sys
from pathlib import Path
path = Path(sys.argv[1])
today = sys.argv[2]
text = path.read_text(encoding='utf-8')
text2, n = re.subn(r'(状态：)[^·\n]+', r'\1已关闭', text, count=1)
if n != 1:
    raise SystemExit('cannot update 状态 in ' + str(path))
if '## 验收区' not in text2:
    text2 = text2.rstrip() + f\"\"\"

## 验收区

**合入批准** · 日期：{today}
- 判定：通过
- ✅ 人审 diff 后合入批准（北星 W2）
\"\"\"
elif '合入批准' not in text2.split('## 验收区', 1)[-1][:400]:
    # 已有验收区则补一行
    text2 = text2.replace('## 验收区', '## 验收区\n\n**合入批准** · 日期：' + today + '\n- 判定：通过\n', 1)
path.write_text(text2, encoding='utf-8')
" "$path" "$today"
}

approve_one() {
  local id="$1"
  local path stem branch
  path="$(resolve_card "$id")" || return 1
  stem="$(basename "$path" .md)"
  branch="codex/${stem}"

  echo "== 合入批准 ${id} (${branch}) =="
  print_external_repo_hint "$path" "$branch"

  # 优先 2017 ready；本地机审区也可
  local api_ok=false
  if curl -sf --max-time 8 "${BOARD_URL}/board/ready_for_merge" \
    | "$PYTHON_BIN" -c "import json,sys; d=json.load(sys.stdin); sys.exit(0 if any(c.get('id')==sys.argv[1] for c in d.get('cards') or []) else 1)" "$id" 2>/dev/null; then
    api_ok=true
  fi
  if [[ "$api_ok" != true ]]; then
    if ! check_audit "$path"; then
      # try tip of branch for 机审区
      git fetch origin "$branch" >/dev/null 2>&1 || {
        echo "[ERROR] ${id}: 不在 ready 队列且本地无机审通过；origin/${branch} 不可用" >&2
        return 1
      }
      if ! git show "origin/${branch}:${path}" 2>/dev/null \
        | "$PYTHON_BIN" -c "
import sys
sys.path.insert(0, '.')
from server.board.models import machine_audit_passed_text
sys.exit(0 if machine_audit_passed_text(sys.stdin.read()) else 1)
"; then
        echo "[ERROR] ${id}: 机审未通过（API ready + 本地/分支机审区均失败）" >&2
        return 1
      fi
    fi
  fi

  git fetch origin main
  git fetch origin "$branch" 2>/dev/null || true

  # 工作树须在 main
  current="$(git rev-parse --abbrev-ref HEAD)"
  if [[ "$current" != "main" ]]; then
    echo "[ERROR] 请在 main 上执行合入批准（当前：${current}）" >&2
    return 1
  fi
  git pull --ff-only origin main

  # 合入策略：ff / 已在 main 仅关卡 / 无分支或分叉时须 --close-only
  if ! git rev-parse --verify "origin/${branch}" >/dev/null 2>&1; then
    if [[ "$CLOSE_ONLY" == true ]]; then
      echo "[WARN] 无 origin/${branch} → --close-only 仅关卡（实现已在 main）"
    else
      echo "[ERROR] 缺少 origin/${branch}。若实现已在 main 可加 --close-only" >&2
      return 1
    fi
  elif [[ "$(git rev-parse origin/main)" == "$(git rev-parse "origin/${branch}")" ]]; then
    echo "[INFO] tip 与 main 相同，仅关卡"
  elif git merge-base --is-ancestor "origin/${branch}" origin/main; then
    echo "[INFO] ${branch} 已在 main 历史中，仅关卡"
  elif git merge-base --is-ancestor origin/main "origin/${branch}"; then
    git merge --ff-only "origin/${branch}"
  elif [[ "$CLOSE_ONLY" == true ]]; then
    echo "[WARN] ${branch} 与 main 分叉 → --close-only 仅关卡（业务 diff 已人工确认在 main/外仓）"
  else
    echo "[ERROR] ${branch} 无法 ff 合入 main（非快进）。" >&2
    echo "  建议：卡内分支 git rebase origin/main 后再合入；若代码已在 main 可加 --close-only" >&2
    return 1
  fi

  close_card "$path"
  git add -- "$path"
  if ! git diff --cached --quiet; then
    git commit -m "$(cat <<EOF
merge: 合入批准 ${id}

EOF
)"
  fi
  git push origin main
  echo "[OK] 合入批准完成：${id} → 请 2017 pull（部署流程）"

  # 卫生：已合入 main 的卡分支自动删除（分叉/未合入一律保留，保护 --close-only）
  if git rev-parse --verify "origin/${branch}" >/dev/null 2>&1 \
    && git merge-base --is-ancestor "origin/${branch}" origin/main >/dev/null 2>&1; then
    git branch -D "${branch}" >/dev/null 2>&1 || true
    if git push origin --delete "${branch}" >/dev/null 2>&1; then
      echo "[OK] 已删除已合入分支: ${branch}"
    else
      echo "[WARN] 远端分支删除失败（不影响合入）: ${branch}"
    fi
  fi
}

FAILED=0
for id in "${IDS[@]}"; do
  if ! approve_one "$id"; then
    FAILED=$((FAILED + 1))
  fi
done

if [[ "$FAILED" -gt 0 ]]; then
  echo "[ERROR] ${FAILED} 张卡合入失败" >&2
  exit 1
fi
echo "[OK] 全部合入批准完成（${#IDS[@]}）"
