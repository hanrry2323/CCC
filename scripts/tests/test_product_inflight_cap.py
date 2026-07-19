"""Product inflight 全局/每 WS 上限与 PID 重建。"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))


def _load_engine():
    spec = importlib.util.spec_from_file_location(
        "ccc_engine_prod", SCRIPTS / "ccc-engine.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_can_launch_product_global_and_per_ws_caps(tmp_path, monkeypatch):
    engine = _load_engine()
    engine._product_inflight.clear()
    ws_a = tmp_path / "a"
    ws_b = tmp_path / "b"
    ws_a.mkdir()
    ws_b.mkdir()

    # 全局满
    for i in range(engine.MAX_PRODUCT_INFLIGHT):
        other = Path(f"/tmp/other-ws-{i}")
        engine._product_inflight[f"{other}|t{i}"] = {
            "workspace": other,
            "tid": f"t{i}",
        }
    assert engine._can_launch_product(ws_a) is False

    engine._product_inflight.clear()
    # 同 WS 满（默认 2）
    for i in range(engine.MAX_PRODUCT_PER_WS):
        key = engine._task_key(ws_a, f"local-{i}")
        engine._product_inflight[key] = {
            "workspace": ws_a,
            "tid": f"local-{i}",
        }
    assert engine._can_launch_product(ws_a) is False
    assert engine._can_launch_product(ws_b) is True


def test_rebuild_product_inflight_from_live_pids(tmp_path):
    engine = _load_engine()
    engine._product_inflight.clear()
    pids = tmp_path / ".ccc" / "pids"
    pids.mkdir(parents=True)
    (pids / "alive-task.product.pid").write_text(str(os.getpid()))
    (pids / "dead-task.product.pid").write_text("999999999")
    engine._rebuild_product_inflight([tmp_path])
    keys = list(engine._product_inflight.keys())
    assert any("alive-task" in k for k in keys)
    assert not any("dead-task" in k for k in keys)


def test_process_backlog_respects_per_ws_cap(tmp_path, monkeypatch):
    engine = _load_engine()
    engine._product_inflight.clear()
    monkeypatch.setattr(engine, "_degraded_mode", False)
    monkeypatch.setattr(engine, "_activate_workspace", lambda ws: ws)
    monkeypatch.setattr(engine, "_is_upstream_healthy", lambda: True)
    monkeypatch.setattr(engine, "_log_stats", lambda *a, **k: None)

    board = tmp_path / ".ccc" / "board"
    for col in (
        "backlog",
        "planned",
        "in_progress",
        "testing",
        "verified",
        "released",
        "abnormal",
    ):
        (board / col).mkdir(parents=True)
    (tmp_path / ".ccc" / "plans").mkdir(parents=True)
    (tmp_path / ".ccc" / "phases").mkdir(parents=True)
    (tmp_path / ".ccc" / "pids").mkdir(parents=True)

    tasks = []
    for i in range(3):
        tid = f"xy-cap-{i}"
        tasks.append({"id": tid, "title": tid, "complexity": "medium"})
        (board / "backlog" / f"{tid}.json").write_text(
            json.dumps({"id": tid, "title": tid, "complexity": "medium"})
        )

    launched: list[str] = []

    def _launch(tid):
        launched.append(tid)
        return {"ok": True}

    monkeypatch.setattr(engine.ccc_board, "launch_product_async", _launch)
    monkeypatch.setattr(
        engine.ccc_board, "_classify_task_intake", lambda *_a, **_k: "full"
    )

    class _Store:
        def list_tasks(self, col):
            if col == "backlog":
                return list(tasks)
            return []

        def move_task(self, *a, **k):
            return True

        def update_index(self):
            return None

    monkeypatch.setattr(engine, "_get_store", lambda ws: _Store())
    engine._process_backlog(tmp_path)
    assert len(launched) == engine.MAX_PRODUCT_PER_WS
    assert len(engine._product_inflight) == engine.MAX_PRODUCT_PER_WS


def test_write_heartbeat_includes_slot_fields(tmp_path, monkeypatch):
    engine = _load_engine()
    (tmp_path / ".ccc").mkdir(parents=True)
    engine._product_inflight.clear()
    engine._product_inflight["x|y"] = {"tid": "y"}
    engine._pending_relaunch.clear()

    class _Store:
        def list_tasks(self, col):
            if col == "testing":
                return [{"id": "t1"}]
            return []

    monkeypatch.setattr(engine, "_get_store", lambda ws: _Store())
    engine._write_heartbeat(
        tmp_path,
        "running-1",
        1,
        [123],
        testing_count=2,
        global_active_count=3,
    )
    hb = json.loads((tmp_path / ".ccc" / "engine-heartbeat.json").read_text())
    assert hb["dev_slots"] == {"used": 3, "max": engine.MAX_CONCURRENT}
    assert hb["product_inflight"] == 1
    assert hb["testing"] == 2
    assert "pending_relaunch" in hb


def test_gc_product_inflight_clears_orphan_when_task_missing(tmp_path, monkeypatch):
    engine = _load_engine()
    engine._product_inflight.clear()
    (tmp_path / ".ccc" / "pids").mkdir(parents=True)
    key = engine._task_key(tmp_path, "gone-task")
    engine._product_inflight[key] = {"workspace": tmp_path, "tid": "gone-task"}

    class _Store:
        def find_task(self, tid):
            return None, None

    monkeypatch.setattr(engine, "_get_store", lambda ws: _Store())
    monkeypatch.setattr(engine, "_activate_workspace", lambda ws: ws)
    n = engine._gc_product_inflight([tmp_path])
    assert n == 1
    assert key not in engine._product_inflight
    assert engine._can_launch_product(tmp_path) is True


def test_gc_product_inflight_clears_epic_planned_without_pid(tmp_path, monkeypatch):
    engine = _load_engine()
    engine._product_inflight.clear()
    (tmp_path / ".ccc" / "pids").mkdir(parents=True)
    key = engine._task_key(tmp_path, "epic-planned")
    engine._product_inflight[key] = {"workspace": tmp_path, "tid": "epic-planned"}

    class _Store:
        def find_task(self, tid):
            return "backlog", {
                "id": tid,
                "card_kind": "epic",
                "split_status": "planned",
            }

    monkeypatch.setattr(engine, "_get_store", lambda ws: _Store())
    monkeypatch.setattr(engine, "_activate_workspace", lambda ws: ws)
    engine._gc_product_inflight([tmp_path])
    assert key not in engine._product_inflight


def test_gc_product_inflight_keeps_live_pid(tmp_path, monkeypatch):
    engine = _load_engine()
    engine._product_inflight.clear()
    pids = tmp_path / ".ccc" / "pids"
    pids.mkdir(parents=True)
    tid = "live-epic"
    (pids / f"{tid}.product.pid").write_text(str(os.getpid()))
    key = engine._task_key(tmp_path, tid)
    engine._product_inflight[key] = {"workspace": tmp_path, "tid": tid}

    class _Store:
        def find_task(self, tid_):
            return "backlog", {
                "id": tid_,
                "card_kind": "epic",
                "split_status": "pending",
            }

    monkeypatch.setattr(engine, "_get_store", lambda ws: _Store())
    monkeypatch.setattr(engine, "_activate_workspace", lambda ws: ws)
    monkeypatch.setattr(
        engine.ccc_board,
        "check_product_async",
        lambda _tid: {"status": "running"},
    )
    engine._gc_product_inflight([tmp_path])
    assert key in engine._product_inflight


def test_gc_product_inflight_empty_backlog_orphans(tmp_path, monkeypatch):
    """空板时 GC 仍清掉内存孤儿（不依赖 _process_backlog）。"""
    engine = _load_engine()
    engine._product_inflight.clear()
    (tmp_path / ".ccc" / "pids").mkdir(parents=True)
    for i in range(engine.MAX_PRODUCT_PER_WS):
        tid = f"orphan-{i}"
        key = engine._task_key(tmp_path, tid)
        engine._product_inflight[key] = {"workspace": tmp_path, "tid": tid}

    class _Store:
        def find_task(self, tid):
            return None, None

        def list_tasks(self, col):
            return []

    monkeypatch.setattr(engine, "_get_store", lambda ws: _Store())
    monkeypatch.setattr(engine, "_activate_workspace", lambda ws: ws)
    assert engine._can_launch_product(tmp_path) is False
    engine._gc_product_inflight([tmp_path])
    assert engine._product_inflight == {}
    assert engine._can_launch_product(tmp_path) is True
