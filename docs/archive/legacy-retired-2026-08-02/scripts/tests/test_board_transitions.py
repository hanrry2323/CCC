"""Board column transitions — 形式化验证（v0.62.0）。

COLUMN_TRANSITIONS 白名单定义了 19 条允许迁移路径、
（7×7 − 7 自环 − 19 允许）= 23 条禁止路径。
每条路径以参数化单测验证，失败即精确定位。
"""

from __future__ import annotations

import sys
from collections import deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from _board_store import COLUMNS, COLUMN_TRANSITIONS, FileBoardStore

# ── 允许的迁移路径（从 COLUMN_TRANSITIONS 提取）──
ALLOWED: list[tuple[str, str]] = []
for to_col, from_list in COLUMN_TRANSITIONS.items():
    for from_col in from_list:
        ALLOWED.append((from_col, to_col))


# ── 禁止的迁移路径（所有 from×to 对减去自环、减去允许）──
_ALL_PAIRS = [(f, t) for f in COLUMNS for t in COLUMNS if f != t]
FORBIDDEN: list[tuple[str, str]] = [p for p in _ALL_PAIRS if p not in ALLOWED]


def _ts():
    return "2026-07-17T12:00:00+08:00"


# ── DAG 路径规划 ──

def _build_transition_graph() -> dict[str, list[str]]:
    """根据 COLUMN_TRANSITIONS 构建有向图。

    COLUMN_TRANSITIONS 定义 {目标列: [允许的源列列表]}，
    因此有向边 from→to 当且仅当 from ∈ COLUMN_TRANSITIONS[to]。
    反向迁移（如 in_progress→backlog）也由对应的白名单条目标记。
    """
    graph: dict[str, set[str]] = {c: set() for c in COLUMNS}
    for to_col, from_list in COLUMN_TRANSITIONS.items():
        for from_col in from_list:
            graph[from_col].add(to_col)  # 只加实有向边：from → to
    return {c: sorted(v) for c, v in graph.items()}


_GRAPH = _build_transition_graph()


def _find_path(from_col: str, to_col: str) -> list[str] | None:
    """BFS 找从 from_col 到 to_col 的一条合法路径（含起终点）。"""
    if from_col == to_col:
        return [from_col]
    visited = {from_col}
    q: deque[tuple[str, list[str]]] = deque()
    q.append((from_col, [from_col]))
    while q:
        cur, path = q.popleft()
        for neighbor in _GRAPH.get(cur, []):
            if neighbor == to_col:
                return path + [neighbor]
            if neighbor not in visited:
                visited.add(neighbor)
                q.append((neighbor, path + [neighbor]))
    return None


def _walk_to(tid: str, store: FileBoardStore, target_col: str) -> bool:
    """通过 BFS 规划的路径把卡移动到 target_col，返回是否成功。"""
    current = store.resolve_task_column(tid)
    if current == target_col:
        return True
    if current is None:
        return False
    path = _find_path(current, target_col)
    if path is None:
        return False
    # 沿路径逐步移动
    for i in range(len(path) - 1):
        if not store.move_task(tid, path[i], path[i + 1]):
            return False
    return True


@pytest.fixture()
def board_store(tmp_path):
    """tmp_path 隔离的 FileBoardStore，含一张 work 卡（创建在 planned）。

    work 不能在 backlog 直接创建（见 _board_store.py:592-601 的安全门禁）；
    planned 是 work 的合法初始列，且可从 planned 沿 DAG 到达任何列。
    """
    store = FileBoardStore(tmp_path)
    ok = store.create_task(
        {
            "id": "w1",
            "title": "Test Work",
            "description": "work card for column transitions",
            "card_kind": "work",
            "created_at": _ts(),
            "updated_at": _ts(),
        },
        column="planned",
    )
    assert ok, "fixture: failed to create work card in planned"
    return store


@pytest.mark.parametrize("from_col,to_col", ALLOWED)
def test_allowed_transition(from_col, to_col, board_store):
    """所有 COLUMN_TRANSITIONS 白名单路径必须可通。"""
    tid = "w1"
    ok = _walk_to(tid, board_store, from_col)
    assert ok, f"setup: cannot reach {from_col} from start column"
    ok = board_store.move_task(tid, from_col, to_col)
    assert ok, f"迁移被拒绝: {from_col} → {to_col}"
    # 验证卡确实在新列
    col, task = board_store.find_task(tid)
    assert col == to_col, f"move_task 返回 ok 但卡仍在 {col} 而非 {to_col}"


@pytest.mark.parametrize("from_col,to_col", FORBIDDEN)
def test_forbidden_transition(from_col, to_col, board_store):
    """所有白名单外的迁移路径必须被拒绝。"""
    tid = "w1"
    ok = _walk_to(tid, board_store, from_col)
    if not ok:
        pytest.skip(f"cannot reach {from_col} from start column")
    ok = board_store.move_task(tid, from_col, to_col)
    assert not ok, f"非法迁移被接受: {from_col} → {to_col}"
    # 卡应仍在 from_col
    col, _ = board_store.find_task(tid)
    assert col == from_col, f"非法迁移后卡不应变列: 期望 {from_col}, 实际 {col}"


# ── 特殊规则：epic 不可离开 backlog ──


def test_epic_cannot_leave_backlog(board_store):
    """epic 在 backlog 中不可 move_task 到任何其他列。"""
    store = board_store
    store.create_task(
        {
            "id": "e1",
            "title": "Test Epic",
            "card_kind": "epic",
            "created_at": _ts(),
            "updated_at": _ts(),
        },
        column="backlog",
    )
    for target in [c for c in COLUMNS if c != "backlog"]:
        ok = store.move_task("e1", "backlog", target)
        assert not ok, f"epic 不应离开 backlog → {target}"
    col, _ = store.find_task("e1")
    assert col == "backlog", f"epic 被移动了 {col}"


def test_epic_created_only_in_backlog(board_store):
    """create_task epics only in backlog."""
    store = board_store
    for col in [c for c in COLUMNS if c != "backlog"]:
        ok = store.create_task(
            {
                "id": f"e-{col}",
                "title": f"Epic in {col}",
                "card_kind": "epic",
                "created_at": _ts(),
                "updated_at": _ts(),
            },
            column=col,
        )
        assert not ok, f"epic 不应在 {col} 创建"


# ── 多副本消除：pick_canonical_column ──


def test_pick_canonical_abnormal_wins():
    """abnormal 列优先于其他列。"""
    from _board_store import pick_canonical_column

    assert pick_canonical_column({"backlog", "abnormal"}) == "abnormal"
    assert pick_canonical_column({"planned", "abnormal"}) == "abnormal"
    assert pick_canonical_column({"released", "abnormal"}) == "abnormal"


def test_pick_canonical_furthest():
    """无 abnormal 时取流水线最远列。"""
    from _board_store import pick_canonical_column

    assert pick_canonical_column({"backlog", "planned"}) == "planned"
    assert pick_canonical_column({"backlog", "released"}) == "released"
    assert pick_canonical_column({"planned", "testing", "released"}) == "released"
    assert pick_canonical_column({"backlog", "in_progress"}) == "in_progress"


def test_pick_canonical_empty_returns_none():
    from _board_store import pick_canonical_column

    assert pick_canonical_column(set()) is None
    assert pick_canonical_column(["invalid_col"]) is None
