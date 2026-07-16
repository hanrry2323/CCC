"""test_ccc_exec_commit_scope_git_integration.py — 真实 git 集成测试

覆盖 scope-reject 的 .ccc/ 系统元数据豁免逻辑（防止 fad416c 类回归）:

场景1: .ccc/ 系统文件改动不被视为 scope 越界
  - tracked .ccc/phases/t.phases.json (ccc 元数据) + tracked src/foo.py (scope)
  - 两者都改 → phases.json 不被回退, exit 0

场景2: 真 scope 越界（新建外部文件）→ 拒绝
  - scope=src/foo.py, 但 src/evil.py 被创建
  → 检测+删除, exit 1

场景3: 已跟踪的 scope 外文件改动 → 拒绝 checkout
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
def git_repo(tmp_path):
    """Create a temp git repo with .ccc/ structure and initial commit."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(["init", "-b", "main"], cwd=repo)
    _git(["config", "user.email", "test@x"], cwd=repo)
    _git(["config", "user.name", "Test"], cwd=repo)

    # src/foo.py — tracked, used as scope target
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "foo.py").write_text("print('hello')\n")
    # .ccc/phases/t.phases.json — tracked CCC metadata
    ccc = repo / ".ccc"
    (ccc / "phases").mkdir(parents=True)
    (ccc / "plans").mkdir()
    (ccc / "reports").mkdir()
    (ccc / "verdicts").mkdir()
    phases = ccc / "phases" / "t.phases.json"
    phases.write_text(json.dumps({
        "phases": [
            {
                "id": 1,
                "status": "done",
                "scope": ["src/foo.py"],
                "commit_message": "test phase 1",
                "commit": None,
            }
        ],
    }) + "\n")

    _git(["add", "src/foo.py", ".ccc"], cwd=repo)
    _git(["commit", "-m", "initial"], cwd=repo)
    return repo


def _run_commit(repo, task="t"):
    return subprocess.run(
        ["bash", str(SCRIPT), str(repo), task],
        capture_output=True, text=True, timeout=15,
    )


# ============================================================
# 场景1: .ccc/ 文件改动不被 scope-reject 误杀（防 fad416c 回归）
# ============================================================
def test_ccc_metadata_exempt_from_scope_reject(git_repo):
    """.ccc/phases/*.phases.json 改动 → 不被 scope-reject 当越界文件回退."""
    # 改 scope 内文件
    (git_repo / "src" / "foo.py").write_text("print('world')\n")
    # 改 .ccc/ 文件（executor 真实写入 phases.json 含 commit hash）
    phases_path = git_repo / ".ccc" / "phases" / "t.phases.json"
    phases_path.write_text(json.dumps({
        "phases": [
            {
                "id": 1,
                "status": "done",
                "scope": ["src/foo.py"],
                "commit_message": "test phase 1 ccc-task-id=test-uuid",
                "commit": None,
            }
        ],
        "task_id": "test-uuid",
    }) + "\n")
    # .ccc/task_id sidecar
    sidecar = phases_path.with_suffix(phases_path.suffix + ".task_id")
    sidecar.write_text("test-uuid\n")

    before = len(_git(["log", "--oneline"], cwd=git_repo).stdout.strip().splitlines())

    proc = _run_commit(git_repo)
    after = len(_git(["log", "--oneline"], cwd=git_repo).stdout.strip().splitlines())

    # 1) exit 0 — 成功提交
    assert proc.returncode == 0, \
        f"期望 exit 0, 实际 {proc.returncode}\nstdout: {proc.stdout}\nstderr: {proc.stderr}"
    # 2) git log 有新增 commit
    assert after == before + 1, f"应新增 1 commit: {before} → {after}"
    # 3) phases.json 未被回退（commit 字段已回填）
    data = json.loads(phases_path.read_text())
    filled = data["phases"][0]["commit"]
    assert filled and filled not in ("null", "None", ""), \
        f"phases.json commit 字段未回填: {filled!r}"
    # 4) src/foo.py 改动在 commit 中
    content = (git_repo / "src" / "foo.py").read_text()
    assert content == "print('world')\n", f"src/foo.py 被还原: {content!r}"
    # 5) 输出不包含 "scope 外文件" 提示
    assert "scope 外" not in (proc.stdout + proc.stderr), \
        f"不应有 scope 越界提示:\n{proc.stdout}"


