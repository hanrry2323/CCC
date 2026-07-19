"""test_flow_sse_offset.py — Phase 2.4 验收：flow_events offset 增量读只返回新行。"""
from __future__ import annotations

import json
import os
from pathlib import Path

from chat_server.services import flow_events


def _write_log(tmp_path: Path, lines: list[str]) -> Path:
    log = tmp_path / "flow-events.jsonl"
    log.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return log


def _rec(ts: str, event: str, pid: str, eid: str = "e1") -> str:
    return json.dumps(
        {"ts": ts, "event": event, "data": {"project_id": pid, "epic_id": eid}},
        ensure_ascii=False,
    )


def test_offset_reads_only_new_lines(tmp_path, monkeypatch):
    log = _write_log(tmp_path, [_rec("2026-07-19T00:00:01+08:00", "a", "p1")])
    monkeypatch.setenv("CCC_FLOW_EVENTS_LOG", str(log))
    # 重新加载模块以应用 env
    import importlib

    importlib.reload(flow_events)

    recs1, off1, ino1 = flow_events.read_events_from_offset(0, project_id="p1")
    assert len(recs1) == 1
    assert off1 > 0

    # 追加新行
    with log.open("a", encoding="utf-8") as f:
        f.write(_rec("2026-07-19T00:00:02+08:00", "b", "p1") + "\n")
    recs2, off2, ino2 = flow_events.read_events_from_offset(off1, project_id="p1")
    assert len(recs2) == 1
    assert recs2[0]["event"] == "b"
    assert off2 > off1
    assert ino1 == ino2


def test_offset_filters_by_project(tmp_path, monkeypatch):
    log = _write_log(
        tmp_path,
        [
            _rec("2026-07-19T00:00:01+08:00", "a", "p1"),
            _rec("2026-07-19T00:00:02+08:00", "b", "p2"),
            _rec("2026-07-19T00:00:03+08:00", "c", "p1"),
        ],
    )
    monkeypatch.setenv("CCC_FLOW_EVENTS_LOG", str(log))
    import importlib

    importlib.reload(flow_events)

    recs, _, _ = flow_events.read_events_from_offset(0, project_id="p1")
    assert [r["event"] for r in recs] == ["a", "c"]


def test_offset_handles_truncation(tmp_path, monkeypatch):
    log = _write_log(
        tmp_path,
        [_rec(f"2026-07-19T00:00:0{i}+08:00", f"e{i}", "p1") for i in range(1, 6)],
    )
    monkeypatch.setenv("CCC_FLOW_EVENTS_LOG", str(log))
    import importlib

    importlib.reload(flow_events)

    _, off1, _ = flow_events.read_events_from_offset(0, project_id="p1")
    # 截断文件
    log.write_text(_rec("2026-07-19T00:00:09+08:00", "fresh", "p1") + "\n", encoding="utf-8")
    recs, off2, _ = flow_events.read_events_from_offset(off1, project_id="p1")
    # offset > size → 重置到 0，读到 fresh
    assert len(recs) == 1
    assert recs[0]["event"] == "fresh"
    assert off2 > 0


def test_offset_after_ts_filter(tmp_path, monkeypatch):
    log = _write_log(
        tmp_path,
        [
            _rec("2026-07-19T00:00:01+08:00", "a", "p1"),
            _rec("2026-07-19T00:00:02+08:00", "b", "p1"),
            _rec("2026-07-19T00:00:03+08:00", "c", "p1"),
        ],
    )
    monkeypatch.setenv("CCC_FLOW_EVENTS_LOG", str(log))
    import importlib

    importlib.reload(flow_events)

    recs, _, _ = flow_events.read_events_from_offset(
        0, project_id="p1", after_ts="2026-07-19T00:00:02+08:00"
    )
    assert [r["event"] for r in recs] == ["c"]
