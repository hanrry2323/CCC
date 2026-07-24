"""engine/process.py — Engine 进程生命周期管理（kill / cleanup / memory）。

fix-planning-2026-07-24 ccc-engine.py 拆分布局：自包含模块，
零 ccc-engine 内部依赖（仅 stdlib + _config + _workspace_registry fallback）。
原 ccc-engine.py:3651-4050 进程管理函数迁移到此处。
"""

from __future__ import annotations

import os
import signal
import subprocess
import time
from pathlib import Path

from _config import get_logger

_log = get_logger("engine.process")


def collect_grandchildren(pid: int, acc: list[int]) -> None:
    """递归收集 pid 的全部子孙进程。"""
    try:
        r = subprocess.run(
            ["pgrep", "-P", str(pid)],
            capture_output=True,
            text=True,
            timeout=3,
        )
        if r.returncode == 0:
            for line in r.stdout.strip().splitlines():
                line = line.strip()
                if not line.isdigit():
                    continue
                child = int(line)
                if child not in acc:
                    acc.append(child)
                    collect_grandchildren(child, acc)
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError, ValueError):
        pass


def kill_process_tree(pid: int) -> bool:
    """发 SIGTERM→等→SIGKILL 递归子进程。返回 True 表示进程最终已死。"""
    children: list[int] = []
    try:
        r = subprocess.run(
            ["pgrep", "-P", str(pid)],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if r.returncode == 0:
            for line in r.stdout.strip().splitlines():
                line = line.strip()
                if line.isdigit():
                    child = int(line)
                    children.append(child)
                    collect_grandchildren(child, children)
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError, ValueError):
        pass

    for child_pid in reversed(children):
        try:
            os.kill(child_pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError, OSError):
            pass
    if children:
        time.sleep(3)
    for child_pid in reversed(children):
        try:
            os.kill(child_pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError, OSError):
            pass

    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return True
    except PermissionError:
        _log.warning("kill tree %d permission denied", pid)
        return False
    except OSError as exc:
        _log.warning("kill tree %d SIGTERM failed: %s", pid, exc)
        return False

    time.sleep(5)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    except (PermissionError, OSError):
        return True

    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        return True
    except OSError as exc:
        _log.warning("kill tree %d SIGKILL failed: %s", pid, exc)
        return False

    time.sleep(1)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    except (PermissionError, OSError):
        return True
    return False


kill_pid = kill_process_tree


def graceful_kill_active_tasks() -> int:
    """遍历 Engine 注册 workspace 的 .ccc/pids/*.pid，对每个 runner PID 调 kill_process_tree。

    修复 stability-audit-2026-07-24 类别③ + diff-review 中风险 #4：
    扫描范围限制到 Engine 注册 workspace（list_engine_paths），
    失败时 fallback 到 CCC_WORKSPACE_ROOTS 或 ~/program。

    Returns: 被尝试 kill 的 PID 数。
    """
    paths: list[Path] = []
    try:
        from _workspace_registry import list_engine_paths

        paths = list_engine_paths()
    except Exception as exc:  # noqa: BLE001
        _log.warning("[shutdown] list_engine_paths 失败，fallback 到 CCC_WORKSPACE_ROOTS: %s", exc)
    if not paths:
        roots_raw = (os.environ.get("CCC_WORKSPACE_ROOTS") or "").strip()
        if roots_raw:
            roots = [Path(p).expanduser() for p in roots_raw.split(",") if p.strip()]
        else:
            roots = [Path.home() / "program"]
        for program_dir in roots:
            if not program_dir.is_dir():
                continue
            for ws in sorted(program_dir.iterdir()):
                paths.append(ws)
    killed = 0
    for ws in sorted(paths):
        pids_dir = ws / ".ccc" / "pids"
        if not pids_dir.is_dir():
            continue
        for pidf in sorted(pids_dir.glob("*.pid")):
            if pidf.name.endswith(".done"):
                continue
            try:
                pid = int(pidf.read_text().strip())
            except (ValueError, OSError):
                continue
            try:
                kill_process_tree(pid)
                killed += 1
            except Exception as exc:  # noqa: BLE001
                _log.warning("[shutdown] kill %s (%s) failed: %s", pid, pidf.name, exc)
    return killed


def get_proc_rss_mb(pid: int) -> float:
    """取进程 RSS（MB），失败返回 0。"""
    try:
        r = subprocess.run(
            ["ps", "-o", "rss=", "-p", str(pid)],
            capture_output=True,
            text=True,
            timeout=3,
        )
        if r.returncode == 0 and r.stdout.strip().isdigit():
            return int(r.stdout.strip()) / 1024.0
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError, ValueError):
        pass
    return 0.0


def cleanup_zombie_pid_refs(ws: Path) -> None:
    """清理 ws/.ccc/pids/ 中进程已死但 .pid 仍存在的文件。"""
    pids_dir = ws / ".ccc" / "pids"
    if not pids_dir.is_dir():
        return
    for pidf in sorted(pids_dir.glob("*.pid")):
        if pidf.name.endswith(".done"):
            continue
        try:
            pid = int(pidf.read_text().strip())
        except (ValueError, OSError):
            continue
        try:
            os.kill(pid, 0)
        except (ProcessLookupError, OSError):
            try:
                pidf.unlink()
                _log.info("[pids] cleanup zombie ref: %s", pidf.name)
            except OSError:
                pass


def cleanup_global_opencode_pids() -> int:
    """跨 workspace 扫描 <ws>/.ccc/pids/opencode-*.pid，清理进程已死的残留。"""
    cleaned = 0
    program_dir = Path.home() / "program"
    if not program_dir.is_dir():
        return 0
    for ws in sorted(program_dir.iterdir()):
        pids_dir = ws / ".ccc" / "pids"
        if not pids_dir.is_dir():
            continue
        for pidf in sorted(pids_dir.glob("opencode-*.pid")):
            try:
                pid = int(pidf.read_text().strip())
            except (ValueError, OSError):
                continue
            try:
                os.kill(pid, 0)
                continue
            except (ProcessLookupError, OSError):
                try:
                    pidf.unlink()
                    cleaned += 1
                except OSError:
                    pass
    return cleaned


def check_process_memory(ws: Path) -> None:
    """若 Engine 进程 RSS > cfg._MEM_KILL_MB（默认 1500MB），SIGKILL 自身。"""
    from _config import Config

    cfg = Config()
    kill_mb = getattr(cfg, "_MEM_KILL_MB", 1500)
    try:
        rss_mb = get_proc_rss_mb(os.getpid())
    except Exception:
        return
    if rss_mb > kill_mb:
        _log.error(
            "[mem-kill] Engine RSS %.0fMB > %dMB, SIGKILL 自身",
            rss_mb,
            kill_mb,
        )
        os.kill(os.getpid(), signal.SIGKILL)
