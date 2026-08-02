"""Mac2017 host CPU/memory time series — parallelism capacity probe.

Writes ``~/.ccc/stats/host-resources.jsonl`` (rotated). Used to decide whether
``MAX_CONCURRENT`` / global OpenCode slots can rise — correlate load & mem with
``active_dev`` / ``opencode_n``.

Sample is cheap (loadavg + vm_stat + process counts); Engine calls every ~60s.
"""

from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STATS_DIR = Path.home() / ".ccc" / "stats"
HOST_RESOURCES_PATH = STATS_DIR / "host-resources.jsonl"

# Throttle for callers that fire every tick
_DEFAULT_INTERVAL_SEC = 60.0
_last_sample_mono: float = 0.0


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def ncpu() -> int:
    try:
        return int(os.cpu_count() or 1)
    except Exception:
        return 1


def _loadavg() -> tuple[float | None, float | None, float | None]:
    try:
        a, b, c = os.getloadavg()
        return float(a), float(b), float(c)
    except OSError:
        return None, None, None


def _memory_snapshot() -> dict[str, Any]:
    """macOS vm_stat → used/total/pct (same shape as _ops_probe.local_resources)."""
    try:
        out = subprocess.check_output(["vm_stat"], text=True, timeout=3)
        page = 4096
        m = re.search(r"page size of (\d+)", out)
        if m:
            page = int(m.group(1))
        free = inactive = wired = active = speculative = compressed = 0
        for line in out.splitlines():
            key = line.split(":")[0].strip()
            digits = re.sub(r"\D", "", line.split(":")[-1]) if ":" in line else ""
            val = int(digits or 0)
            if key == "Pages free":
                free = val
            elif key == "Pages inactive":
                inactive = val
            elif key == "Pages wired down" or key == "Pages wired":
                wired = val
            elif key == "Pages active":
                active = val
            elif key == "Pages speculative":
                speculative = val
            elif "occupied by compressor" in key.lower() or key.startswith(
                "Pages occupied by compressor"
            ):
                compressed = val
        # Prefer sysctl hw.memsize for total when available
        total_bytes = None
        try:
            raw = subprocess.check_output(
                ["sysctl", "-n", "hw.memsize"], text=True, timeout=2
            ).strip()
            total_bytes = int(raw)
        except (subprocess.SubprocessError, OSError, ValueError):
            pages = free + inactive + wired + active + speculative
            total_bytes = pages * page if pages else None
        # Pressure proxy: active + wired + compressor (not free+inactive)
        used = (wired + active + compressed) * page
        # Cap used at total
        if total_bytes and used > total_bytes:
            used = total_bytes
        return {
            "used_bytes": used,
            "total_bytes": total_bytes,
            "used_pct": round(100.0 * used / total_bytes, 1) if total_bytes else None,
            "free_pages": free,
            "inactive_pages": inactive,
        }
    except Exception as exc:
        return {"error": str(exc)}


def _count_cmdline(substr: str) -> int:
    try:
        out = subprocess.check_output(
            ["ps", "-axo", "command="], text=True, timeout=5
        )
    except (subprocess.SubprocessError, OSError):
        return 0
    n = 0
    needle = substr.lower()
    for line in out.splitlines():
        if needle in line.lower():
            n += 1
    return n


def collect_sample(
    *,
    active_dev: int | None = None,
    max_concurrent: int | None = None,
    opencode_slots: int | None = None,
) -> dict[str, Any]:
    """One host sample (no I/O)."""
    load1, load5, load15 = _loadavg()
    cpus = ncpu()
    mem = _memory_snapshot()
    load_ratio = (
        round(load1 / cpus, 3) if load1 is not None and cpus > 0 else None
    )
    opencode_n = _count_cmdline("opencode run")
    sample: dict[str, Any] = {
        "t": _now_iso(),
        "host": socket.gethostname(),
        "ncpu": cpus,
        "load": {"1": load1, "5": load5, "15": load15},
        "load_ratio": load_ratio,  # load1 / ncpu — primary CPU pressure
        "memory": mem,
        "opencode_n": opencode_n,
        "claude_n": _count_cmdline("claude"),
        "active_dev": active_dev,
        "max_concurrent": max_concurrent,
        "opencode_slots": opencode_slots,
    }
    return sample


def append_sample(sample: dict[str, Any], path: Path | None = None) -> Path:
    path = path or HOST_RESOURCES_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        from _jsonl_rotate import append_jsonl

        append_jsonl(path, sample)
    except ImportError:
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(sample, ensure_ascii=False) + "\n")
    return path


def sample_and_append(
    *,
    active_dev: int | None = None,
    max_concurrent: int | None = None,
    opencode_slots: int | None = None,
    path: Path | None = None,
    force: bool = False,
    interval_sec: float = _DEFAULT_INTERVAL_SEC,
) -> dict[str, Any] | None:
    """Throttle + write. Returns sample or None if skipped by throttle."""
    global _last_sample_mono
    now = time.monotonic()
    if not force and (now - _last_sample_mono) < interval_sec:
        return None
    _last_sample_mono = now
    sample = collect_sample(
        active_dev=active_dev,
        max_concurrent=max_concurrent,
        opencode_slots=opencode_slots,
    )
    append_sample(sample, path=path)
    return sample


