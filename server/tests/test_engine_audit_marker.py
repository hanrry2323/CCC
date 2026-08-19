"""引擎机审在途判定（audit running marker）回归测试。

2026-08-20 事故回归：机审子进程失败后 `{id}-audit.running` 标记残留且只含
engine_pid，判定逻辑把常驻 engine 当「机审在途」→ 失败卡 2h 不重审（mx055 卡死）。

修复语义：
- engine 自身 PID（engine_pid= 行 / 等于当前 engine 的 pid= 行）不作为在途依据；
- 存在存活子进程 → 在途（防双审）；
- 无存活子进程 → 仅刚写入（宽限期 900s 内）算在途；超期 = 残留死标记，可重审。
"""

from __future__ import annotations

import os
import time
from pathlib import Path

from server.engine.main import _audit_marker_alive

DEAD_PID = 99999999
FAKE_LIVE_PID = 12345


def _write_marker(
    log_dir: Path,
    work_id: str,
    content: str,
    *,
    age_seconds: float = 0,
) -> Path:
    marker = log_dir / f"{work_id}-audit.running"
    marker.write_text(content, encoding="utf-8")
    if age_seconds > 0:
        old = time.time() - age_seconds
        os.utime(marker, (old, old))
    return marker


def test_no_marker_not_inflight(tmp_path: Path) -> None:
    assert _audit_marker_alive(tmp_path, "mx099") is False


def test_live_child_pid_inflight(tmp_path: Path, monkeypatch) -> None:
    """子进程真存活 → 在途（无论 engine_pid 死活）。"""
    monkeypatch.setattr("server.engine.main._pid_alive", lambda pid: pid != DEAD_PID)
    _write_marker(
        tmp_path,
        "mx099",
        f"engine_pid={DEAD_PID}\npid={DEAD_PID}\nchild_pid={FAKE_LIVE_PID}\n",
    )
    assert _audit_marker_alive(tmp_path, "mx099") is True


def test_fresh_marker_engine_pid_only_inflight(tmp_path: Path) -> None:
    """刚写入（子进程未拉起）仍需防双审 → 在途。"""
    _write_marker(tmp_path, "mx099", f"engine_pid={os.getpid()}\npid={os.getpid()}\n")
    assert _audit_marker_alive(tmp_path, "mx099") is True


def test_fresh_marker_dead_child_inflight(tmp_path: Path) -> None:
    """子进程已死但标记刚写 → 宽限期内在途（防拉起重叠）。"""
    _write_marker(
        tmp_path,
        "mx099",
        f"engine_pid={os.getpid()}\npid={DEAD_PID}\nchild_pid={DEAD_PID}\n",
    )
    assert _audit_marker_alive(tmp_path, "mx099") is True


def test_stale_marker_engine_pid_only_not_inflight(tmp_path: Path) -> None:
    """复现 bug：残留标记仅含 engine_pid 且超宽限期 → 必须可重审（修复前判在途）。"""
    _write_marker(
        tmp_path,
        "mx099",
        f"engine_pid={os.getpid()}\npid={os.getpid()}\n",
        age_seconds=3600,
    )
    assert _audit_marker_alive(tmp_path, "mx099") is False


def test_stale_marker_dead_child_not_inflight(tmp_path: Path) -> None:
    """子进程死 + 标记超期 → 残留死标记，可重审。"""
    _write_marker(
        tmp_path,
        "mx099",
        f"engine_pid={os.getpid()}\npid={DEAD_PID}\nchild_pid={DEAD_PID}\n",
        age_seconds=3600,
    )
    assert _audit_marker_alive(tmp_path, "mx099") is False


def test_stale_marker_live_child_inflight(tmp_path: Path, monkeypatch) -> None:
    """子进程真活着 → 无论标记多旧都在途（重审中的卡不被误回收）。"""
    monkeypatch.setattr("server.engine.main._pid_alive", lambda pid: pid != DEAD_PID)
    _write_marker(
        tmp_path,
        "mx099",
        f"engine_pid={DEAD_PID}\npid={DEAD_PID}\nchild_pid={FAKE_LIVE_PID}\n",
        age_seconds=7200,
    )
    assert _audit_marker_alive(tmp_path, "mx099") is True
