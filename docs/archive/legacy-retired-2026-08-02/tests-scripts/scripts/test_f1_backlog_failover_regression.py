"""F2-1: fail_counter + quarantine path regression (mirrors e2e smoke)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from _board_store import FileBoardStore  # noqa: E402
from _product_fail_counter import (  # noqa: E402
    clear_product_fail_count,
    load_product_fail_count,
    write_product_fail_count,
)


@pytest.fixture()
def ws(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    for col in (
        "backlog",
        "planned",
        "in_progress",
        "testing",
        "verified",
        "released",
        "abnormal",
        "events",
    ):
        (tmp_path / ".ccc" / "board" / col).mkdir(parents=True)
    (tmp_path / ".ccc" / ".product-fail-counter").mkdir(parents=True)
    (tmp_path / ".ccc" / "profile.md").write_text("# F2-1 failover\n", encoding="utf-8")
    (tmp_path / ".ccc" / "state.md").write_text("# state\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    import _config

    monkeypatch.setattr(_config, "_resolve_workspace", lambda: tmp_path)
    return tmp_path


def test_fail_counter_below_max_allows_retry(ws: Path):
    counter = ws / ".ccc" / ".product-fail-counter" / "t-retry.json"
    write_product_fail_count(counter, 1, now=1000.0)
    fc, _ = load_product_fail_count(counter, now=1000.0, max_retries=3)
    assert fc < 3


def test_fail_count_at_max_quarantines(ws: Path):
    store = FileBoardStore(ws)
    tid = "mid-fail-max"
    store.create_task(
        {
            "id": tid,
            "title": tid,
            "status": "backlog",
            "created_at": "2026-07-11",
            "updated_at": "2026-07-11",
        },
        column="backlog",
    )
    counter = ws / ".ccc" / ".product-fail-counter" / f"{tid}.json"
    write_product_fail_count(counter, 3, now=1000.0)
    fc, _ = load_product_fail_count(counter, now=1000.0, max_retries=3)
    assert fc >= 3
    store.quarantine(tid, f"product_role failed {fc} times")
    bl_ids = [t["id"] for t in store.list_tasks("backlog")]
    ab_ids = [t["id"] for t in store.list_tasks("abnormal")]
    assert tid not in bl_ids
    assert tid in ab_ids
    # 无 plan/phases 时不落 quarantines/ 目录；原因写在 task.note
    ab = next(t for t in store.list_tasks("abnormal") if t["id"] == tid)
    assert "failed 3 times" in str(ab.get("note") or "")


def test_success_clears_fail_counter(ws: Path):
    counter = ws / ".ccc" / ".product-fail-counter" / "t-ok.json"
    write_product_fail_count(counter, 2, now=1000.0)
    assert counter.is_file()
    clear_product_fail_count(counter)
    assert not counter.is_file()
    fc, _ = load_product_fail_count(counter, now=1000.0, max_retries=3)
    assert fc == 0


def test_backlog_newest_first_planned_fifo(ws: Path):
    store = FileBoardStore(ws)
    for tid, day in (
        ("oldest-2026-07-10", "2026-07-10"),
        ("mid-2026-07-11", "2026-07-11"),
        ("newest-2026-07-12", "2026-07-12"),
    ):
        store.create_task(
            {
                "id": tid,
                "title": tid,
                "status": "backlog",
                "created_at": day,
                "updated_at": day,
            },
            column="backlog",
        )
    tasks = store.list_tasks("backlog")
    dates = [t.get("created_at", "") for t in tasks]
    assert dates == sorted(dates, reverse=True)

    store.create_task(
        {
            "id": "w-old",
            "title": "w-old",
            "status": "planned",
            "card_kind": "work",
            "created_at": "2026-07-10",
            "updated_at": "2026-07-10",
        },
        column="planned",
    )
    store.create_task(
        {
            "id": "w-new",
            "title": "w-new",
            "status": "planned",
            "card_kind": "work",
            "created_at": "2026-07-12",
            "updated_at": "2026-07-12",
        },
        column="planned",
    )
    p_dates = [t.get("created_at", "") for t in store.list_tasks("planned")]
    assert p_dates == sorted(p_dates)

    c = ws / ".ccc" / ".product-fail-counter" / "oldest-2026-07-10.json"
    c.write_text(json.dumps({"fail_count": 2}, indent=2), encoding="utf-8")
    assert json.loads(c.read_text(encoding="utf-8"))["fail_count"] == 2
