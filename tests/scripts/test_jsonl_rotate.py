"""test_jsonl_rotate.py — Phase 4.3: _jsonl_rotate 轮转 + tail 读"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from _jsonl_rotate import append_jsonl, rotate_if_needed, tail_read_jsonl


def _rec(i: int) -> dict:
    return {"i": i, "ts": f"2026-07-19T00:00:{i:02d}Z"}


def test_append_creates_file(tmp_path):
    p = tmp_path / "events.jsonl"
    append_jsonl(p, _rec(1))
    assert p.is_file()
    lines = p.read_text().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["i"] == 1


def test_rotate_triggers_at_max_bytes(tmp_path):
    p = tmp_path / "events.jsonl"
    # max_bytes 设很小，写几条就触发轮转
    for i in range(50):
        append_jsonl(p, _rec(i), max_bytes=500, backup_count=3)
    assert p.is_file()
    # 应该有 .1 备份
    assert p.with_suffix(".jsonl.1").is_file()
    # 主文件应小于阈值（轮转后从头开始）
    assert p.stat().st_size < 500 or p.with_suffix(".jsonl.1").is_file()


def test_rotate_chain_drops_oldest(tmp_path):
    p = tmp_path / "events.jsonl"
    # 大量写入，触发多级轮转
    for i in range(200):
        append_jsonl(p, _rec(i), max_bytes=200, backup_count=2)
    # backup_count=2 → 只保留 .1 和 .2
    assert p.with_suffix(".jsonl.1").is_file()
    assert p.with_suffix(".jsonl.2").is_file()
    assert not p.with_suffix(".jsonl.3").exists()


def test_tail_read_returns_last_n(tmp_path):
    p = tmp_path / "events.jsonl"
    for i in range(100):
        append_jsonl(p, _rec(i))
    last10 = tail_read_jsonl(p, last=10)
    assert len(last10) == 10
    # 最近的 i=99 在末尾
    assert last10[-1]["i"] == 99
    assert last10[0]["i"] == 90


def test_tail_read_across_rotations(tmp_path):
    p = tmp_path / "events.jsonl"
    # 写满 + 轮转，再写新一批
    for i in range(50):
        append_jsonl(p, _rec(i), max_bytes=1000, backup_count=3)
    # 此时主文件可能有部分，.1 有上一批
    for i in range(50, 60):
        append_jsonl(p, _rec(i), max_bytes=1000, backup_count=3)
    last = tail_read_jsonl(p, last=200)
    # 至少能读到最近 10 条（i=50..59）
    is_50_to_59 = [r for r in last if 50 <= r["i"] <= 59]
    assert len(is_50_to_59) == 10


def test_tail_read_empty_file(tmp_path):
    p = tmp_path / "events.jsonl"
    assert tail_read_jsonl(p, last=10) == []


def test_tail_read_malformed_lines_skipped(tmp_path):
    p = tmp_path / "events.jsonl"
    p.write_text('{"i":1}\nnot json\n{"i":2}\n', encoding="utf-8")
    rows = tail_read_jsonl(p, last=10)
    assert [r["i"] for r in rows] == [1, 2]


def test_tail_read_last_zero_returns_all(tmp_path):
    p = tmp_path / "events.jsonl"
    for i in range(5):
        append_jsonl(p, _rec(i))
    rows = tail_read_jsonl(p, last=0)
    assert len(rows) == 5
