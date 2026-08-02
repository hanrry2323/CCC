"""Reap leftover ``opencode run --dir <ws>`` processes.

Root cause (stress / medium fanout): opencode's node workers often outlive the
CLI parent. Board ``.ccc/pids/*.pid`` tracks the *runner* bash/python PID, not
the opencode leaf — so a dead runner + live opencode looks "claimed" forever
and blocks same-workspace serialization (1 OpenCode / ws by design).

This module is the shared kill path for runner EXIT, hang sweep, and
check_complete after ``.done``.
"""

from __future__ import annotations

import os
import signal
import subprocess
import time
from pathlib import Path


def pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def etime_to_sec(etime: str) -> int:
    """Parse ``ps -o etime``: ``[[dd-]hh:]mm:ss``."""
    etime = (etime or "").strip()
    days = 0
    if "-" in etime:
        d, etime = etime.split("-", 1)
        days = int(d or 0)
    parts = [int(x) for x in etime.split(":")]
    if len(parts) == 3:
        h, m, s = parts
    elif len(parts) == 2:
        h, m, s = 0, parts[0], parts[1]
    else:
        return days * 86400
    return days * 86400 + h * 3600 + m * 60 + s


def kill_process_group(pid: int, sig: int = signal.SIGTERM) -> bool:
    try:
        os.killpg(pid, sig)
        return True
    except (ProcessLookupError, PermissionError, OSError):
        try:
            os.kill(pid, sig)
            return True
        except (ProcessLookupError, PermissionError, OSError):
            return False


def claimed_alive_pids(ws: Path) -> set[int]:
    """PIDs from ``.ccc/pids/*.pid`` that are still alive (runner / exec)."""
    claimed: set[int] = set()
    pids_dir = Path(ws) / ".ccc" / "pids"
    if not pids_dir.is_dir():
        return claimed
    for pf in pids_dir.glob("*.pid"):
        try:
            pid = int(pf.read_text().strip().split()[0])
        except (ValueError, OSError, IndexError):
            continue
        if pid_alive(pid):
            claimed.add(pid)
    return claimed


def list_opencode_for_workspace(ws: Path) -> list[tuple[int, int]]:
    """Return ``[(pid, age_sec), ...]`` for ``opencode run --dir <ws>``."""
    ws = Path(ws).resolve()
    needle = f"--dir {ws}"
    needle2 = f"--dir {ws}/"
    found: list[tuple[int, int]] = []
    try:
        out = subprocess.check_output(
            ["ps", "-axo", "pid=,etime=,command="],
            text=True,
            timeout=15,
        )
    except (subprocess.SubprocessError, OSError):
        return found
    for line in out.splitlines():
        line = line.strip()
        if "opencode run" not in line or "--dir" not in line:
            continue
        if needle not in line and needle2 not in line and str(ws) not in line:
            continue
        try:
            pid_s, etime, *_rest = line.split(None, 2)
            pid = int(pid_s)
            age = etime_to_sec(etime)
        except (ValueError, IndexError):
            continue
        found.append((pid, age))
    return found


def reap_opencode_workspace(
    ws: Path,
    *,
    max_age_sec: int = 0,
    exclude_pids: set[int] | None = None,
    also_kill_claimed_dead: bool = True,
    grace_sec: float = 1.0,
) -> list[int]:
    """TERM then KILL opencode leaves for ``ws``.

    - ``max_age_sec=0``: reap immediately (use after task ``.done`` / runner exit).
    - Hang sweep typically uses 300–600s so brand-new launches survive.
    - Dead ``.pid`` files do **not** protect orphans (``also_kill_claimed_dead``).
    - Live claimed PIDs (and their process groups) are skipped via ``exclude_pids``
      plus alive board pid files.
    """
    ws = Path(ws).resolve()
    exclude = set(exclude_pids or ())
    if also_kill_claimed_dead:
        exclude |= claimed_alive_pids(ws)
    else:
        # legacy: trust pid file text even if dead (unsafe — prefer default)
        pids_dir = ws / ".ccc" / "pids"
        if pids_dir.is_dir():
            for pf in pids_dir.glob("*.pid"):
                try:
                    exclude.add(int(pf.read_text().strip().split()[0]))
                except (ValueError, OSError, IndexError):
                    continue

    killed: list[int] = []
    for pid, age in list_opencode_for_workspace(ws):
        if pid in exclude:
            continue
        if age < max_age_sec:
            continue
        if kill_process_group(pid, signal.SIGTERM):
            killed.append(pid)
    if killed and grace_sec > 0:
        time.sleep(grace_sec)
    for pid, age in list_opencode_for_workspace(ws):
        if pid in exclude:
            continue
        if age < max_age_sec and pid not in killed:
            continue
        if pid in killed or age >= max_age_sec:
            kill_process_group(pid, signal.SIGKILL)
            if pid not in killed:
                killed.append(pid)
    return killed
