"""看板三视图查询 + 线路图聚合占位（契约 §4）。

- 实时：按契约 §2 状态筛选分组。
- 7 天：回写时间在 `[now - days, now]` 窗口内，按回写时间倒序。
- 按项目：分组 + 计数 + 各状态分布。
- 线路图：§2 状态 → 线路图桶聚合（P3 占位）。
"""

from __future__ import annotations

from datetime import date, timedelta

from server.board.models import (
    ROADMAP_BUCKETS,
    STATE_TO_ROADMAP,
    STATES,
    UNKNOWN,
    BoardItem,
    base_state,
)


def _parse_date(value: str) -> date | None:
    """解析 YYYY-MM-DD；无效返回 None。"""
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def view_realtime(items: list[BoardItem]) -> dict[str, list[dict]]:
    """实时视图：按基础态分组（只含非空组；未知状态归入「未知」）。

    组键用 `base_state`（括号前基础态）；组内明细的 `state` 保留原文全串。
    """
    grouped: dict[str, list[dict]] = {state: [] for state in STATES}
    for item in items:
        base = base_state(item.state)
        bucket = base if base in grouped else UNKNOWN
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
    """按项目分类：分组 + 计数 + 各状态分布，按任务数倒序。"""
    groups: dict[str, list[BoardItem]] = {}
    for item in items:
        groups.setdefault(item.project, []).append(item)
    rows = []
    for project, members in sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0])):
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

    返回按项目分组、按任务数倒序的 {project, buckets: [{bucket, count}]} 列表。
    """
    groups: dict[str, list[BoardItem]] = {}
    for item in items:
        groups.setdefault(item.project, []).append(item)

    rows: list[dict] = []
    for project, members in sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0])):
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
