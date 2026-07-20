"""Product async GC / session completion markers (pipeline green)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from _task_commit import porcelain_product_paths  # noqa: E402


def _load_engine_helpers():
    """Load ccc-engine helpers without running main."""
    path = SCRIPTS / "ccc-engine.py"
    spec = importlib.util.spec_from_file_location("ccc_engine_gc_test", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    # Avoid double-import side effects if already loaded
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_porcelain_allows_flow_smoke_excludes_board(tmp_path=None):
    porcelain = (
        " M .ccc/state.md\n"
        " M .ccc/board/index.json\n"
        " M .ccc/engine-heartbeat.json\n"
        "?? .ccc/flow-smoke.md\n"
        " M README.md\n"
        "?? .ccc/reports/t1.report.md\n"
        "?? .ccc/plans/t1.plan.md\n"
    )
    got = porcelain_product_paths(porcelain)
    assert ".ccc/flow-smoke.md" in got
    assert "README.md" in got
    assert ".ccc/reports/t1.report.md" not in got
    assert ".ccc/plans/t1.plan.md" not in got
    assert ".ccc/board/index.json" not in got
    assert ".ccc/state.md" not in got
    assert ".ccc/engine-heartbeat.json" not in got


def test_find_task_commit_accepts_parent_epic_id(tmp_path: Path):
    from _task_commit import find_task_commit, _commit_grep_needles

    assert _commit_grep_needles("flow-green-abc-w1") == [
        "flow-green-abc-w1",
        "flow-green-abc",
    ]
    # no git repo → empty
    assert find_task_commit(tmp_path, "flow-green-abc-w1") == ""


def test_porcelain_only_meta_is_empty():
    assert porcelain_product_paths(" M .ccc/state.md\n M .ccc/board/index.json\n") == []


def test_product_async_markers_has_out(tmp_path: Path):
    eng = _load_engine_helpers()
    ws = tmp_path / "app"
    pids = ws / ".ccc" / "pids"
    pids.mkdir(parents=True)
    tid = "flow-smoke-dead"
    (pids / f"{tid}.product.out").write_text(
        "---CHILDREN---\n[]\n---END_CHILDREN---\n", encoding="utf-8"
    )
    alive, has_done, has_out = eng._product_async_markers(ws, tid)
    assert alive is False
    assert has_done is False
    assert has_out is True


def test_finalize_via_out_calls_check(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    eng = _load_engine_helpers()
    ws = tmp_path / "app"
    pids = ws / ".ccc" / "pids"
    pids.mkdir(parents=True)
    tid = "epic-out-only"
    (pids / f"{tid}.product.out").write_text(
        "---CHILDREN---\n[]\n---END_CHILDREN---\n", encoding="utf-8"
    )
    key = f"{ws}::{tid}"
    eng._product_inflight[key] = {"tid": tid, "workspace": ws}

    calls: list[str] = []

    class _Board:
        @staticmethod
        def check_product_async(task_id: str):
            calls.append(task_id)
            return {"status": "success"}

    monkeypatch.setattr(eng, "ccc_board", _Board)
    monkeypatch.setattr(eng, "_activate_workspace", lambda _ws: None)
    monkeypatch.setattr(eng, "engine_log", lambda *_a, **_k: None)

    outcome = eng._finalize_or_gc_product_key(ws, tid, key)
    assert outcome == "finalized"
    assert calls == [tid]
    assert key not in eng._product_inflight


def test_product_session_writes_done_markers(tmp_path: Path):
    path = SCRIPTS / "ccc-product-session.py"
    spec = importlib.util.spec_from_file_location("ccc_product_session_markers", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)

    out = tmp_path / "t1.product.out"
    out.write_text("x", encoding="utf-8")
    stem = mod._marker_stem(out, "t1")
    mod._write_completion_markers(stem, 0, ok=True)
    assert (tmp_path / "t1.product.done").read_text(encoding="utf-8").startswith("ok")
    assert (tmp_path / "t1.product.exitcode").read_text(encoding="utf-8").strip() == "0"
