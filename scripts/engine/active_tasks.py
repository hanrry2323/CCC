"""engine.active_tasks — active task 持久化与槽位释放。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from _config import get_logger
from _executor import _sanitized_env
from _utils import now_iso
from engine.slots import release_opencode_slot

_log = get_logger("engine")

ACTIVE_TASKS_FILE = Path.home() / ".ccc" / "engine-active-tasks.json"


def _eng():
    for name in ("ccc_engine", "ccc_engine_test", "ccc_engine_parallel_test", "__main__"):
        m = sys.modules.get(name)
        if m is not None and hasattr(m, "MAX_CONCURRENT"):
            return m
    for m in sys.modules.values():
        f = getattr(m, "__file__", None)
        if f and str(f).endswith("ccc-engine.py") and hasattr(m, "MAX_CONCURRENT"):
            return m
    return None


def _engine_log(msg: str, *args: str) -> None:
    if args:
        msg = msg % args
    _log.info("%s", msg)


def _task_key(ws: Path, tid: str) -> str:
    return f"{ws.resolve()}|{tid}"


def _can_accept_dev(active_tasks: dict[str, dict]) -> bool:
    eng = _eng()
    max_c = getattr(eng, "MAX_CONCURRENT", 3) if eng else 3
    return len(active_tasks) < max_c


def _register_active(
    active_tasks: dict[str, dict],
    ws: Path,
    tid: str,
    *,
    complexity: str = "medium",
    mode: str | None = None,
) -> bool:
    """统一登记 active_tasks；已满则拒绝（保证 len ≤ MAX_CONCURRENT）。"""
    key = _task_key(ws, tid)
    if key in active_tasks:
        return True
    if not _can_accept_dev(active_tasks):
        eng = _eng()
        max_c = getattr(eng, "MAX_CONCURRENT", 3) if eng else 3
        _engine_log(
            f"[slot] refuse register {tid}: "
            f"dev_slots={len(active_tasks)}/{max_c}"
        )
        return False
    info: dict = {
        "workspace": ws,
        "task_id": tid,
        "complexity": complexity,
        "started_at": now_iso(),
    }
    if mode:
        info["mode"] = mode
    active_tasks[key] = info
    _save_active_tasks(active_tasks)
    return True


def _save_active_tasks(active_tasks: dict[str, dict]) -> None:
    """持久化 active_tasks 到 ~/.ccc/engine-active-tasks.json，Engine 重启后恢复。"""
    try:
        ACTIVE_TASKS_FILE.parent.mkdir(parents=True, exist_ok=True)
        serializable = {}
        for k, v in active_tasks.items():
            item = dict(v)
            ws = item.get("workspace")
            ws_s = str(ws) if ws is not None else ""
            low = ws_s.lower()
            if (
                "/pytest-" in low
                or "pytest-of-" in low
                or "/pytest_of_" in low
                or "/var/folders/" in low
                or "/tmp/" in low
            ):
                _engine_log(f"[persist] 跳过测试路径 active_task: {k}")
                continue
            if isinstance(ws, Path):
                item["workspace"] = str(ws)
            serializable[k] = item
        ACTIVE_TASKS_FILE.write_text(
            json.dumps(serializable, ensure_ascii=False, indent=2, default=str)
        )
    except (OSError, TypeError) as exc:
        _engine_log(f"[persist] save active_tasks 失败: {exc}")


def _load_active_tasks() -> dict[str, dict]:
    """从持久化文件恢复 active_tasks。返回 dict（可能是空的）。"""
    if not ACTIVE_TASKS_FILE.exists():
        return {}
    try:
        raw = json.loads(ACTIVE_TASKS_FILE.read_text())
        if not isinstance(raw, dict):
            return {}
        restored = {}
        for k, v in raw.items():
            ws_str = v.get("workspace", "")
            ws_path = Path(ws_str).resolve() if ws_str else None
            if not ws_path or not ws_path.is_dir() or not (ws_path / ".ccc" / "board").is_dir():
                _engine_log(f"[persist] 忽略 {k}: workspace 不存在")
                continue
            v["workspace"] = ws_path

            tid = v.get("task_id", "")
            alive = False
            if tid:
                import subprocess as _sp

                pids_dir = ws_path / ".ccc" / "pids"
                for pidf in sorted(pids_dir.glob(f"{tid}*.pid")):
                    if pidf.name.endswith(".done"):
                        continue
                    try:
                        pid = int(pidf.read_text().strip())
                        r = _sp.run(
                            ["ps", "-p", str(pid), "-o", "state="],
                            capture_output=True,
                            text=True,
                            timeout=3,
                            env=_sanitized_env(),
                        )
                        state = r.stdout.strip()
                        if state and state != "Z":
                            alive = True
                            break
                    except (ValueError, OSError):
                        continue
            if not alive:
                _engine_log(
                    f"[persist] 排除僵尸 active_task {k}: "
                    f"进程不存活 (tid={tid})"
                )
                continue
            restored[k] = v

        if restored:
            _engine_log(f"[persist] 恢复 {len(restored)} 个 active_tasks (存活)")
        return restored
    except (json.JSONDecodeError, OSError, TypeError) as exc:
        _engine_log(f"[persist] load active_tasks 失败: {exc}")
        return {}
    finally:
        try:
            ACTIVE_TASKS_FILE.unlink(missing_ok=True)
        except OSError:
            pass


def _drop_active_task_and_slots(
    active_tasks: dict[str, dict] | None, task_key: str
) -> None:
    """F-CON-02: quarantine/完成时统一释放槽位并从 active_tasks 移除。"""
    released = release_opencode_slot(task_key)
    if active_tasks is not None and task_key in active_tasks:
        active_tasks.pop(task_key, None)
        _save_active_tasks(active_tasks)
    if released:
        _engine_log(f"[slot] released {released} opencode slot(s) for {task_key}")
