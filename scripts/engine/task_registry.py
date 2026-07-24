"""engine/task_registry.py — 任务生命周期（active_tasks / relaunch / product inflight）。

fix-planning-2026-07-24 ccc-engine.py 拆分布局：自包含模块。
原 ccc-engine.py:441-1058 任务生命周期函数 + module-level dicts 迁出。

使用：
    from engine.task_registry import (
        task_key, can_accept_dev, enqueue_pending_relaunch,
        git_head_for_task, relaunch_allowed, note_relaunch,
        product_inflight_for_ws, can_launch_product,
        rebuild_product_inflight, product_async_markers,
        drop_product_inflight, finalize_or_gc_product_key,
        gc_product_inflight,
        MAX_CONCURRENT, MAX_PRODUCT_INFLIGHT, MAX_PRODUCT_PER_WS,
    )
"""

from __future__ import annotations

import logging
import os
import subprocess
import time
from pathlib import Path

from _config import Config
from _utils import now_iso_utc
from engine.workspace import _activate_workspace, _get_store

_log = logging.getLogger("ccc.engine.task_registry")

_cfg = Config()
MAX_CONCURRENT = max(1, int(os.environ.get("CCC_MAX_CONCURRENT", "4") or "4"))
MAX_PRODUCT_INFLIGHT = int(os.environ.get("CCC_MAX_PRODUCT_INFLIGHT", "3") or "3")
MAX_PRODUCT_PER_WS = int(os.environ.get("CCC_MAX_PRODUCT_PER_WS", "2") or "2")

_pending_relaunch: dict[str, dict] = {}
_relaunch_meta: dict[str, dict] = {}
_product_inflight: dict[str, dict] = {}


def _now_iso() -> str:
    return now_iso_utc()


def task_key(ws: Path, tid: str) -> str:
    return f"{ws.resolve()}|{tid}"


def can_accept_dev(active_tasks: dict[str, dict]) -> bool:
    return len(active_tasks) < MAX_CONCURRENT


def enqueue_pending_relaunch(
    ws: Path,
    tid: str,
    *,
    complexity: str = "medium",
    reason: str = "recover",
) -> None:
    key = task_key(ws, tid)
    _pending_relaunch[key] = {
        "workspace": ws,
        "task_id": tid,
        "complexity": complexity,
        "reason": reason,
        "enqueued_at": time.time(),
    }
    _log.info("[slot] pending_relaunch +%s (%s)", tid, reason)


def git_head_for_task(ws: Path, tid: str) -> str:
    try:
        r = subprocess.run(
            ["git", "log", "-1", "--format=%H", f"--grep={tid}", "-E"],
            cwd=str(ws),
            capture_output=True,
            text=True,
            timeout=5,
        )
        return (r.stdout or "").strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def relaunch_backoff_key(ws: Path, tid: str, phase: int | None) -> str:
    return f"{task_key(ws, tid)}:p{phase if phase is not None else 0}"


def relaunch_allowed(ws: Path, tid: str, phase: int | None = None) -> bool:
    key = relaunch_backoff_key(ws, tid, phase)
    meta = _relaunch_meta.get(key) or {}
    now = time.time()
    last_ts = float(meta.get("last_ts") or 0)
    count = int(meta.get("count") or 0)
    last_head = str(meta.get("last_head") or "")
    cur_head = git_head_for_task(ws, tid)
    if cur_head and cur_head != last_head:
        return True
    if last_ts <= 0:
        return True
    wait = min(60 * (2 ** max(count - 1, 0)), 600)
    if now - last_ts < wait:
        _log.info(
            "[slot] relaunch backoff %s p=%s: wait %.0fs (elapsed %.0fs, n=%d)",
            tid,
            phase,
            wait,
            now - last_ts,
            count,
        )
        return False
    return True


def note_relaunch(ws: Path, tid: str, phase: int | None = None) -> None:
    key = relaunch_backoff_key(ws, tid, phase)
    prev = _relaunch_meta.get(key) or {}
    _relaunch_meta[key] = {
        "last_ts": time.time(),
        "count": int(prev.get("count") or 0) + 1,
        "last_head": git_head_for_task(ws, tid),
    }


def product_inflight_for_ws(ws: Path) -> int:
    ws_s = str(ws.resolve())
    n = 0
    for info in _product_inflight.values():
        w = info.get("workspace")
        if w is None:
            continue
        if str(Path(w).resolve()) == ws_s:
            n += 1
    return n


def can_launch_product(ws: Path) -> bool:
    if len(_product_inflight) >= MAX_PRODUCT_INFLIGHT:
        return False
    if product_inflight_for_ws(ws) >= MAX_PRODUCT_PER_WS:
        return False
    return True


