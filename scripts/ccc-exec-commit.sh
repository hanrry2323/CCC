#!/bin/bash
# ccc-exec-commit.sh — Executor 退出后自动 commit（替代 LLM 做机械操作）
#
# 职责：读 phases.json → git add scope 文件 → commit → 回写 hash
# 用法：
#   ccc-exec-commit.sh <workspace> <task>              # 处理所有待 commit phase
#   ccc-exec-commit.sh <workspace> <task> --phase N    # 仅处理指定 phase
#
# 幂等：已填 commit hash 的 phase 自动 skip
# 退出码：0=全部完成 / 1=部分失败 / 2=参数错误

set -euo pipefail

# --help 优先（不需要 2 个参数）
if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    echo "ccc-exec-commit.sh — Executor 退出后自动 commit"
    echo ""
    echo "用法:"
    echo "  ccc-exec-commit.sh <workspace> <task>              # 所有待 commit phase"
    echo "  ccc-exec-commit.sh <workspace> <task> --phase N    # 仅指定 phase"
    echo ""
    echo "退出码: 0=全部完成  1=部分失败  2=参数错误"
    exit 0
fi

if [[ $# -lt 2 ]]; then
    echo "用法: ccc-exec-commit.sh <workspace> <task> [--phase N]" >&2
    echo "查看帮助: ccc-exec-commit.sh --help" >&2
    exit 2
fi

WORKSPACE="$1"
TASK="$2"
PHASES_FILE="$WORKSPACE/.ccc/phases/$TASK.phases.json"
PHASE_FILTER=""
shift 2

while [[ $# -gt 0 ]]; do
    case "$1" in
        --phase)
            PHASE_FILTER="$2"
            shift 2
            ;;
        --help|-h)
            echo "ccc-exec-commit.sh — Executor 退出后自动 commit"
            echo ""
            echo "用法:"
            echo "  ccc-exec-commit.sh <workspace> <task>              # 所有待 commit phase"
            echo "  ccc-exec-commit.sh <workspace> <task> --phase N    # 仅指定 phase"
            echo ""
            echo "退出码: 0=全部完成  1=部分失败  2=参数错误"
            exit 0
            ;;
        *)
            echo "未知参数: $1" >&2
            exit 2
            ;;
    esac
done

# --- 验证 ---
if [[ ! -f "$PHASES_FILE" ]]; then
    echo "❌ phases.json 不存在: $PHASES_FILE" >&2
    exit 2
fi

cd "$WORKSPACE"
if ! git rev-parse --git-dir >/dev/null 2>&1; then
    echo "❌ $WORKSPACE 不是 git 仓库" >&2
    exit 2
fi

# 检查有无已暂存未提交（避免与外部脚本混合）
CACHED=$(git diff --cached --name-only 2>/dev/null | wc -l | tr -d ' ')
if [[ "$CACHED" -gt 0 ]]; then
    echo "⚠️  工作区已有已暂存未提交的文件 ($CACHED 个)，跳过" >&2
    echo "   请先处理: git diff --cached --name-only" >&2
    exit 1
fi

# --- 解析 phases.json ---
python3 - "$PHASES_FILE" "$PHASE_FILTER" "$WORKSPACE" <<'PYEOF'
import json, os, subprocess, sys

fp = sys.argv[1]
phase_filter = sys.argv[2] if sys.argv[2] else None
workspace = sys.argv[3] if len(sys.argv) > 3 else os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(fp))))

with open(fp) as f:
    data = json.load(f)

# --- 红线 15: 读取顶层 task_id 字段 ---
task_id = data.get('task_id', '').strip()
if not task_id:
    print("  ❌ phases.json 缺少顶层 'task_id' 字段（红线 15 强制）")
    sys.exit(1)

# --- 红线 15: 幂等检测：git log 中已有同 task_id 的 commit 则整体跳过 ---
# re-run 命中 fast-forward，不产生重复 commit
try:
    grep_pattern = "ccc-task-id=" + task_id
    existing = subprocess.run(
        ["git", "log", "--grep=" + grep_pattern, "--oneline", "-1"],
        cwd=workspace, capture_output=True, text=True
    )
    if existing.returncode == 0 and existing.stdout.strip():
        first_token = existing.stdout.strip().split()[0] if existing.stdout.strip() else ""
        print("  ⏭  IDEMPOTENT: task 已提交 (ccc-task-id=" + task_id + ")，跳过整次 commit")
        print("     已有 commit: " + first_token)
        sys.exit(0)
