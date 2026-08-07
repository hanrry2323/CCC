"""Engine 并发/进程埋点测试（engine-metrics.jsonl / worker-events.jsonl / 采样器）。"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

from server.engine import metrics


def test_slot_snapshot_writes_jsonl(tmp_path: Path) -> None:
    metrics.record_slot_snapshot(
        tmp_path,
        exec_used=1,
        exec_max=3,
        audit_used=0,
        audit_max=2,
        pending_exec=2,
        audit_pending=1,
    )
    lines = (tmp_path / "engine-metrics.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["kind"] == "slots"
    assert rec["exec_max"] == 3
    assert rec["audit_max"] == 2
    assert rec["audit_pending"] == 1
    assert rec["ts"]


def test_worker_event_writes_jsonl(tmp_path: Path) -> None:
    metrics.record_worker_event(
        tmp_path,
        work_id="w1",
        phase="run",
        ok=True,
        returncode=0,
        duration_s=1.234,
        exit_kind="ok",
        peak_rss_mb=12.5,
        peak_cpu_pct=3.2,
    )
    rec = json.loads(
        (tmp_path / "worker-events.jsonl").read_text(encoding="utf-8").splitlines()[0]
    )
    assert rec["work_id"] == "w1"
    assert rec["phase"] == "run"
    assert rec["ok"] is True
    assert rec["returncode"] == 0
    assert rec["exit_kind"] == "ok"
    assert rec["peak_rss_mb"] == 12.5
    assert rec["peak_cpu_pct"] == 3.2
    assert rec["duration_s"] == 1.234


def test_ps_stats_dead_pid_returns_none() -> None:
    assert metrics._ps_stats(999_999_999) is None


def test_process_sampler_records_peak(tmp_path: Path) -> None:
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(2)"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    sampler = metrics.ProcessSampler(proc, interval=0.2)
    sampler.start()
    try:
        time.sleep(0.7)
    finally:
        sampler.stop()
        proc.terminate()
        proc.wait(timeout=5)
    assert sampler.peak_rss_mb is not None and sampler.peak_rss_mb > 0
