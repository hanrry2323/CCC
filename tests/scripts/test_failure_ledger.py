"""test_failure_ledger.py — Phase 4.1: _failure_ledger append/read/quarantine"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from _failure_ledger import (
    failures_path,
    infer_role_from_reason,
    read_failures,
    record_failure,
    resolve_stderr_path,
)


def _make_ws(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    (ws / ".ccc" / "stats").mkdir(parents=True)
    (ws / ".ccc" / "reports").mkdir(parents=True)
    (ws / ".ccc" / "verdicts").mkdir(parents=True)
    return ws


def test_failures_path(tmp_path):
    ws = _make_ws(tmp_path)
    assert failures_path(ws) == ws / ".ccc" / "stats" / "failures.jsonl"


def test_record_failure_appends(tmp_path):
    ws = _make_ws(tmp_path)
    p = record_failure(
        ws,
        task_id="t1",
        role="engine",
        reason="hang_detected pid=123",
        phase=1,
        from_col="in_progress",
    )
    assert p.is_file()
    rows = [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
    assert len(rows) == 1
    assert rows[0]["task_id"] == "t1"
    assert rows[0]["role"] == "engine"
    assert rows[0]["phase"] == 1
    assert rows[0]["from_col"] == "in_progress"
    assert rows[0]["to_col"] == "abnormal"  # 默认
    assert "ts" in rows[0]


def test_record_failure_multiple_appends(tmp_path):
    ws = _make_ws(tmp_path)
    for i in range(5):
        record_failure(ws, task_id=f"t{i}", role="dev", reason=f"exit={i}")
    rows = read_failures(ws, last=0)
    assert len(rows) == 5
    assert [r["task_id"] for r in rows] == [f"t{i}" for i in range(5)]


def test_read_failures_last_n(tmp_path):
    ws = _make_ws(tmp_path)
    for i in range(10):
        record_failure(ws, task_id=f"t{i}", role="dev", reason=f"r{i}")
    last3 = read_failures(ws, last=3)
    assert len(last3) == 3
    assert [r["task_id"] for r in last3] == ["t7", "t8", "t9"]


def test_read_failures_empty_when_no_file(tmp_path):
    ws = _make_ws(tmp_path)
    assert read_failures(ws) == []


def test_resolve_stderr_path_prefers_result_json(tmp_path):
    ws = _make_ws(tmp_path)
    (ws / ".ccc" / "reports" / "t1.result.json").write_text("{}", encoding="utf-8")
    (ws / ".ccc" / "verdicts" / "t1.verdict.md").write_text("v", encoding="utf-8")
    rel = resolve_stderr_path(ws, "t1")
    assert rel == ".ccc/reports/t1.result.json"


def test_resolve_stderr_path_falls_back_to_verdict(tmp_path):
    ws = _make_ws(tmp_path)
    (ws / ".ccc" / "verdicts" / "t1.verdict.md").write_text("v", encoding="utf-8")
    rel = resolve_stderr_path(ws, "t1")
    assert rel == ".ccc/verdicts/t1.verdict.md"


def test_resolve_stderr_path_none(tmp_path):
    ws = _make_ws(tmp_path)
    assert resolve_stderr_path(ws, "t1") is None


def test_infer_role_from_reason():
    assert infer_role_from_reason("product fanout failed") == "product"
    assert infer_role_from_reason("reviewer timeout") == "reviewer"
    assert infer_role_from_reason("verdict missing") == "reviewer"
    assert infer_role_from_reason("pytest exit=1") == "tester"
    assert infer_role_from_reason("tester assert") == "tester"
    assert infer_role_from_reason("hang_detected pid=123") == "engine"
    assert infer_role_from_reason("watchdog killed") == "engine"
    assert infer_role_from_reason("opencode slot lost") == "dev"
    assert infer_role_from_reason("dev_role relaunch") == "dev"
    assert infer_role_from_reason("kb archive failed") == "kb"
    assert infer_role_from_reason("unknown error") == "engine"


def test_record_failure_truncates_long_reason(tmp_path):
    ws = _make_ws(tmp_path)
    long_reason = "x" * 1000
    record_failure(ws, task_id="t1", role="engine", reason=long_reason)
    rows = read_failures(ws)
    assert len(rows[0]["reason"]) == 500


def test_record_failure_with_extra(tmp_path):
    ws = _make_ws(tmp_path)
    record_failure(
        ws,
        task_id="t1",
        role="engine",
        reason="r",
        extra={"retry_count": 3, "custom": "data"},
    )
    rows = read_failures(ws)
    assert rows[0]["extra"] == {"retry_count": 3, "custom": "data"}


def test_record_failure_includes_stderr_tail(tmp_path):
    ws = _make_ws(tmp_path)
    # 写一个 verdict 文件作为 stderr 源
    (ws / ".ccc" / "verdicts" / "t1.verdict.md").write_text(
        "# Verdict\n\n**Verdict:** FAIL\n\n```\nerror line 1\nerror line 2\n```",
        encoding="utf-8",
    )
    record_failure(ws, task_id="t1", role="reviewer", reason="verdict FAIL")
    rows = read_failures(ws)
    assert rows[0]["stderr_path"] == ".ccc/verdicts/t1.verdict.md"
    assert "FAIL" in rows[0]["stderr_tail"]
