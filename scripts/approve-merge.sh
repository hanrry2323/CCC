#!/usr/bin/env bash
# ── CCC：合入批准（北星 W2 · 人审 diff 后唯一常规动作）──
#
# 用法：
#   scripts/approve-merge.sh <card-id> [<card-id>...]
#   scripts/approve-merge.sh --ready              # 批处理 2017 ready_for_merge 队列
#   scripts/approve-merge.sh --close-only <id>    # 分支已分叉/已合入时仅关卡（ready 必需）
#
# 校验：机审通过（本地卡或 API）+ origin/codex/<stem> 存在。
# 动作：跨仓收口——业务仓分支先 ff 合入业务 main + 删（分叉阻断整卡）；
#       CCC 仓能 ff 则 ff-merge；否则 --close-only / 分支已在 main → 只关卡。
#       【合入后须部署检查】：成功合入后自动检查 2017 生产 vs 主干，落后则触发热重启部署。
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
        if machine_audit_passed_text(card):
            m = re.match(r"^([a-z]{2,4}\d{3})-", Path(f).stem)
            if m:
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

# 完成钩子（Doc-Gate）机械门禁：维护区四问必须勾选且说明非空
check_maintenance() {
  local path="$1"
  "$PYTHON_BIN" -c "
import sys
from pathlib import Path
sys.path.insert(0, '.')
from server.board.docgate import verify_maintenance
ok, problems = verify_maintenance(sys.argv[1], '.')
if not ok:
    print('[ERROR] 完成钩子（维护区声明不实）：' + '；'.join(problems), file=sys.stderr)
    sys.exit(1)
print('[OK] 完成钩子：维护区四问已勾选且说明完整')
sys.exit(0)
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

# 跨仓收口：业务仓分支 ff 合入业务 main + 删分支（分叉则阻断整卡合入）
close_business_repo() {
  local path="$1" branch="$2"
  "$PYTHON_BIN" - "$path" "$branch" <<'PY'
import re, subprocess, sys
from pathlib import Path

sys.path.insert(0, ".")
from server.board.registry import load_projects

card = Path(sys.argv[1])
branch = sys.argv[2]
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
            "fan@192.168.3.116",
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

  # 机审证据 = 分支信封（git show origin/<branch>:<卡路径> 含 机审：通过）
  git fetch origin main >/dev/null 2>&1
  git fetch origin "$branch" >/dev/null 2>&1 || true
  local audit_ok=false
  if git rev-parse --verify "origin/${branch}" >/dev/null 2>&1 \
    && git show "origin/${branch}:${path}" 2>/dev/null \
      | "$PYTHON_BIN" -c "
import sys
sys.path.insert(0, '.')
from server.board.models import machine_audit_passed_text
sys.exit(0 if machine_audit_passed_text(sys.stdin.read()) else 1)
"; then
    audit_ok=true
  elif check_audit "$path"; then
    # 已合入/无分支（close-only）场景：本地卡机审区
    audit_ok=true
  fi
  if [[ "$audit_ok" != true ]]; then
    echo "[ERROR] ${id}: 分支信封无机审通过证据（origin/${branch} 卡无机审区，本地卡也无）" >&2
    return 1
  fi

  # 完成钩子（Doc-Gate）：维护区机械门禁，缺失/占位拒绝合入
  if ! check_maintenance "$path"; then
    echo "[ERROR] ${id}: 维护区未完成 → 拒绝合入。请执行体补齐 ## 维护区 四问后重试。" >&2
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
  if ! close_business_repo "$path" "$branch"; then
    echo "[ERROR] ${id}: 业务仓收口失败（业务分支分叉/不可达）→ 整卡不合入。" >&2
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
  local prod_repo="/Users/fan/program/CCC"
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
  echo "[INFO] 本地未找到 2017 生产目录，尝试通过 SSH 检查 192.168.3.116..."
  local ssh_cmd="ssh -o BatchMode=yes -o ConnectTimeout=5 fan@192.168.3.116"
  if ! $ssh_cmd "echo ping" >/dev/null 2>&1; then
    echo "[WARN] 无法 SSH 连接 192.168.3.116，跳过 2017 部署检查。"
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

if [[ ${#IDS[@]} -gt 0 ]]; then
  deploy_check_2017
fi
