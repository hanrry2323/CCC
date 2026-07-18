"""Desktop API：Thread + transfer gate + flow snapshot（TestClient）。"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from chat_server.app import create_app  # noqa: E402


@pytest.fixture()
def client(tmp_path, monkeypatch):
    chat_dir = tmp_path / "chat"
    chat_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("CCC_CHAT_DIR", str(chat_dir))
    monkeypatch.setenv("CCC_FLOW_EVENTS_LOG", str(tmp_path / "flow.jsonl"))
    from chat_server import config as hub_cfg
    from chat_server.services import flow_events as fe

    monkeypatch.setattr(hub_cfg, "CHAT_DIR", chat_dir)
    monkeypatch.setattr(fe, "events_log_path", lambda: tmp_path / "flow.jsonl")
    app = create_app()
    return TestClient(app)


def _auth():
    return ("ccc", "ccc")


def test_desktop_config(client):
    r = client.get("/api/desktop/config", auth=_auth())
    assert r.status_code == 200
    d = r.json()
    assert d["threads"] == "unified"
    assert d["transfer"] == "epic_only"
    assert d["dual_source_history"] is False


def test_threads_crud(client, monkeypatch):
    # stub projects
    from chat_server.routers import projects as proj

    monkeypatch.setitem(
        proj.PROJECTS,
        "demo",
        {
            "name": "demo",
            "path": str(Path.cwd()),
            "role": "app",
            "engine_eligible": True,
        },
    )
    monkeypatch.setitem(proj.PROJECT_TO_WORKSPACE, "demo", "demo")
    monkeypatch.setattr(proj, "default_project_id", lambda: "demo")
    monkeypatch.setattr(proj, "get_project_path", lambda pid: str(Path.cwd()))

    r = client.post(
        "/api/desktop/threads",
        auth=_auth(),
        json={"project_id": "demo", "title": "方案"},
    )
    assert r.status_code == 200, r.text
    tid = r.json()["thread_id"]

    r2 = client.get("/api/desktop/threads?project_id=demo", auth=_auth())
    assert r2.status_code == 200
    ids = [t["thread_id"] for t in r2.json()["threads"]]
    assert tid in ids

    r3 = client.get(f"/api/desktop/threads/{tid}?project_id=demo", auth=_auth())
    assert r3.status_code == 200
    assert r3.json()["title"]


def test_transfer_gate_400(client, monkeypatch):
    from chat_server.routers import projects as proj

    monkeypatch.setitem(
        proj.PROJECTS,
        "demo",
        {
            "name": "demo",
            "path": "/tmp",
            "role": "app",
            "engine_eligible": True,
        },
    )
    r = client.post(
        "/api/desktop/transfer",
        auth=_auth(),
        json={"project_id": "demo", "title": "x"},
    )
    assert r.status_code == 400
    body = r.json()
    assert body["ok"] is False
    assert body["errors"]


def test_transfer_creates_epic_only(client, monkeypatch):
    from chat_server.routers import projects as proj
    from chat_server.routers import desktop as desk

    monkeypatch.setitem(
        proj.PROJECTS,
        "demo",
        {
            "name": "demo",
            "path": str(Path.cwd()),
            "role": "app",
            "engine_eligible": True,
        },
    )
    monkeypatch.setitem(proj.PROJECT_TO_WORKSPACE, "demo", "demo")
    monkeypatch.setattr(desk, "_assert_dispatchable_workspace", lambda ws: Path.cwd())
    monkeypatch.setattr(desk, "_hub_ensure_engine", lambda *a, **k: {"ok": True})
    monkeypatch.setattr(
        desk,
        "_write_seed_artifacts",
        lambda *a, **k: {"plan": "x"},
    )
    monkeypatch.setattr(
        desk,
        "_merge_create_payload",
        lambda body, **kw: {"task_id": "epic-desk-1", "engine_wake": {"ok": True}},
    )

    class FakeResp:
        status_code = 200
        body = json.dumps({"task_id": "epic-desk-1", "ok": True}).encode()

    with patch.object(desk, "board_proxy", new=AsyncMock(return_value=FakeResp())):
        r = client.post(
            "/api/desktop/transfer",
            auth=_auth(),
            json={
                "project_id": "demo",
                "title": "加标记",
                "goal": "README 加一行",
                "acceptance": ["grep MARK"],
                "pipeline": "dev",
                "feasibility": "ok",
                "executor_intent": "opencode",
                "plan_md": "# P\n\n## 验收\n- x\n",
            },
        )
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["ok"] is True
    assert d["epic_id"] == "epic-desk-1"
    assert d["column"] == "backlog"


def test_flow_snapshot_empty(client, monkeypatch):
    from chat_server.routers import projects as proj

    monkeypatch.setitem(
        proj.PROJECTS,
        "demo",
        {"name": "demo", "path": "/tmp", "role": "app", "engine_eligible": True},
    )
    monkeypatch.setitem(proj.PROJECT_TO_WORKSPACE, "demo", "demo")
    r = client.get(
        "/api/desktop/flow/snapshot?project_id=demo",
        auth=_auth(),
    )
    assert r.status_code == 200
    d = r.json()
    assert d.get("empty") is True
