"""H-2: work 卡列迁移时 FileBoardStore.move_task 主动 append work_status。"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from _board_store import FileBoardStore  # noqa: E402


def _work_status_lines(log_path: Path, work_id: str) -> list[dict]:
    if not log_path.is_file():
        return []
    out = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if rec.get("event") != "work_status":
            continue
        data = rec.get("data") or {}
        if data.get("work_id") == work_id:
            out.append(rec)
    return out


@pytest.fixture()
def flow_log(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    log = tmp_path / "flow-events.jsonl"
    monkeypatch.setenv("CCC_FLOW_EVENTS_LOG", str(log))
    return log


def _create_work(store: FileBoardStore, wid: str, *, parent: str = "e1") -> None:
    store.create_task(
        {
            "id": wid,
            "title": f"Work {wid}",
            "description": "d",
            "card_kind": "work",
            "parent_id": parent,
            "executor": "opencode",
        },
        column="planned",
    )


def test_work_status_chain_planned_to_released(
    tmp_path: Path, flow_log: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(
        "_product_fanout._project_id_for_workspace",
        lambda _ws: "qb",
    )
    store = FileBoardStore(tmp_path)
    _create_work(store, "w-chain")
    if flow_log.is_file():
        flow_log.write_text("", encoding="utf-8")

    assert store.move_task("w-chain", "planned", "in_progress")
    assert store.move_task("w-chain", "in_progress", "testing")
    assert store.move_task("w-chain", "testing", "verified")
    assert store.move_task("w-chain", "verified", "released")

    lines = _work_status_lines(flow_log, "w-chain")
    statuses = [ln["data"]["status"] for ln in lines]
    assert statuses == ["in_progress", "testing", "verified", "released"]
    for ln, expected_from in zip(
        lines, ["planned", "in_progress", "testing", "verified"]
    ):
        data = ln["data"]
        assert data["from"] == expected_from
        assert data["epic_id"] == "e1"
        assert data.get("project_id") == "qb"
        assert data.get("executor") == "opencode"


def test_work_status_abnormal(
    tmp_path: Path, flow_log: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(
        "_product_fanout._project_id_for_workspace",
        lambda _ws: "hp",
    )
    store = FileBoardStore(tmp_path)
    _create_work(store, "w-abn")
    if flow_log.is_file():
        flow_log.write_text("", encoding="utf-8")

    assert store.move_task("w-abn", "planned", "in_progress")
    assert store.move_task("w-abn", "in_progress", "abnormal")

    lines = _work_status_lines(flow_log, "w-abn")
    assert [ln["data"]["status"] for ln in lines] == ["in_progress", "abnormal"]
    assert lines[-1]["data"]["from"] == "in_progress"


def test_epic_move_does_not_emit_work_status(
    tmp_path: Path, flow_log: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(
        "_product_fanout._project_id_for_workspace",
        lambda _ws: "xianyu",
    )
    store = FileBoardStore(tmp_path)
    store.create_task(
        {"id": "e-skip", "title": "Epic", "card_kind": "epic", "split_status": "pending"},
        column="backlog",
    )
    if flow_log.is_file():
        flow_log.write_text("", encoding="utf-8")

    # epic 不可离开 backlog → move 失败，且不应写 work_status
    assert store.move_task("e-skip", "backlog", "planned") is False
    assert _work_status_lines(flow_log, "e-skip") == []
    assert not any(
        json.loads(ln).get("event") == "work_status"
        for ln in flow_log.read_text(encoding="utf-8").splitlines()
        if ln.strip()
    ) if flow_log.is_file() and flow_log.read_text(encoding="utf-8").strip() else True


def test_backlog_target_does_not_emit(
    tmp_path: Path, flow_log: Path, monkeypatch: pytest.MonkeyPatch
):
    """迁入 backlog 不在 H-2 触发列集合。"""
    monkeypatch.setattr(
        "_product_fanout._project_id_for_workspace",
        lambda _ws: "qb",
    )
    store = FileBoardStore(tmp_path)
    store.create_task(
        {
            "id": "w-back",
            "title": "W",
            "card_kind": "work",
            "parent_id": "e1",
        },
        column="planned",
    )
    assert store.move_task("w-back", "planned", "in_progress")
    if flow_log.is_file():
        flow_log.write_text("", encoding="utf-8")
    assert store.move_task("w-back", "in_progress", "backlog")
    assert _work_status_lines(flow_log, "w-back") == []


def test_append_event_failure_does_not_block_move(
    tmp_path: Path, flow_log: Path, monkeypatch: pytest.MonkeyPatch
):
    store = FileBoardStore(tmp_path)
    _create_work(store, "w-fail")

    with patch(
        "chat_server.services.flow_events.append_event",
        side_effect=RuntimeError("boom"),
    ):
        assert store.move_task("w-fail", "planned", "in_progress") is True
    # 文件已迁入 in_progress
    assert any(t["id"] == "w-fail" for t in store.list_tasks("in_progress"))
