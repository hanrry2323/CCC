"""H-1: epic → done 时 Engine 主动 append_event(epic_done)，不依赖 SSE。"""

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
from _product_fanout import apply_fanout, refresh_epic_lifecycle  # noqa: E402


def _child(cid: str, scope: str = "x.py"):
    return {
        "id": cid,
        "title": f"Title {cid}",
        "description": "d",
        "plan_md": f"# {cid}\n\n## 验收\n- pytest -q {scope}\n",
        "phases": [
            {
                "phase": 1,
                "status": "pending",
                "description": "impl",
                "scope": [scope],
                "subtasks": {"1.1": "pending"},
                "timeout": 600,
                "commit": None,
                "notes": "",
            }
        ],
    }


def _release_child(store: FileBoardStore, wid: str) -> None:
    store.move_task(wid, "planned", "in_progress")
    store.move_task(wid, "in_progress", "testing")
    store.move_task(wid, "testing", "verified")
    store.move_task(wid, "verified", "released")


def _epic_done_lines(log_path: Path, epic_id: str) -> list[dict]:
    if not log_path.is_file():
        return []
    out = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if rec.get("event") != "epic_done":
            continue
        data = rec.get("data") or {}
        if data.get("epic_id") == epic_id:
            out.append(rec)
    return out


@pytest.fixture()
def flow_log(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    log = tmp_path / "flow-events.jsonl"
    monkeypatch.setenv("CCC_FLOW_EVENTS_LOG", str(log))
    # chat_server.services.flow_events caches path via env each call — ok
    return log


def test_epic_done_appended_when_all_children_released(
    tmp_path: Path, flow_log: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(
        "_product_fanout._project_id_for_workspace",
        lambda _ws: "xianyu",
    )
    store = FileBoardStore(tmp_path)
    store.create_task({"id": "e-done", "title": "E"}, column="backlog")
    apply_fanout(
        store,
        store.list_tasks("backlog")[0],
        children_raw=[_child("e-done-w1")],
    )
    # fanout also writes events — clear so we only assert done transition
    if flow_log.is_file():
        flow_log.write_text("", encoding="utf-8")

    _release_child(store, "e-done-w1")
    assert refresh_epic_lifecycle(store, "e-done") == "done"

    lines = _epic_done_lines(flow_log, "e-done")
    assert len(lines) == 1
    data = lines[0]["data"]
    assert data["split_status"] == "done"
    assert data["epic_id"] == "e-done"
    assert data.get("project_id") == "xianyu"


def test_epic_done_written_once_on_repeat_refresh(
    tmp_path: Path, flow_log: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(
        "_product_fanout._project_id_for_workspace",
        lambda _ws: "qb",
    )
    store = FileBoardStore(tmp_path)
    store.create_task({"id": "e-once", "title": "E"}, column="backlog")
    apply_fanout(
        store,
        store.list_tasks("backlog")[0],
        children_raw=[_child("e-once-w1")],
    )
    if flow_log.is_file():
        flow_log.write_text("", encoding="utf-8")

    _release_child(store, "e-once-w1")
    assert refresh_epic_lifecycle(store, "e-once") == "done"
    assert refresh_epic_lifecycle(store, "e-once") == "done"
    assert refresh_epic_lifecycle(store, "e-once") == "done"

    assert len(_epic_done_lines(flow_log, "e-once")) == 1


def test_append_event_failure_does_not_block_lifecycle(
    tmp_path: Path, flow_log: Path, monkeypatch: pytest.MonkeyPatch
):
    store = FileBoardStore(tmp_path)
    store.create_task({"id": "e-fail", "title": "E"}, column="backlog")
    apply_fanout(
        store,
        store.list_tasks("backlog")[0],
        children_raw=[_child("e-fail-w1")],
    )
    _release_child(store, "e-fail-w1")

    with patch(
        "chat_server.services.flow_events.append_event",
        side_effect=RuntimeError("boom"),
    ):
        assert refresh_epic_lifecycle(store, "e-fail") == "done"

    _, epic = store.find_task("e-fail")
    assert epic["split_status"] == "done"
    assert epic.get("ui_hidden") is True
