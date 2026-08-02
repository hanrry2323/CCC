"""engine.verify_gate — min-pipeline verify→done（kb 快通 + parent epic refresh）。

Product entry remains ``run_verify_gate`` in ``engine.gates`` / ``board.roles.verify``.
This module owns verified→released so ``gates.py`` stays thinner.
"""
from __future__ import annotations

import sys
from pathlib import Path

from _config import get_logger
from board.roles import kb_role
from engine.workspace import (
    workspace_scope,
    _get_store,
    _ws_label,
)

_log = get_logger("engine")


def _eng():
    for name in ("ccc_engine", "ccc_engine_test", "ccc_engine_parallel_test", "__main__"):
        m = sys.modules.get(name)
        if m is not None and hasattr(m, "engine_log"):
            return m
    for m in sys.modules.values():
        f = getattr(m, "__file__", None)
        if f and str(f).endswith("ccc-engine.py") and hasattr(m, "engine_log"):
            return m
    return None


def _engine_log(msg: str, *args: str) -> None:
    if args:
        msg = msg % args
    _log.info("%s", msg)


def refresh_parent_epic(ws: Path, work_tid: str) -> None:
    """子卡进入 verified/released 后立刻刷新 parent epic 五态。"""
    try:
        store = _get_store(ws)
        _col, task = store.find_task(work_tid)
        parent = (task or {}).get("parent_id")
        if not parent:
            from _board_store import normalize_task_view as _ntv

            task = _ntv(task or {"id": work_tid}, column=_col or "testing")
            parent = task.get("parent_id")
        if not parent:
            return
        from _product_fanout import refresh_epic_lifecycle

        new = refresh_epic_lifecycle(store, str(parent))
        if new:
            _engine_log(f"[{_ws_label(ws)}] epic {parent} refresh → {new}")
    except Exception as exc:
        _engine_log(f"[{_ws_label(ws)}] refresh parent epic for {work_tid}: {exc}")


# Compat alias used by gates.py
_refresh_parent_epic = refresh_parent_epic


def run_verified_kb_gate(ws: Path) -> None:
    """扫 verified → done。min-pipeline：跳过 kb LLM 快通 released。"""
    with workspace_scope(ws):
        return run_verified_kb_gate_unlocked(ws)


def run_verified_kb_gate_unlocked(ws: Path) -> None:
    eng = _eng()
    store = _get_store(ws)
    verified = store.list_tasks("verified")
    if not verified:
        return
    label = _ws_label(ws)

    try:
        from engine.min_pipeline import enabled as _min_on
    except Exception:
        def _min_on() -> bool:
            return True

    if _min_on():
        _engine_log(
            f"[{label}] [min-pipeline] verify→done skip kb LLM "
            f"({len(verified)} verified)"
        )
        for task in verified:
            tid = str(task.get("id") or "")
            if not tid:
                continue
            ok = store.move_task(tid, "verified", "released")
            if ok:
                if eng:
                    try:
                        eng._log_stats(
                            ws,
                            "move",
                            tid,
                            from_col="verified",
                            to_col="released",
                            path="min_pipeline_kb_fast",
                        )
                    except Exception as exc:
                        _log.debug("kb-fast stats: %s", exc)
                _engine_log(f"[{label}] {tid} ✓ min-pipeline → released")
                refresh_parent_epic(ws, tid)
        store.update_index()
        return

    _engine_log(f"[{label}] verified 列有 {len(verified)} 个任务，跑 kb_role")
    try:
        result = kb_role()
        moved = (result or {}).get("moved") or []
        for tid in moved:
            if eng:
                eng._log_stats(ws, "move", tid, from_col="verified", to_col="released")
            _engine_log(f"[{label}] {tid} ✓ kb → released")
            refresh_parent_epic(ws, tid)
        store.update_index()
    except Exception as exc:
        _engine_log(f"[{label}] kb_role 异常: {exc}")


# Compat aliases (ccc-engine / tests / loop)
_run_verified_kb_gate = run_verified_kb_gate
_run_verified_kb_gate_unlocked = run_verified_kb_gate_unlocked
