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


def test_transfer_preserves_non_main_thread_id(client, monkeypatch):
    """同对话多任务：真实 thread_id 必须落盘，禁止强改成 ::main。"""
    from chat_server.routers import projects as proj
    from chat_server.routers import desktop as desk
    from chat_server.services import flow_events as fe

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
    monkeypatch.setattr(desk, "_write_seed_artifacts", lambda *a, **k: {"plan": "x"})
    monkeypatch.setattr(
        desk,
        "_merge_create_payload",
        lambda body, **kw: {"task_id": "epic-t2", "engine_wake": {"ok": True}},
    )

    class FakeResp:
        status_code = 200
        body = json.dumps({"task_id": "epic-t2", "ok": True}).encode()

    with patch.object(desk, "board_proxy", new=AsyncMock(return_value=FakeResp())):
        r = client.post(
            "/api/desktop/transfer",
            auth=_auth(),
            json={
                "project_id": "demo",
                "thread_id": "demo::494276D0",
                "title": "第二笔",
                "goal": "再加一行",
                "acceptance": ["grep TWO"],
                "pipeline": "dev",
                "feasibility": "ok",
                "executor_intent": "opencode",
                "plan_md": "# P\n\n## 验收\n- x\n",
            },
        )
    assert r.status_code == 200, r.text
    last = fe.load_last_epic("demo")
    assert last is not None
    assert last["epic_id"] == "epic-t2"
    assert last["thread_id"] == "demo::494276D0"
    items = fe.list_recent_epics("demo", thread_id="demo::494276D0", limit=10)
    assert [e["epic_id"] for e in items] == ["epic-t2"]


def test_transfer_same_thread_queues_two_epics(client, monkeypatch):
    """同一 thread 连续两笔 transfer：两张 epic 均绑定该 thread，最新在前。"""
    from chat_server.routers import projects as proj
    from chat_server.routers import desktop as desk
    from chat_server.services import flow_events as fe

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
    monkeypatch.setattr(desk, "_write_seed_artifacts", lambda *a, **k: {"plan": "x"})

    seq = {"n": 0}

    def _merge(body, **kw):
        seq["n"] += 1
        return {"task_id": f"epic-q{seq['n']}", "engine_wake": {"ok": True}}

    monkeypatch.setattr(desk, "_merge_create_payload", _merge)

    class FakeResp:
        status_code = 200

        @property
        def body(self):
            return json.dumps({"task_id": f"epic-q{seq['n']}", "ok": True}).encode()

    payload_base = {
        "project_id": "demo",
        "thread_id": "demo::AAAA",
        "goal": "g",
        "acceptance": ["a"],
        "pipeline": "dev",
        "feasibility": "ok",
        "executor_intent": "opencode",
        "plan_md": "# P\n\n## 验收\n- x\n",
    }
    with patch.object(desk, "board_proxy", new=AsyncMock(return_value=FakeResp())):
        r1 = client.post(
            "/api/desktop/transfer",
            auth=_auth(),
            json={**payload_base, "title": "第一笔"},
        )
        r2 = client.post(
            "/api/desktop/transfer",
            auth=_auth(),
            json={**payload_base, "title": "第二笔"},
        )
    assert r1.status_code == 200 and r2.status_code == 200
    items = fe.list_recent_epics("demo", thread_id="demo::AAAA", limit=10)
    assert [e["epic_id"] for e in items] == ["epic-q2", "epic-q1"]
    assert all(e.get("thread_id") == "demo::AAAA" for e in items)
    last = fe.load_last_epic("demo")
    assert last["epic_id"] == "epic-q2"
    assert last["thread_id"] == "demo::AAAA"


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


def test_flow_epics_history(client, monkeypatch):
    from chat_server.routers import projects as proj
    from chat_server.services import flow_events as fe

    monkeypatch.setitem(
        proj.PROJECTS,
        "demo",
        {"name": "demo", "path": "/tmp", "role": "app", "engine_eligible": True},
    )
    fe.remember_last_epic("demo", "e-hist-1", "First", thread_id="t1")
    fe.remember_last_epic("demo", "e-hist-2", "Second", thread_id="t2")
    r = client.get("/api/desktop/flow/epics?project_id=demo", auth=_auth())
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["ok"] is True
    ids = [e["epic_id"] for e in d["epics"]]
    assert ids[0] == "e-hist-2"
    assert "e-hist-1" in ids

    r2 = client.get(
        "/api/desktop/flow/epics?project_id=demo&thread_id=t1",
        auth=_auth(),
    )
    assert r2.status_code == 200
    ids2 = [e["epic_id"] for e in r2.json()["epics"]]
    assert ids2 == ["e-hist-1"]


def test_flow_snapshot_reads_columns(client, monkeypatch):
    from chat_server.routers import projects as proj
    from chat_server.routers import desktop as desk
    from chat_server.services import flow_events as fe

    monkeypatch.setitem(
        proj.PROJECTS,
        "demo",
        {"name": "demo", "path": "/tmp", "role": "app", "engine_eligible": True},
    )
    monkeypatch.setitem(proj.PROJECT_TO_WORKSPACE, "demo", "demo")
    fe.remember_last_epic("demo", "e1", "E")

    class FakeResp:
        status_code = 200
        body = json.dumps(
            {
                "columns": {
                    "backlog": [
                        {
                            "id": "e1",
                            "title": "E",
                            "card_kind": "epic",
                            "split_status": "planned",
                        }
                    ],
                    "planned": [
                        {
                            "id": "e1-w1",
                            "title": "W",
                            "parent_id": "e1",
                            "executor": "python",
                            "depends_on_tasks": [],
                        }
                    ],
                }
            }
        ).encode()

    with patch.object(desk, "board_proxy", new=AsyncMock(return_value=FakeResp())):
        r = client.get(
            "/api/desktop/flow/snapshot?project_id=demo&epic_id=e1",
            auth=_auth(),
        )
    assert r.status_code == 200, r.text
    d = r.json()
    assert d.get("empty") is False
    assert d["epic"]["id"] == "e1"
    assert d["works"][0]["executor"] == "python"
