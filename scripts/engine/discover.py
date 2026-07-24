"""engine/discover.py — Workspace 发现 + wake/rediscover 调度。

fix-planning-2026-07-24 ccc-engine.py 拆分布局：自包含模块。
原 ccc-engine.py:695-815 + 2900-3021 散布的 9 函数迁出。

使用：
    from engine.discover import (
        discover_workspaces, rediscover_workspaces,
        apply_wake_payload, apply_dispatch_wake,
        prioritize_wake_workspace, sleep_until_wake, wait_tick,
    )
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path

from _board_store import FileBoardStore
from _config import Config

_log = logging.getLogger("ccc.engine.discover")


def discover_workspaces() -> list[Path]:
    try:
        from _workspace_registry import list_engine_paths, migrate_registry_roles

        migrate_registry_roles(dry_run=False)
        return list_engine_paths()
    except ImportError:
        program_dir = Path.home() / "program"
        if not program_dir.is_dir():
            return []
        result: list[Path] = []
        for ws in sorted(program_dir.iterdir()):
            if (ws / ".ccc" / "board").is_dir():
                result.append(ws)
        return result


def queue_has_consumable_work(store: FileBoardStore) -> bool:
    for col in ("backlog", "planned", "in_progress", "testing", "verified"):
        if store.list_tasks(col):
            return True
    return False


def may_invent() -> bool:
    try:
        from _ccc_control import may_invent as _mi

        return _mi()
    except ImportError:
        return False


def rediscover_workspaces(current: list[Path]) -> list[Path]:
    try:
        discovered = discover_workspaces()
    except Exception as exc:
        _log.warning("[workspace] rediscover failed: %s", exc)
        return list(current)
    if not discovered:
        return list(current)
    old = {str(p.resolve()) for p in current}
    new = {str(p.resolve()) for p in discovered}
    if old != new:
        _log.info(
            "[workspace] rediscover %d -> %d: %s",
            len(current),
            len(discovered),
            [p.name for p in discovered],
        )
        return discovered
    return list(current)


def apply_wake_payload(payload: dict | None, workspaces: list[Path]) -> bool:
    if not payload or not isinstance(payload, dict):
        return False
    reason = str(payload.get("reason") or "")
    is_dispatch = (
        reason.startswith("task_dispatch")
        or reason in ("wake", "task_dispatch", "hub_manual_start")
        or "task_dispatch" in reason
        or bool(payload.get("workspace") or payload.get("task_id"))
    )
    if not is_dispatch:
        return False
    _log.info("[wake] apply reason=%s task=%s ws=%s", reason, payload.get("task_id"), payload.get("workspace"))
    return True


def apply_dispatch_wake(workspaces: list[Path], already_consumed: dict | None = None) -> bool:
    wake_path = Path.home() / ".ccc" / "engine.wake"
    if already_consumed is not None:
        return apply_wake_payload(already_consumed, workspaces)
    if not wake_path.is_file():
        return False
    try:
        payload = json.loads(wake_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if apply_wake_payload(payload, workspaces):
        try:
            wake_path.unlink()
        except OSError:
            pass
        return True
    return False


def prioritize_wake_workspace(workspaces: list[Path], wake_priority_ws: Path | None = None) -> list[Path]:
    if wake_priority_ws is None or not workspaces:
        return list(workspaces)
    try:
        pri_res = wake_priority_ws.resolve()
    except OSError:
        return list(workspaces)
    head: list[Path] = []
    rest: list[Path] = []
    for ws in workspaces:
        try:
            if ws.resolve() == pri_res:
                head.append(ws)
            else:
                rest.append(ws)
        except OSError:
            rest.append(ws)
    if not head:
        if pri_res.is_dir():
            return [pri_res] + list(workspaces)
        return list(workspaces)
    return head + rest


def sleep_until_wake(seconds: float) -> dict | None:
    try:
        from _engine_wake import consume_wake

        end = time.time() + max(0.0, seconds)
        while time.time() < end:
            payload = consume_wake()
            if payload is not None:
                return payload if isinstance(payload, dict) else {"reason": "wake"}
            time.sleep(min(2.0, max(0.1, end - time.time())))
        payload = consume_wake()
        if payload is not None:
            return payload if isinstance(payload, dict) else {"reason": "wake"}
        return None
    except Exception:
        time.sleep(seconds)
        return None


def wait_tick(tick_start: float) -> None:
    cfg = Config()
    elapsed = time.time() - tick_start
    remaining = cfg.engine_poll_interval - elapsed
    if remaining > 0:
        time.sleep(min(remaining, cfg.engine_poll_interval))