# ============================================================
# 场景2: 真 scope 越界（新建外部文件）→ 拒绝
# ============================================================
def test_untracked_file_outside_scope_rejected(git_repo):
    """scope 外新建文件 → 检测+删除, exit 1."""
    # 改 scope 内
    (git_repo / "src" / "foo.py").write_text("print('world')\n")
    # 新建 scope 外文件 (未跟踪)
    (git_repo / "src" / "evil.py").write_text("print('evil')\n")
    # 写 phases.json（含标记）
    phases_path = git_repo / ".ccc" / "phases" / "t.phases.json"
    phases_path.write_text(json.dumps({
        "phases": [
            {
                "id": 1,
                "status": "done",
                "scope": ["src/foo.py"],
                "commit_message": "test phase 1 ccc-task-id=test-uuid-2",
                "commit": None,
            }
        ],
        "task_id": "test-uuid-2",
    }) + "\n")
    sidecar = phases_path.with_suffix(phases_path.suffix + ".task_id")
    sidecar.write_text("test-uuid-2\n")

    before = len(_git(["log", "--oneline"], cwd=git_repo).stdout.strip().splitlines())

    proc = _run_commit(git_repo)
    after = len(_git(["log", "--oneline"], cwd=git_repo).stdout.strip().splitlines())

    # 1) exit 1 — 拒绝提交
    assert proc.returncode == 1, \
        f"期望 exit 1, 实际 {proc.returncode}\nstdout: {proc.stdout}\nstderr: {proc.stderr}"
    # 2) 无新 commit
    assert after == before, f"不应产生新 commit: {before} → {after}"
    # 3) evil.py 已被删除
    assert not (git_repo / "src" / "evil.py").exists(), \
        "src/evil.py 应被删除"
    # 4) 输出含 "scope 外" 提示
    out = proc.stdout + proc.stderr
    assert "scope 外" in out, f"缺 scope 外提示:\n{out}"
    # 5) src/foo.py 改动应被保留（因为 git checkout 只回退 extra 文件）
    content = (git_repo / "src" / "foo.py").read_text()
    assert content == "print('world')\n", f"src/foo.py 被意外还原: {content!r}"


# ============================================================
# 场景3: 已跟踪的 scope 外文件改动 → 拒绝 checkout
# ============================================================
def test_tracked_file_outside_scope_rejected(git_repo):
    """已跟踪文件改在 scope 外 → 被 checkout 回退, exit 1."""
    # 加一个 tracked 文件在 scope 外
    (git_repo / "src" / "bar.py").write_text("print('bar')\n")
    _git(["add", "src/bar.py"], cwd=git_repo)
    _git(["commit", "-m", "add bar.py"], cwd=git_repo)

    # 改 scope 内的 foo.py
    (git_repo / "src" / "foo.py").write_text("print('world')\n")
    # 改 scope 外的 bar.py
    (git_repo / "src" / "bar.py").write_text("print('bar modified')\n")

    phases_path = git_repo / ".ccc" / "phases" / "t.phases.json"
    phases_path.write_text(json.dumps({
        "phases": [
            {
                "id": 1,
                "status": "done",
                "scope": ["src/foo.py"],
                "commit_message": "test phase 1 ccc-task-id=test-uuid-3",
                "commit": None,
            }
        ],
        "task_id": "test-uuid-3",
    }) + "\n")
    sidecar = phases_path.with_suffix(phases_path.suffix + ".task_id")
    sidecar.write_text("test-uuid-3\n")

    before = len(_git(["log", "--oneline"], cwd=git_repo).stdout.strip().splitlines())

    proc = _run_commit(git_repo)
    after = len(_git(["log", "--oneline"], cwd=git_repo).stdout.strip().splitlines())

    # 1) exit 1
    assert proc.returncode == 1, \
        f"期望 exit 1, 实际 {proc.returncode}\nstdout: {proc.stdout}\nstderr: {proc.stderr}"
    # 2) 无新 commit
    assert after == before, f"不应产生新 commit: {before} → {after}"
    # 3) bar.py 被 checkout 回退
    content = (git_repo / "src" / "bar.py").read_text()
    assert content == "print('bar')\n", f"bar.py 未被回退: {content!r}"
    # 4) foo.py 改动保留
    content2 = (git_repo / "src" / "foo.py").read_text()
    assert content2 == "print('world')\n", f"foo.py 被意外还原: {content2!r}"


# ============================================================
# 语法检查
# ============================================================
def test_script_syntax():
    """bash -n 语法零错误."""
    proc = subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True, text=True)
    assert proc.returncode == 0, f"语法错误: {proc.stderr}"
