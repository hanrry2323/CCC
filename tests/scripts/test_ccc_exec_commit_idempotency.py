"""test_ccc_exec_commit_idempotency.py — Red Line 15: ccc-task-id 幂等 commit.

覆盖三条路径:
1. 含 ccc-task-id=<id> 标记 → commit 成功
2. 不含标记 → 拒绝 (exit 1, 无新 commit)
3. 重复执行同一 task_id → 幂等跳过 (exit 0, 无新 commit)
"""
from __future__ import annotations
import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT = ROOT / "scripts" / "ccc-exec-commit.sh"


def _git(args, cwd):
    return subprocess.run(
        ["git"] + args, cwd=cwd, capture_output=True, text=True, check=False,
    )


@pytest.fixture
def fake_workspace(tmp_path):
    """Create temp git repo with .ccc/phases/<task>.phases.json (含 task_id 顶层字段)."""
    repo = tmp_path / "testrepo"
    repo.mkdir()
    _git(["init", "-b", "main"], cwd=repo)
    _git(["config", "user.email", "test@x"], cwd=repo)
    _git(["config", "user.name", "Test"], cwd=repo)
    # Initial commit
    (repo / "README.md").write_text("# test\n")
    _git(["add", "README.md"], cwd=repo)
    _git(["commit", "-m", "initial"], cwd=repo)
    # .ccc directory structure
    ccc = repo / ".ccc"
    (ccc / "phases").mkdir(parents=True)
    (ccc / "reports").mkdir()
    (ccc / "plans").mkdir()
    (ccc / "verdicts").mkdir()
    return repo


def _write_phases_with_task_id(repo, task, task_id, phase_id, scope_file,
                               commit_message, status="done", commit=None):
    """写带 task_id 顶层字段的 phases.json."""
    phases = repo / ".ccc" / "phases" / f"{task}.phases.json"
    payload = {
        "task_id": task_id,
        "phases": [
            {
                "id": phase_id,
                "status": status,
                "commit": commit,
                "scope": [scope_file],
                "commit_message": commit_message,
            }
        ],
    }
    phases.write_text(json.dumps(payload, ensure_ascii=False) + "\n")
    return phases


def _run_commit(repo, task):
    return subprocess.run(
        ["bash", str(SCRIPT), str(repo), task],
        capture_output=True, text=True, timeout=15,
    )


def _git_log_count(repo):
    return len(_git(["log", "--oneline"], cwd=repo).stdout.strip().splitlines())


# ============================================================
# Path 1: 含 ccc-task-id 标记 → commit 成功
# ============================================================
def test_path1_with_marker_commits_successfully(fake_workspace):
    """commit message 含 ccc-task-id=<id> 标记 → 正常 commit，phases.json 回填 commit 字段."""
    task = "task1"
    task_id = "task-uuid-aaaa"
    target = fake_workspace / "feature.txt"
    target.write_text("hello\n")
    # 不预 git add，脚本会自己 add

    _write_phases_with_task_id(
        fake_workspace, task, task_id,
        phase_id=1, scope_file="feature.txt",
        commit_message="feat: add feature ccc-task-id=task-uuid-aaaa",
    )

    before = _git_log_count(fake_workspace)
    proc = _run_commit(fake_workspace, task)
    after = _git_log_count(fake_workspace)

    # 退出码 0 (成功)
    assert proc.returncode == 0, f"期望成功退出，实际 {proc.returncode}\nstderr: {proc.stderr}\nstdout: {proc.stdout}"
    # 多了一个 commit
    assert after == before + 1, f"git log 数量未增加: {before} → {after}"
    # phases.json commit 字段已回填
    phases = json.loads((fake_workspace / ".ccc" / "phases" / f"{task}.phases.json").read_text())
    filled = phases["phases"][0]["commit"]
    assert filled and filled not in ("null", "None", ""), f"commit 字段未回填: {filled!r}"
    # 最近一次 commit message 含标记
    last_msg = _git(["log", "-1", "--format=%s"], cwd=fake_workspace).stdout.strip()
    assert f"ccc-task-id={task_id}" in last_msg, f"commit message 缺标记: {last_msg!r}"


# ============================================================
# Path 2: 不含标记 → 拒绝 (exit 非 0, 无新 commit)
# ============================================================
def test_path2_without_marker_rejected(fake_workspace):
    """commit message 缺 ccc-task-id=<id> → 脚本拒绝，退出码 1，无新 commit."""
    task = "task2"
    task_id = "task-uuid-bbbb"
    target = fake_workspace / "feature2.txt"
    target.write_text("hello2\n")
    # 不预 git add

    _write_phases_with_task_id(
        fake_workspace, task, task_id,
        phase_id=1, scope_file="feature2.txt",
        commit_message="feat: this message has no marker",
    )

    before = _git_log_count(fake_workspace)
    proc = _run_commit(fake_workspace, task)
    after = _git_log_count(fake_workspace)

    # 退出码非 0 (拒绝)
    assert proc.returncode != 0, f"期望拒绝 (非 0)，实际 {proc.returncode}\nstdout: {proc.stdout}"
    # 无新 commit
    assert after == before, f"不应有 commit 产生: {before} → {after}"
    # 错误输出含红线 15 提示
    out = proc.stdout + proc.stderr
    assert "ccc-task-id=" in out or "红线 15" in out, f"缺红线 15 提示信息:\n{out}"