def rebuild_product_inflight(workspaces: list[Path]) -> None:
    global _product_inflight
    rebuilt: dict[str, dict] = {}
    for ws in workspaces:
        pids_dir = ws / ".ccc" / "pids"
        if not pids_dir.is_dir():
            continue
        for pid_file in pids_dir.glob("*.product.pid"):
            tid = pid_file.name[: -len(".product.pid")]
            try:
                pid = int(pid_file.read_text().strip())
            except (OSError, ValueError):
                continue
            alive = False
            try:
                os.kill(pid, 0)
                alive = True
            except (OSError, ProcessLookupError):
                alive = False
            if not alive:
                continue
            key = task_key(ws, tid)
            rebuilt[key] = {
                "tid": tid,
                "started_at": _now_iso(),
                "workspace": ws,
                "pid": pid,
            }
    _product_inflight = rebuilt
    if rebuilt:
        _log.info(
            "[product] 重建 inflight=%d (max_global=%d, max_per_ws=%d)",
            len(rebuilt),
            MAX_PRODUCT_INFLIGHT,
            MAX_PRODUCT_PER_WS,
        )


def product_async_markers(ws: Path, tid: str) -> tuple[bool, bool, bool]:
    pids_dir = Path(ws) / ".ccc" / "pids"
    pid_file = pids_dir / f"{tid}.product.pid"
    done_file = pids_dir / f"{tid}.product.done"
    out_file = pids_dir / f"{tid}.product.out"
    alive = False
    if pid_file.is_file():
        try:
            pid = int(pid_file.read_text().strip())
            os.kill(pid, 0)
            alive = True
        except (OSError, ValueError, ProcessLookupError):
            alive = False
    has_out = False
    if out_file.is_file():
        try:
            has_out = bool(out_file.read_text(encoding="utf-8", errors="replace").strip())
        except OSError:
            has_out = False
    return alive, done_file.is_file(), has_out


def drop_product_inflight(key: str, reason: str) -> None:
    if key not in _product_inflight:
        return
    info = _product_inflight.pop(key, None) or {}
    tid = info.get("tid") or "?"
    _log.info("[product] inflight GC drop %s: %s", tid, reason)


def finalize_or_gc_product_key(ws: Path, tid: str, key: str) -> str:
    if key not in _product_inflight:
        return "dropped"
    alive, has_done, has_out = product_async_markers(ws, tid)
    if has_done or alive or has_out:
        via = "done" if has_done else ("alive" if alive else "out")
        try:
            _activate_workspace(ws)
            _log.info("[product] finalize via %s: %s", via, tid)
            import ccc_board

            result = ccc_board.check_product_async(tid)
        except Exception as exc:
            _log.info("[product] GC check %s 异常: %s", tid, exc)
            result = {"status": "running"}
        status = result.get("status")
        if status in ("success", "failed"):
            drop_product_inflight(key, f"check->{status}")
            return "finalized"
        if alive:
            return "kept"
        drop_product_inflight(key, "stale markers without live pid")
        return "dropped"

    try:
        store = _get_store(ws)
        col, task = store.find_task(tid)
    except Exception:
        col, task = None, None
    if col is None:
        drop_product_inflight(key, "task missing from board")
        return "dropped"
    if col != "backlog":
        drop_product_inflight(key, f"not in backlog (col={col})")
        return "dropped"
    kind = (task or {}).get("card_kind") or "epic"
    split = (task or {}).get("split_status") or "pending"
    if kind == "epic" and split != "pending":
        drop_product_inflight(key, f"epic split_status={split}")
        return "dropped"
    drop_product_inflight(key, "no live product pid")
    return "dropped"


def gc_product_inflight(workspaces: list[Path]) -> int:
    if not _product_inflight:
        return 0
    ws_set = {str(Path(w).resolve()) for w in workspaces}
    dropped = 0
    for key in list(_product_inflight.keys()):
        info = _product_inflight.get(key) or {}
        ws = info.get("workspace")
        tid = str(info.get("tid") or "").strip()
        if ws is None or not tid:
            drop_product_inflight(key, "invalid entry")
            dropped += 1
            continue
        ws_p = Path(ws)
        try:
            ws_s = str(ws_p.resolve())
        except OSError:
            drop_product_inflight(key, "workspace unreadable")
            dropped += 1
            continue
        if ws_set and ws_s not in ws_set:
            pass
        before = key in _product_inflight
        outcome = finalize_or_gc_product_key(ws_p, tid, key)
        if before and outcome != "kept":
            dropped += 1
    return dropped
