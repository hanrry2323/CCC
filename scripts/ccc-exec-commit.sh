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

# --- post-exec 标记检查 ---
# 如果 post-exec 钩子已 git add -A && git commit，跳过整次 exec-commit
COMMIT_MARKER_DIR="$HOME/.ccc/committed-phases"
if [[ -d "$COMMIT_MARKER_DIR" ]]; then
    MATCHING=$( (ls "$COMMIT_MARKER_DIR/${TASK}"*.marker 2>/dev/null || true) | wc -l | tr -d ' ')
    if [[ -n "$MATCHING" && "$MATCHING" -gt 0 ]]; then
        echo "post-exec 已提交（${MATCHING} 个标记），跳过 exec-commit"
        exit 0
    fi
fi

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
    exit 0  # soft skip, not hard block
fi

# --- 解析 phases.json ---
python3 - "$PHASES_FILE" "$PHASE_FILTER" "$WORKSPACE" <<'PYEOF'
import json, os, subprocess, sys

fp = sys.argv[1]
phase_filter = sys.argv[2] if sys.argv[2] else None
workspace = sys.argv[3] if len(sys.argv) > 3 else os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(fp))))


def _write_phases(path, data, orig_format):
    """Write phases.json preserving the original input format.

    Bug fix (historical task phase 1, 2026-07): previously ccc-exec-commit
    always wrote `{"phases": [...]}` JSON wrapper, causing JSONL →
    JSON format drift on every commit. Now we detect input format and
    write back in the same format to keep diffs minimal and tests stable.

    task_id is stored in a sidecar `.task_id` file to avoid polluting
    phases.json with metadata lines that ccc-precheck would reject.

    Args:
        path: phases.json file path
        data: dict with 'phases' list (and possibly 'task_id')
        orig_format: 'jsonl' | 'json' | 'array' | 'empty'
    """
    phases = data.get('phases', [])
    task_id = data.get('task_id', '')

    # Write task_id to sidecar (one line, plain UUID)
    if task_id:
        sidecar = path + '.task_id'
        with open(sidecar, 'w') as f:
            f.write(task_id + '\n')

    with open(path, 'w') as f:
        if orig_format == 'jsonl':
            # JSONL: write each phase as one JSON object per line (no header)
            # Use compact separators (',', ':') to preserve diff-compatibility
            # with the typical input format (no extra spaces). Verifier note:
            # bug fix for Probe 1 format drift.
            for p in phases:
                f.write(json.dumps(p, ensure_ascii=False, separators=(',', ':')) + '\n')
        elif orig_format == 'array':
            # JSON 数组: 顶层是 [...]
            json.dump(phases, f, indent=2, ensure_ascii=False)
            f.write('\n')
        else:
            # 'json' 或 'empty': 写标准 {"phases": [...]} wrapper
            # 不内嵌 task_id(已在 sidecar)
            json.dump({"phases": phases}, f, indent=2, ensure_ascii=False)
            f.write('\n')

with open(fp) as f:
    content = f.read().strip()

# 兼容 3 种格式: 单 JSON 对象 / JSON 数组 / JSONL (每行一个对象)
# 检测策略: 先尝试整个 content 作为 single JSON 解析,
# 只有当 JSON 解析失败 + 每行都各自独立是 JSON 对象时,才走 JSONL 路径
# 同时记录原始格式 _ORIG_FORMAT 用于写回时保持一致,避免 JSONL → JSON 漂移
# task_id 从 .task_id sidecar 读取,避免污染 phases.json
sidecar = fp + '.task_id'
task_id_from_sidecar = ''
if os.path.exists(sidecar):
    try:
        task_id_from_sidecar = open(sidecar).read().strip()
    except Exception:
        pass

if not content:
    data = {"task_id": task_id_from_sidecar} if task_id_from_sidecar else {}
    _ORIG_FORMAT = "empty"
elif content.startswith('['):
    # JSON 数组格式(顶层是数组)
    data = {"phases": json.loads(content)}
    _ORIG_FORMAT = "array"
else:
    # 尝试作为单 JSON 对象/包装对象解析(支持 multi-line indented JSON)
    try:
        data = json.loads(content)
        # 兼容"整个对象即单 phase"的旧 schema
        if 'phase' in data and 'phases' not in data:
            data = {"phases": [data]}
        elif 'phases' not in data:
            # 单 JSON 对象但没有 phases 数组 → 当作单 phase
            data = {"phases": [data]}
        _ORIG_FORMAT = "json"
    except json.JSONDecodeError:
        # 回退到 JSONL(每行一个独立 JSON 对象)
        phases = []
        for line in content.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                phases.append(json.loads(line))
            except json.JSONDecodeError:
                # 整段都不能解析,放弃
                raise
        data = {"phases": phases}
        _ORIG_FORMAT = "jsonl"