def read_recent(n: int = 120, path: Path | None = None) -> list[dict[str, Any]]:
    path = path or HOST_RESOURCES_PATH
    if not path.is_file():
        return []
    try:
        from _jsonl_rotate import tail_read_jsonl

        rows = tail_read_jsonl(path, last=n)
        return [r for r in rows if isinstance(r, dict)]
    except Exception:
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            out: list[dict[str, Any]] = []
            for line in lines[-n:]:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
            return out
        except OSError:
            return []


def _percentile(vals: list[float], p: float) -> float | None:
    if not vals:
        return None
    s = sorted(vals)
    if len(s) == 1:
        return s[0]
    k = (len(s) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(s) - 1)
    if f == c:
        return s[f]
    return s[f] + (s[c] - s[f]) * (k - f)


def summarize(
    rows: list[dict[str, Any]] | None = None,
    *,
    n: int = 180,
    path: Path | None = None,
) -> dict[str, Any]:
    """Aggregate curve → headroom hint for raising parallelism."""
    rows = rows if rows is not None else read_recent(n, path=path)
    load_ratios: list[float] = []
    mem_pcts: list[float] = []
    active_devs: list[float] = []
    opencodes: list[float] = []
    for r in rows:
        lr = r.get("load_ratio")
        if lr is None:
            load = (r.get("load") or {}).get("1")
            cpus = r.get("ncpu") or 1
            if load is not None and cpus:
                lr = float(load) / float(cpus)
        if lr is not None:
            load_ratios.append(float(lr))
        mem = r.get("memory") or {}
        if mem.get("used_pct") is not None:
            mem_pcts.append(float(mem["used_pct"]))
        if r.get("active_dev") is not None:
            active_devs.append(float(r["active_dev"]))
        if r.get("opencode_n") is not None:
            opencodes.append(float(r["opencode_n"]))

    load_p50 = _percentile(load_ratios, 50)
    load_p95 = _percentile(load_ratios, 95)
    mem_p50 = _percentile(mem_pcts, 50)
    mem_p95 = _percentile(mem_pcts, 95)
    max_c = None
    for r in reversed(rows):
        if r.get("max_concurrent") is not None:
            max_c = int(r["max_concurrent"])
            break

    # Heuristic (documented): raise only when both CPU & mem have headroom
    # P5: 忙时样本不足 30 点不建议加并行（idle 曲线不够）
    verdict = "insufficient_data"
    reason = "need ≥30 busy-hour samples before raising MAX_CONCURRENT"
    if len(load_ratios) >= 12 and len(mem_pcts) >= 12:
        assert load_p95 is not None and mem_p95 is not None
        if len(load_ratios) < 30:
            verdict = "collecting"
            reason = (
                f"samples={len(load_ratios)}<30 — hold MAX_CONCURRENT; "
                f"load_p95={load_p95:.2f} mem_p95={mem_p95:.0f}% (preliminary)"
            )
        elif load_p95 < 0.55 and mem_p95 < 70:
            verdict = "headroom"
            reason = (
                f"load_ratio_p95={load_p95:.2f}<0.55 and mem_p95={mem_p95:.0f}%<70% "
                f"— try MAX_CONCURRENT+1 (watch same-ws mutex; default stay 4)"
            )
        elif load_p95 > 0.85 or mem_p95 > 85:
            verdict = "saturated"
            reason = (
                f"load_ratio_p95={load_p95:.2f} or mem_p95={mem_p95:.0f}% "
                f"— do not raise parallel; fix hangs first"
            )
        else:
            verdict = "borderline"
            reason = (
                f"load_ratio_p95={load_p95:.2f} mem_p95={mem_p95:.0f}% "
                f"— hold current max; recheck after busy hour"
            )

    return {
        "samples": len(rows),
        "ncpu": rows[-1].get("ncpu") if rows else ncpu(),
        "max_concurrent": max_c,
        "load_ratio": {"p50": load_p50, "p95": load_p95},
        "mem_used_pct": {"p50": mem_p50, "p95": mem_p95},
        "active_dev": {
            "avg": round(sum(active_devs) / len(active_devs), 2) if active_devs else None,
            "max": max(active_devs) if active_devs else None,
        },
        "opencode_n": {
            "avg": round(sum(opencodes) / len(opencodes), 2) if opencodes else None,
            "max": max(opencodes) if opencodes else None,
        },
        "verdict": verdict,
        "reason": reason,
        "path": str(path or HOST_RESOURCES_PATH),
        "generated_at": _now_iso(),
    }


def sparkline(values: list[float | None], width: int = 40) -> str:
    """Unicode sparkline for CLI/ops text."""
    blocks = "▁▂▃▄▅▆▇█"
    clean = [v for v in values if v is not None]
    if not clean:
        return "—"
    lo, hi = min(clean), max(clean)
    span = (hi - lo) or 1.0
    chars: list[str] = []
    step = max(1, len(values) // width) if len(values) > width else 1
    sliced = values[::step][:width]
    for v in sliced:
        if v is None:
            chars.append("·")
            continue
        idx = int((float(v) - lo) / span * (len(blocks) - 1))
        chars.append(blocks[max(0, min(len(blocks) - 1, idx))])
    return "".join(chars)
