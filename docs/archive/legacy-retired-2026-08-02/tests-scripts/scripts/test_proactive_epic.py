"""F4-3: POST /api/desktop/proactive-epic — 投递 + 幂等 + 鉴权。"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture()
def client(tmp_path, monkeypatch):
    chat_dir = tmp_path / "chat"
    chat_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("CCC_CHAT_DIR", str(chat_dir))
    monkeypatch.setenv("CCC_CHAT_USER", "ccc")
    monkeypatch.setenv("CCC_CHAT_PASS", "ccc")
    monkeypatch.setenv("CCC_FLOW_EVENTS_LOG", str(tmp_path / "flow.jsonl"))
    from chat_server import config as hub_cfg
    from chat_server.services import flow_events as fe

    monkeypatch.setattr(hub_cfg, "CHAT_DIR", chat_dir)
    monkeypatch.setattr(hub_cfg, "AUTH_USER", "ccc")
    monkeypatch.setattr(hub_cfg, "AUTH_PASS", "ccc")
    monkeypatch.setattr(fe, "events_log_path", lambda: tmp_path / "flow.jsonl")
    from chat_server.app import create_app

    return TestClient(create_app())


def _auth():
    return ("ccc", "ccc")


def _stub_project(monkeypatch):
    from chat_server.routers import desktop as desk
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
    monkeypatch.setattr(desk, "_assert_dispatchable_workspace", lambda ws: Path.cwd())
    calls = {"wake": 0}

    def _wake(*_a, **_k):
        calls["wake"] += 1
        return {"ok": True}

    monkeypatch.setattr(desk, "_hub_ensure_engine", _wake)
    monkeypatch.setattr(desk, "_write_seed_artifacts", lambda *a, **k: {"plan": "x"})
    monkeypatch.setattr(
        desk,
        "_merge_create_payload",
        lambda body, **kw: {"task_id": "epic-proactive-1"},
    )
    return desk, calls


def test_proactive_requires_auth(client: TestClient):
    r = client.post(
        "/api/desktop/proactive-epic",
        json={
            "project_id": "demo",
            "source": "ci",
            "title": "CI 失败",
            "goal": "修一下",
        },
    )
    assert r.status_code == 401


def test_proactive_queues_epic_without_wake(client: TestClient, monkeypatch):
    desk, calls = _stub_project(monkeypatch)

    class FakeResp:
        status_code = 200
        body = json.dumps({"task_id": "epic-proactive-1", "ok": True}).encode()

    with patch.object(desk, "board_proxy", new=AsyncMock(return_value=FakeResp())):
        r = client.post(
            "/api/desktop/proactive-epic",
            auth=_auth(),
            json={
                "project_id": "demo",
                "source": "ci",
                "title": "CI 失败：pytest",
                "goal": "修复 pytest 红灯",
                "payload": {"run_id": "99", "job": "pytest"},
            },
        )
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["ok"] is True
    assert d["queued"] is True
    assert d["epic_id"] == "epic-proactive-1"
    assert d.get("idempotent_replay") is False
    assert calls["wake"] == 0


def test_proactive_idempotent(client: TestClient, monkeypatch):
    desk, _calls = _stub_project(monkeypatch)
    create_calls = {"n": 0}

    class FakeResp:
        status_code = 200
        body = json.dumps({"task_id": "epic-proactive-1", "ok": True}).encode()

    async def _proxy(*_a, **_k):
        create_calls["n"] += 1
        return FakeResp()

    body = {
        "project_id": "demo",
        "source": "ci",
        "title": "CI 失败：pytest",
        "goal": "修复 pytest 红灯",
        "payload": {"run_id": "idem-1"},
    }
    with patch.object(desk, "board_proxy", new=_proxy):
        r1 = client.post("/api/desktop/proactive-epic", auth=_auth(), json=body)
        r2 = client.post("/api/desktop/proactive-epic", auth=_auth(), json=body)
    assert r1.status_code == 200 and r2.status_code == 200
    d1, d2 = r1.json(), r2.json()
    assert d1["epic_id"] == d2["epic_id"]
    assert d2.get("idempotent_replay") is True
    assert d2.get("queued") is True
    assert create_calls["n"] == 1


def test_proactive_invalid_source(client: TestClient, monkeypatch):
    _stub_project(monkeypatch)
    r = client.post(
        "/api/desktop/proactive-epic",
        auth=_auth(),
        json={
            "project_id": "demo",
            "source": "webhook",
            "title": "x",
            "goal": "y",
        },
    )
    assert r.status_code == 400
    assert r.json()["ok"] is False


def test_ingest_script_dry_run():
    script = SCRIPTS / "ccc-ingest-ci-failure.sh"
    assert script.is_file()
    proc = subprocess.run(
        ["bash", "-n", str(script)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    env = os.environ.copy()
    env["CCC_PROACTIVE_DRY_RUN"] = "1"
    env["CCC_PROJECT_ID"] = "demo"
    proc2 = subprocess.run(
        ["bash", str(script)],
        cwd=str(ROOT),
        input='{"title":"CI 失败","goal":"修","payload":{"run_id":"1"}}\n',
        capture_output=True,
        text=True,
        env=env,
        timeout=15,
        check=False,
    )
    assert proc2.returncode == 0, proc2.stderr + proc2.stdout
    data = json.loads(proc2.stdout.strip())
    assert data["project_id"] == "demo"
    assert data["source"] == "ci"
    assert data["payload"]["run_id"] == "1"
