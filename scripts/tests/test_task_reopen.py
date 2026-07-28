"""v0.42: reopen_task + clear pids"""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from _board_store import FileBoardStore
from _task_reopen import reopen_task, clear_task_pid_markers


def _mk_ws(tmp_path: Path) -> Path:
    for col in (
        "backlog",
        "planned",
        "in_progress",
        "testing",
        "verified",
        "released",
        "abnormal",
    ):
        (tmp_path / ".ccc" / "board" / col).mkdir(parents=True)
    (tmp_path / ".ccc" / "pids").mkdir(parents=True)
    return tmp_path


def test_reopen_from_abnormal(tmp_path, monkeypatch):
    ws = _mk_ws(tmp_path)
    store = FileBoardStore(ws)
    tid = "reopen-1"
    store.create_task(
        {
            "id": tid,
            "title": "t",
            "status": "abnormal",
            "created_at": "2026-07-17",
            "updated_at": "2026-07-17",
        },
        column="abnormal",
    )
    pid = ws / ".ccc" / "pids" / f"{tid}.reviewer.pid"
    pid.write_text("123")

    monkeypatch.setenv("HOME", str(tmp_path))
    import _ccc_control as ctrl
    import _engine_wake as wake

    ctrl.CONTROL_DIR = tmp_path / ".ccc"
    ctrl.CONTROL_FILE = ctrl.CONTROL_DIR / "control.json"
    ctrl.DISABLED_SENTINEL = ctrl.CONTROL_DIR / "DISABLED"
    wake.WAKE_FILE = tmp_path / ".ccc" / "engine.wake"
    ctrl.set_mode("ui", reason="test", source="cli")

    with patch.object(wake, "_bootstrap_engine_launchd", return_value=(False, "skip")):
        out = reopen_task(ws, tid, to_col="planned", wake=True)

    assert out["ok"] is True
    assert out["from"] == "abnormal"
    assert out["to"] == "planned"
    assert not pid.exists()
    assert any(t["id"] == tid for t in store.list_tasks("planned"))
    assert wake.WAKE_FILE.is_file()
    assert out["engine_wake"]["mode_after"] == "enabled"


def test_reopen_rejects_verified(tmp_path):
    ws = _mk_ws(tmp_path)
    store = FileBoardStore(ws)
    store.create_task(
        {
            "id": "v1",
            "title": "t",
            "status": "verified",
            "created_at": "2026-07-17",
            "updated_at": "2026-07-17",
        },
        column="verified",
    )
    out = reopen_task(ws, "v1", wake=False)
    assert out["ok"] is False
    assert "cannot reopen" in out["error"]


def test_clear_pid_markers(tmp_path):
    ws = _mk_ws(tmp_path)
    f = ws / ".ccc" / "pids" / "x.product.pid"
    f.write_text("1")
    cleared = clear_task_pid_markers(ws, "x")
    assert "x.product.pid" in cleared
    assert not f.exists()


def test_clear_pid_markers_new_suffixes(tmp_path):
    """Phase C / 015: .reviewer.timeout / .reviewer.exitcode / .tester.timeout 对称清理。"""
    ws = _mk_ws(tmp_path)
    tid = "015-suffix"
    for sfx in (".reviewer.timeout", ".reviewer.exitcode", ".tester.timeout"):
        (ws / ".ccc" / "pids" / f"{tid}{sfx}").write_text("1")
    cleared = clear_task_pid_markers(ws, tid)
    for sfx in (".reviewer.timeout", ".reviewer.exitcode", ".tester.timeout"):
        assert f"{tid}{sfx}" in cleared, f"missing {sfx}"
        assert not (ws / ".ccc" / "pids" / f"{tid}{sfx}").exists()


def test_reopen_abnormal_clean_pids_glob_fallback(tmp_path):
    """Glob 兜底清理也 handle 新 suffix（即使 _PID_SUFFIXES 缺漏）。"""
    ws = _mk_ws(tmp_path)
    tid = "015-glob"
    for sfx in (".unknown.new", ".strange.marker"):
        (ws / ".ccc" / "pids" / f"{tid}{sfx}").write_text("1")
    cleared = clear_task_pid_markers(ws, tid)
    for sfx in (".unknown.new", ".strange.marker"):
        assert f"{tid}{sfx}" in cleared, f"glob fallback missing {sfx}"


def test_reopen_rejects_released(tmp_path):
    """Released 列也不可 reopen。"""
    ws = _mk_ws(tmp_path)
    store = FileBoardStore(ws)
    store.create_task(
        {"id": "r1", "title": "t", "status": "released", "created_at": "2026-07-17"},
        column="released",
    )
    out = reopen_task(ws, "r1", wake=False)
    assert out["ok"] is False
    assert "cannot reopen" in out["error"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
