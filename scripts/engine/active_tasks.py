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

        # v0.51.0 (P1-4): 先收集所有 (task_key, candidate_pids) 再单次 ps 拉全表
        # 旧版每个 .pid 文件 fork 一次 ps，N×M 次子进程；新版只 fork 1 次。
        candidates: dict[str, set[int]] = {}  # task_key → set of pids
        metadata: dict[str, dict] = {}  # task_key → v (with workspace resolved)
        for k, v in raw.items():
            ws_str = v.get("workspace", "")
            ws_path = Path(ws_str).resolve() if ws_str else None
            if not ws_path or not ws_path.is_dir() or not (ws_path / ".ccc" / "board").is_dir():
                _engine_log(f"[persist] 忽略 {k}: workspace 不存在")
                continue
            v["workspace"] = ws_path
            metadata[k] = v

            tid = v.get("task_id", "")
            if not tid:
                _engine_log(f"[persist] 排除僵尸 active_task {k}: 无 task_id")
                continue

            pids_dir = ws_path / ".ccc" / "pids"
            pids: set[int] = set()
            for pidf in sorted(pids_dir.glob(f"{tid}*.pid")):
                if pidf.name.endswith(".done"):
                    continue
                try:
                    pids.add(int(pidf.read_text().strip()))
                except (ValueError, OSError):
                    continue
            if not pids:
                _engine_log(
                    f"[persist] 排除僵尸 active_task {k}: 无 PID 文件 (tid={tid})"
                )
                continue
            candidates[k] = pids

        # 单次 ps 拉所有候选 PID 的状态
        all_pids: set[int] = set()
        for s in candidates.values():
            all_pids |= s
        alive_pids = _query_pids_alive(all_pids)

        # 对每个 task 检查是否有任一 PID 存活
        restored: dict[str, dict] = {}
        for k, pids in candidates.items():
            if pids & alive_pids:
                restored[k] = metadata[k]
            else:
                _engine_log(
                    f"[persist] 排除僵尸 active_task {k}: "
                    f"进程不存活 (pids={sorted(pids)})"
                )

        if restored:
            _engine_log(f"[persist] 恢复 {len(restored)} 个 active_tasks (存活)")
        return restored
    except (json.JSONDecodeError, OSError, TypeError) as exc:
        _engine_log(f"[persist] load active_tasks 失败: {exc}")
        return {}


def _query_pids_alive(pids: set[int]) -> set[int]:
    """v0.51.0 (P1-4): 单次 ps 拉所有 PID 的状态，返回存活 PID 集合。

    PID 状态非 Z（zombie）且非空视为存活。ps 失败时返回空集（保守处理，
    让上层将所有候选视为僵尸 → 不恢复，符合旧版语义）。
    """
    if not pids:
        return set()
    try:
        import subprocess as _sp

        cmd = ["ps", "-o", "pid=,state="] + [str(p) for p in sorted(pids)]
        r = _sp.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=5,
            env=_sanitized_env(),
        )
        alive: set[int] = set()
        for line in r.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split(None, 1)
            if len(parts) < 2:
                continue
            try:
                pid = int(parts[0])
            except ValueError:
                continue
            state = parts[1].strip()
            if state and state != "Z":
                alive.add(pid)
        return alive
    except (OSError, ValueError):
        return set()


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


def _dev_runner_done(ws: Path, tid: str) -> bool:
    return (Path(ws) / ".ccc" / "pids" / f"{tid}.done").is_file()


def _dev_runner_pid_alive(ws: Path, tid: str) -> bool:
    pid_path = Path(ws) / ".ccc" / "pids" / f"{tid}.pid"
    if not pid_path.is_file():
        return False
    try:
        import os

        pid = int(pid_path.read_text().strip())
        os.kill(pid, 0)
        return True
    except (OSError, ValueError, ProcessLookupError):
        return False


def workspace_blocks_new_opencode(
    ws: Path, active_tasks: dict[str, dict], *, lease_sec: float = 90.0
) -> bool:
    """同仓互斥：仅当存在活 runner 或未过期 lease（无 .done）时挡新卡。

    产线提效 P1：死 pid + 已有 ``.done`` 不得挡同仓下一卡（幽灵槽）。
    """
    import time
    from datetime import datetime

    ws_r = Path(ws).resolve()
    now = time.time()
    for info in active_tasks.values():
        other = info.get("workspace")
        try:
            other_r = Path(other).resolve() if other else None
        except OSError:
            other_r = None
        if other_r != ws_r:
            continue
        tid = str(info.get("task_id") or "")
        if not tid:
            return True
        if _dev_runner_done(ws_r, tid):
            # 终态应收口释槽；本 tick 不挡新 launch
            continue
        if _dev_runner_pid_alive(ws_r, tid):
            return True
        # 无 .done：刚 register / 尚无 pid → lease 内仍挡
        started = info.get("started_at")
        age = lease_sec + 1.0
        if isinstance(started, str) and started:
            try:
                ts = started.replace("Z", "+00:00")
                age = now - datetime.fromisoformat(ts).timestamp()
            except ValueError:
                age = 0.0
        if age <= lease_sec:
            return True
        # lease 过期 + 死 pid + 无 done → 不挡（交给 check_complete 收口）
        _engine_log(
            f"[slot] [{ws_r.name}] ghost active {tid} "
            f"(dead/no-done, age={age:.0f}s) — 不挡同仓 launch"
        )
    return False


def release_dev_slot(
    active_tasks: dict[str, dict] | None,
    ws: Path,
    tid: str,
    *,
    reap: bool = True,
) -> None:
    """终态必释槽：pop active_tasks + release_opencode_slot + 可选 reap。"""
    key = _task_key(ws, tid)
    _drop_active_task_and_slots(active_tasks, key)
    if reap:
        try:
            from _opencode_reap import reap_opencode_workspace

            reap_opencode_workspace(Path(ws), max_age_sec=0, grace_sec=0.2)
        except Exception as exc:
            _engine_log(f"[slot] reap after release {tid}: {exc}")

