#!/usr/bin/env bash
# ── CCC：合入批准（北星 W2 · 人审 diff 后唯一常规动作）──
#
# 用法：
#   scripts/approve-merge.sh <card-id> [<card-id>...]
#   scripts/approve-merge.sh --ready              # 批处理 2017 ready_for_merge 队列
#   scripts/approve-merge.sh --close-only <id>    # 分支已在 main 历史/无分支时仅关卡（ready 必需）
#
# 校验：机审通过（本地卡或 API）+ origin/codex/<stem> 存在。
# 动作：跨仓收口——业务仓分支先 ff 合入业务 main + 删（分叉阻断整卡，--close-only 也不放行分叉）；
#       CCC 仓能 ff 则 ff-merge；否则 --close-only / 分支已在 main → 只关卡。
#       【合入后须部署检查】：成功合入后自动检查 2017 生产 vs 主干，落后则触发热重启部署。
# 合入前 main 卡头允许滞后；本脚本写关闭态。

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHON_BIN="${CCC_PYTHON_BIN:-python3}"
BOARD_URL="${CCC_BOARD_URL:-http://192.168.3.116:7788}"
# 跨机执行支持（默认保留 2017 生产）：SSH 目标主机（user@ip）与 2017 生产仓路径均可覆盖
CCC_SSH_HOST="${CCC_SSH_HOST:-fan@192.168.3.116}"
CCC_PROD_REPO="${CCC_PROD_REPO:-/Users/fan/program/CCC}"
# shellcheck source=lib/card-resolve.sh
source "$SCRIPT_DIR/lib/card-resolve.sh"
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
    # 分支信封证据：origin/codex/* 分支卡含「机审：通过」且未合入 main → ready
    git fetch origin main >/dev/null 2>&1
    git fetch origin >/dev/null 2>&1
    "$PYTHON_BIN" - <<'PY'
import re, subprocess, sys
from pathlib import Path

sys.path.insert(0, ".")
from server.board.models import machine_audit_passed_text

out = subprocess.check_output(["git", "branch", "-r"], text=True)
ready = []
for b in out.splitlines():
    b = b.strip()
    if not b.startswith("origin/codex/"):
        continue
    if subprocess.run(
        ["git", "merge-base", "--is-ancestor", b, "origin/main"],
        capture_output=True,
    ).returncode == 0:
        continue  # 已合入 main
    files = subprocess.check_output(
        ["git", "ls-tree", "-r", "--name-only", b], text=True
    ).splitlines()
    for f in files:
        if not f.startswith("docs/dispatch/") or not f.endswith(".md"):
            continue
        # 只认与分支同名 stem 的卡：分支 codex/ccc013-flow-verify-pipeline
        # 只应贡献 ccc013，避免把分支里携带的历史卡（如已关闭 ccc004）误扫进 ready
        if Path(f).stem != b.removeprefix("origin/codex/"):
            continue
        # 卡在 main 已关闭（close-only/历史残留分支）→ 不重复批准
        main_card = subprocess.run(
            ["git", "show", f"origin/main:{f}"],
            capture_output=True,
            text=True,
        )
        if main_card.returncode == 0 and "状态：已关闭" in main_card.stdout:
            continue
        card = subprocess.check_output(["git", "show", f"{b}:{f}"], text=True)
        m = re.match(r"^([a-z]{2,4}\d{3})-", Path(f).stem)
        if m and machine_audit_passed_text(card):
            # P0 硬化（2026-08-22）：ready 入队须账本有机审记录（卡文自写不算，防假关闭污染批次）
            from server.board.audit_ledger import has_pass

            if has_pass(m.group(1)):
                ready.append(m.group(1))
            break
print("\n".join(sorted(set(ready))))
PY
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

# 完成钩子（Doc-Gate）机械门禁：维护区四问必须勾选且说明非空
# 校验上下文 = 分支临时工作树（origin/<branch>），卡文件/方案文件/git diff 全部基于
# 分支信封，与机审证据同源；分支不可读（close-only/已合入）时回退 main 工作区。
check_maintenance() {
  local path="$1"
  local branch="${2:-}"
  local tmpwt=""
  local repo_root="."
  if [[ -n "$branch" ]] && git rev-parse --verify "origin/${branch}" >/dev/null 2>&1; then
    tmpwt="$(mktemp -d)"
    if ! git worktree add -q --detach "$tmpwt" "origin/${branch}" 2>/dev/null; then
      rm -rf "$tmpwt"
      return 1
    fi
    repo_root="$tmpwt"
  fi
  local ret=0
  "$PYTHON_BIN" -c "
import sys
sys.path.insert(0, '.')
from server.board.docgate import verify_maintenance
ok, problems = verify_maintenance(sys.argv[1], sys.argv[2])
if not ok:
    print('[ERROR] 完成钩子（维护区声明不实）：' + '；'.join(problems), file=sys.stderr)
    sys.exit(1)
print('[OK] 完成钩子：维护区四问已勾选且说明完整')
sys.exit(0)
" "$path" "$repo_root" || ret=1
  if [[ -n "$tmpwt" ]]; then git worktree remove -f "$tmpwt" 2>/dev/null; rm -rf "$tmpwt"; fi
  return "$ret"
}

