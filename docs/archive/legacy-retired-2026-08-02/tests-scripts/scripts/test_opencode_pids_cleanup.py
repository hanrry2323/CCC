"""Global opencode-pids cleanup logic (mirror of engine helper)."""
from __future__ import annotations

import os
from pathlib import Path


def _cleanup_dead_pid_files(pids_dir: Path) -> int:
    cleaned = 0
    for f in sorted(pids_dir.glob("*.pid")):
        try:
            raw = f.read_text(encoding="utf-8", errors="replace").strip()
            pid = int(raw.split()[0]) if raw else 0
        except (ValueError, OSError):
            pid = 0
        alive = False
        if pid > 0:
            try:
                os.kill(pid, 0)
                alive = True
            except OSError:
                alive = False
        if alive:
            continue
        f.unlink()
        cleaned += 1
    return cleaned


def test_cleanup_removes_dead_pid_files(tmp_path):
    pids = tmp_path / "opencode-pids"
    pids.mkdir()
    dead = pids / "dead.pid"
    dead.write_text("999999991\n", encoding="utf-8")
    cleaned = _cleanup_dead_pid_files(pids)
    assert cleaned == 1
    assert not dead.exists()
