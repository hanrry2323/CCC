"""Desktop board-repair API + service unit tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from _board_store import FileBoardStore  # noqa: E402
from chat_server.app import create_app  # noqa: E402


@pytest.fixture()
def ws(tmp_path):
    root = tmp_path / "app"
    (root / ".ccc" / "board" / "backlog").mkdir(parents=True)
    (root / ".ccc" / "board" / "abnormal").mkdir(parents=True)
    for col in ("planned", "in_progress", "testing", "verified", "released"):
        (root / ".ccc" / "board" / col).mkdir(parents=True, exist_ok=True)
    return root


@pytest.fixture()
def client(tmp_path, monkeypatch, ws):
    chat_dir = tmp_path / "chat"
    chat_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("CCC_CHAT_DIR", str(chat_dir))
    monkeypatch.setenv("CCC_FLOW_EVENTS_LOG", str(tmp_path / "flow.jsonl"))
    monkeypatch.setenv("CCC_BOARD_REPAIR_LOG", str(tmp_path / "repair.jsonl"))
    from chat_server import config as hub_cfg
    from chat_server.routers import desktop as desk
    from chat_server.services import flow_events as fe

    monkeypatch.setattr(hub_cfg, "CHAT_DIR", chat_dir)
    monkeypatch.setattr(fe, "events_log_path", lambda: tmp_path / "flow.jsonl")
    demo = {
        "id": "demo",
        "name": "demo",
        "path": str(ws),
        "engine_eligible": True,
        "role": "app",
    }
    monkeypatch.setattr(desk, "PROJECTS", {"demo": demo})
    monkeypatch.setattr(desk, "PROJECT_TO_WORKSPACE", {"demo": "demo"})
    monkeypatch.setattr(
        desk, "get_project_path", lambda pid: str(ws) if pid == "demo" else ""
    )
    monkeypatch.setattr(desk, "reload_projects", lambda: None)
    app = create_app()
    return TestClient(app)


def _auth():
    return ("ccc", "ccc")


def _seed_failed_epic(ws: Path, tid: str = "epic-fail-1") -> None:
    store = FileBoardStore(ws)
    assert store.create_task(
        {
            "id": tid,
            "title": "Failed epic",
            "card_kind": "epic",
            "split_status": "failed",
            "status": "backlog",
            "goal": "g",
            "acceptance": ["a"],
            "pipeline": "dev",
        },
        column="backlog",
    )


def _seed_abnormal(ws: Path, tid: str = "work-abn-1") -> None:
    store = FileBoardStore(ws)
    assert store.create_task(
        {
            "id": tid,
            "title": "Abnormal work",
            "card_kind": "work",
            "status": "abnormal",
            "goal": "g",
            "acceptance": ["a"],
            "pipeline": "dev",
        },
        column="abnormal",
    )


def test_board_repair_settles_stuck_running_orphan(ws, tmp_path, monkeypatch):
    """running epic + 子卡缺失/无在途 → clear_blockers 沉底。"""
    monkeypatch.setenv("CCC_BOARD_REPAIR_LOG", str(tmp_path / "r.jsonl"))
    monkeypatch.setenv("CCC_FLOW_EVENTS_LOG", str(tmp_path / "f.jsonl"))
    from chat_server import config as hub_cfg
    from chat_server.services import board_repair as br
    from chat_server.services import flow_events as fe

    monkeypatch.setattr(hub_cfg, "CHAT_DIR", tmp_path / "chat")
    (tmp_path / "chat").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(fe, "events_log_path", lambda: tmp_path / "f.jsonl")

    store = FileBoardStore(ws)
    assert store.create_task(
        {
            "id": "epic-orphan-1",
            "title": "Orphan running",
            "card_kind": "epic",
            "split_status": "running",
            "status": "backlog",
            "child_ids": ["epic-orphan-1-w1", "epic-orphan-1-w2"],
            "goal": "g",
            "acceptance": ["a"],
            "pipeline": "dev",
        },
        column="backlog",
    )
    # w1 released, w2 missing → stuck
    assert store.create_task(
        {
            "id": "epic-orphan-1-w1",
            "title": "child1",
            "card_kind": "work",
            "status": "released",
            "parent_id": "epic-orphan-1",
            "goal": "g",
            "acceptance": ["a"],
            "pipeline": "dev",
        },
        column="released",
    )

    st = br.list_blockers(ws)
    assert any(x["id"] == "epic-orphan-1" for x in st["stuck_running_epics"])
    assert st["blocker_count"] >= 1

    out = br.run_repair(
        action="clear_blockers",
        workspace=ws,
        project_id="demo",
        reason="test_stuck",
    )
    assert out["ok"] is True
    assert "epic-orphan-1" in (out.get("settled_stuck") or {}).get("settled", [])
    _, epic = store.find_task("epic-orphan-1")
    assert epic.get("split_status") == "done"
    assert epic.get("ui_hidden") is True
    assert br.list_blockers(ws)["blocker_count"] == 0


def test_board_repair_status_and_clear(client, ws, tmp_path):
    _seed_failed_epic(ws)
    _seed_abnormal(ws)
    from chat_server.services import flow_events as fe

    fe.remember_last_epic("demo", "epic-fail-1", "Failed epic")
    fe.append_event(
        "epic_created",
        {"epic_id": "epic-fail-1", "project_id": "demo", "title": "Failed epic"},
    )

    r = client.post(
        "/api/desktop/board-repair",
        auth=_auth(),
        json={"project_id": "demo", "action": "status"},
    )
    assert r.status_code == 200
    d = r.json()
    assert d["ok"] is True
    assert d["blocker_count"] >= 2

    r2 = client.post(
        "/api/desktop/board-repair",
        auth=_auth(),
        json={"project_id": "demo", "action": "clear_blockers"},
    )
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["ok"] is True
    assert d2.get("ready_hint") is True

    store = FileBoardStore(ws)
    _, failed = store.find_task("epic-fail-1")
    assert failed is not None
    assert failed.get("ui_hidden") is True

    assert fe.load_last_epic("demo") is None
    audit = tmp_path / "repair.jsonl"
    assert audit.is_file()
    assert "clear_blockers" in audit.read_text(encoding="utf-8")


def test_board_repair_purge_flow(client, ws):
    from chat_server.services import flow_events as fe

    fe.remember_last_epic("demo", "e-ghost", "Ghost")
    fe.append_event(
        "fanout",
        {"epic_id": "e-ghost", "project_id": "demo", "works": []},
    )
    r = client.post(
        "/api/desktop/board-repair",
        auth=_auth(),
        json={"project_id": "demo", "action": "purge_flow", "epic_id": "e-ghost"},
    )
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert fe.load_last_epic("demo") is None


def test_board_repair_service_unit(ws, tmp_path, monkeypatch):
    monkeypatch.setenv("CCC_BOARD_REPAIR_LOG", str(tmp_path / "r.jsonl"))
    monkeypatch.setenv("CCC_FLOW_EVENTS_LOG", str(tmp_path / "f.jsonl"))
    from chat_server import config as hub_cfg
    from chat_server.services import board_repair as br
    from chat_server.services import flow_events as fe

    monkeypatch.setattr(hub_cfg, "CHAT_DIR", tmp_path / "chat")
    (tmp_path / "chat").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(fe, "events_log_path", lambda: tmp_path / "f.jsonl")

    _seed_failed_epic(ws, "e1")
    out = br.run_repair(
        action="archive",
        workspace=ws,
        project_id="demo",
        reason="test",
    )
    assert out["ok"] is True
    assert "e1" in out["hidden"]


def test_purge_epic_traces_unit(tmp_path, monkeypatch):
    from chat_server import config as hub_cfg
    from chat_server.services import flow_events as fe

    monkeypatch.setattr(hub_cfg, "CHAT_DIR", tmp_path / "chat")
    (tmp_path / "chat").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(fe, "events_log_path", lambda: tmp_path / "flow.jsonl")
    fe.remember_last_epic("p1", "e9", "T")
    fe.append_event("epic_created", {"epic_id": "e9", "project_id": "p1"})
    fe.append_event("fanout", {"epic_id": "other", "project_id": "p1"})
    out = fe.purge_epic_traces("p1", "e9")
    assert out["ok"] is True
    assert out["cleared_last_epic"] is True
    assert out["removed_flow_events"] >= 1
    assert fe.load_last_epic("p1") is None
    remaining = fe.read_events(project_id="p1", limit=50)
    assert all(
        str((r.get("data") or {}).get("epic_id") or "") != "e9" for r in remaining
    )


def test_hub_ensure_engine_enrichment_fields(monkeypatch):
    """transfer 响应须带 workspace_eligible / block_reason 供 Desktop 人话阻塞。"""
    from chat_server.routers import board as board_mod

    monkeypatch.setattr(
        board_mod,
        "_workspace_root",
        lambda ws: None,
    )

    def fake_ensure(**kwargs):
        return {
            "ok": True,
            "engine_running": False,
            "launch_note": "kickstart_fail:test",
            "mode_after": "enabled",
        }

    import sys
    from types import ModuleType

    fake_wake = ModuleType("_engine_wake")
    fake_wake.ensure_engine_for_task = fake_ensure
    fake_wake.is_engine_running = lambda: False
    fake_reg = ModuleType("_workspace_registry")
    fake_reg.entry_engine_eligible = lambda e: True
    fake_reg.is_orch_path = lambda p: False
    fake_reg.lookup_entry = lambda x: {"name": "demo", "engine": True, "role": "app"}
    monkeypatch.setitem(sys.modules, "_engine_wake", fake_wake)
    monkeypatch.setitem(sys.modules, "_workspace_registry", fake_reg)

    out = board_mod._hub_ensure_engine("demo", "tid-1")
    assert out["ok"] is True
    assert out["workspace_eligible"] is True
    assert out["engine_running"] is False
    assert out.get("block_reason") == "engine_not_running"
    assert "Engine not running" in (out.get("message") or "")
