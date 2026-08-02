"""test_board_queries — 三视图 + 7 天窗口边界 + 项目分组 + 线路图聚合。"""

from __future__ import annotations

from datetime import date

from server.board.models import BoardItem
from server.board.queries import (
    roadmap_aggregate,
    state_counts,
    view_by_project,
    view_realtime,
    view_recent,
)


def _item(
    item_id: str,
    state: str = "待分派",
    project: str = "PRJ-X",
    executor: str = "执行体",
    written: str = "未知",
) -> BoardItem:
    return BoardItem(
        id=item_id,
        title="示例任务",
        state=state,
        project=project,
        executor=executor,
        dispatched_at="2026-08-02",
        written_at=written,
        reject_count=0,
    )


class TestViewRealtime:
    """实时视图：按状态分组。"""

    def test_groups_by_state(self) -> None:
        items = [
            _item("a", state="待分派"),
            _item("b", state="执行中"),
            _item("c", state="待分派"),
        ]
        view = view_realtime(items)
        assert len(view["待分派"]) == 2
        assert len(view["执行中"]) == 1
        assert "已回写" not in view  # 空组不出现

    def test_unknown_state_bucket(self) -> None:
        items = [_item("a", state="怪异值")]
        view = view_realtime(items)
        assert len(view["未知"]) == 1


class TestViewRecent:
    """7 天回写视图：窗口边界 + 排序。"""

    NOW = date(2026, 8, 2)

    def test_window_boundary(self) -> None:
        items = [
            _item("in_today", written="2026-08-02"),
            _item("in_7d", written="2026-07-26"),   # 恰 7 天 → 含
            _item("out_8d", written="2026-07-25"),  # 8 天 → 不含
            _item("no_write", written="未知"),        # 无回写 → 不含
        ]
        recent = view_recent(items, now=self.NOW, days=7)
        assert [row["id"] for row in recent] == ["in_today", "in_7d"]

    def test_sorted_desc(self) -> None:
        items = [
            _item("older", written="2026-07-28"),
            _item("newer", written="2026-08-01"),
        ]
        recent = view_recent(items, now=self.NOW, days=7)
        assert [row["id"] for row in recent] == ["newer", "older"]


class TestViewByProject:
    """按项目分类：分组 + 计数 + 状态分布。"""

    def test_group_and_count(self) -> None:
        items = [
            _item("a", project="PRJ-X"),
            _item("b", project="PRJ-X"),
            _item("c", project="PRJ-Y"),
        ]
        rows = view_by_project(items)
        assert rows[0]["project"] == "PRJ-X"  # count 多者在前
        assert rows[0]["count"] == 2
        assert rows[0]["states"]["待分派"] == 2
        assert rows[1]["project"] == "PRJ-Y"
        assert rows[1]["count"] == 1


class TestRoadmap:
    """线路图聚合占位。"""

    def test_state_to_bucket(self) -> None:
        items = [
            _item("a", state="待分派"),
            _item("b", state="执行中"),
            _item("c", state="已回写"),
            _item("d", state="已关闭"),
            _item("e", state="打回"),
        ]
        counts = {row["bucket"]: row["count"] for row in roadmap_aggregate(items)}
        assert counts == {
            "未开发": 1,
            "开发中": 1,
            "已开发待验收": 1,
            "已验收待确认": 0,
            "确认可用": 1,
            "有问题": 1,
        }


class TestStateCounts:
    """顶部徽章计数。"""

    def test_counts(self) -> None:
        items = [
            _item("a", state="待分派"),
            _item("b", state="待分派"),
            _item("c", state="待分派"),
            _item("d", state="执行中"),
        ]
        assert state_counts(items) == {
            "待分派": 3,
            "执行中": 1,
            "已回写": 0,
            "已关闭": 0,
            "打回": 0,
        }


class TestStateNormalization:
    """带括号状态变体：按基础态归桶；明细保留全串；未知归未知桶。"""

    def test_variant_buckets_to_base_state(self) -> None:
        items = [
            _item("a", state="待分派（实现）"),
            _item("b", state="打回（原因）"),
            _item("c", state="已回写（有条件）"),
        ]
        view = view_realtime(items)
        assert len(view["待分派"]) == 1
        assert len(view["打回"]) == 1
        assert len(view["已回写"]) == 1

    def test_detail_keeps_full_state(self) -> None:
        items = [_item("b", state="打回（原因）")]
        view = view_realtime(items)
        assert view["打回"][0]["state"] == "打回（原因）"
        assert view["打回"][0]["id"] == "b"

    def test_variant_roadmap_and_counts(self) -> None:
        items = [
            _item("a", state="待分派（实现）"),
            _item("b", state="打回（原因）"),
            _item("c", state="已回写（有条件）"),
        ]
        counts = {row["bucket"]: row["count"] for row in roadmap_aggregate(items)}
        assert counts["未开发"] == 1
        assert counts["已开发待验收"] == 1
        assert counts["有问题"] == 1
        assert state_counts(items) == {
            "待分派": 1,
            "执行中": 0,
            "已回写": 1,
            "已关闭": 0,
            "打回": 1,
        }

    def test_variant_by_project_states(self) -> None:
        items = [
            _item("a", state="打回（原因）", project="PRJ-X"),
            _item("b", state="打回（原因）", project="PRJ-X"),
        ]
        rows = view_by_project(items)
        assert rows[0]["states"]["打回"] == 2

    def test_unknown_state_to_unknown_bucket(self) -> None:
        items = [_item("a", state="怪异值"), _item("b", state="")]
        view = view_realtime(items)
        assert len(view["未知"]) == 2

    def test_recent_keeps_full_state(self) -> None:
        items = [_item("b", state="打回（原因）", written="2026-08-02")]
        recent = view_recent(items, now=date(2026, 8, 2), days=7)
        assert recent[0]["state"] == "打回（原因）"
