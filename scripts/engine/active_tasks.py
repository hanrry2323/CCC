"""engine.active_tasks — active task 持久化与槽位释放。"""
from __future__ import annotations

import fcntl
import json
import os
import sys
import tempfile
from pathlib import Path

from _config import get_logger
from _executor import _sanitized_env
from _utils import now_iso
from engine.slots import release_opencode_slot

_log = get_logger("engine")

ACTIVE_TASKS_FILE = Path.home() / ".ccc" / "engine-active-tasks.json"
ACTIVE_TASKS_BAK_FILE = Path.home() / ".ccc" / "engine-active-tasks.json.bak"


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


def _atomic_write_json(path: Path, content: str) -> None:
    """atomic write：独立 lock fd + mkstemp + fsync + dir fsync。

    修复 stability-audit-2026-07-24 类别①：直接 write_text 崩溃可截断。
    本地实现避免 engine 模块依赖 _board_store（边界独立）。
    修复 diff-review-2026-07-24 中风险 #2：用独立 lock_fd 持锁到 os.replace
    完成（原实现 fdopen close 时释放 lock，replace 阶段无锁保护）。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    # 独立 lock fd（O_CREAT 创建空 lock 文件，不影响 path 内容）
    lock_path = path.with_name(path.name + ".lock")
    lock_fd = os.open(str(lock_path), os.O_RDWR | os.O_CREAT, 0o644)
    try:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
        except OSError:
            # flock 不支持时降级
            pass
        fd, tmp_name = tempfile.mkstemp(
            dir=str(path.parent),
            prefix=".active-",
            suffix=".tmp",
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8", closefd=True) as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())
            try:
                dir_fd = os.open(str(path.parent), os.O_RDONLY)
                try:
                    os.fsync(dir_fd)
                finally:
                    os.close(dir_fd)
            except OSError as exc:
                _log.debug("active_tasks dir fsync: %s", exc)
            os.replace(tmp_name, str(path))
        except Exception:
            try:
                os.unlink(tmp_name)
            except OSError as exc:
                _log.debug("active_tasks tmp unlink: %s", exc)
            raise
    finally:
        try:
            os.close(lock_fd)
        except OSError as exc:
            _log.debug("active_tasks lock_fd close: %s", exc)


def _save_active_tasks(active_tasks: dict[str, dict]) -> None:
    """持久化 active_tasks 到 ~/.ccc/engine-active-tasks.json。

    修复 stability-audit-2026-07-24 类别①：用 _atomic_write_json 替代
    直接 write_text（崩溃可截断）+ flock 跨进程串行化。
    """
    try:
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
        _atomic_write_json(
            ACTIVE_TASKS_FILE,
            json.dumps(serializable, ensure_ascii=False, indent=2, default=str),
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
        # 修复 stability-audit-2026-07-24 类别①：损坏 JSON 时备份原文件再返回 {}
        # 避免下一轮 save 覆盖证据（之前会直接丢失）
        if isinstance(exc, json.JSONDecodeError):
            try:
                ACTIVE_TASKS_BAK_FILE.write_text(
                    ACTIVE_TASKS_FILE.read_text(encoding="utf-8"),
                    encoding="utf-8",
                )
                _engine_log(
                    f"[persist] 损坏 JSON 已备份到 {ACTIVE_TASKS_BAK_FILE}"
                )
            except OSError as backup_exc:
                _engine_log(f"[persist] 备份失败: {backup_exc}")
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



# ── v0.62.0:Claude --bg 长 session 跟踪 ──────────────────────
# 记录所有 claude --bg / --resume 启动的 background session,提供:
# - register_bg_session:ccc-reviewer-bg.sh(阶段 1)启动时调
# - verify_bg_session:Engine tick 每 30s 调,kill -0 探活
# - list_long_lived_sessions:HUB /api/ops/bg-sessions 调(阶段 3)
# - heartbeat 超时(>1h 无活动)→ 标记 dead 但不杀进程(留给 nudge 路径)

from dataclasses import dataclass, field, asdict as _asdict  # noqa: E402
import time as _time  # noqa: E402


@dataclass
class LongLivedSession:
    """v0.62.0 阶段 2:长 session 跟踪。

    key 形式: "{role}:{task_id}"(role = product / reviewer / etc.)
    """
    task_id: str
    role: str
    session_id: str  # 短 sha(ccc-reviewer-bg.sh 写文件时存)
    pid: int  # wrapper 进程 PID(不是真 claude 进程)
    model: str
    started_at: float = field(default_factory=_time.time)
    last_heartbeat: float = field(default_factory=_time.time)
    # 心跳超时阈值(秒);Engine tick 探活后更新
    # timeout 后标记 dead,Hub 端不再显示(但不杀进程——留给 nudge 续)
    heartbeat_timeout_sec: int = 3600  # 1h

    def is_alive(self) -> bool:
        """Engine tick 调,kill -0 探活 wrapper 进程。"""
        try:
            import os as _os
            _os.kill(self.pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False

    def heartbeat(self) -> None:
        self.last_heartbeat = _time.time()

    def is_idle_timeout(self) -> bool:
        """心跳超 1h 视为 idle 状态,触发 nudge 提示。"""
        return (_time.time() - self.last_heartbeat) > self.heartbeat_timeout_sec

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "role": self.role,
            "session_id": self.session_id,
            "pid": self.pid,
            "model": self.model,
            "started_at": self.started_at,
            "last_heartbeat": self.last_heartbeat,
            "age_sec": int(_time.time() - self.started_at),
            "alive": self.is_alive(),
            "idle_timeout": self.is_idle_timeout(),
        }


_LONG_LIVED_SESSIONS: dict[str, LongLivedSession] = {}


def _bg_session_key(role: str, task_id: str) -> str:
    return f"{role}:{task_id}"


def register_bg_session(
    task_id: str,
    role: str,
    session_id: str,
    pid: int,
    model: str,
) -> LongLivedSession:
    """v0.62.0 阶段 2:注册 claude --bg 长 session。

    ccc-reviewer-bg.sh(阶段 1)启动时调,记入 _LONG_LIVED_SESSIONS。
    同 task_id+role 重复注册会覆盖(session_id 续到 resume 走新 ID)。
    """
    sess = LongLivedSession(
        task_id=task_id, role=role, session_id=session_id,
        pid=pid, model=model,
    )
    _LONG_LIVED_SESSIONS[_bg_session_key(role, task_id)] = sess
    return sess


def unregister_bg_session(role: str, task_id: str) -> None:
    _LONG_LIVED_SESSIONS.pop(_bg_session_key(role, task_id), None)


def verify_bg_session(role: str, task_id: str) -> bool:
    """Engine tick 30s 调一次:kill -0 探活,失败标 dead 但不杀。"""
    sess = _LONG_LIVED_SESSIONS.get(_bg_session_key(role, task_id))
    if sess is None:
        return False
    alive = sess.is_alive()
    if alive:
        sess.heartbeat()
    return alive


def list_long_lived_sessions() -> list[dict]:
    """Hub /api/ops/bg-sessions 调:返所有活着 + idle 状态。"""
    out = []
    now = _time.time()
    for sess in list(_LONG_LIVED_SESSIONS.values()):
        alive = sess.is_alive()
        if alive:
            sess.heartbeat()
        d = sess.to_dict()
        d["age_min"] = int(d.pop("age_sec") / 60)
        out.append(d)
    return out


def nudge_bg_session(role: str, task_id: str, message: str) -> bool:
    """v0.63.0 占位:nudge 通道。当前 v0.62.0 不实现(写文件占位,nudge 不触发)。

    返回 True 表示 nudge 已"调度"(目前只写文件 + 标记);实际注入到
    claude session 由 v0.63.0 通过文件 watch + cat | claude --resume 实现。

    路径:env `CCC_BG_NUDGE_DIR` 可覆盖(测试用),默认 /Users/fan/.ccc/bg-sessions/。
    """
    import os as _os
    sess = _LONG_LIVED_SESSIONS.get(_bg_session_key(role, task_id))
    if sess is None or not sess.is_alive():
        return False
    # v0.62.0:仅写文件标记,nudge 不真触发(等 v0.63.0 注入)
    nudge_dir = Path(_os.environ.get("CCC_BG_NUDGE_DIR", "/Users/fan/.ccc/bg-sessions"))
    nudge_dir.mkdir(parents=True, exist_ok=True)
    nudge_file = nudge_dir / f"{sess.session_id}.nudge"
    nudge_file.write_text(message)
    _engine_log(
        f"[bg-nudge] role={role} task={task_id} session={sess.session_id[:8]} 写入 nudge 占位文件"
    )
    return True
