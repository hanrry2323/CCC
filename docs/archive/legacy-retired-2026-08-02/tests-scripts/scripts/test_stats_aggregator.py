"""test_stats_aggregator.py — _stats_aggregator 模块单元测试 (v0.51.0 P1-10)

覆盖:
  - aggregate_stats: events.jsonl 不存在 → 空 summary；正常多事件聚合；
    损坏 JSON 行跳过；按 task 失败率计算；product_fail spike >3 触发 warning；
    quarantine spike >5 触发 enable_fallback_chain 建议；
    move >10 且 0 failures 触发 system_healthy
  - load_summary: 文件不存在返回 {}；JSON 损坏返回 {}；正常返回 dict
  - _write_summary: 原子写（tmp + rename）

业务关键性：Engine 决策 + Executor fallback 都依赖 summary.json，错误聚合会导致 fallback 误判。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from _stats_aggregator import (  # noqa: E402
    _events_file,
    _summary_file,
    aggregate_stats,
    load_summary,
)


def _write_events(ws: Path, events: list[dict]) -> None:
    """写入 events.jsonl（每行一个 JSON 对象）。"""
    ev = _events_file(ws)
    ev.parent.mkdir(parents=True, exist_ok=True)
    with ev.open("w", encoding="utf-8") as f:
        for e in events:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")


# ──────────────────────────────────────────────────────────────────
# aggregate_stats — 空 / 不存在
# ──────────────────────────────────────────────────────────────────


def test_aggregate_stats_no_events_file_writes_empty_summary(tmp_path: Path):
    """events.jsonl 不存在时应写空 summary.json。"""
    summary = aggregate_stats(tmp_path)
    assert summary["total_events"] == 0
    assert summary["events_by_type"] == {}
    assert summary["task_stats"] == {}
    assert summary["perf_insights"] == []
    assert summary["recommendations"] == []
    assert summary["workspace"] == tmp_path.name
    # summary.json 落盘
    assert _summary_file(tmp_path).exists()
    loaded = json.loads(_summary_file(tmp_path).read_text(encoding="utf-8"))
    assert loaded["total_events"] == 0


def test_aggregate_stats_normal_events(tmp_path: Path):
    """正常多事件聚合：按 event 类型计数 + 按 task 聚合。"""
    _write_events(
        tmp_path,
        [
            {"event": "move", "task": "t1", "t": "2026-01-01T00:00:00Z"},
            {"event": "move", "task": "t2", "t": "2026-01-01T00:01:00Z"},
            {"event": "product_done", "task": "t1", "t": "2026-01-01T00:02:00Z"},
            {
                "event": "pytest",
                "task": "t1",
                "t": "2026-01-01T00:03:00Z",
                "exit_code": 0,
                "duration_s": 1.5,
            },
        ],
    )

    summary = aggregate_stats(tmp_path)
    assert summary["total_events"] == 4
    assert summary["events_by_type"]["move"] == 2
    assert summary["events_by_type"]["product_done"] == 1
    assert summary["events_by_type"]["pytest"] == 1
    assert summary["latest_event_ts"] == "2026-01-01T00:03:00Z"

    # task_stats
    assert summary["task_stats"]["total"] == 2
    assert summary["task_stats"]["success"] == 1  # t1 has pytest exit_code=0
    assert summary["task_stats"]["failed"] == 0

    # task_stats.details: t1 有 latency_samples
    t1_detail = summary["task_stats"]["details"]["t1"]
    assert t1_detail["has_success"] is True
    assert t1_detail["latency_samples"] == 1
    assert t1_detail["avg_latency_s"] == 1.5


def test_aggregate_stats_corrupted_lines_skipped(tmp_path: Path):
    """损坏的 JSON 行不阻塞聚合（行被计入 total 但不进 events_by_type）。"""
    ev = _events_file(tmp_path)
    ev.parent.mkdir(parents=True, exist_ok=True)
    ev.write_text(
        json.dumps({"event": "move", "task": "t1", "t": "2026-01-01T00:00:00Z"})
        + "\n"
        "this is not json\n"
        + json.dumps({"event": "move", "task": "t2", "t": "2026-01-01T00:01:00Z"})
        + "\n",
        encoding="utf-8",
    )

    summary = aggregate_stats(tmp_path)
    # total_events 计所有非空行（包括损坏行）；events_by_type 只统计合法 JSON
    assert summary["total_events"] == 3
    assert summary["events_by_type"]["move"] == 2
    # 损坏行不应造成 task_stats 异常
    assert summary["task_stats"]["total"] == 2  # 只有 t1 / t2


def test_aggregate_stats_blank_lines_skipped(tmp_path: Path):
    """空行应被跳过。"""
    ev = _events_file(tmp_path)
    ev.parent.mkdir(parents=True, exist_ok=True)
    ev.write_text(
        "\n"
        + json.dumps({"event": "move", "t": "2026-01-01T00:00:00Z"})
        + "\n\n",
        encoding="utf-8",
    )
    summary = aggregate_stats(tmp_path)
    assert summary["total_events"] == 1


def test_aggregate_stats_task_failure_rate(tmp_path: Path):
    """有 fail/quarantine 事件的 task 应被统计为 has_failure。"""
    _write_events(
        tmp_path,
        [
            {"event": "move", "task": "t1", "t": "2026-01-01T00:00:00Z"},
            {"event": "quarantine", "task": "t2", "t": "2026-01-01T00:01:00Z"},
            {"event": "pytest_fail", "task": "t2", "t": "2026-01-01T00:02:00Z"},
        ],
    )
    summary = aggregate_stats(tmp_path)
    assert summary["task_stats"]["total"] == 2
    assert summary["task_stats"]["failed"] == 1  # t2 has fail/quarantine events

    # perf_insights 应包含 failure rate
    failure_metric = next(
        (p for p in summary["perf_insights"] if p["metric"] == "task_failure_rate"),
        None,
    )
    assert failure_metric is not None
    assert failure_metric["value"] == 50.0  # 1/2


def test_aggregate_stats_product_fail_spike_triggers_warning(tmp_path: Path):
    """product_fail 次数 > 3 应触发 spike warning。"""
    _write_events(
        tmp_path,
        [
            {"event": "product_fail", "task": f"t{i}", "t": "2026-01-01T00:00:00Z"}
            for i in range(4)
        ],
    )
    summary = aggregate_stats(tmp_path)
    spike = next(
        (p for p in summary["perf_insights"] if p["metric"] == "product_fail_spike"),
        None,
    )
    assert spike is not None
    assert spike["value"] == 4
    assert spike["severity"] == "warning"


def test_aggregate_stats_quarantine_spike_triggers_recommendation(tmp_path: Path):
    """quarantine 次数 > 5 应触发 enable_fallback_chain 建议。"""
    _write_events(
        tmp_path,
        [
            {"event": "quarantine", "task": f"t{i}", "t": "2026-01-01T00:00:00Z"}
            for i in range(6)
        ],
    )
    summary = aggregate_stats(tmp_path)
    rec = next(
        (
            r
            for r in summary["recommendations"]
            if r["action"] == "enable_fallback_chain"
        ),
        None,
    )
    assert rec is not None
    assert "6" in rec["reason"]


def test_aggregate_stats_product_fail_triggers_check_product_role(tmp_path: Path):
    """product_fail > 3 应触发 check_product_role 建议。"""
    _write_events(
        tmp_path,
        [
            {"event": "product_fail", "task": f"t{i}", "t": "2026-01-01T00:00:00Z"}
            for i in range(4)
        ],
    )
    summary = aggregate_stats(tmp_path)
    rec = next(
        (
            r
            for r in summary["recommendations"]
            if r["action"] == "check_product_role"
        ),
        None,
    )
    assert rec is not None


def test_aggregate_stats_system_healthy_recommendation(tmp_path: Path):
    """move > 10 且 0 failures 触发 system_healthy 建议。"""
    _write_events(
        tmp_path,
        [
            {"event": "move", "task": f"t{i}", "t": "2026-01-01T00:00:00Z"}
            for i in range(11)
        ],
    )
    summary = aggregate_stats(tmp_path)
    rec = next(
        (
            r
            for r in summary["recommendations"]
            if r["action"] == "system_healthy"
        ),
        None,
    )
    assert rec is not None


def test_aggregate_stats_idempotent(tmp_path: Path):
    """多次运行结果应一致（不修改 events.jsonl）。"""
    _write_events(
        tmp_path,
        [{"event": "move", "task": "t1", "t": "2026-01-01T00:00:00Z"}] * 5,
    )
    ev_before = _events_file(tmp_path).read_text(encoding="utf-8")

    s1 = aggregate_stats(tmp_path)
    s2 = aggregate_stats(tmp_path)
    ev_after = _events_file(tmp_path).read_text(encoding="utf-8")

    assert ev_before == ev_after  # events.jsonl 未被修改
    assert s1["total_events"] == s2["total_events"]
    assert s1["events_by_type"] == s2["events_by_type"]


# ──────────────────────────────────────────────────────────────────
# load_summary
# ──────────────────────────────────────────────────────────────────


def test_load_summary_missing_returns_empty(tmp_path: Path):
    assert load_summary(tmp_path) == {}


def test_load_summary_corrupted_returns_empty(tmp_path: Path):
    sf = _summary_file(tmp_path)
    sf.parent.mkdir(parents=True, exist_ok=True)
    sf.write_text("not json {{{", encoding="utf-8")
    assert load_summary(tmp_path) == {}


def test_load_summary_normal(tmp_path: Path):
    sf = _summary_file(tmp_path)
    sf.parent.mkdir(parents=True, exist_ok=True)
    sf.write_text(
        json.dumps({"total_events": 42, "workspace": "demo"}) + "\n",
        encoding="utf-8",
    )
    out = load_summary(tmp_path)
    assert out["total_events"] == 42
    assert out["workspace"] == "demo"


def test_aggregate_then_load_roundtrip(tmp_path: Path):
    """aggregate_stats 写完后 load_summary 应能读到相同数据。"""
    _write_events(
        tmp_path,
        [
            {"event": "move", "task": "t1", "t": "2026-01-01T00:00:00Z"},
            {"event": "quarantine", "task": "t2", "t": "2026-01-01T00:01:00Z"},
        ],
    )
    written = aggregate_stats(tmp_path)
    loaded = load_summary(tmp_path)
    assert loaded["total_events"] == written["total_events"]
    assert loaded["task_stats"]["total"] == written["task_stats"]["total"]


# ──────────────────────────────────────────────────────────────────
# _write_summary — 原子性 / tmp 清理
# ──────────────────────────────────────────────────────────────────


def test_write_summary_atomic_rename(tmp_path: Path):
    """_write_summary 走 temp + rename，写完后不留 tmp 文件。"""
    from _stats_aggregator import _write_summary

    _write_summary(tmp_path, {"total_events": 1, "workspace": tmp_path.name})
    assert _summary_file(tmp_path).exists()
    # 不应残留 .tmp 文件
    tmp_file = _summary_file(tmp_path).with_suffix(".tmp")
    assert not tmp_file.exists()


def test_write_summary_handles_failure(monkeypatch, tmp_path: Path):
    """写失败时应清理 tmp 文件并不抛异常。"""
    from _stats_aggregator import _write_summary

    def fail_rename(self, target):  # noqa: ARG001
        raise OSError("read-only filesystem")

    monkeypatch.setattr(Path, "rename", fail_rename)
    # 不应抛
    _write_summary(tmp_path, {"total_events": 1})
    # summary.json 不应存在（rename 失败），但 tmp 应被清理
    assert not _summary_file(tmp_path).exists()
