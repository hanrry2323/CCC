"""Engine 并发与执行体进程埋点（JSONL 追加，供运维/看板消费）。

两个文件都写在 ``EXECUTOR_LOG_DIR`` 下，append-only，单行 JSON：
- ``engine-metrics.jsonl``：每轮心跳的槽位快照（并发效率时序）。
- ``worker-events.jsonl``：每个执行体/机审子进程的退出事件（资源占用 + 优雅退出）。

埋点失败只记日志，绝不抛进 Engine 热路径。
"""

from __future__ import annotations

import json
import logging
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("ccc.engine.metrics")

SLOT_METRICS_FILE = "engine-metrics.jsonl"
WORKER_EVENTS_FILE = "worker-events.jsonl"


def _utcnow_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def _append(log_dir: str | Path, filename: str, record: dict) -> None:
    try:
        path = Path(log_dir)
        path.mkdir(parents=True, exist_ok=True)
        with (path / filename).open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        logger.exception("metrics 写入失败（不阻断主流程）: %s/%s", log_dir, filename)


def record_slot_snapshot(log_dir: str | Path, **fields) -> None:
    """每轮心跳一行：槽位使用/上限、队列深度、吞吐。"""
    _append(log_dir, SLOT_METRICS_FILE, {"ts": _utcnow_iso(), "kind": "slots", **fields})


def record_worker_event(
    log_dir: str | Path,
    *,
    work_id: str,
    phase: str,
    ok: bool,
    returncode: int | None,
    duration_s: float | None,
    exit_kind: str,
    peak_rss_mb: float | None = None,
    peak_cpu_pct: float | None = None,
    problems: list[str] | None = None,
) -> None:
    """每个执行体/机审子进程退出一行；exit_kind ∈ ok/nonzero/timeout/signal/launch_error。"""
    record = {
        "ts": _utcnow_iso(),
        "kind": "worker",
        "work_id": work_id,
        "phase": phase,
        "ok": bool(ok),
        "returncode": returncode,
        "duration_s": round(duration_s, 3) if duration_s is not None else None,
        "exit_kind": exit_kind,
        "peak_rss_mb": round(peak_rss_mb, 2) if peak_rss_mb is not None else None,
        "peak_cpu_pct": round(peak_cpu_pct, 2) if peak_cpu_pct is not None else None,
        "problem": problems[0] if problems else None,
    }
    _append(log_dir, WORKER_EVENTS_FILE, record)


def _ps_stats(pid: int) -> tuple[int, float] | None:
    """``ps -o rss=,pcpu=`` 单次采样（macOS/Linux）；失败返回 None（降级）。"""
    try:
        out = subprocess.run(
            ["ps", "-o", "rss=,pcpu=", "-p", str(pid)],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
        if out.returncode != 0:
            return None
        parts = out.stdout.split()
        if len(parts) >= 2:
            return int(float(parts[0])), float(parts[1])
    except Exception:
        return None
    return None


class ProcessSampler(threading.Thread):
    """Popen 子进程资源采样：每 interval 秒采 RSS/CPU 峰值；进程退出或 stop 即止。"""

    def __init__(self, proc, interval: float = 5.0) -> None:
        super().__init__(daemon=True, name="ccc-proc-sampler")
        self._proc = proc
        self._interval = max(0.5, float(interval))
        self._stop = threading.Event()
        self.peak_rss_mb: float | None = None
        self.peak_cpu_pct: float | None = None

    def run(self) -> None:
        while not self._stop.is_set():
            if self._proc.poll() is not None:
                return
            stats = _ps_stats(self._proc.pid)
            if stats is not None:
                rss_mb, cpu = stats[0] / 1024.0, stats[1]
                if self.peak_rss_mb is None or rss_mb > self.peak_rss_mb:
                    self.peak_rss_mb = rss_mb
                if self.peak_cpu_pct is None or cpu > self.peak_cpu_pct:
                    self.peak_cpu_pct = cpu
            self._stop.wait(self._interval)

    def stop(self) -> None:
        self._stop.set()
