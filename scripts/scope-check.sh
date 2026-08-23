#!/usr/bin/env bash
# ── scripts/scope-check.sh ──
# 机械范围核验（P0-1a · 2026-08-23）
#
# 用途：比对「分支实际改动文件列表」vs「卡 ## 范围 白名单声明」，
#       不一致 = 范围越界 → 退出码非 0（approve-merge 硬拒绝，非警告）。
#       与 engine check_range_gate（server/engine/main.py）同一 whitelist 口径：
#       ## 范围 节内 `反引号` 路径 = 白名单；含 不动/保持/不改/禁止/不碰 的行跳过。
#
# 用法：
#   scripts/scope-check.sh <card_path> <branch>
#     card_path 本地卡文件路径（仅用于取卡文件相对路径；范围内容走分支信封）
#     branch    分支名（如 codex/xy060-xxx）——diff 基准 origin/main..origin/<branch>
#
# 退出码：0 = 范围内 / 无白名单声明（空=不拦，与 engine 一致）；1 = 范围越界；2 = 分支不可读。
#
# 审核红线自洽：范围证据 = 分支信封 git diff（机审证据同源），不回退本地卡。

set -euo pipefail

CARD_PATH="${1:?缺 card_path}"
BRANCH="${2:?缺 branch}"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# 卡文件相对路径（repo 内）
REL_CARD="${CARD_PATH#$PROJECT_ROOT/}"
if [[ "$REL_CARD" == "$CARD_PATH" ]]; then
  REL_CARD="${CARD_PATH#./}"
fi

# 分支信封可读性
if ! git rev-parse --verify "origin/${BRANCH}" >/dev/null 2>&1; then
  echo "[ERROR] origin/${BRANCH} 不可读（scope-check）" >&2
  exit 2
fi

# 从分支信封提取 ## 范围 白名单（与 engine check_range_gate 同源实现）
python3 - "$BRANCH" "$REL_CARD" <<'PY'
import fnmatch, re, subprocess, sys
from pathlib import Path

branch, rel_card = sys.argv[1], sys.argv[2]

def git(*args):
    return subprocess.check_output(["git", *args], text=True).strip()

# 1) 分支信封卡内容
card = git("show", f"origin/{branch}:{rel_card}")

# 2) 提取 ## 范围 节
lines = card.splitlines()
range_lines, in_range = [], False
for line in lines:
    s = line.strip()
    if s.startswith("## 范围"):
        in_range = True
        continue
    if in_range:
        if s.startswith("## ") or s.startswith("---"):
            break
        range_lines.append(line)

whitelist = []
if in_range:
    for line in range_lines:
        if any(kw in line for kw in ["不动", "保持", "不改", "禁止", "不碰"]):
            continue
        for m in re.findall(r"`([^`]+)`", line):
            m2 = m.strip()
            if m2:
                whitelist.append(m2)

# 无白名单声明 → 不拦截（与 engine 一致），输出说明供人审参考
if not whitelist:
    print("[INFO] scope-check: 卡无 ## 范围 白名单声明（engine 同口径：不拦），请人审核对 diff")
    sys.exit(0)

def match_path(f, p):
    if fnmatch.fnmatch(f, p):
        return True
    p_dir = p if p.endswith("/") else p + "/"
    return f.startswith(p_dir)

# 3) 分支实际改动文件（相对 main）
out = subprocess.run(
    ["git", "diff", "--name-only", "origin/main", f"origin/{branch}"],
    capture_output=True, text=True,
)
if out.returncode != 0:
    print("[ERROR] git diff origin/main..branch 失败", file=sys.stderr)
    sys.exit(2)
modified = [f for f in out.stdout.splitlines() if f.strip()]

out_of_scope = []
for f in modified:
    # 豁免仅限卡文件本身（与 engine check_range_gate 同口径：按路径或 basename）
    if f == rel_card or Path(f).name == Path(rel_card).name:
        continue
    if f.endswith(".running") or f.endswith(".tmp") or f.endswith(".log"):
        continue
    if any(match_path(f, p) for p in whitelist):
        continue
    out_of_scope.append(f)

if out_of_scope:
    print(
        f"[ERROR] 范围越界：分支 origin/{branch} 改动文件不在卡 ## 范围 白名单内\n"
        f"  越界文件: {sorted(set(out_of_scope))}\n"
        f"  白名单声明: {whitelist}",
        file=sys.stderr,
    )
    sys.exit(1)

print(f"[OK] 范围核验通过：{len(modified)} 个改动文件均在白名单内（{whitelist}）")
sys.exit(0)
PY
