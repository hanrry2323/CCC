"""TDD: self-heal failure buckets + exhaust vs recoverable (field-backed).

Field samples (Mac2017 2026-07-30):
- qb: acceptance-gate: acceptance_empty_bullets → was mis-bucketed as other
- qb: product async timeout after 1200s
- medio/xianyu: acceptance_fail_budget + reviewer 未产出 verdict
- qx-observer: hang_detected: hang auto-restart 耗尽
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))


@pytest.mark.parametrize(
    "reason,bucket",
    [
        (
            "acceptance_fail_budget n=1: acceptance-gate: acceptance_empty_bullets",
            "acceptance_fail",
        ),
        (
            "acceptance_fail_budget n=2: acceptance-gate: acceptance_cmd_failed",
            "acceptance_fail",
        ),
        (
            "hang_detected: hang auto-restart 耗尽（1 次）— w1 phase 1",
            "hang",
        ),
        (
            "product async timeout after 1200s",
            "product_timeout",
        ),
        (
            "reviewer 未产出 verdict",
            "reviewer_timeout",
        ),
        (
            "dirty_block: business dirty outside plan scope Author:",
            "dirty_block",
        ),
        (
            "engine: in_progress 滞留 2.0h (阈值 2h)",
            "stale_inflight",
        ),
        (
            "phase graph unresolvable（epic 子卡，禁止 product regen）",
            "phase_unresolvable",
        ),
        (
            "reviewer_fail_loop_exhausted (4)",
            "fail_loop_exhausted",
        ),
    ],
)
def test_classify_field_reasons(reason, bucket):
    from _failure_buckets import classify_failure_bucket

    assert classify_failure_bucket(reason) == bucket


@pytest.mark.parametrize(
    "reason,exhaust",
    [
        # Exhaust only when Engine already spent same-card budget / 耗尽 markers
        ("hang_detected: hang auto-restart 耗尽（1 次）", True),
        ("short_path_fail_budget path=script_seed n=3: acceptance:acceptance_cmd_failed", True),
        ("acceptance_fail_budget n=2: acceptance-gate: acceptance_cmd_failed", True),
        ("reviewer_fail_loop_exhausted (3)", True),
        ("phase graph unresolvable（epic 子卡）", True),
        ("engine: 重试3次全部失败，隔离", True),
        # Transient / first-hit — Engine may still refeed; board_repair must NOT archive
        ("connection timeout retry later", False),
        ("acceptance:acceptance_cmd_failed", False),
        ("reviewer 未产出 verdict", False),
        ("**Verdict:** TIMEOUT", False),
        ("product async timeout after 1200s", False),
    ],
)
def test_is_exhaust_reason_aligned_with_refeed(reason, exhaust):
    from _failure_buckets import is_exhaust_reason

    assert is_exhaust_reason(reason) is exhaust


def test_optimize_hints_cover_new_buckets():
    from _failure_buckets import bucket_optimize_hints

    assert "空 bullets" in bucket_optimize_hints("acceptance_fail") or "探针" in bucket_optimize_hints(
        "acceptance_fail"
    )
    dirty = bucket_optimize_hints("dirty_block")
    assert "卫生" in dirty or "噪音" in dirty or "reopen" in dirty
    assert "invent" not in dirty.lower() or "禁 invent" in dirty
    rev = bucket_optimize_hints("reviewer_timeout")
    assert "verdict" in rev.lower() or "审" in rev
    prod = bucket_optimize_hints("product_timeout")
    assert "扇出" in prod or "缩小" in prod


def test_is_recoverable_abnormal_uses_exhaust_gate(ws_board, tmp_path, monkeypatch):
    from _board_store import FileBoardStore
    from chat_server.services import board_repair as br

    ws = ws_board
    store = FileBoardStore(ws)
    assert store.create_task(
        {
            "id": "w-transient",
            "title": "t",
            "card_kind": "work",
            "status": "abnormal",
            "note": "connection timeout",
            "goal": "g",
            "acceptance": ["a"],
            "pipeline": "dev",
        },
        column="abnormal",
    )
    assert store.create_task(
        {
            "id": "w-exhaust",
            "title": "e",
            "card_kind": "work",
            "status": "abnormal",
            "note": "hang_detected: hang auto-restart 耗尽（1 次）",
            "goal": "g",
            "acceptance": ["a"],
            "pipeline": "dev",
        },
        column="abnormal",
    )
    _, t1 = store.find_task("w-transient")
    _, t2 = store.find_task("w-exhaust")
    assert br.is_recoverable_abnormal(ws, t1) is True
    assert br.is_recoverable_abnormal(ws, t2) is False


def test_clear_blockers_archives_exhaust_reopens_transient(ws_board, tmp_path, monkeypatch):
    monkeypatch.setenv("CCC_BOARD_REPAIR_LOG", str(tmp_path / "r.jsonl"))
    monkeypatch.setenv("CCC_FLOW_EVENTS_LOG", str(tmp_path / "f.jsonl"))
    from chat_server import config as hub_cfg
    from chat_server.services import board_repair as br
    from chat_server.services import flow_events as fe
    from _board_store import FileBoardStore

    monkeypatch.setattr(hub_cfg, "CHAT_DIR", tmp_path / "chat")
    (tmp_path / "chat").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(fe, "events_log_path", lambda: tmp_path / "f.jsonl")

    ws = ws_board
    store = FileBoardStore(ws)
    assert store.create_task(
        {
            "id": "w-ok",
            "title": "recoverable",
            "card_kind": "work",
            "status": "abnormal",
            "note": "connection timeout",
            "goal": "g",
            "acceptance": ["a"],
            "pipeline": "dev",
        },
        column="abnormal",
    )
    assert store.create_task(
        {
            "id": "w-dead",
            "title": "exhausted",
            "card_kind": "work",
            "status": "abnormal",
            "note": "acceptance_fail_budget n=2: acceptance-gate: acceptance_cmd_failed",
            "goal": "g",
            "acceptance": ["a"],
            "pipeline": "dev",
        },
        column="abnormal",
    )
    out = br.clear_blockers(ws, "demo", reason="test_exhaust_split")
    assert "w-ok" in (out.get("reopened_recoverable") or {}).get("reopened", [])
    assert "w-dead" in (out.get("archived") or {}).get("hidden", [])
    col_ok, _ = store.find_task("w-ok")
    assert col_ok == "planned"
    _, dead = store.find_task("w-dead")
    assert dead.get("ui_hidden") is True


@pytest.fixture()
def ws_board(tmp_path):
    root = tmp_path / "app"
    for col in (
        "backlog",
        "planned",
        "in_progress",
        "testing",
        "verified",
        "released",
        "abnormal",
    ):
        (root / ".ccc" / "board" / col).mkdir(parents=True, exist_ok=True)
    return root
