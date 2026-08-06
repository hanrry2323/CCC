"""看板三视图查询 + 线路图聚合占位（契约 §4）。

- 实时：按契约 §2 状态筛选分组。
- 7 天：回写时间在 `[now - days, now]` 窗口内，按回写时间倒序。
- 按项目：分组 + 计数 + 各状态分布。
- 线路图：§2 状态 → 线路图桶聚合（P3 占位）。
"""

from __future__ import annotations

from datetime import date, timedelta

from server.board.models import (
    BOARD_COLUMNS,
    ROADMAP_BUCKETS,
    STATE_TO_ROADMAP,
    STATES,
    UNCLASSIFIED,
    UNKNOWN,
    BoardItem,
    base_state,
    board_column,
)


def _project_rows_sorted(groups: dict[str, list[BoardItem]]) -> list[tuple[str, list[BoardItem]]]:
    """按项目排序：未分类置底，其余按任务数倒序、名称升序（T53 按项目聚合）。"""
    return sorted(
        groups.items(),
        key=lambda kv: (kv[0] == UNCLASSIFIED, -len(kv[1]), kv[0]),
    )


def _parse_date(value: str) -> date | None:
    """解析 YYYY-MM-DD；无效返回 None。"""
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def view_realtime(items: list[BoardItem]) -> dict[str, list[dict]]:
    """实时视图：按看板列分组（已回写且无机审通过 →「机审」栏）。

    组内明细的 `state` 保留卡头原文；另含 `board_column`。
    """
    grouped: dict[str, list[dict]] = {col: [] for col in BOARD_COLUMNS}
    for item in items:
        col = board_column(item.state, item.machine_audit_passed)
        bucket = col if col in grouped else UNKNOWN
        grouped.setdefault(bucket, []).append(item.to_dict())
    return {state: entries for state, entries in grouped.items() if entries}


def view_recent(
    items: list[BoardItem],
    now: date | None = None,
    days: int = 7,
) -> list[dict]:
    """7 天回写视图：回写时间在窗口内，按回写时间倒序。"""
    today = now or date.today()
    cutoff = today - timedelta(days=days)
    recent: list[dict] = []
    for item in items:
        written = _parse_date(item.written_at)
        if written is None:
            continue
        if cutoff <= written <= today:
            recent.append(item.to_dict())
    recent.sort(key=lambda row: row["written_at"], reverse=True)
    return recent


def view_by_project(items: list[BoardItem]) -> list[dict]:
    """按项目分类：分组 + 计数 + 各状态分布，按任务数倒序（未分类置底）。"""
    groups: dict[str, list[BoardItem]] = {}
    for item in items:
        groups.setdefault(item.project, []).append(item)
    rows = []
    for project, members in _project_rows_sorted(groups):
        rows.append(
            {
                "project": project,
                "count": len(members),
                "states": {
                    state: sum(1 for i in members if base_state(i.state) == state)
                    for state in STATES
                },
            }
        )
    return rows


def roadmap_aggregate(items: list[BoardItem]) -> list[dict]:
    """线路图聚合（L1 总览）：§2 状态 → 桶计数（兼容旧名）。"""
    return roadmap_overview(items)


def roadmap_overview(items: list[BoardItem]) -> list[dict]:
    """L1 线路图总览：全项目桶聚合。

    返回按 ROADMAP_BUCKETS 顺序的 {bucket, count} 列表。
    「已验收待确认」为预留空桶，当前无状态映射。
    """
    counts = {bucket: 0 for bucket in ROADMAP_BUCKETS}
    for item in items:
        bucket = STATE_TO_ROADMAP.get(base_state(item.state))
        if bucket is not None:
            counts[bucket] += 1
    return [{"bucket": bucket, "count": counts[bucket]} for bucket in ROADMAP_BUCKETS]


def roadmap_by_project(items: list[BoardItem]) -> list[dict]:
    """L2 单项目线路图：各项目桶聚合。

    返回按项目分组、按任务数倒序（未分类置底）的 {project, buckets: [{bucket, count}]} 列表。
    """
    groups: dict[str, list[BoardItem]] = {}
    for item in items:
        groups.setdefault(item.project, []).append(item)

    rows: list[dict] = []
    for project, members in _project_rows_sorted(groups):
        counts = {bucket: 0 for bucket in ROADMAP_BUCKETS}
        for item in members:
            bucket = STATE_TO_ROADMAP.get(base_state(item.state))
            if bucket is not None:
                counts[bucket] += 1
        rows.append(
            {
                "project": project,
                "count": len(members),
                "buckets": [
                    {"bucket": bucket, "count": counts[bucket]}
                    for bucket in ROADMAP_BUCKETS
                ],
            }
        )
    return rows


def roadmap_project_detail(
    items: list[BoardItem],
    project: str,
) -> list[dict]:
    """L3 项目线路图明细：按桶分组列出项目内全部任务卡。

    返回 [{bucket, items: [...]}]，items 为 BoardItem.to_dict()。
    """
    members = [i for i in items if i.project == project]
    grouped: dict[str, list[dict]] = {bucket: [] for bucket in ROADMAP_BUCKETS}
    for item in members:
        bucket = STATE_TO_ROADMAP.get(base_state(item.state))
        if bucket is not None:
            grouped[bucket].append(item.to_dict())
    return [
        {"bucket": bucket, "items": grouped[bucket]}
        for bucket in ROADMAP_BUCKETS
    ]


def state_counts(items: list[BoardItem]) -> dict[str, int]:
    """顶部徽章：契约 §2 各状态计数（按基础态）。"""
    return {
        state: sum(1 for i in items if base_state(i.state) == state) for state in STATES
    }


def board_column_counts(items: list[BoardItem]) -> dict[str, int]:
    """看板列计数（含派生「机审」）：与 snapshot.columns 同语义。"""
    counts = {col: 0 for col in BOARD_COLUMNS}
    for item in items:
        col = board_column(item.state, item.machine_audit_passed)
        if col in counts:
            counts[col] += 1
        else:
            counts[col] = counts.get(col, 0) + 1
    return counts


def states_response(items: list[BoardItem]) -> dict:
    """GET /board/states 载荷：顶层=卡头五态；columns=看板列；防「已回写=2」与「机审列」混淆。"""
    payload: dict = dict(state_counts(items))
    payload["columns"] = board_column_counts(items)
    payload["note"] = "顶层键=卡头五态；columns=看板列（机审为派生）"
    return payload


def ready_for_merge(items: list[BoardItem]) -> dict:
    """GET /board/ready_for_merge：看板列「已回写」且机审通过（可合入批准）。"""
    cards = [
        item.to_dict()
        for item in items
        if board_column(item.state, item.machine_audit_passed) == "已回写"
        and item.machine_audit_passed
    ]
    return {
        "cards": cards,
        "count": len(cards),
        "note": "质量门=机审通过+机械门禁；人侧口令=合入批准（非验收考古）",
    }
