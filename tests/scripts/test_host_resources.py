"""Tests for scripts/_host_resources.py"""
from __future__ import annotations

import json
from pathlib import Path

from _host_resources import (
    summarize,
    sparkline,
    append_sample,
    read_recent,
    _percentile,
)


def test_percentile():
    assert _percentile([1, 2, 3, 4], 50) == 2.5
    assert _percentile([10.0], 95) == 10.0


def test_sparkline_nonempty():
    s = sparkline([0.1, 0.5, 0.9, None, 0.2])
    assert len(s) >= 4
    assert "·" in s


def test_summarize_headroom(tmp_path: Path):
    path = tmp_path / "host-resources.jsonl"
    for i in range(15):
        append_sample(
            {
                "t": f"2026-07-22T10:{i:02d}:00+08:00",
                "ncpu": 8,
                "load": {"1": 1.0, "5": 1.0, "15": 1.0},
                "load_ratio": 0.2,
                "memory": {"used_pct": 40.0, "used_bytes": 1, "total_bytes": 2},
                "opencode_n": 1,
                "active_dev": 2,
                "max_concurrent": 4,
            },
            path=path,
        )
    s = summarize(n=20, path=path)
    assert s["samples"] == 15
    assert s["verdict"] == "headroom"
    assert s["load_ratio"]["p95"] is not None


def test_summarize_saturated(tmp_path: Path):
    path = tmp_path / "host-resources.jsonl"
    for i in range(15):
        append_sample(
            {
                "t": f"t{i}",
                "ncpu": 4,
                "load_ratio": 0.95,
                "memory": {"used_pct": 90.0},
                "opencode_n": 4,
                "active_dev": 4,
                "max_concurrent": 4,
            },
            path=path,
        )
    s = summarize(read_recent(20, path=path))
    assert s["verdict"] == "saturated"


def test_insufficient_data(tmp_path: Path):
    path = tmp_path / "host-resources.jsonl"
    append_sample(
        {"load_ratio": 0.1, "memory": {"used_pct": 30}, "ncpu": 4},
        path=path,
    )
    s = summarize(n=10, path=path)
    assert s["verdict"] == "insufficient_data"
