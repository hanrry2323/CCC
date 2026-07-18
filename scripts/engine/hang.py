"""engine.hang — hung phase 检测与自动重启。"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import traceback as _traceback
from datetime import timezone
from pathlib import Path

from _config import Config, get_logger
from _executor import _sanitized_env
from _utils import now_iso
from board.phase import _current_running_phase
from board.roles.dev import dev_role_relaunch
from engine.workspace import (
    _activate_workspace,
    _find_task_column,
    _get_store,
    _ws_label,
)

_log = get_logger("engine")
cfg = Config()

_MAX_HANG_RETRY = 2
_hang_retry_counter: dict[str, int] = {}
_HANG_COUNTER_FILE = Path.home() / ".ccc" / "engine-hang-retries.json"
_HANG_CHECK_INTERVAL_SEC = 300
_HANG_BUSY_MAX_SEC = 3600
_MEM_KILL_MB = 1500


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


def _load_hang_retry_counter() -> None:
    """F-ARCH-01: 从磁盘恢复 hang 重试计数。"""
    global _hang_retry_counter
    try:
        if _HANG_COUNTER_FILE.is_file():
            data = json.loads(_HANG_COUNTER_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                _hang_retry_counter = {str(k): int(v) for k, v in data.items()}
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        _hang_retry_counter = {}


def _save_hang_retry_counter() -> None:
    """F-ARCH-01: 持久化 hang 重试计数。"""
    try:
        _HANG_COUNTER_FILE.parent.mkdir(parents=True, exist_ok=True)
        _HANG_COUNTER_FILE.write_text(
            json.dumps(_hang_retry_counter, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError:
        pass


def _check_and_mark_hung(ws: Path, active_tasks: dict[str, dict]) -> None:
    """扫描 active_tasks 中的 running phase，检测 hung 条件并写 .hung marker。"""
    from datetime import datetime as _dt

    eng = _eng()
    _activate_workspace(ws)
    label = _ws_label(ws)
    pids_dir = ws / ".ccc" / "pids"
    now = _dt.now(timezone.utc)

    store = _get_store(ws)
    for _key, info in list(active_tasks.items()):
        if info.get("workspace") != ws:
            continue
        tid = info["task_id"]
        if _find_task_column(store, tid) == "abnormal":
            continue
        try:
            cur_phase = _current_running_phase(tid)
        except Exception as exc:
            _engine_log(f"[{label}] hang-detect: 读 {tid} current phase 失败: {exc}")
            continue
        if cur_phase is None or cur_phase <= 0:
            continue

        phase_market_subid = getattr(eng, "_phase_market_subid", None) if eng else None
        if phase_market_subid is None:
            subid = f"{tid}__p{cur_phase}"
        else:
            subid = phase_market_subid(tid, cur_phase)
        hung_path = pids_dir / f"{subid}.hung"
        done_path = pids_dir / f"{subid}.done"
        pid_path = pids_dir / f"{subid}.pid"

        if hung_path.is_file():
            continue
        if done_path.is_file():
            continue

        if not pid_path.is_file():
            continue
        try:
            pid = int(pid_path.read_text().strip())
        except (ValueError, OSError) as exc:
            _engine_log(f"[{label}] hang-detect: {tid} 读 PID 失败: {exc}")
            continue
        if pid <= 0:
            continue

        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            continue
        except PermissionError:
            pass
        except OSError as exc:
            _engine_log(f"[{label}] hang-detect: {tid} PID={pid} 检查异常: {exc}")
            continue

        started_str = info.get("started_at", "")
        if not started_str:
            continue
        try:
            started = _dt.fromisoformat(str(started_str).replace("Z", "+00:00"))
            elapsed = (now - started).total_seconds()
        except (ValueError, TypeError) as exc:
            _engine_log(f"[{label}] hang-detect: {tid} started_at 解析失败: {exc}")
            continue
        if elapsed < _HANG_CHECK_INTERVAL_SEC:
            continue

        try:
            result = subprocess.run(
                ["ps", "-p", str(pid), "-o", "%cpu="],
                capture_output=True,
                text=True,
                timeout=5,
                env=_sanitized_env(),
            )
        except subprocess.TimeoutExpired:
            _engine_log(f"[{label}] hang-detect: {tid} ps 超时，跳过本次")
            continue
        except OSError as exc:
            _engine_log(f"[{label}] hang-detect: {tid} ps 异常: {exc}")
            continue
        if result.returncode != 0:
            continue
        try:
            cpu = float(result.stdout.strip())
        except ValueError:
            _engine_log(
                f"[{label}] hang-detect: {tid} ps 输出无法解析: {result.stdout!r}"
            )
            continue

        get_proc_rss_mb = getattr(eng, "_get_proc_rss_mb", None) if eng else None
        rss_mb = get_proc_rss_mb(pid) if get_proc_rss_mb else 0.0
        mem_kill = getattr(cfg, "mem_kill_mb", _MEM_KILL_MB)
        if rss_mb > mem_kill:
            _engine_log(
                f"[{label}] hang-detect: {tid} RSS={rss_mb:.0f}MB > {mem_kill}MB，标记 hung"
            )
            marker = {
                "task_id": tid,
                "phase": cur_phase,
                "pid": pid,
                "cpu": cpu,
                "rss_mb": round(rss_mb, 1),
                "elapsed_sec": int(elapsed),
                "detected_at": now_iso(),
                "reason": "rss_over_limit",
            }
            try:
                hung_path.write_text(json.dumps(marker, ensure_ascii=False) + "\n")
            except OSError as exc:
                _engine_log(f"[{label}] hang-detect: {tid} 写 .hung 失败: {exc}")
            continue

        if cpu > 0.0 and elapsed < _HANG_BUSY_MAX_SEC:
            continue

        _latest = 0.0
        try:
            for _pf in sorted(
                pids_dir.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True
            ):
                if _pf.name.startswith(f"{subid}.") and _pf.name != hung_path.name:
                    _latest = _pf.stat().st_mtime
                    break
        except OSError:
            pass
        if _latest and (now.timestamp() - _latest) < 120 and cpu <= 0.0:
            continue

        marker = {
            "task_id": tid,
            "phase": cur_phase,
            "pid": pid,
            "cpu": cpu,
            "rss_mb": round(rss_mb, 1),
            "elapsed_sec": int(elapsed),
            "detected_at": now_iso(),
        }
        try:
            hung_path.write_text(json.dumps(marker, ensure_ascii=False) + "\n")
        except OSError as exc:
            _engine_log(f"[{label}] hang-detect: {tid} 写 .hung 失败: {exc}")
            continue

        if eng:
            eng._log_stats(
                ws,
                "hang_detected",
                tid,
                phase=cur_phase,
                pid=pid,
                cpu=cpu,
                elapsed_sec=int(elapsed),
            )
        try:
            from _failure_ledger import record_failure

            record_failure(
                ws,
                task_id=tid,
                role="engine",
                reason=f"hang_detected pid={pid} cpu={cpu:.1f}% elapsed={int(elapsed)}s",
                phase=cur_phase,
                from_col="in_progress",
                to_col=None,
                exit_code=None,
                related_stats_event="hang_detected",
            )
        except Exception:
            _engine_log(
                f"[failures] hang_detected ledger: {_traceback.format_exc()[:300]}"
            )
        _engine_log(
            f"[{label}] hang-detect: {tid} phase {cur_phase} PID={pid} "
            f"CPU={cpu:.1f}% 运行时长={int(elapsed)}s → 标记 .hung"
        )


def _run_hang_auto_restart(ws: Path, active_tasks: dict[str, dict]) -> None:
    """扫描 active_tasks 中的 hung phase 并自动重启（v0.31+）。"""
    global _hang_retry_counter

    eng = _eng()
    _activate_workspace(ws)
    label = _ws_label(ws)
    pids_dir = ws / ".ccc" / "pids"

    store = _get_store(ws)
    for key, info in list(active_tasks.items()):
        if info.get("workspace") != ws:
            continue
        tid = info["task_id"]
        if _find_task_column(store, tid) == "abnormal":
            active_tasks.pop(key, None)
            _hang_retry_counter.pop(key, None)
            continue
        try:
            cur_phase = _current_running_phase(tid)
        except Exception as exc:
            _engine_log(f"[{label}] hang-auto: 读 {tid} current phase 失败: {exc}")
            continue
        if cur_phase is None or cur_phase <= 0:
            continue

        phase_market_subid = getattr(eng, "_phase_market_subid", None) if eng else None
        if phase_market_subid is None:
            subid = f"{tid}__p{cur_phase}"
        else:
            subid = phase_market_subid(tid, cur_phase)
        hung_path = pids_dir / f"{subid}.hung"
        if not hung_path.is_file():
            continue

        retries = _hang_retry_counter.get(key, 0)
        _engine_log(
            f"[{label}] hang-auto: {tid} phase {cur_phase} 标记 hung "
            f"(auto-retry {retries + 1}/{_MAX_HANG_RETRY})"
        )

        pid_path = pids_dir / f"{subid}.pid"
        pid: int | None = None
        if pid_path.is_file():
            try:
                pid = int(pid_path.read_text().strip())
            except (ValueError, OSError):
                pid = None
        else:
            _engine_log(
                f"[{label}] hang-auto: {tid} 缺 {pid_path.name}（可能已退出），跳过 kill"
            )

        kill_process_tree = getattr(eng, "_kill_process_tree", None) if eng else None
        if pid is not None and pid > 0 and kill_process_tree:
            if kill_process_tree(pid):
                _engine_log(f"[{label}] hang-auto: {tid} PID={pid} 进程树已 kill")
            else:
                _engine_log(f"[{label}] hang-auto: {tid} PID={pid} kill 失败，继续")

        git_stash_ws = getattr(eng, "_git_stash_ws", None) if eng else None
        if git_stash_ws is None:
            _engine_log(f"[{label}] hang-auto: {tid} git stash helper 不可用，跳过 restart")
            try:
                hung_path.unlink()
            except OSError:
                pass
            continue
        if not git_stash_ws(ws, tid, cur_phase):
            _engine_log(f"[{label}] hang-auto: {tid} git stash 失败，跳过 restart")
            try:
                hung_path.unlink()
            except OSError:
                pass
            continue

        try:
            hung_path.unlink()
        except OSError as exc:
            _engine_log(f"[{label}] hang-auto: 清理 {hung_path.name} 失败: {exc}")

        if retries >= _MAX_HANG_RETRY:
            reason = f"hang auto-restart 耗尽（{_MAX_HANG_RETRY} 次）— {tid} phase {cur_phase}"
            _engine_log(f"[{label}] hang-auto: {tid} 超限 → abnormal")
            if eng:
                eng._quarantine_with_notify(
                    ws,
                    tid,
                    reason,
                    phase=cur_phase,
                    active_tasks=active_tasks,
                    role="engine",
                    from_col="in_progress",
                )
            _hang_retry_counter.pop(key, None)
            _save_hang_retry_counter()
            active_tasks.pop(key, None)
            continue

        try:
            _activate_workspace(ws)
            result = dev_role_relaunch(tid)
        except Exception as exc:
            _engine_log(f"[{label}] hang-auto: {tid} relaunch 异常: {exc}")
            result = {"ok": False}

        _hang_retry_counter[key] = retries + 1
        _save_hang_retry_counter()
        if result.get("ok"):
            _engine_log(
                f"[{label}] hang-auto: {tid} phase {cur_phase} 已重启 "
                f"(retry {retries + 1}/{_MAX_HANG_RETRY})"
            )
        else:
            _engine_log(f"[{label}] hang-auto: {tid} relaunch 返回非 ok: {result}")
