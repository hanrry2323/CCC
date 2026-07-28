"""test_reviewer_async_empty.py — Phase A 红测 + Phase B 验收.

Gaps (014):
A1: .done + 空 .out → 必须写 FAIL verdict, 返回 failed
A2: 无 .done + 无存活 pid  → 必须写 FAIL verdict, 返回 failed
A3: 有 .reviewer.timeout (无 done) → 必须写 TIMEOUT verdict, 返回 TIMEOUT
"""

from __future__ import annotations

from pathlib import Path

import pytest


def _pids_dir(ws: Path, task_id: str) -> Path:
    return ws / ".ccc" / "pids"


def _write_marker(pids_dir: Path, task_id: str, suffix: str, content: str = "") -> None:
    (pids_dir / f"{task_id}{suffix}").write_text(content, encoding="utf-8")


def _verdict_file(ws: Path, task_id: str) -> Path:
    return ws / ".ccc" / "verdicts" / f"{task_id}.verdict.md"


@pytest.fixture
def ws(tmp_path: Path) -> Path:
    w = tmp_path / "ws"
    (w / ".ccc" / "pids").mkdir(parents=True)
    (w / ".ccc" / "verdicts").mkdir(parents=True)
    return w


@pytest.fixture(scope="module")
def _reviewer():
    """Load reviewer module once."""
    import importlib.util

    repo = Path(__file__).resolve().parents[2]
    mod_path = repo / "scripts" / "board" / "roles" / "reviewer.py"
    spec = importlib.util.spec_from_file_location(
        "board.roles.reviewer_test", mod_path
    )
    assert spec and spec.loader, f"cannot load {mod_path}"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── Helper: call check_reviewer_async with monkeypatched ws ─────────────


def _call_check(task_id: str, ws: Path, _reviewer) -> dict:
    """Call check_reviewer_async(task_id, ws) and return result dict."""
    return _reviewer.check_reviewer_async(task_id, ws)


# ── A1: done exists but .out is empty → FAIL verdict ───────────────────


def test_a1_done_with_empty_out_writes_fail_verdict(ws: Path, _reviewer):
    """A1: done marker + 空 .out → verdict 文件必须含 FAIL, 返回 failed."""
    tid = "014-a1-test"
    pd = _pids_dir(ws, tid)
    _write_marker(pd, tid, ".reviewer.done", "{}")
    _write_marker(pd, tid, ".reviewer.out", "")

    result = _call_check(tid, ws, _reviewer)

    assert result.get("status") == "failed", f"expected failed, got {result}"
    vf = _verdict_file(ws, tid)
    assert vf.is_file(), f"verdict file not created at {vf}"
    content = vf.read_text(encoding="utf-8")
    assert "FAIL" in content, f"expected FAIL in verdict, got: {repr(content)}"


# ── A2: no done + dead pid → FAIL verdict ────────────────────────────


def test_a2_no_done_dead_pid_writes_fail_verdict(ws: Path, _reviewer):
    """A2: 无 done + pid 文件但进程已死 → verdict 必须含 FAIL, 返回 failed."""
    tid = "014-a2-test"
    pd = _pids_dir(ws, tid)
    # pid=999999 almost certainly doesn't exist
    _write_marker(pd, tid, ".reviewer.pid", "999999")

    result = _call_check(tid, ws, _reviewer)

    assert result.get("status") == "failed", f"expected failed, got {result}"
    vf = _verdict_file(ws, tid)
    assert vf.is_file(), f"verdict file not created at {vf}"
    content = vf.read_text(encoding="utf-8")
    assert "FAIL" in content, f"expected FAIL in verdict, got: {repr(content)}"


def test_a2b_no_done_no_pid_writes_fail_verdict(ws: Path, _reviewer):
    """A2b: 无 done、无 pid 文件 → 进程早退 → 必须写 FAIL verdict."""
    tid = "014-a2b-test"
    result = _call_check(tid, ws, _reviewer)

    assert result.get("status") == "failed", f"expected failed, got {result}"
    vf = _verdict_file(ws, tid)
    assert vf.is_file(), f"verdict file not created at {vf}"
    content = vf.read_text(encoding="utf-8")
    assert "FAIL" in content, f"expected FAIL in verdict, got: {repr(content)}"


# ── A3: .reviewer.timeout exists → TIMEOUT verdict ────────────────────


def test_a3_timeout_marker_writes_timeout_verdict(ws: Path, _reviewer):
    """A3: .reviewer.timeout 存在(无 done) → verdict 必须含 TIMEOUT, 返回 TIMEOUT."""
    tid = "014-a3-test"
    pd = _pids_dir(ws, tid)
    _write_marker(pd, tid, ".reviewer.timeout", "timeout after 600s")

    result = _call_check(tid, ws, _reviewer)

    assert result.get("status") == "TIMEOUT", f"expected TIMEOUT, got {result}"
    vf = _verdict_file(ws, tid)
    assert vf.is_file(), f"verdict file not created at {vf}"
    content = vf.read_text(encoding="utf-8")
    assert "TIMEOUT" in content, f"expected TIMEOUT in verdict, got: {repr(content)}"


def test_a3b_timeout_marker_with_done_still_uses_llm_output(ws: Path, _reviewer):
    """.timeout + .done 同时存在 → reviewer.py 已完成(有 done), 走正常解析路径."""
    tid = "014-a3b-test"
    pd = _pids_dir(ws, tid)
    _write_marker(pd, tid, ".reviewer.timeout", "timeout after 600s")
    _write_marker(
        pd, tid, ".reviewer.done", '{"verdict": "pass", "summary": "ok"}'
    )
    _write_marker(pd, tid, ".reviewer.out", '{"verdict": "pass", "summary": "ok"}')

    result = _call_check(tid, ws, _reviewer)

    # Has done → should parse output normally → PASS
    assert result.get("status") == "pass", f"expected pass, got {result}"
