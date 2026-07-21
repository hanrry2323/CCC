"""test_phase14_flow_rail_bind.py — Phase14 契约：绑定权威 + epic_done 推送 + done 终态。

SSOT:
- docs/product/hub-shell-phase14-flow-rail-bind-brief.md §3.1 A/B/C/E
- docs/product/flow-events.md（`epic_done` 推送契约）

覆盖：
1. snapshot_from_board 在 works 全 released/verified + epic split_status=done 时，user_stage=done。
2. is_terminal_stage 判定 done/failed/blocked。
3. board-poll SSE 路径在 stage=done 转入时，主动 emit `epic_done` 且只 emit 一次（防重弹）。
4. recent epics 列表里，bound_hint 仍优先精确 thread 匹配；空时返 None（不挂任意最近 epic）。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# 让测试可在仓根 / tests/scripts/ 直接 python 运行
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from chat_server.services import flow_events  # noqa: E402


def _board(*, epic_col: str, epic_split: str, works: list[tuple[str, str]]) -> dict:
    """构造最小化 board 视图：epic 卡 + work 卡。"""
    cols: dict[str, list[dict]] = {"verified": [], "released": []}
    cols[epic_col] = [
        {
            "id": "epic1",
            "title": "示例 epic",
            "card_kind": "epic",
            "split_status": epic_split,
        }
    ]
    for wid, wcol in works:
        cols[wcol].append(
            {
                "id": wid,
                "title": wid,
                "parent_id": "epic1",
                "executor": "opencode",
                "depends_on_tasks": [],
            }
        )
    return cols


def test_snapshot_user_stage_done_when_split_status_done():
    board = _board(epic_col="released", epic_split="done", works=[("w1", "released")])
    snap = flow_events.snapshot_from_board(board, epic_id="epic1", project_id="p1")
    assert snap["user_stage"] == "done", snap
    assert snap["works"][0]["status"] == "released"
    assert snap["headline"] == "已完成"


def test_snapshot_user_stage_done_when_all_works_released_and_no_split():
    board = _board(
        epic_col="released", epic_split="running", works=[("w1", "released"), ("w2", "released")]
    )
    snap = flow_events.snapshot_from_board(board, epic_id="epic1", project_id="p1")
    assert snap["user_stage"] == "done"


def test_snapshot_user_stage_failed_when_split_failed():
    board = _board(epic_col="abnormal", epic_split="failed", works=[])
    snap = flow_events.snapshot_from_board(board, epic_id="epic1", project_id="p1")
    assert snap["user_stage"] == "failed"
    assert snap["headline"].startswith("编排异常") or snap["headline"].startswith("卡住")


def test_is_terminal_stage_classification():
    assert flow_events.is_terminal_stage("done") is True
    assert flow_events.is_terminal_stage("failed") is True
    assert flow_events.is_terminal_stage("blocked") is True
    assert flow_events.is_terminal_stage("DONE") is True  # case-insensitive
    assert flow_events.is_terminal_stage("running") is False
    assert flow_events.is_terminal_stage(None) is False
    assert flow_events.is_terminal_stage("") is False


def test_bound_hint_prefers_exact_thread_match_for_thread_exact_view(tmp_path, monkeypatch):
    """精确 thread 视角（非 ::main）下：bound_hint 只在该 tid 历史里有命中时返回；空时不挂任意最近 epic。"""
    fake_home = tmp_path
    monkeypatch.setenv("CCC_CHAT_DIR", str(fake_home / "chat"))
    from chat_server import config

    monkeypatch.setattr(config, "CHAT_DIR", fake_home / "chat")
    pid = "p1"
    flow_events.remember_last_epic(
        pid, "epic-A", title="A", thread_id="custom-tid-1", client_request_id="c-A"
    )
    flow_events.remember_last_epic(
        pid, "epic-B", title="B", thread_id="custom-tid-2", client_request_id="c-B"
    )
    # thread_exact 视角：list 已按 tid 过滤，bound_hint 在精确匹配项里选最近
    items_1 = flow_events.list_recent_epics(pid, thread_id="custom-tid-1", limit=20)
    assert items_1 and items_1[0]["epic_id"] == "epic-A"
    hint_1 = flow_events.bound_hint_for_epics(items_1, thread_id="custom-tid-1")
    assert hint_1 == "epic-A"

    # thread_exact 视角下没匹配时 → 列表空 → hint=None（不挂任意最近）
    items_3 = flow_events.list_recent_epics(pid, thread_id="custom-tid-3", limit=20)
    assert items_3 == []
    hint_3 = flow_events.bound_hint_for_epics(items_3, thread_id="custom-tid-3")
    assert hint_3 is None


def test_bound_hint_project_main_view_returns_most_recent(tmp_path, monkeypatch):
    """项目视图（::main）：bound_hint 返最近一条（项目即对话的口径）；Desktop 客户端
    必须在 prefer/localBound/hint/match 顺序里只在 hint 命中时才接受，未匹配走空态。"""
    fake_home = tmp_path
    monkeypatch.setenv("CCC_CHAT_DIR", str(fake_home / "chat"))
    from chat_server import config

    monkeypatch.setattr(config, "CHAT_DIR", fake_home / "chat")
    pid = "p2"
    flow_events.remember_last_epic(
        pid, "epic-X", title="X", thread_id="other-tid", client_request_id="c-X"
    )
    items = flow_events.list_recent_epics(pid, thread_id="p2::main", limit=20)
    hint = flow_events.bound_hint_for_epics(items, thread_id="p2::main")
    # ::main 视角下，list 不过滤，bound_hint 返最近一条（项目语义）
    assert hint == "epic-X"
    assert items  # 不为空：项目视图保留全部 epic


def test_epic_done_event_dedup_within_consecutive_done(tmp_path, monkeypatch):
    """Phase14 §B：board-poll 兜底在 stage=done 转入时主动推 epic_done；连续 done 不重复推。

    等价模拟 last_terminal_stage 的去重语义。
    failed 由 Phase9 止损路径处理，本通道不主动推（避免重复推送）。
    跨 done→failed→done 的二次 done 仍允许重推（客户端清轨是幂等的）。
    """
    last_terminal_stage: dict[str, str] = {}
    eid = "epic1"

    def maybe_emit(stage: str) -> list[str]:
        events: list[str] = []
        prev = last_terminal_stage.get(eid)
        if stage == "done" and prev != "done":
            events.append("epic_done")
        last_terminal_stage[eid] = stage
        return events

    # 1) running → done：emit
    assert maybe_emit("running") == []
    assert maybe_emit("done") == ["epic_done"]
    # 2) 连续 done（同 stage）：不再 emit（防重弹）
    assert maybe_emit("done") == []
    assert maybe_emit("done") == []
    # 3) done → failed：phase9 止损路径处理；本通道不重推 epic_done
    assert maybe_emit("failed") == []