# ============================================================
# Path 3: 重复执行 → 幂等跳过 (exit 0, 无新 commit)
# ============================================================
def test_path3_repeated_run_idempotent(fake_workspace):
    """同一 task_id 已 commit 过 → 重复执行时整体跳过，exit 0，无新 commit."""
    task = "task3"
    task_id = "task-uuid-cccc"
    target = fake_workspace / "feature3.txt"
    target.write_text("hello3\n")
    # 不预 git add

    _write_phases_with_task_id(
        fake_workspace, task, task_id,
        phase_id=1, scope_file="feature3.txt",
        commit_message="feat: add feature ccc-task-id=task-uuid-cccc",
    )

    # 第一次：成功 commit
    p1 = _run_commit(fake_workspace, task)
    assert p1.returncode == 0, f"第一次执行应成功，实际 {p1.returncode}\n{p1.stdout}\n{p1.stderr}"
    after_first = _git_log_count(fake_workspace)

    # 第二次：幂等跳过
    p2 = _run_commit(fake_workspace, task)
    after_second = _git_log_count(fake_workspace)

    # 退出码 0
    assert p2.returncode == 0, f"重复执行期望退出 0，实际 {p2.returncode}\nstdout: {p2.stdout}"
    # 无新 commit
    assert after_second == after_first, f"重复执行不应产生新 commit: {after_first} → {after_second}"
    # 提示信息含 IDEMPOTENT
    out = p2.stdout + p2.stderr
    assert "IDEMPOTENT" in out or "幂等" in out or "跳过" in out, f"缺幂等提示:\n{out}"


# ============================================================
# 辅助: phases.json 缺 task_id 字段 → 自动注入 UUID
# ============================================================
def test_phases_missing_task_id_auto_injects(fake_workspace):
    """phases.json 顶层缺 task_id 字段 → 脚本自动注入 UUID，exit 0."""
    task = "task4"
    phases = fake_workspace / ".ccc" / "phases" / f"{task}.phases.json"
    phases.write_text(json.dumps({
        "phases": [
            {"id": 1, "status": "done", "commit": None,
             "scope": ["README.md"],
             "commit_message": "feat: x"}
        ]
    }) + "\n")

    proc = _run_commit(fake_workspace, task)
    assert proc.returncode == 0
    out = proc.stdout + proc.stderr
    assert "自动注入 task_id" in out, f"缺自动注入提示:\n{out}"


# ============================================================
# 辅助: bash 语法
# ============================================================
def test_script_syntax():
    """bash -n 语法零错误."""
    proc = subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True, text=True)
    assert proc.returncode == 0, f"语法错误: {proc.stderr}"


# ============================================================
# Auto-inject: 缺 task_id → 自动注入 UUID
# ============================================================
def test_empty_task_id_auto_injects(fake_workspace):
    """phases.json 缺 task_id → 脚本自动注入 UUID，写回 phases.json."""
    task = "task-auto-1"
    target = fake_workspace / "autofile.txt"
    target.write_text("auto-inject test\n")

    # 构造: 无 task_id 顶层字段，commit_message 也不带标记
    # （按新行为: task_id 会被自动注入，但 commit_message 缺标记 → 标记检测会拒绝）
    # 本测试只验证 task_id 自动注入并写回，所以用空 phases 数组
    phases = fake_workspace / ".ccc" / "phases" / f"{task}.phases.json"
    phases.write_text(json.dumps({"phases": []}) + "\n")

    proc = _run_commit(fake_workspace, task)
    assert proc.returncode == 0, f"空 phases 应正常退出，实际 {proc.returncode}\n{proc.stdout}\n{proc.stderr}"

    # Bug fix (historical task phase 1, 2026-07): task_id moved to sidecar
    # file `<phases>.task_id` to avoid polluting phases.json with metadata
    # lines that ccc-precheck would reject (lines without phase/status fields).
    sidecar = phases.with_suffix(phases.suffix + ".task_id")
    assert sidecar.exists(), f"task_id sidecar 未生成: {sidecar}"
    tid = sidecar.read_text().strip()
    # UUID v4 格式: 8-4-4-4-12 hex chars
    parts = tid.split("-")
    assert len(parts) == 5, f"不是 UUID 格式: {tid!r}"
    assert all(len(p) in (8, 4, 4, 4, 12) for p in parts), f"UUID 段长不对: {tid!r}"
    # 打印提示应含自动注入
    out = proc.stdout + proc.stderr
    assert "自动注入" in out or "auto" in out.lower() or "inject" in out.lower(), \
        f"缺自动注入提示:\n{out}"


# ============================================================
# Auto-inject: 有 task_id → 不覆盖
# ============================================================
def test_existing_task_id_not_overwritten(fake_workspace):
    """phases.json 已有 task_id → 脚本不覆盖，值保持不变."""
    task = "task-auto-2"
    fixed_id = "fixed-uuid-999"

    phases = fake_workspace / ".ccc" / "phases" / f"{task}.phases.json"
    # 用空 phases 数组，避免 commit 流程干扰
    phases.write_text(json.dumps({
        "task_id": fixed_id,
        "phases": [],
    }) + "\n")

    proc = _run_commit(fake_workspace, task)
    assert proc.returncode == 0, f"空 phases 应正常退出，实际 {proc.returncode}\n{proc.stdout}\n{proc.stderr}"

    # 验证 task_id 未被覆盖
    data = json.loads(phases.read_text())
    assert data.get("task_id") == fixed_id, \
        f"task_id 被覆盖了: 期望 {fixed_id!r}, 实际 {data.get('task_id')!r}"
