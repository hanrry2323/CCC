"""C 阶段二：执行中卡与旁路事件合成视图。"""

from server.board.executing import build_executing_view
from server.board.models import BoardItem


def _card(card_id: str, state: str = "执行中") -> BoardItem:
    return BoardItem(
        id=card_id,
        title=f"title-{card_id}",
        state=state,
        executor="executor-a",
        dispatched_at="2026-09-05",
    )


def _event(work_id: str, ts: float, event: str = "executor_started") -> dict:
    return {
        "work_id": work_id,
        "event": event,
        "ts": ts,
        "event_id": f"e-{work_id}-{ts}",
        "payload": {"card_title": f"title-{work_id}"},
    }


def test_card_with_event_is_enriched_and_card_only_is_retained():
    result = build_executing_view([_card("a"), _card("b")], [_event("a", 10)])

    assert result["count"] == 2
    by_id = {row["id"]: row for row in result["items"]}
    assert by_id["a"]["source"] == "card+event"
    assert by_id["a"]["event"]["event"] == "executor_started"
    assert by_id["b"]["source"] == "card-only"
    assert by_id["b"]["event"] is None
    assert result["reconciliation"]["last_event_ts"] == 10
    assert result["generated_at"]


def test_terminal_event_is_suppressed_without_reviving_card():
    result = build_executing_view(
        [_card("done", "已回写"), _card("closed", "已关闭"), _card("running")],
        [_event("done", 20, "executor_completed"), _event("closed", 21), _event("running", 22)],
    )

    assert [row["id"] for row in result["items"]] == ["running"]
    assert result["reconciliation"]["suppressed_terminal_events"] == 2


def test_orphan_events_are_counted_and_discarded():
    result = build_executing_view([_card("known")], [_event("missing", 30)])

    assert result["items"][0]["source"] == "card-only"
    assert result["reconciliation"]["orphan_work_ids"] == 1


def test_latest_event_wins_and_malformed_rows_do_not_crash():
    result = build_executing_view(
        [_card("a")],
        [None, {"work_id": "a", "ts": "bad"}, _event("a", 2), _event("a", 1)],
    )

    assert result["items"][0]["event_ts"] == 2