except Exception as e:
    # git log 失败不应阻断流程，继续往下走
    print("  ⚠️  git log 幂等检测失败 (exit " + str(e) + ")，继续执行")

phases = data.get('phases', [])
if not phases:
    sys.exit(0)
changed = False
errors = 0
all_committed_scopes = []

for p in phases:
    pid = p.get('id')
    status = p.get('status', '')
    existing_commit = p.get('commit')

    # 按 --phase 过滤
    if phase_filter and str(pid) != str(phase_filter):
        continue

    # 只处理 done/in_progress/verified 但无 commit hash 的 phase
    if status not in ('done', 'in_progress', 'verified'):
        print(f"  ○ phase {pid}: status={status} → skip")
        continue
    if existing_commit and existing_commit not in ('null', 'None', ''):
        print(f"  ✓ phase {pid}: 已有 commit {existing_commit[:12]} → skip (幂等)")
        continue

    scope = p.get('scope') or p.get('expected_files', [])
    commit_msg = p.get('commit_message', '').strip()

    # --- 红线 15: 标记检测：commit_message 必须含 ccc-task-id=<task_id> ---
    marker = f"ccc-task-id={task_id}"
    if marker not in commit_msg:
        print(f"  ❌ phase {pid}: commit_message 缺少标记 '{marker}'（红线 15 强制）")
        print(f"     当前 message: {commit_msg[:60]}")
        errors += 1
        continue

    if not scope:
        print(f"  ❌ phase {pid}: scope 为空，跳过（无安全 fallback）")
        errors += 1
        continue
    else:
        print(f"  → phase {pid}: git add {len(scope)} 文件")
        scope_marker = "-- " + " ".join(scope)

    if not commit_msg:
        print(f"  ⚠️  phase {pid}: commit_message 为空，使用默认消息")
        commit_msg = f"chore({os.path.basename(workspace)}): phase {pid} auto-commit"

    # B3: scope 重叠阻断（多 phase 改同一文件时前 phase 改动会污染当前 phase）
    if scope and pid > 1:
        overlap_detected = False
        for prev_scope in all_committed_scopes:
            overlap = set(scope) & set(prev_scope)
            if overlap:
                print(f"  ❌ phase {pid}: scope 与之前 phase 重叠: {overlap}")
                print(f"     Git working tree 线性，同一文件跨 phase 改会污染 commit")
                overlap_detected = True
        if overlap_detected:
            errors += 1
            continue

    # git add
    if scope_marker == "--all":
        rc = subprocess.call(["git", "add", "--all"], cwd=workspace)
    else:
        rc = subprocess.call(["git", "add"] + scope, cwd=workspace)
    if rc != 0:
        print(f"  ❌ phase {pid}: git add 失败 (exit {rc})")
        errors += 1
        continue

    # Check if anything was actually staged
    staged = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=workspace, capture_output=True, text=True
    ).stdout.strip()
    if not staged:
        print(f"  ○ phase {pid}: 无改动需 commit → skip")
        if scope_marker != "--all":
            # 回退 unstage 以免影响后续 phase
            subprocess.call(["git", "reset", "HEAD"] + scope, cwd=workspace,
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        continue

    # git commit
    rc = subprocess.call(
        ["git", "commit", "-m", commit_msg],
        cwd=workspace,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    if rc != 0:
        print(f"  ❌ phase {pid}: commit 失败 (exit {rc})")
        # unstage to avoid lock
        subprocess.call(["git", "reset", "HEAD"], cwd=workspace,
                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        errors += 1
        print(f"    停止处理后续 phase — 修复后重新执行")
        break

    # 取 hash
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=workspace, capture_output=True, text=True
    )
    commit_hash = result.stdout.strip()

    # 写回 phases.json
    p['commit'] = commit_hash
    changed = True
    all_committed_scopes.append(scope)
    print(f"  ✓ phase {pid}: committed {commit_hash[:12]} — {commit_msg[:50]}")

if changed:
    with open(fp, 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write('\n')
    print(f"  ✅ phases.json 已更新: {fp}")

sys.exit(0 if errors == 0 else 1)
PYEOF
EXIT_CODE=$?
exit $EXIT_CODE