# 密钥/凭据扫描门禁（2026-08-16 质量门禁）：对 origin/main..分支 diff 扫疑似密钥，命中即阻断。
# 落地 qx-map 红线「不碰密钥明文」为机械合入门禁。仅匹配高置信度格式（AKIA/私钥头/GitHub token/OpenAI key/Slack token）。
check_secret_scan() {
  local branch="$1" id="$2"
  if ! git rev-parse --verify "origin/${branch}" >/dev/null 2>&1; then
    return 0
  fi
  local hits
  hits="$(git diff origin/main..."origin/${branch}" 2>/dev/null \
    | grep -nE 'AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]+PRIVATE KEY-----|ghp_[A-Za-z0-9]{36}|sk-[A-Za-z0-9]{20,}|xox[baprs]-[A-Za-z0-9-]{10,}' \
    || true)"
  if [ -n "$hits" ]; then
    echo "[error] ${id}: 分支 diff 检测到疑似密钥/凭据 → 阻断合入（2026-08-16 密钥扫描门禁）。请移除敏感信息后重新机审。" >&2
    echo "$hits" | head -5 >&2
    return 1
  fi
  return 0
}

# 外仓提示：registry.mac2017 非 CCC 本仓时打印分支/HEAD/是否已在业务 main（不自动 push）
print_external_repo_hint() {
  local path="$1" branch="$2"
  "$PYTHON_BIN" - "$path" "$branch" "$CCC_SSH_HOST" <<'PY' || true
import re, subprocess, sys
from pathlib import Path

sys.path.insert(0, ".")
from server.board.registry import load_projects

card = Path(sys.argv[1])
branch = sys.argv[2]
ssh_host = sys.argv[3]
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
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", ssh_host, cmd],
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

# 跨仓收口：业务仓分支 ff 合入业务 main + 删分支（分叉则阻断整卡合入）
close_business_repo() {
  local path="$1" branch="$2"
  "$PYTHON_BIN" - "$path" "$branch" "$CCC_SSH_HOST" <<'PY'
import re, subprocess, sys
from pathlib import Path

sys.path.insert(0, ".")
from server.board.registry import load_projects

card = Path(sys.argv[1])
branch = sys.argv[2]
ssh_host = sys.argv[3]
text = card.read_text(encoding="utf-8")
m = re.search(r"项目：([^·\n]+)", text)
prefix = m.group(1).strip() if m else ""
projects = load_projects()
by_prefix = {p.prefix: p for p in projects if p.prefix}
entry = by_prefix.get(prefix)
ccc = by_prefix.get("ccc")
if entry is None or not entry.path_mac2017:
    print("[外仓] 无业务仓（平台卡），跳过")
    sys.exit(0)
if ccc and entry.path_mac2017 == ccc.path_mac2017:
    print("[外仓] 同 CCC 仓，跳过")
    sys.exit(0)
repo = entry.path_mac2017
if not repo.startswith("/") or ".." in repo:
    print(f"[外仓] 业务仓路径非法: {repo}")
    sys.exit(2)

remote = "origin/" + branch
cmd = (
    f"cd {repo} && "
    f"git fetch -q origin >/dev/null 2>&1; "
    f"if ! git rev-parse --verify {remote} >/dev/null 2>&1; then echo 'NO_BRANCH'; exit 0; fi; "
    f"if git merge-base --is-ancestor {remote} origin/main >/dev/null 2>&1; then "
    f"  git push origin --delete {branch} >/dev/null 2>&1 && echo 'MERGED_DELETED' || echo 'MERGED_DELETE_FAIL'; "
    f"elif git merge-base --is-ancestor origin/main {remote} >/dev/null 2>&1; then "
    f"  git merge --ff-only {remote} >/dev/null 2>&1 && git push -q origin main >/dev/null 2>&1 "
    f"    && git push origin --delete {branch} >/dev/null 2>&1 && echo 'FF_MERGED_DELETED' || echo 'FF_MERGE_FAIL'; "
    f"else echo 'DIVERGED'; exit 3; fi"
)
try:
    out = subprocess.check_output(
        [
            "ssh",
            "-o", "BatchMode=yes",
            "-o", "ConnectTimeout=5",
            ssh_host,
            cmd,
        ],
        text=True,
        stderr=subprocess.DEVNULL,
        timeout=90,
    ).strip()
except (subprocess.SubprocessError, OSError) as exc:
    print(f"[外仓] 业务仓收口失败（ssh 不可达）: {exc}")
    sys.exit(2)
print(f"[外仓] {prefix} {repo}: {out}")
sys.exit(0)
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
# 人审节点③：批准行更新为「老板合入批准」（无则插入到卡头首行后；单行最新语义）
if re.search(r'(^|\n)\s*> 批准：', text2):
    text2 = re.sub(r'(\n\s*> 批准：)([^\n]*)', r'\1老板合入批准 · ' + today, text2, count=1)
else:
    m = re.search(r'^# 任务卡[^\n]*\n', text2)
    if m:
        text2 = text2[:m.end()] + '> 批准：老板合入批准 · ' + today + '\n' + text2[m.end():]
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

# ── sync_plan_cards：卡关闭后自动同步方案「关联卡」（ccc062）──
# 卡头「关联」含 prefix-plan-NNN 时，把本卡 ID 追加到方案「关联卡」字段。
# 无方案编号则跳过（如 phase-3 关联、无方案卡）。
sync_plan_cards() {
  local path="$1"
  "$PYTHON_BIN" - "$path" <<'PY'
import re, sys
from pathlib import Path
sys.path.insert(0, ".")
from server.board.plans import update_plan
from server.board.docgate import get_card_id

card_path = Path(sys.argv[1])
try:
    text = card_path.read_text(encoding="utf-8")
except OSError:
    print(f"[skip] 无法读取卡文件: {card_path}")
    raise SystemExit(0)

card_id = get_card_id(card_path)
related = re.search(r"关联：([^\n·]*)", text)
related = related.group(1) if related else ""
plan_m = re.search(r"([a-z]{2,4})-plan-([0-9]{3})", related)
if not plan_m:
    print(f"[skip] {card_id} 卡头无 prefix-plan-NNN 关联方案，跳过方案关联卡同步")
    raise SystemExit(0)

plan_prefix, plan_num = plan_m.group(1), plan_m.group(2)
plans_dir = Path("docs") / "projects" / plan_prefix / "plans"
matches = sorted(plans_dir.glob(f"{plan_num}-*.md"))
if not matches:
    print(f"[warn] {card_id} 关联方案文件不存在: docs/projects/{plan_prefix}/plans/{plan_num}-*.md")
    raise SystemExit(0)

rel_path = str(Path("docs") / "projects" / plan_prefix / "plans" / matches[0].name)
plan_text = matches[0].read_text(encoding="utf-8")
cur_cards = ""
m = re.search(r"关联卡：([^\n]*)", plan_text)
if m:
    cur_cards = m.group(1).strip()

existing = [c.strip() for c in cur_cards.split(",") if c.strip()] if cur_cards else []
# P0 全链路修复：卡已在关联卡中也调 update_plan（cards 不变）→ 触发 sync_plan_progress 重算方案进度。
# 此前直接 skip：卡关闭后方案「进度：」行永不更新（卡是 convert 转卡时写进关联卡的，永远命中此分支）。
new_cards = ", ".join(existing + [card_id]) if card_id not in existing else ", ".join(existing)
result = update_plan(Path("."), rel_path=rel_path, cards=new_cards)
if "error" in result:
    print(f"[warn] 方案关联卡同步失败: {result['error']}")
else:
    print(f"[ok] {card_id} 已加入方案 {plan_prefix}-plan-{plan_num} 关联卡: {new_cards}")
PY
}

approve_one() {
  local id="$1"
  local path stem branch
  path="$(resolve_card "$id")" || return 1
  stem="$(basename "$path" .md)"
  branch="codex/${stem}"

  echo "== 合入批准 ${id} (${branch}) =="
  print_external_repo_hint "$path" "$branch"

  # 架构漂移门禁（第三步）：合入前机械检查（卡头项目/退役端口/版本一致/死文件）
  if ! bash scripts/arch-drift-check.sh >/dev/null 2>&1; then
    echo "[error] 架构漂移门禁未通过——阻断合入。运行 bash scripts/arch-drift-check.sh 查看明细。" >&2
    return 1
  fi

  # 机审证据 = 分支信封（git show origin/<branch>:<卡路径> 含 机审：通过）
  # 分支存在时信封是唯一权威，不回退本地卡（消除本地回退后门）。
  git fetch origin main >/dev/null 2>&1
  git fetch origin "$branch" >/dev/null 2>&1 || true
  local audit_ok=false
  local has_branch=false
  if git rev-parse --verify "origin/${branch}" >/dev/null 2>&1; then
    has_branch=true
  fi

  if $has_branch; then
    # 分支存在 → 分支信封是唯一证据，不回退本地 docs/dispatch
    if git show "origin/${branch}:${path}" 2>/dev/null \
      | "$PYTHON_BIN" -c "
import sys
sys.path.insert(0, '.')
from server.board.models import machine_audit_passed_text
sys.exit(0 if machine_audit_passed_text(sys.stdin.read()) else 1)
"; then
      audit_ok=true
    fi
  elif [[ "$CLOSE_ONLY" == true ]]; then
    # close-only 且无分支：分支信封已不可得（已删/已合入）。机审真值走下方 ledger 校验，
    # 不再回退本地卡文机审区（2026-08-22 P0 硬化：卡文自写不算真值，防假关闭复发）。
    audit_ok=true
  fi
  if [[ "$audit_ok" != true ]]; then
    echo "[ERROR] ${id}: 分支信封无机审通过证据（origin/${branch} 卡无机审区，本地卡也无）" >&2
    return 1
  fi

  # V6：机审钉 commit——以分支上最后一个写入「机审：通过」信封的审计提交为漂移基准。
  # 支持多轮审计（审计就地修复 → 二次机审复核）：二次复核信封在首轮钉之后，取信封提交
  # 作基准而非首枚钉，避免「已复核修复」被误判为未复审漂移。基准之后出现非卡改动 = 漂移 → 拒绝。
  # 审计真实性由下方 ledger machine_audit_pass 门禁兜底（卡文自写不算），V6 只管「审计后是否漂移」。
  local last_env_commit="" _c
  for _c in $(git log --format='%H' "origin/${branch}" -- "$path" 2>/dev/null); do
    if git show "$_c" -- "$path" 2>/dev/null | grep -qE '^\+[[:space:]]*机审：通过'; then
      last_env_commit="$_c"
      break
    fi
  done
  # 钉完整性加固：最后一枚「被审」钉必须可解析且不晚于最后审计信封提交（防分支改写/信钉倒挂）。
  local pinned
  pinned="$(git show "origin/${branch}:${path}" 2>/dev/null | grep -oE '被审 [0-9a-f]{12}' | tail -1 || true)"
  if [[ -n "$pinned" ]]; then
    local pin_sha
    pin_sha="${pinned#被审 }"
    if ! git rev-parse --verify "${pin_sha}^{commit}" >/dev/null 2>&1; then
      echo "[ERROR] ${id}: 信封被审 commit ${pin_sha} 无法解析（分支可能已被改写）" >&2
      return 1
    fi
    if [[ -n "$last_env_commit" && "$pin_sha" != "$last_env_commit" ]] \
      && ! git merge-base --is-ancestor "$pin_sha" "$last_env_commit" >/dev/null 2>&1; then
      echo "[ERROR] ${id}: 被审钉 ${pin_sha} 不在最后审计信封提交 ${last_env_commit} 祖先链上 → 信封可信度异常" >&2
      return 1
    fi
  fi
  if [[ -n "$last_env_commit" ]]; then
    local drift_rc=0
    if git rev-parse --verify "origin/${branch}" >/dev/null 2>&1; then
      git diff --quiet "${last_env_commit}".."origin/${branch}" -- . ':(exclude)docs/dispatch/**' 2>/dev/null
      drift_rc=$?
    else
      echo "[WARN] ${id}: 本地无 ${branch} 分支，跳过本仓漂移检查（业务仓卡片由业务 ff-only 门禁守护）" >&2
      drift_rc=0
    fi
    if [[ "$drift_rc" -ne 0 ]]; then
      # 2026-08-22 P0 硬化：机审后漂移一律硬拒绝，--close-only 不再放行（防未复审代码合入）
      echo "[ERROR] ${id}: 机审后漂移——最后审计信封 ${last_env_commit} 之后分支存在非卡文件改动（diff rc=${drift_rc}），须重新机审（--close-only 不放行）" >&2
      return 1
    fi
  fi

  # 完成钩子（Doc-Gate）：维护区机械门禁，缺失/占位拒绝合入（校验分支信封）
  if ! check_maintenance "$path" "$branch"; then
    # 2026-08-22 P0 硬化：维护区失败一律硬拒绝，--close-only 不再放行（完成钩子不可绕过）
    echo "[ERROR] ${id}: 维护区未完成 → 拒绝合入。请执行体补齐 ## 维护区 四问后重试（--close-only 不放行）。" >&2
    return 1
  fi

  # 密钥/凭据扫描门禁（2026-08-16 质量门禁）：分支 diff 夹带密钥 → 阻断合入
  if ! check_secret_scan "$branch" "$id"; then
    return 1
  fi

  # P0-1a（2026-08-23）：机械范围核验——git diff 实际改动文件 vs 卡 ## 范围 白名单声明。
  # 不一致 = 硬拒绝（不是警告）。与 engine check_range_gate 同 whitelist 口径；
  # 证据 = 分支信封 diff（机审证据同源），不回退本地卡。
  if $has_branch && ! bash scripts/scope-check.sh "$path" "$branch"; then
    echo "[ERROR] ${id}: 范围核验未通过——分支改动文件超出卡 ## 范围 白名单 → 拒绝合入（P0-1a 硬门禁，--close-only 不放行）" >&2
    return 1
  fi

  # P0-1c（2026-08-23）：git 提交真实性核验——被审 pin 在分支上 + author 匹配执行体身份。
  if $has_branch && ! bash scripts/git-truth-check.sh "$path" "$branch"; then
    echo "[ERROR] ${id}: git 真实性核验未通过（被审 commit 不在分支 / author 不匹配 / 夹带他人提交）→ 拒绝合入（P0-1c 硬门禁）" >&2
    return 1
  fi

  # P0-1b（2026-08-23）：测试真实性机械核验——卡声明测试的真实退出码必须为 0（wrapper 截获日志）。
# 证据日志落 $EXECUTOR_LOG_DIR/<card_id>.test-evidence.log（与 dsh-* wrapper 同源，不信卡/机审区自述）。
# 无测试声明（no_test_declared）→ 放行；缺日志/真实失败 → 硬拒绝，--close-only 不放行。
check_test_evidence() {
  local id="$1"
  local log_dir="${EXECUTOR_LOG_DIR:-}"
  if [[ -z "$log_dir" ]]; then
    local cfg_path="${CCC_CONFIG_ENV:-}"
    if [[ -z "$cfg_path" ]]; then
      cfg_path="/Users/fan/program/CCC/server/config/config.env"
    fi
    if [[ -f "$cfg_path" ]]; then
      log_dir="$(grep -E '^\s*EXECUTOR_LOG_DIR\s*=' "$cfg_path" 2>/dev/null | tail -1 | cut -d= -f2- | tr -d '"' | tr -d "'" | xargs 2>/dev/null || true)"
    fi
  fi
  if [[ -z "$log_dir" ]]; then
    log_dir="$HOME/.ccc/logs/exec"
  fi
  # work_id == card_id（store.py），兼容大小写
  local cand1="${log_dir}/${id}.test-evidence.log"
  local cand2="${log_dir}/$(echo "$id" | tr '[:upper:]' '[:lower:]').test-evidence.log"
  local cand3="${log_dir}/$(echo "$id" | tr '[:lower:]' '[:upper:]').test-evidence.log"
  local evidence=""
  for cand in "$cand1" "$cand2" "$cand3"; do
    if [[ -f "$cand" ]]; then evidence="$cand"; break; fi
  done
  # 卡是否声明了测试（有则必须有证据）
  local has_test_declared=false
  if python3 - "$path" <<'PY' 2>/dev/null | grep -q "has_test"; then
import re, sys
from pathlib import Path
text = Path(sys.argv[1]).read_text(encoding="utf-8")
in_gate=False
has=False
for line in text.splitlines():
    s=line.strip()
    if s.startswith("## 门禁"):
        in_gate=True
        continue
    if in_gate:
        if s.startswith("## ") or s.startswith("---"):
            break
        if s.startswith("测试") and (":" in s or "：" in s):
            cmd=s.split(":",1)[1].strip() if ":" in s else s.split("：",1)[1].strip()
            cmd=cmd.strip("`").strip().strip("'").strip('"').strip()
            if cmd:
                has=True
                break
print("has_test" if has else "no_test")
PY
    has_test_declared=true
  fi
  # 无测试声明 → 不拦（与 test-evidence.sh 无可验语义一致）
  if [[ "$has_test_declared" != "true" ]]; then
    return 0
  fi
  if [[ -z "$evidence" ]]; then
    echo "[ERROR] ${id}: 缺测试真实性证据日志（${cand1} 不存在）→ 拒绝合入。卡声明了测试但无 wrapper 截获记录，请让 DSH 重跑机审/执行以生成 evidence log（P0-1b）。" >&2
    return 1
  fi
  if grep -q "no_test_declared" "$evidence" 2>/dev/null; then
    return 0
  fi
  if ! grep -q "exit_code=0" "$evidence" 2>/dev/null; then
    local rc
    rc="$(grep -oE 'exit_code=[0-9]+' "$evidence" 2>/dev/null | tail -1 || echo "exit_code=?")"
    echo "[ERROR] ${id}: 测试真实性核验失败（${rc}，证据 ${evidence}）→ 拒绝合入。卡声明测试真实失败，wrapper 已截获，不信卡回写区自述通过（P0-1b）。" >&2
    tail -20 "$evidence" 2>/dev/null | sed 's/^/  | /' >&2 || true
    return 1
  fi
  # 辅助标记检查：exit_code=0 但出现明显失败字样时告警但不硬拦（以退出码为准，避免误伤非 pytest 命令）
  return 0
}
if ! check_test_evidence "$id"; then
  echo "[ERROR] ${id}: 测试真实性核验未通过 → 拒绝合入（P0-1b 硬门禁，--close-only 不放行）" >&2
  return 1
fi

  # 033 阶段 2 M6：机审 provenance——查 ledger 有 machine_audit_pass ��录（不只信卡文件「机审：通过」文本）
  # 2026-08-19 硬化（断点③）：ledger 能力后的卡必须有机审 provenance，缺失=阻断。
  # 2026-08-22 单源化（P0-3）：日期边界由「卡文日期(可伪造)」改为「账本是否为空(伪造免疫)」。
  #   - 账本为空 = 账本能力前(pre-era) → 降级卡文机审区（旧卡兼容，可加 --close-only）
  #   - 账本已有记录但缺本卡 → 硬拒绝（卡文自写「机审：通过」不构成真值）
  # 根因：cla020-028 卡体写"机审通过"但 board flag=false + 无 ledger 记录，被 close-only 放行（假关闭事故）。
  if ! "$PYTHON_BIN" -c "
import sys
sys.path.insert(0, '.')
from server.board.audit_ledger import has_action, _machine_audit_pass_ids
if not _machine_audit_pass_ids():
    sys.exit(0)  # 账本为空（pre-era）→ 降级放行，卡文机审区作旧卡兼容
sys.exit(0 if has_action('machine_audit_pass', '${id}') else 1)
" 2>/dev/null; then
    echo "[ERROR] ${id}: 账本已有机审记录但缺本卡 machine_audit_pass（机审真值单源化：卡文自写不算）→ 拒绝合入。请先走机审（manual-audit.sh）留 ledger 记录，或 scripts/sync-audit-ledger.py 同步双机台账。" >&2
    return 1
  fi

  # 工作树须在 main
  current="$(git rev-parse --abbrev-ref HEAD)"
  if [[ "$current" != "main" ]]; then
    echo "[ERROR] 请在 main 上执行合入批准（当前：${current}）" >&2
    return 1
  fi
  git pull --ff-only origin main

  # 跨仓收口：业务仓分支先合业务 main + 删（分叉阻断整卡，杜绝「卡关闭≠代码落地」）
  # 2026-08-19 回退 b072a72a：--close-only 不再放行业务仓分叉——分叉=代码没合入main，
  # 必须阻断整卡让执行体 rebase，不存在"close-only 放行分叉"的合理场景。
  # （b072a72a 曾让 --close-only 绕过此阻断，制造 cla020-028 九卡假关闭事故）
  if ! close_business_repo "$path" "$branch"; then
    echo "[ERROR] ${id}: 业务仓收口失败（业务分支分叉/不可达）→ 整卡不合入（--close-only 也不放行分叉）。" >&2
    echo "  处理：让执行体把业务分支 rebase 到业务 main 后再「合入批准」。" >&2
    return 1
  fi

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
  # ★ 刷新 cards.index.jsonl：close_card 改了卡 .md 但索引未同步，sync_plan_progress 读旧索引会算 closed=0
  # （同 plans.py:748 范式：写卡后 load_dispatch_cards 刷新索引，让 sync 读到最新「已关闭」）
  "$PYTHON_BIN" -c "
import sys; sys.path.insert(0, '.')
from server.board.loader import load_dispatch_cards
load_dispatch_cards('docs/dispatch')
" 2>/dev/null || echo "[WARN] ${id}: 索引刷新失败（不阻断合入，sync 可能滞后）" >&2
  # 033 阶段 2 M6：合入成功写批准真值账本（approve_merge）——「老板合入批准」不再仅靠卡头批准行
  # 2026-08-22 P0 硬化：账本写失败 = 合入失败回滚（此前仅 WARN，三节点证据链断，审计不可追溯）
  if ! "$PYTHON_BIN" -c "
import sys
sys.path.insert(0, '.')
from server.board.audit_ledger import record_action
record_action('approve_merge', '${id}', source='approve-merge', detail='${branch}')
" 2>/dev/null; then
    echo "[ERROR] ${id}: approve_merge 账本写入失败 → 合入失败回滚（卡已置关闭未提交，已 git checkout 还原）" >&2
    git checkout -- "$path" 2>/dev/null || true
    return 1
  fi
  sync_plan_cards "$path"
  # 机审命中率台账（v4 · 2026-08-14 复审 P1-C）：合入后关卡（无返工）→ 通过行标命中
  "$PYTHON_BIN" -c "
import sys
sys.path.insert(0, '.')
try:
    from server.board.audit_ledger import mark_card_pass_hit
    mark_card_pass_hit(sys.argv[1])
except Exception:
    pass
" "$id" || true
  # S5（2026-08-22）：合入后 L1 质量分（增量不可劣化）——出分进 ledger，劣化则 WARN 报告
  if [ -f scripts/quality-score.py ]; then
    if "$PYTHON_BIN" scripts/quality-score.py . "${branch}" --record >/tmp/quality-${id}.json 2>&1; then
      echo "[OK] ${id} 质量分达标（见 /tmp/quality-${id}.json）"
    else
      echo "[WARN] ${id} 质量分劣化（增量不可劣化门禁，软告警）——见 /tmp/quality-${id}.json" >&2
    fi
  fi
  # 竞态防护（tst003 事故教训）：close_card 之后、git add 之前存在窗口，并发
  # server/git_sync.py:_force_align_dispatch 会按「远端 main（本批尚未推送）」强制对齐
  # docs/dispatch，把刚合入的卡改写回出卡占位版并被当真提交推送（净回退）。
  # 提交前断言卡头仍为「已关闭」，被并发改写则中止，杜绝静默回退入库。
  if ! grep -q "状态：已关闭" "$path"; then
    echo "[ERROR] ${id}: 合入竞态——close_card 后卡头非已关闭（疑似 git_sync 强制对齐并发改写工作树）→ 中止合入（不提交/不推送/不部署），请排除干扰后重跑" >&2
    return 1
  fi
  git add -- "$path"
  if ! git diff --cached --quiet; then
    git commit -m "$(cat <<EOF
merge: 合入批准 ${id}

EOF
)"
  fi

  # sidecar 同步：清除该卡的 sidecar 流程态
  "$PYTHON_BIN" - "$id" <<'PY'
import sys
sys.path.insert(0, ".")
from server.web.server import _executor_log_dir
from server.engine.runtime_state import clear_card_state

log_dir = _executor_log_dir()
if log_dir:
    clear_card_state(log_dir, sys.argv[1])
    print(f"[OK] sidecar 已同步：已清除卡 {sys.argv[1]} 的 sidecar 流程态")
else:
    print("[WARN] 未配置 EXECUTOR_LOG_DIR，跳过 sidecar 清除")
PY

  # 分支清理：已合入 main 的本地及远端分支自动删除，分叉分支保留并加日志
  if git rev-parse --verify "origin/${branch}" >/dev/null 2>&1; then
    # 注意：此时可能已经有其它修改被 commit，所以我们需要以 origin/main 作为合入对比基准
    if git merge-base --is-ancestor "origin/${branch}" origin/main >/dev/null 2>&1; then
      git branch -D "${branch}" >/dev/null 2>&1 || true
      if git push origin --delete "${branch}" >/dev/null 2>&1; then
        echo "[OK] 已删除已合入分支: ${branch}"
      else
        echo "[WARN] 远端分支删除失败（不影响合入）: ${branch}"
      fi
    else
      echo "[INFO] 分支 ${branch} 与 main 分叉（含有独立 diff），保留该分支"
    fi
  fi

  # 输出收口日志
  echo "收口完成：card=${id} 已关闭 + sidecar 已同步"

  git push origin main
  echo "[OK] 合入批准完成：${id} → 批次全部收口后将自动触发 2017 部署检查"
}

deploy_check_2017() {
  local prod_repo="${CCC_PROD_REPO:-/Users/fan/program/CCC}"
  echo "== 正在触发 2017 生产部署检查 =="

  # 1. 如果当前运行路径就是 2017 生产目录，直接本地执行 deploy-ccc.sh
  if [[ "${PROJECT_ROOT}" == "${prod_repo}" ]]; then
    echo "[INFO] 当前已在 2017 生产目录中，直接运行部署流程..."
    if "${prod_repo}/scripts/deploy-ccc.sh"; then
      echo "[OK] 2017 生产部署成功！"
    else
      echo "[ERROR] 2017 生产部署失败！" >&2
      return 1
    fi
    return 0
  fi

  # 2. 如果在本地能找到 2017 生产目录（说明在同一个系统的其它 worktree 里）
  if [[ -d "${prod_repo}/.git" ]]; then
    echo "[INFO] 检测到本地 2017 生产目录，检查是否需要同步部署..."
    git -C "${prod_repo}" fetch -q origin >/dev/null 2>&1 || true
    local prod_h remote_h
    prod_h="$(git -C "${prod_repo}" rev-parse HEAD 2>/dev/null || echo '')"
    remote_h="$(git -C "${prod_repo}" rev-parse origin/main 2>/dev/null || echo '')"
    if [[ -n "$prod_h" && "$prod_h" != "$remote_h" ]]; then
      echo "[INFO] 2017 生产 HEAD (${prod_h:0:7}) 落后于 origin/main (${remote_h:0:7})，开始部署..."
      if "${prod_repo}/scripts/deploy-ccc.sh"; then
        echo "[OK] 2017 生产部署成功！"
      else
        echo "[ERROR] 2017 生产部署失败！" >&2
        return 1
      fi
    else
      echo "[OK] 2017 生产已经是最新 (${prod_h:0:7})，无需部署。"
    fi
    return 0
  fi

  # 3. 如果本地没有该目录，尝试通过 SSH 到 2017 生产机进行检查
  echo "[INFO] 本地未找到 2017 生产目录，尝试通过 SSH 检查 ${CCC_SSH_HOST}..."
  local ssh_cmd="ssh -o BatchMode=yes -o ConnectTimeout=5 ${CCC_SSH_HOST}"
  if ! $ssh_cmd "echo ping" >/dev/null 2>&1; then
    echo "[WARN] 无法 SSH 连接 ${CCC_SSH_HOST}，跳过 2017 部署检查。"
    return 0
  fi

  local check_cmd="cd ${prod_repo} && git fetch -q origin && prod_h=\$(git rev-parse HEAD) && remote_h=\$(git rev-parse origin/main) && if [[ \"\$prod_h\" != \"\$remote_h\" ]]; then echo 'BEHIND'; else echo 'UP_TO_DATE'; fi"
  local res
  res=$($ssh_cmd "${check_cmd}" 2>/dev/null || echo "ERROR")
  if [[ "$res" == "BEHIND" ]]; then
    echo "[INFO] 2017 生产落后于 origin/main，通过 SSH 执行部署..."
    if $ssh_cmd "cd ${prod_repo} && ./scripts/deploy-ccc.sh"; then
      echo "[OK] 2017 生产通过 SSH 部署成功！"
    else
      echo "[ERROR] 2017 生产通过 SSH 部署失败！" >&2
      return 1
    fi
  elif [[ "$res" == "UP_TO_DATE" ]]; then
    echo "[OK] 2017 生产通过 SSH 检查：已经是最新，无需部署。"
  else
    echo "[WARN] 通过 SSH 检查 2017 生产状态失败，返回值为: ${res}"
  fi
}

# 螺旋上升 P2-1：合入后即时触发 DSH 全局跑通复核（B1，approve-merge 钩子）
# 复用 deploy_check_2017 的 SSH 结构；fire-and-forget 后台不阻塞收尾。
trigger_dsh_patrol() {
  local host="${CCC_SSH_HOST:-fan@192.168.3.116}"
  local ssh_cmd="ssh -o BatchMode=yes -o ConnectTimeout=5 ${host}"
  if ! $ssh_cmd "echo ping" >/dev/null 2>&1; then
    echo "[WARN] 无法 SSH 连接 ${host}，跳过合入后 DSH 复核触发。"
    return 0
  fi
  echo "[INFO] 触发合入后 DSH 全局跑通复核（${host}，后台执行，结果进巡检页）..."
  # 后台 + nohup，合入收尾不被 DSH 运行阻塞（DSH 全量核实需数分钟）
  $ssh_cmd "cd /Users/fan && nohup /bin/bash /Users/fan/.dsh/run_patrol.sh >> /Users/fan/.dsh/patrol_merge.log 2>&1 &" >/dev/null 2>&1 \
    && echo "[OK] DSH 全局跑通复核已触发（结果 ~数分钟 后进巡检页）" \
    || echo "[WARN] DSH 复核触发命令执行失败"
  return 0
}

# ── C2: 待合入积压提醒 ──
"$PYTHON_BIN" -c "
import os, sys
sys.path.insert(0, '.')
try:
    from server.board.loader import load_dispatch_cards
    from server.board.queries import ready_for_merge
    items = load_dispatch_cards('docs/dispatch')
    payload = ready_for_merge(items)
    warning = payload.get('warning')
    if warning:
        print('\n' + '='*60, file=sys.stderr)
        print('[ALERT] ' + warning, file=sys.stderr)
        print('='*60 + '\n', file=sys.stderr)
except Exception as e:
    pass
" || true

# R6（2026-08-22 S1 单机化）：双机台账同步已废弃（CCC 全在 2017，合入读本地 ledger 即权威）。
# sync-audit-ledger.py 保留仅作历史；不再从 approve-merge 调用。

# P0-1d（2026-08-23）：环节②抽验——每批≥1张 + 每5张抽1张（20% 随机），每次合入时执行。
# 执行方=环节②（本脚本），不在 DSH 内。抽样种子取批次 ID 哈希，避免被操纵挑卡。
_SPOT_SAMPLED=()
if [[ ${#IDS[@]} -gt 0 && -x scripts/spot-check.sh ]]; then
  _spot_n=${#IDS[@]}
  _spot_cnt=$(( (_spot_n + 4) / 5 ))
  if [[ $_spot_cnt -lt 1 ]]; then _spot_cnt=1; fi
  if [[ $_spot_cnt -gt $_spot_n ]]; then _spot_cnt=$_spot_n; fi
  _spot_seed="$(printf '%s\n' "${IDS[@]}" | sort | tr -d '\n' | cksum | awk '{print $1}')"
  _spot_py_out="$(python3 - "${IDS[@]}" -- "${_spot_cnt}" "${_spot_seed}" <<'PY'
import random, sys
args = sys.argv[1:]
try:
    sep = args.index("--")
except ValueError:
    sep = len(args) - 2
ids = args[:sep]
cnt = int(args[sep+1]) if sep+1 < len(args) else 0
seed = int(args[sep+2]) if sep+2 < len(args) else 0
random.seed(seed)
k = min(cnt, len(ids))
print("\n".join(random.sample(ids, k) if k else []))
PY
)"
  _SPOT_SAMPLED=()
  while IFS= read -r _spot_line; do
    [[ -n "$_spot_line" ]] && _SPOT_SAMPLED+=("$_spot_line")
  done <<< "$_spot_py_out"
  if [[ ${#_SPOT_SAMPLED[@]} -gt 0 ]]; then
    echo "== 环节②抽验（P0-1d）：本批 ${#IDS[@]} 张中抽 ${#_SPOT_SAMPLED[@]} 张 → ${_SPOT_SAMPLED[*]} =="
    _SPOT_FAIL=0
    for _sid in "${_SPOT_SAMPLED[@]}"; do
      if ! bash scripts/spot-check.sh "$_sid"; then
        echo "[ERROR] spot-check ${_sid} 未通过 → 本批合入阻断（环节②抽验不通过，打回重做）" >&2
        _SPOT_FAIL=1
      fi
    done
    if [[ $_SPOT_FAIL -ne 0 ]]; then
      echo "[ERROR] 环节②抽验失败（${#_SPOT_SAMPLED[@]} 张中至少 1 张不通过）→ 拒绝整批合入" >&2
      exit 1
    fi
    echo "[OK] 环节②抽验全部通过（${#_SPOT_SAMPLED[@]} 张）"
  fi
fi

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

# ── 业务仓部署端健康检查（2026-08-20 加 · 覆盖所有已注册项目）──
# 部署端表与 qx-map AGENTS.md「项目部署端一览」一致：开发机≠部署机。
# 规则：部署端不健康 = 告警并提示（不阻断合卡，但回执必须明确）。
deploy_check_business() {
  local ssh_2017="ssh -o BatchMode=yes -o ConnectTimeout=5 ${CCC_SSH_HOST}"
  echo "== 正在检查关联业务仓部署端健康 =="
  local checked=""
  for id in "${IDS[@]}"; do
    local prefix="${id%%[0-9]*}"
    [[ -z "$prefix" || "$checked" == *" $prefix "* ]] && continue
    checked="$checked $prefix "
    case "$prefix" in
      ccc|cla|clw|cd|hp*|qb|xy|mx)
        ;;
      *)
        echo "[INFO] ${prefix}: 未知项目前缀，跳过部署端检查。"
        continue
        ;;
    esac
    case "$prefix" in
      xy)
        # 部署端 = Mac2017 :8765 admin API
        local xy_ok
        xy_ok=$($ssh_2017 "curl -s -o /dev/null -w '%{http_code}' --max-time 8 http://127.0.0.1:8765/api/health 2>/dev/null || echo 000" 2>/dev/null || echo SKIP)
        if [[ "$xy_ok" =~ ^(200|401|404)$ ]]; then
          echo "[OK] xy 部署端健康（2017:8765 HTTP ${xy_ok}）"
        else
          echo "[WARN] xy 部署端异常（2017:8765 → ${xy_ok}）——admin 服务可能未运行或未重启，需人工确认！"
        fi
        ;;
      mx)
        # 部署端 = HP :3000 medio-server（M1/2017 均 HTTP 直连）
        local mx_ok
        mx_ok=$(curl -s -o /dev/null -w '%{http_code}' --max-time 8 http://192.168.3.131:3000/api/v1/health 2>/dev/null || echo 000)
        if [[ "$mx_ok" == "200" ]]; then
          echo "[OK] mx 部署端健康（HP:3000 HTTP 200）"
        else
          echo "[WARN] mx 部署端异常（HP:3000 → ${mx_ok}）——medio-server 未运行，需人工确认！"
        fi
        ;;
      hp)
        # 部署端 = HP :8082/:8083（M1 SSH 密钥缺失，走 HTTP 直连）
        local hp_ok
        hp_ok=$(curl -s -o /dev/null -w '%{http_code}' --max-time 8 http://192.168.3.131:8082/ 2>/dev/null || echo 000)
        if [[ "$hp_ok" =~ ^(200|404)$ ]]; then
          echo "[OK] hp 部署端可达（HP:8082 HTTP ${hp_ok}）"
        else
          echo "[WARN] hp 部署端异常（HP:8082 → ${hp_ok}）——memory-store 未运行，需人工确认！"
        fi
        ;;
      qb)
        echo "[INFO] qb: 自动化测试项目，无常驻生产服务，跳过部署端检查。"
        ;;
      ccc|cla|clw|cd)
        echo "[INFO] ${prefix}: CCC 底座位卡，部署端检查已由 deploy_check_2017 覆盖。"
        ;;
    esac
  done
}

if [[ ${#IDS[@]} -gt 0 ]]; then
  deploy_check_2017
  deploy_check_business
  # DSH 全局跑通复核触发去重（2026-08-20）：合入后复核由 2017 scheduler 的
  # merge_sha 去重触发承担（server/engine/scheduler.py），此处的无条件触发停用，
  # 避免一次合入双触发；6h cron 作为定时兜底。函数定义保留供手动复用。
  # trigger_dsh_patrol
fi
