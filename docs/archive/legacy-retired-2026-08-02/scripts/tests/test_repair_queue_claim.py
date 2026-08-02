"""TDD: repair-queue claim/inject for L3b (Mac2017 Engine → Hub → M1 sidecar)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))


def test_claim_qxo_alias_matches_qx_observer(tmp_path, monkeypatch):
    """Desktop project_id=qxo must claim Engine rows written as qx-observer."""
    from chat_server.services import repair_queue as rq

    q = tmp_path / "repair-queue.jsonl"
    monkeypatch.setenv("CCC_REPAIR_QUEUE", str(q))
    # Legacy Engine enqueue used folder name before alias fix
    q.write_text(
        json.dumps(
            {
                "ts": "2026-07-30T13:00:00+08:00",
                "status": "pending",
                "kind": "epic_optimize",
                "project_id": "qx-observer",
                "epic_id": "v9-s1b",
                "thread_id": "",
                "hint": "hang",
                "buckets": "hang",
                "prompt": "x",
                "key": "qx-observer|v9-s1b|epic_optimize",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    claimed = rq.claim_for_inject(project_id="qxo", limit=2)
    assert len(claimed) == 1
    assert claimed[0]["epic_id"] == "v9-s1b"
    assert claimed[0]["project_id"] == "qxo"
    assert rq.load_pending() == []


def test_claim_for_inject_marks_injected(tmp_path, monkeypatch):
    from chat_server.services import repair_queue as rq

    q = tmp_path / "repair-queue.jsonl"
    monkeypatch.setenv("CCC_REPAIR_QUEUE", str(q))
    r = rq.enqueue_epic_optimize(
        project_id="hp",
        epic_id="epic-hp-1",
        hint="phase unresolvable",
        buckets="phase_unresolvable",
    )
    assert r["ok"] and not r.get("deduped")
    claimed = rq.claim_for_inject(project_id="hp", limit=2)
    assert len(claimed) == 1
    assert claimed[0]["epic_id"] == "epic-hp-1"
    assert claimed[0]["kind"] == "epic_optimize"
    assert "自动投" in (claimed[0].get("prompt") or "")
    # second claim same turn window → empty (already injected)
    claimed2 = rq.claim_for_inject(project_id="hp", limit=2)
    assert claimed2 == []
    pending = rq.load_pending()
    assert pending == []  # injected not pending
    # reinject after force pending restore
    rq.mark_status(r["key"], "pending")
    assert len(rq.load_pending()) == 1


def test_claim_filters_by_project(tmp_path, monkeypatch):
    from chat_server.services import repair_queue as rq

    q = tmp_path / "repair-queue.jsonl"
    monkeypatch.setenv("CCC_REPAIR_QUEUE", str(q))
    rq.enqueue_epic_optimize(project_id="qb", epic_id="e1", hint="h", buckets="hang")
    rq.enqueue_epic_optimize(project_id="hp", epic_id="e2", hint="h", buckets="hang")
    claimed = rq.claim_for_inject(project_id="qb", limit=5)
    assert len(claimed) == 1
    assert claimed[0]["project_id"] == "qb"
    assert len(rq.load_pending()) == 1  # hp still pending


def test_format_inject_block_requires_auto_transfer():
    from chat_server.services import repair_queue as rq

    block = rq.format_inject_block(
        [
            {
                "kind": "epic_optimize",
                "project_id": "medio-0",
                "epic_id": "e1",
                "hint": "acceptance_fail_budget",
                "buckets": "acceptance_fail",
                "prompt": "x",
            }
        ]
    )
    assert "耗尽改大卡" in block or "epic_optimize" in block
    assert "自动投" in block
    assert "禁止只藏卡" in block
    assert "medio-0" in block


def test_board_repair_status_includes_repair_queue(ws_board, tmp_path, monkeypatch):
    from _board_store import FileBoardStore
    from chat_server.services import board_repair as br
    from chat_server.services import repair_queue as rq

    monkeypatch.setenv("CCC_REPAIR_QUEUE", str(tmp_path / "rq.jsonl"))
    monkeypatch.setenv("CCC_BOARD_REPAIR_LOG", str(tmp_path / "r.jsonl"))
    rq.enqueue_epic_optimize(
        project_id="demo",
        epic_id="epic-x",
        hint="hang 耗尽",
        buckets="hang",
    )
    out = br.run_repair(
        action="status",
        workspace=ws_board,
        project_id="demo",
    )
    assert out.get("ok") is True
    rq_info = out.get("repair_queue") or {}
    assert int(rq_info.get("pending_count") or 0) >= 1
    assert any(x.get("epic_id") == "epic-x" for x in (rq_info.get("pending") or []))


def test_hub_claim_endpoint(tmp_path, monkeypatch, ws_board):
    fastapi = pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from chat_server.app import create_app
    from chat_server import config as hub_cfg
    from chat_server.routers import desktop as desk
    from chat_server.services import repair_queue as rq

    chat_dir = tmp_path / "chat"
    chat_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("CCC_CHAT_DIR", str(chat_dir))
    monkeypatch.setenv("CCC_REPAIR_QUEUE", str(tmp_path / "rq.jsonl"))
    monkeypatch.setattr(hub_cfg, "CHAT_DIR", chat_dir)
    demo = {
        "id": "demo",
        "name": "demo",
        "path": str(ws_board),
        "engine_eligible": True,
        "role": "app",
    }
    monkeypatch.setattr(desk, "PROJECTS", {"demo": demo})
    monkeypatch.setattr(desk, "PROJECT_TO_WORKSPACE", {"demo": "demo"})
    monkeypatch.setattr(
        desk, "get_project_path", lambda pid: str(ws_board) if pid == "demo" else ""
    )
    monkeypatch.setattr(desk, "reload_projects", lambda: None)
    rq.enqueue_epic_optimize(
        project_id="demo", epic_id="e1", hint="h", buckets="hang"
    )
    client = TestClient(create_app())
    r = client.post(
        "/api/desktop/repair-queue/claim",
        auth=("ccc", "ccc"),
        json={"project_id": "demo", "limit": 2},
    )
    assert r.status_code == 200
    body = r.json()
    assert body.get("ok") is True
    assert len(body.get("claimed") or []) == 1
    assert "自动投" in (body.get("inject_block") or "")


@pytest.fixture()
def ws_board(tmp_path):
    root = tmp_path / "app"
    for col in (
        "backlog",
        "planned",
        "in_progress",
        "testing",
        "verified",
        "released",
        "abnormal",
    ):
        (root / ".ccc" / "board" / col).mkdir(parents=True, exist_ok=True)
    (root / ".ccc" / "agent-mind").mkdir(parents=True, exist_ok=True)
    return root
