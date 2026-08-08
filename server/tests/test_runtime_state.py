"""运行时卡状态 sidecar 测试（主树干净化地基）。"""

from __future__ import annotations

import os
from pathlib import Path

from server.engine.runtime_state import read_card_state, write_card_state, clear_card_state


def test_write_and_read_last_wins(tmp_path: Path) -> None:
    write_card_state(tmp_path, "xy001", state="执行中", retry_count=0)
    write_card_state(tmp_path, "xy001", state="已回写", retry_count=1, reason="超时重试")
    write_card_state(tmp_path, "xy002", state="打回", reason="缺测试")

    rt = read_card_state(tmp_path)
    assert rt["xy001"]["state"] == "已回写"
    assert rt["xy001"]["retry_count"] == 1
    assert rt["xy001"]["reason"] == "超时重试"
    assert rt["xy002"]["state"] == "打回"
    assert rt["xy002"]["reason"] == "缺测试"


def test_clear_card_state_null_invalidation(tmp_path: Path) -> None:
    """测试 clear_card_state 追加 null 失效标记后，read_card_state last-wins 会让该卡无状态。"""
    write_card_state(tmp_path, "xy001", state="已回写", retry_count=1)
    rt1 = read_card_state(tmp_path)
    assert rt1["xy001"]["state"] == "已回写"

    # 清除状态（追加 null 失效记录）
    clear_card_state(tmp_path, "xy001")
    rt2 = read_card_state(tmp_path)
    assert "xy001" not in rt2  # 已被失效，视为不存在


def test_store_ignores_sidecar_for_closed_rejected_todo_cards(tmp_path: Path) -> None:
    """测试 FileBoardStore 派发队列：若磁盘状态为已关闭/打回/待分派，忽略 sidecar 流程态。"""
    from server.engine.store import FileBoardStore
    from server.engine.task import State
    from server.engine.dispatch import ExecutorRegistry

    # 1. 模拟磁盘卡片
    card_dir = tmp_path / "docs" / "dispatch" / "xy"
    card_dir.mkdir(parents=True)
    card_file = card_dir / "xy999-test.md"
    card_file.write_text(
        "# 任务卡 xy999 · 测试\n"
        "> 关联：TEST · 执行体：demo · 验收：Codex · 状态：打回 · 日期：2026-08-08\n"
        "## 目标\nx\n",
        encoding="utf-8"
    )

    # 2. 模拟 sidecar：残留「已回写」
    log_dir = tmp_path / "logs"
    write_card_state(log_dir, "xy999", state="已回写")

    # 3. 构造 FileBoardStore 并获取任务
    reg = ExecutorRegistry(())
    store = FileBoardStore(tmp_path / "docs" / "dispatch", reg, log_dir=log_dir)
    works = store.list_work()
    assert len(works) == 1
    # 磁盘是「打回」，即使 sidecar 说是「已回写」，也应该以磁盘为准判定为 State.REJECTED
    assert works[0].state == State.REJECTED


def test_compose_board_items_ignores_sidecar_for_closed_rejected_todo_cards(tmp_path: Path) -> None:
    """测试 _compose_board_items：若磁盘状态为已关闭/打回/待分派，看板合成忽略 sidecar 流程态。"""
    from server.board.models import BoardItem
    from server.web.server import _compose_board_items

    # 1. 构造 BoardItem（代表磁盘数据）
    items = [
        BoardItem(id="hp009", title="hp009-task", state="打回"),
        BoardItem(id="xy026", title="xy026-task", state="待分派"),
    ]

    # 2. 模拟 sidecar 流程态残留「已回写」
    os.environ["EXECUTOR_LOG_DIR"] = str(tmp_path)
    try:
        write_card_state(tmp_path, "hp009", state="已回写")
        write_card_state(tmp_path, "xy026", state="已回写")

        composed = _compose_board_items(items)
        assert len(composed) == 2
        # 看板合并结果必须显示磁盘真实状态，而不是 sidecar 残留状态
        assert composed[0].state == "打回"
        assert composed[1].state == "待分派"
    finally:
        os.environ.pop("EXECUTOR_LOG_DIR", None)


def test_redispatch_marker(tmp_path: Path) -> None:
    write_card_state(tmp_path, "xy003", state="待分派", retry_count=0, redispatch="2026-08-07T00:00:00Z")
    rt = read_card_state(tmp_path)
    assert rt["xy003"]["redispatch"] == "2026-08-07T00:00:00Z"
    assert rt["xy003"]["retry_count"] == 0


def test_corrupt_line_tolerated(tmp_path: Path) -> None:
    write_card_state(tmp_path, "ok1", state="执行中")
    (tmp_path / "state" / "cards.jsonl").write_text(
        (tmp_path / "state" / "cards.jsonl").read_text(encoding="utf-8")
        + "not-json\n{\"id\": \"ok2\", \"state\": \"已回写\"}\n",
        encoding="utf-8",
    )
    rt = read_card_state(tmp_path)
    assert rt["ok1"]["state"] == "执行中"
    assert rt["ok2"]["state"] == "已回写"


def test_missing_file_returns_empty(tmp_path: Path) -> None:
    assert read_card_state(tmp_path / "nope") == {}
