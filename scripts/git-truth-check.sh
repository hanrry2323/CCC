#!/usr/bin/env bash
# ── scripts/git-truth-check.sh ──
# git 提交真实性核验（P0-1c · 2026-08-23）
#
# 用途：验证卡片声称的「被审 <sha>」（机审钉 commit）是否真实存在于对应分支：
#   1) 被审 sha 可解析为 commit；
#   2) 该 commit 是 origin/<branch> 的祖先（真在分支上，非凭空编造）；
#   3) 该 commit 的 author 匹配执行体身份（CCC Dev <ccc-dev@localhost>）——
#      机审钉必须是 DSH 执行体产出的 commit，不是他人/伪造署名；
#   4) 分支上所有「非卡文件」提交的 author 也必须匹配执行体身份
#      （杜绝夹带他人 commit / 手工提交混入业务分支）。
#
# 改动文件 vs 卡 ## 范围 白名单 的一致性由 scripts/scope-check.sh（P0-1a）承担，
# 两者合流构成「git 真实性 + 范围合规」双门禁。
#
# 用法：
#   scripts/git-truth-check.sh <card_path> <branch>
#     card_path 本地卡文件路径（仅取相对路径；信封内容走分支）
#     branch    分支名（codex/<stem>）
#
# 退出码：0 = 通过（含无 pin 的旧卡）；1 = 真实性核验失败；2 = 分支/环境不可读。
#
# 审核红线自洽：证据 = 分支信封 git 对象（git cat-file/git log），不回退本地卡文本。

set -euo pipefail

CARD_PATH="${1:?缺 card_path}"
BRANCH="${2:?缺 branch}"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# 期望的执行体身份（机审钉/业务提交 author 必须匹配；可经 CCC_EXEC_AUTHOR 覆盖）
EXPECTED_AUTHOR="${CCC_EXEC_AUTHOR:-CCC Dev <ccc-dev@localhost>}"

# 卡文件相对路径
REL_CARD="${CARD_PATH#$PROJECT_ROOT/}"
if [[ "$REL_CARD" == "$CARD_PATH" ]]; then
  REL_CARD="${CARD_PATH#./}"
fi

if ! git rev-parse --verify "origin/${BRANCH}" >/dev/null 2>&1; then
  echo "[ERROR] origin/${BRANCH} 不可读（git-truth-check）" >&2
  exit 2
fi

python3 - "$BRANCH" "$REL_CARD" "$EXPECTED_AUTHOR" <<'PY'
import re, subprocess, sys

branch, rel_card, expected_author = sys.argv[1], sys.argv[2], sys.argv[3]

def git(*args):
    return subprocess.check_output(["git", *args], text=True).strip()

# 1) 信封机审钉
card = git("show", f"origin/{branch}:{rel_card}")
m = re.search(r"被审\s+([0-9a-f]{7,40})", card)
if not m:
    print("[INFO] git-truth-check: 卡无「被审 <sha>」机审钉（旧卡未 pin），无可验证——放行（V6 pin 漂移检查对无 pin 卡不生效）")
    sys.exit(0)
pin = m.group(1)

# 2) pin 可解析为 commit
try:
    pin_full = git("rev-parse", f"{pin}^{{commit}}")
except subprocess.CalledProcessError:
    print(f"[ERROR] 被审 commit {pin} 无法解析为 commit（分支可能被改写/伪造）", file=sys.stderr)
    sys.exit(1)

# 3) pin 是 origin/<branch> 的祖先（真在分支上）
r = subprocess.run(
    ["git", "merge-base", "--is-ancestor", pin_full, f"origin/{branch}"],
    capture_output=True,
)
if r.returncode != 0:
    print(
        f"[ERROR] 被审 {pin_full[:12]} 不是 origin/{branch} 的祖先——声称的 commit 不在该分支上（真实性失败）",
        file=sys.stderr,
    )
    sys.exit(1)

# 4) pin 的 author 匹配执行体身份
pin_author = git("log", "-1", "--format=%an <%ae>", pin_full)
if pin_author != expected_author:
    print(
        f"[ERROR] 被审 commit author 不匹配执行体身份：got={pin_author} want={expected_author}",
        file=sys.stderr,
    )
    sys.exit(1)

# 5) 分支上所有非卡文件提交的 author 也必须匹配（夹带他人 commit = 拒绝）
bad_authors = []
for line in git("log", "--format=%H%x09%an <%ae>", f"origin/main..origin/{branch}").splitlines():
    sha, author = line.split("\t", 1)
    if author != expected_author:
        files = git("show", "--name-only", "--format=", sha).splitlines()
        business = [f for f in files if not f.endswith(".running") and not f.endswith(".tmp")
                    and not f.endswith(".log") and not (f == rel_card or f.endswith("/" + rel_card))]
        if business:
            bad_authors.append(f"{sha[:12]} {author} ({len(business)} 非卡文件)")
if bad_authors:
    print(
        f"[ERROR] 分支存在非执行体身份的提交且含业务文件改动（{len(bad_authors)} 个）：\n  " + "\n  ".join(bad_authors[:10]),
        file=sys.stderr,
    )
    sys.exit(1)

print(f"[OK] git 真实性核验通过：被审 {pin_full[:12]} 在 origin/{branch} 上，author={pin_author}，分支全部业务提交 author 匹配")
sys.exit(0)
PY
