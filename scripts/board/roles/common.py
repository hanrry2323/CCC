"""board.roles.common — shared cfg/store/quarantine helpers for role modules."""
from __future__ import annotations

import json
import os
from pathlib import Path

from _config import Config, get_logger
from _board_store import FileBoardStore
from _utils import now_iso as _utils_now_iso
from _utils import sanitize_id as _utils_sanitize_id
from _claude_cli import resolve_claude_cli

from board.context import get_workspace, ccc_home
from board import store_ops as _store_ops

_log = get_logger("board.roles")

_cfg_instance: Config | None = None
_store_instance: FileBoardStore | None = None


def _get_cfg() -> Config:
    global _cfg_instance
    if _cfg_instance is None:
        _cfg_instance = Config()
    return _cfg_instance


def _get_store() -> FileBoardStore:
    """按当前 get_workspace() 取 store（多仓 Engine 必备；勿钉死 Config.workspace）。"""
    global _store_instance
    ws = get_workspace().resolve()
    if (
        _store_instance is None
        or Path(_store_instance.workspace).resolve() != ws
    ):
        _store_instance = FileBoardStore(ws)
    return _store_instance


def _reset_lazy() -> None:
    global _cfg_instance, _store_instance
    _cfg_instance = None
    _store_instance = None
    _store_ops.reset_store_cache()


class _CfgProxy:
    def __getattr__(self, name: str):
        return getattr(_get_cfg(), name)


class _StoreProxy:
    def __getattr__(self, name: str):
        return getattr(_get_store(), name)


cfg = _CfgProxy()
store = _StoreProxy()
CCC_HOME = ccc_home()
MAX_RETRY = cfg.max_retry
MAX_STALE_HOURS = cfg.max_stale_hours
WORKSPACES = cfg.audit_workspaces


def sanitize_id(tid: str) -> str:
    return _utils_sanitize_id(tid)


def now_iso() -> str:
    return _utils_now_iso()


def _backoff_seconds(retry: int) -> int:
    return min(60 * (2**retry), 3600)


def _quarantine(task_id: str, reason: str) -> None:
    """移入异常列 + failure ledger + lessons（角色共用）。"""
    store.quarantine(task_id, reason)
    try:
        from _failure_ledger import infer_role_from_reason, record_failure

        record_failure(
            get_workspace(),
            task_id=task_id,
            role=infer_role_from_reason(reason or ""),
            reason=reason or "unknown",
            from_col=None,
            to_col="abnormal",
            related_stats_event="quarantine",
        )
    except Exception as exc:
        _log.error("[failures] quarantine ledger failed for %s: %s", task_id, exc)
    try:
        from _lessons import auto_append_lesson_md

        auto_append_lesson_md(get_workspace(), task_id, phase=None, error=reason)
    except Exception as exc:
        _log.warning("[lessons] auto_append failed for %s: %s", task_id, exc)


def _task_id_exists(task_id: str) -> bool:
    return store._task_id_exists(task_id)


def create_task(data: dict, column: str = "backlog") -> bool:
    return store.create_task(data, column=column)


def list_tasks(column: str) -> list[dict]:
    return store.list_tasks(column)


def move_task(task_id: str, from_col: str, to_col: str) -> bool:
    return store.move_task(task_id, from_col, to_col)


def update_index() -> dict:
    return store.update_index()


def _load_retry_from_phases(phases: list[dict], phase_id: int) -> int:
    for p in phases:
        p_id = p.get("phase")
        if p_id is None:
            continue
        if int(p_id) != phase_id:
            continue
        try:
            return int(p.get("retry", 0))
        except (TypeError, ValueError):
            return 0
    return 0


def _load_timeout(phases_file: Path, default: int = None) -> int:
    if default is None:
        default = cfg.default_timeout
    try:
        with open(phases_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                phase = json.loads(line)
                if isinstance(phase, list):
                    phase = phase[0] if phase else {}
                if "schema_version" in phase:
                    continue
                to = phase.get("timeout")
                if to is None:
                    return default
                try:
                    from _config import parse_duration

                    return parse_duration(to, default)
                except Exception:
                    return default
    except (FileNotFoundError, json.JSONDecodeError) as e:
        _log.warning("load phase timeout from %s failed: %s", phases_file, e)
    return default


def _load_retry_cap(
    phases_file: Path, phase_id: int = None, default: int = None
) -> int:
    default_retry = getattr(cfg, "DEFAULT_RETRY", 3) if default is None else default
    try:
        with open(phases_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(obj, list):
                    obj = obj[0] if obj else {}
                if not isinstance(obj, dict) or "schema_version" in obj:
                    continue
                if phase_id is not None and obj.get("phase") != phase_id:
                    continue
                mr = obj.get("max_retry")
                if mr is None:
                    return default_retry
                try:
                    n = int(mr)
                except (TypeError, ValueError):
                    return default_retry
                if n < 1:
                    return default_retry
                return n
    except (FileNotFoundError, OSError) as e:
        _log.warning("load phase max_retry from %s failed: %s", phases_file, e)
    return default_retry


def _claude_bin() -> str:
    return resolve_claude_cli(require=True)


def _get_relay_url() -> str:
    return os.environ.get("AGENT_PLANNER_BASE_URL", "http://127.0.0.1:4000")


def _write_pass_verdict(task_id: str, reason: str) -> None:
    """写 Engine 门禁可读的 PASS verdict（红线 11）。"""
    verdict_dir = get_workspace() / ".ccc" / "verdicts"
    verdict_dir.mkdir(parents=True, exist_ok=True)
    (verdict_dir / f"{task_id}.verdict.md").write_text(
        f"# {task_id} Verdict\n\n"
        f"**Verdict:** PASS\n\n"
        f"{reason}\n",
        encoding="utf-8",
    )