# 优先用 sidecar 里的 task_id(避免污染 phases.json)
if task_id_from_sidecar:
    data['task_id'] = task_id_from_sidecar

changed = False

# --- 红线 15: 读取/自动注入顶层 task_id 字段 ---
import uuid
task_id = data.get('task_id', '').strip()
if not task_id:
    task_id = str(uuid.uuid4())
    data['task_id'] = task_id
    changed = True
    print("  🔧 自动注入 task_id=" + task_id)

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
    # 空 phases 也要写回自动注入的 task_id
    if changed:
        _write_phases(fp, data, _ORIG_FORMAT)
        print("  ✅ phases.json 已更新: " + fp)
    sys.exit(0)
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

    # --- 红线 15: 标记检测 — 仅当 task_id 非自动生成时要求显式标记 ---
    # auto-generated UUID 不可能出现在已有 commit_message 中，宽松处理
    is_auto_task_id = False
    try:
        uuid.UUID(task_id)  # will raise ValueError if not a valid UUID
        is_auto_task_id = True
    except (ValueError, TypeError):
        pass

    marker = f"ccc-task-id={task_id}"
    if not is_auto_task_id and marker not in commit_msg:
        print(f"  ❌ phase {pid}: commit_message 缺少标记 '{marker}'（红线 15 强制）")
        print(f"     当前 message: {commit_msg[:60]}")
        errors += 1
        continue

    # 确保 commit_message 尾部带 ccc-task-id（兜底，兼容 auto-generated 场景）
    if not is_auto_task_id or marker not in commit_msg:
        commit_msg = commit_msg + " ccc-task-id=" + task_id

    if not scope:
        print(f"  ○ phase {pid}: scope 为空，跳过（无改动需 commit）")
        continue
    else:
        # Fix #1: --all scope 不可达 — check before constructing prefix
        if scope == ['all']:
            scope_marker = "--all"
        else:
            scope_marker = "-- " + " ".join(scope)
        print(f"  → phase {pid}: git add {len(scope)} 文件")

    if not commit_msg:
        print(f"  ⚠️  phase {pid}: commit_message 为空，使用默认消息")
        commit_msg = f"chore({os.path.basename(workspace)}): phase {pid} auto-commit"

    # B3: scope 重叠阻断（多 phase 改同一文件时前 phase 改动会污染当前 phase）
    if scope and pid > 1:
        overlap_detected = False
        for prev_scope in all_committed_scopes:
            overlap = set(f.lower() for f in scope) & set(f.lower() for f in prev_scope)
            if overlap:
                print(f"  ❌ phase {pid}: scope 与之前 phase 重叠: {overlap}")
                print(f"     Git working tree 线性，同一文件跨 phase 改会污染 commit")
                overlap_detected = True
        if overlap_detected:
            errors += 1
            continue

    # v0.31 (C1 fix 外部 scope reject): scope 外文件拒绝提交
    if scope_marker != "--all":
        # 查已跟踪修改 + 未跟踪新文件（git diff --name-only 漏新建文件）
        _changed_raw = subprocess.run(
            ["git", "diff", "--name-only"],
            cwd=workspace, capture_output=True, text=True
        ).stdout.strip()
        _untracked_raw = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            cwd=workspace, capture_output=True, text=True
        ).stdout.strip()
        _all_changed = set()
        if _changed_raw:
            _all_changed |= set(_changed_raw.splitlines())
        if _untracked_raw:
            _all_changed |= set(_untracked_raw.splitlines())
        if _all_changed:
            _scope_set = set(scope)
            _extra = _all_changed - _scope_set
            if _extra:
                print(f"  ❌ phase {pid}: scope 外文件被改动: {', '.join(sorted(_extra))}")
                print(f"     拒绝提交，回退 extra 文件到 HEAD")
                for _f in _extra:
                    # 已跟踪文件 → checkout；未跟踪新文件 → rm
                    subprocess.run(["git", "checkout", "--", _f], cwd=workspace,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    if os.path.exists(os.path.join(workspace, _f)):
                        # git checkout 没修复（未跟踪文件），直接删
                        try:
                            os.remove(os.path.join(workspace, _f))
                        except OSError:
                            pass
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

    # 写回 phases.json（Fix #3: 每个 phase 成功后立即写，避免中途被杀丢失 hash）
    p['commit'] = commit_hash
    changed = True
    all_committed_scopes.append(scope)
    print(f"  ✓ phase {pid}: committed {commit_hash[:12]} — {commit_msg[:50]}")
    _write_phases(fp, data, _ORIG_FORMAT)
    print(f"  ✅ phases.json 已更新: {fp}")

sys.exit(0 if errors == 0 else 1)
PYEOF

# Fix #4: set -e 在 python3 调用前生效，之后恢复；否则 Python 非零退出后 shell 直接终止
set +e
EXIT_CODE=$?
set -e
exit $EXIT_CODE
