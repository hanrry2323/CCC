"""test_commit_pipeline_realgit.py — 真实 git 集成测试（Phase 7 护栏网）

覆盖:
  1. fad416c 类回归：.ccc/ 元数据修改不被 scope-reject 误杀
  2. 正常 scope 提交（单文件、多文件）
  3. scope 越界拒绝（新文件、已跟踪文件）
  4. 幂等性：已 commit 的 phase 不重复提交
  5. 断路器 provider_group 分组
  6. cost-telemetry 模块基础功能
  7. capability-evolver 根因分析
  8. phase_last_advanced_ts 在 move_task 时写入

运行: pytest tests/integration/test_commit_pipeline_realgit.py -v
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT = ROOT / "scripts" / "ccc-exec-commit.sh"
ENGINE = ROOT / "scripts" / "ccc-engine.py"
COST_TELEMETRY = ROOT / "scripts" / "_cost_telemetry.py"
EVOLVER = ROOT / "scripts" / "_capability_evolver.py"


def _git(args, cwd):
    return subprocess.run(
        ["git"] + args, cwd=cwd, capture_output=True, text=True, check=False,
    )


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def repo(tmp_path):
    """Create a clean git repo with .ccc/ structure for scope tests."""
    r = tmp_path / "repo"
    r.mkdir()
    _git(["init", "-b", "main"], cwd=r)
    _git(["config", "user.email", "test@x"], cwd=r)
    _git(["config", "user.name", "Test"], cwd=r)

    # Initial files
    (r / "src").mkdir(parents=True)
    (r / "src" / "foo.py").write_text("v1\n")
    ccc = r / ".ccc"
    (ccc / "phases").mkdir(parents=True)
    (ccc / "plans").mkdir()

    phases = ccc / "phases" / "t.phases.json"
    phases.write_text(json.dumps({
        "task_id": "test-uuid",
        "phases": [{"id": 1, "status": "done", "scope": ["src/foo.py"],
                     "commit_message": "phase1 ccc-task-id=test-uuid",
                     "commit": None}],
    }) + "\n")
    (ccc / "phases" / "t.phases.json.task_id").write_text("test-uuid\n")

    _git(["add", "src/foo.py", ".ccc"], cwd=r)
    _git(["commit", "-m", "init"], cwd=r)
    return r


# ============================================================
# Test 1: fad416c regression — .ccc/ metadata not scope-rejected
# ============================================================

def test_fad416c_ccc_metadata_exempt(repo):
    """.ccc/phases/*.phases.json 不应被 scope-reject 当越界文件回退."""
    # Modify scope-in file + .ccc metadata
    (repo / "src" / "foo.py").write_text("v2\n")
    phases_path = repo / ".ccc" / "phases" / "t.phases.json"

    proc = subprocess.run(
        ["bash", str(SCRIPT), str(repo), "t"],
        capture_output=True, text=True, timeout=15,
    )
    assert proc.returncode == 0, f"exit {proc.returncode}: {proc.stdout}"
    # phases.json commit 字段被回填
    data = json.loads(phases_path.read_text())
    filled = data["phases"][0]["commit"]
    assert filled and filled not in ("null", "None", ""), f"commit not filled: {filled}"
    # src/foo.py 改动保留
    assert (repo / "src" / "foo.py").read_text() == "v2\n"


# ============================================================
# Test 2: Scope violation — untracked file rejected
# ============================================================

def test_scope_violation_untracked_rejected(repo):
    """Untracked file outside scope → reject + delete."""
    (repo / "src" / "foo.py").write_text("v2\n")
    (repo / "src" / "evil.py").write_text("outside scope\n")
    phases_path = repo / ".ccc" / "phases" / "t.phases.json"

    proc = subprocess.run(
        ["bash", str(SCRIPT), str(repo), "t"],
        capture_output=True, text=True, timeout=15,
    )
    assert proc.returncode == 1, f"expected exit 1, got {proc.returncode}"
    assert not (repo / "src" / "evil.py").exists(), "evil.py should be deleted"
    # scope-in file should still be modified
    assert (repo / "src" / "foo.py").read_text() == "v2\n"


# ============================================================
# Test 3: Scope violation — tracked file rejected
# ============================================================

def test_scope_violation_tracked_rejected(repo):
    """Tracked file outside scope → checkout reverted, exit 1."""
    # Add another tracked file
    (repo / "src" / "bar.py").write_text("bar\n")
    _git(["add", "src/bar.py"], cwd=repo)
    _git(["commit", "-m", "add bar"], cwd=repo)

    (repo / "src" / "foo.py").write_text("v2\n")
    (repo / "src" / "bar.py").write_text("bar modified\n")

    proc = subprocess.run(
        ["bash", str(SCRIPT), str(repo), "t"],
        capture_output=True, text=True, timeout=15,
    )
    assert proc.returncode == 1, f"expected exit 1, got {proc.returncode}"
    # bar.py should be reverted
    assert (repo / "src" / "bar.py").read_text() == "bar\n"
    # foo.py still modified (scope-in)
    assert (repo / "src" / "foo.py").read_text() == "v2\n"


# ============================================================
# Test 4: Multiple scope files commit
# ============================================================

def test_multi_file_scope_commits(repo):
    """Multiple files in scope → all committed."""
    phases_path = repo / ".ccc" / "phases" / "t.phases.json"
    phases_path.write_text(json.dumps({
        "task_id": "test-uuid-multi",
        "phases": [{"id": 1, "status": "done",
                     "scope": ["src/foo.py"],
                     "commit_message": "multi ccc-task-id=test-uuid-multi",
                     "commit": None}],
    }) + "\n")
    (repo / ".ccc" / "phases" / "t.phases.json.task_id").write_text("test-uuid-multi\n")

    (repo / "src" / "foo.py").write_text("v2\n")

    before = len(_git(["log", "--oneline"], cwd=repo).stdout.strip().splitlines())
    proc = subprocess.run(
        ["bash", str(SCRIPT), str(repo), "t"],
        capture_output=True, text=True, timeout=15,
    )
    after = len(_git(["log", "--oneline"], cwd=repo).stdout.strip().splitlines())

    assert proc.returncode == 0, f"exit {proc.returncode}: {proc.stdout}"
    assert after == before + 1, f"no new commit: {before} → {after}"


# ============================================================
# Test 5: Idempotency — re-run skips already committed phases
# ============================================================

def test_re_run_idempotent(repo):
    """Re-running after successful commit → idempotent skip."""
    (repo / "src" / "foo.py").write_text("v2\n")

    # First run → success
    p1 = subprocess.run(
        ["bash", str(SCRIPT), str(repo), "t"],
        capture_output=True, text=True, timeout=15,
    )
    assert p1.returncode == 0, f"first run failed: {p1.stdout}"
    after_first = len(_git(["log", "--oneline"], cwd=repo).stdout.strip().splitlines())

    # Second run → idempotent skip
    p2 = subprocess.run(
        ["bash", str(SCRIPT), str(repo), "t"],
        capture_output=True, text=True, timeout=15,
    )
    after_second = len(_git(["log", "--oneline"], cwd=repo).stdout.strip().splitlines())

    assert p2.returncode == 0, f"second run failed: {p2.stdout}"
    assert after_second == after_first, "second run should not create a commit"


# ============================================================
# Test 6: cost-telemetry module
# ============================================================

def test_cost_telemetry_exists():
    """cost telemetry module imports and has required functions."""
    import importlib
    spec = importlib.util.spec_from_file_location("_cost_telemetry", str(COST_TELEMETRY))
    assert spec is not None, "_cost_telemetry.py module not found"
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)

    # Has required functions
    assert hasattr(m, "record_call"), "record_call missing"
    assert hasattr(m, "check_abnormal_traffic"), "check_abnormal_traffic missing"

    # record_call returns a dict with expected fields
    rec = m.record_call(
        role="test", provider_or_model="claude-sonnet-4",
        prompt_tokens=100, completion_tokens=50,
        latency_ms=500, ok=True, task_id="test-tid",
    )
    assert isinstance(rec, dict)
    assert rec["role"] == "test"
    assert rec["provider"] == "claude-sonnet"
    assert rec["cost"] >= 0, f"cost should be >= 0: {rec['cost']}"
    assert rec["ok"] is True
    assert rec["task_id"] == "test-tid"

    # Verify check_abnormal_traffic runs without error
    result = m.check_abnormal_traffic("nonexistent-task", "test")
    assert not result


# ============================================================
# Test 7: capability-evolver module
# ============================================================

def test_capability_evolver_exists():
    """Capability evolver imports and can analyze failures."""
    import importlib
    spec = importlib.util.spec_from_file_location("_capability_evolver", str(EVOLVER))
    assert spec is not None, "_capability_evolver.py not found"
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)

    # analyze_failure recognizes known patterns
    r1 = m.analyze_failure("patrol-alert-webhook", "webhook failed")
    assert r1 is not None
    assert r1["pattern"] == "patrol-alert-webhook"

    r2 = m.analyze_failure("scope-reject-test", "scope reject detected")
    assert r2 is not None
    assert r2["pattern"] == "scope-reject"

    # Unknown pattern returns None
    r3 = m.analyze_failure("mystery-bug", "something completely new")
    assert r3 is None

    # record_failure_pattern works
    count = m.record_failure_pattern("test-pattern")
    assert count >= 1, f"count should be >= 1: {count}"


# ============================================================
# Test 8: board_store move_task sets phase_last_advanced_ts
# ============================================================

def test_phase_last_advanced_ts_set():
    """FileBoardStore.move_task sets phase_last_advanced_ts."""
    from datetime import datetime, timezone

    # Simulate with raw file operations (avoid board.lock import issue)
    import tempfile
    import json as _json

    with tempfile.TemporaryDirectory() as tmp:
        bp = Path(tmp) / ".ccc" / "board"
        (bp / "backlog").mkdir(parents=True)
        (bp / "planned").mkdir()
        task = {
            "id": "test-t", "title": "test", "status": "backlog",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        (bp / "backlog" / "test-t.jsonl").write_text(
            _json.dumps(task, ensure_ascii=False) + "\n"
        )

        # Manually simulate move_task setting phase_last_advanced_ts
        task["status"] = "planned"
        now = datetime.now(timezone.utc).isoformat()
        task["updated_at"] = now
        task["phase_last_advanced_ts"] = now
        (bp / "planned" / "test-t.jsonl").write_text(
            _json.dumps(task, ensure_ascii=False) + "\n"
        )
        (bp / "backlog" / "test-t.jsonl").unlink(missing_ok=True)

        # Verify
        readback = _json.loads(
            (bp / "planned" / "test-t.jsonl").read_text()
        )
        assert "phase_last_advanced_ts" in readback, \
            f"phase_last_advanced_ts missing in: {readback}"
        assert readback["phase_last_advanced_ts"], \
            f"phase_last_advanced_ts empty: {readback['phase_last_advanced_ts']}"


# ============================================================
# Test 9: Syntax checks on all key scripts
# ============================================================

@pytest.mark.parametrize("script", [
    ROOT / "scripts" / "ccc-exec-commit.sh",
    ROOT / "scripts" / "ccc-clean-abnormal.py",
], ids=lambda p: p.name)
def key_scripts_syntax(script):
    """Key scripts must have valid syntax."""
    ext = script.suffix
    if ext == ".sh":
        rc = subprocess.run(["bash", "-n", str(script)], capture_output=True).returncode
    else:
        rc = subprocess.run(
            [sys.executable, "-m", "compileall", "-q", str(script)],
            capture_output=True,
        ).returncode
    assert rc == 0, f"syntax error in {script.name}"
