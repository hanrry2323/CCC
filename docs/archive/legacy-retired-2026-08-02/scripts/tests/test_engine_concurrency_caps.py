"""Engine dev 槽位上限：register / recover 不得突破 MAX_CONCURRENT。"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))


def _load_engine():
    spec = importlib.util.spec_from_file_location(
        "ccc_engine_caps", SCRIPTS / "ccc-engine.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    # 2026-07-24 重构：engine.active_tasks._eng() 通过 sys.modules 找 engine 模块；
    # importlib util 不自动注册，需 setdefault 到标准名才能让 _eng() 找到。
    sys.modules.setdefault("ccc_engine", mod)
    return mod


def test_register_active_refuses_when_full(tmp_path, monkeypatch):
    engine = _load_engine()
    monkeypatch.setattr(engine, "_save_active_tasks", lambda *_a, **_k: None)
    active: dict = {}
    for i in range(engine.MAX_CONCURRENT):
        assert engine._register_active(active, tmp_path, f"t{i}")
    assert len(active) == engine.MAX_CONCURRENT
    assert not engine._register_active(active, tmp_path, "overflow")
    assert len(active) == engine.MAX_CONCURRENT
    assert engine._can_accept_dev(active) is False


def test_recover_running_caps_active_and_enqueues_pending(tmp_path, monkeypatch):
    engine = _load_engine()
    monkeypatch.setattr(engine, "_save_active_tasks", lambda *_a, **_k: None)
    monkeypatch.setattr(engine, "_activate_workspace", lambda ws: ws)
    monkeypatch.setattr(engine, "_current_running_phase", lambda tid: 1)
    monkeypatch.setattr(
        engine, "dev_role_check_complete", lambda tid: {"status": "running"}
    )
    monkeypatch.setattr(engine.time, "sleep", lambda *_a, **_k: None)
    monkeypatch.setattr(
        engine.ccc_board, "clear_stale_review_locks", lambda *a, **k: []
    )

    class _Store:
        def list_tasks(self, col):
            if col == "in_progress":
                return [
                    {"id": f"task-{i}", "complexity": "medium"} for i in range(10)
                ]
            return []

    monkeypatch.setattr(engine, "_get_store", lambda ws: _Store())
    engine._pending_relaunch.clear()
    active: dict = {}
    engine._recover_tasks(tmp_path, active)
    assert len(active) <= engine.MAX_CONCURRENT
    assert len(active) == engine.MAX_CONCURRENT
    assert len(engine._pending_relaunch) == 10 - engine.MAX_CONCURRENT


def test_relaunch_backoff_blocks_without_new_commit(tmp_path, monkeypatch):
    engine = _load_engine()
    # 2026-07-24：relaunch_allowed 在 engine.task_registry 里本地调用
    # git_head_for_task（line 98），monkeypatch engine._git_head_for_task 改不到它。
    # 必须 patch 真实源模块：engine.task_registry.git_head_for_task。
    # engine.task_registry._relaunch_meta 与 engine._relaunch_meta 是同对象（已验证），
    # 用任一引用清空即可。
    from engine import task_registry as _tr

    monkeypatch.setattr(_tr, "git_head_for_task", lambda ws, tid: "abc")
    _tr._relaunch_meta.clear()
    assert engine._relaunch_allowed(tmp_path, "t1", 1) is True
    engine._note_relaunch(tmp_path, "t1", 1)
    # 立即再试：应退避
    assert engine._relaunch_allowed(tmp_path, "t1", 1) is False
    # 新 commit → 立即允许
    monkeypatch.setattr(_tr, "git_head_for_task", lambda ws, tid: "def")
    assert engine._relaunch_allowed(tmp_path, "t1", 1) is True
