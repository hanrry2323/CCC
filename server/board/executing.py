"""执行中看板的卡片 + 旁路事件合成视图。

卡状态仍由卡文件/运行时合成视图决定；事件仅补充最近实时进度。
终态卡不会因为事件存储中仍有旧事件而重新进入执行中视图。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

from server.board.models import BoardItem, base_state

_TERMINAL_STATES = frozenset({"已回写", "已关闭", "打回", "作废"})


def _event_ts(row: dict[str, Any]) -> float:
    try:
        return float(row.get("ts", 0))
    except (TypeError, ValueError):
        return 0.0


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _event_view(row: dict[str, Any]) -> dict[str, Any]:
    """返回事件展示字段，不把原始存储记录直接暴露给看板。"""
    payload = row.get("payload")
    return {
        "event": str(row.get("event") or ""),
        "ts": row.get("ts"),
        "payload": dict(payload) if isinstance(payload, dict) else {},
    }


def build_executing_view(
    items: Iterable[BoardItem],
    events: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    """合成执行中卡片与最近事件，并完成一次读时对账。

    A = 当前卡/运行时合成状态；B = 旁路事件存储。A 是状态唯一真值：
    A 中执行中的卡无事件也照常返回；终态卡即使仍有事件也不返回；事件
    引用不存在的卡只计入 orphan_work_ids，不生成虚假卡片。
    """
    card_items = list(items)
    by_id = {str(item.id): item for item in card_items}
    latest: dict[str, dict[str, Any]] = {}
    suppressed_terminal = 0
    orphan_ids: set[str] = set()
    last_event_ts: float | None = None

    for row in events:
        if not isinstance(row, dict):
            continue
        work_id = str(row.get("work_id") or "").strip()
        if not work_id:
            continue
        ts = _event_ts(row)
        if ts and (last_event_ts is None or ts > last_event_ts):
            last_event_ts = ts
        item = by_id.get(work_id)
        if item is None:
            orphan_ids.add(work_id)
            continue
        if base_state(item.state) in _TERMINAL_STATES:
            suppressed_terminal += 1
            continue
        previous = latest.get(work_id)
        if previous is None or _event_ts(previous) <= ts:
            latest[work_id] = row

    entries: list[dict[str, Any]] = []
    for item in card_items:
        # 事件绝不改变这一筛选；终态优先由 A 的状态决定。
        if base_state(item.state) != "执行中":
            continue
        event = latest.get(str(item.id))
        row = {
            "id": item.id,
            "title": item.title,
            "executor": item.executor,
            "state": item.state,
            "dispatched_at": item.dispatched_at,
            "claim_at": getattr(item, "claim_at", ""),
            "event": _event_view(event) if event else None,
            "event_ts": event.get("ts") if event else None,
            "source": "card+event" if event else "card-only",
        }
        entries.append(row)

    entries.sort(key=lambda row: (str(row.get("event_ts") or ""), str(row["id"])), reverse=True)
    return {
        "generated_at": _iso_now(),
        "items": entries,
        "count": len(entries),
        "reconciliation": {
            "suppressed_terminal_events": suppressed_terminal,
            "orphan_work_ids": len(orphan_ids),
            "last_event_ts": last_event_ts,
        },
    }
