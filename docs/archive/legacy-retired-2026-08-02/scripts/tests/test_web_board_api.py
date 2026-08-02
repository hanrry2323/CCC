"""Web 看板 API 契约测试 — SPA 消费的 Hub 端点（29 卡基准）。

窗口 A（web 前端修复）新增前端行为测试，落在现有 pytest 基建（scripts/tests/）。

两类覆盖：
1. Hub 端点契约（渲染/汇总/详情/移卡/配置）：mock Hub→Board 的 board_proxy，
   断言 SPA（boardPage.js）实际读取的 JSON 形状 —— 对应「渲染、详情、汇总」验收。
2. 真行为（29 卡基准）：FileBoardStore 铺 29 卡 → move_task（←/→ 移卡后端等价）
   → 事件落盘（详情弹窗数据源）—— 复用 tests/scripts/test_board_store.py 模式。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

fastapi = pytest.importorskip("fastapi")
from fastapi import Response  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from chat_server.app import create_app  # noqa: E402

# 29 卡基准：4 epic（backlog）+ 25 work（流列）
EPICS = 4
FLOW_COUNTS = {
    "planned": 6,
    "in_progress": 4,
    "testing": 4,
    "verified": 4,
    "released": 4,
    "abnormal": 3,
}
TOTAL = EPICS + sum(FLOW_COUNTS.values())  # == 29


def _auth():
    return ("ccc", "ccc")


def _ts() -> str:
    return "2026-08-01T09:00:00+08:00"


def _epic(i: int) -> dict:
    return {
        "id": f"ep{i}",
        "title": f"大卡 {i}",
        "card_kind": "epic",
        "status": "backlog",
        "_column": "backlog",
        "split_status": "planned",
        "description": f"大卡描述 {i}",
        "created_at": _ts(),
        "updated_at": _ts(),
    }


def _work(col: str, n: int) -> dict:
    return {
        "id": f"t-{col}-{n}",
        "title": f"{col} 卡 {n}",
        "card_kind": "work",
        "status": col,
        "_column": col,
        "description": f"desc {col}-{n}",
        "created_at": _ts(),
        "updated_at": _ts(),
    }


def board_fixture() -> dict:
    """Board API /api/board 输出契约（SPA boardPage 读 columns）。"""
    columns = {"backlog": [_epic(i) for i in range(1, EPICS + 1)]}
    for col, n in FLOW_COUNTS.items():
        columns[col] = [_work(col, i) for i in range(1, n + 1)]
    return {"workspace": "demo", "columns": columns}


class _FakeBoardProxy:
    """模拟 Hub→Board(:7775) 代理：记录调用并按 path 返回契约 payload。"""

    def __init__(self, payloads: dict):
        self.payloads = payloads
        self.calls: list[dict] = []

    async def __call__(self, method, path, params=None, json_body=None):
        self.calls.append(
            {"method": method, "path": path, "params": params, "json_body": json_body}
        )
        body = self.payloads.get(path)
        if body is None:
            if path.endswith("/events") and path.startswith("/api/tasks/"):
                tid = path.split("/")[-2]
                body = {
                    "id": tid,
                    "title": f"任务 {tid}",
                    "description": "详情描述",
                    "_column": "planned",
                    "events": [
                        {
                            "event": "move",
                            "task_id": tid,
                            "from": "planned",
                            "to": "in_progress",
                            "timestamp": _ts(),
                        }
                    ],
                }
            else:
                body = {"ok": True}
        if callable(body):
            body = body(method, path, params, json_body)
        return Response(
            content=json.dumps(body).encode("utf-8"),
            status_code=200,
            media_type="application/json",
        )


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


@pytest.fixture()
def board_api(client, monkeypatch):
    """把 Hub board 路由的 board_proxy 换成 fake，返回 fake 供断言调用记录。"""
    from chat_server.routers import board as board_router

    payloads = {
        "/api/board": board_fixture(),
        "/api/config": {
            "workspaces": ["demo", "other"],
            "default_workspace": "demo",
        },
        "/api/tasks/move": {"ok": True},
    }
    fake = _FakeBoardProxy(payloads)
    monkeypatch.setattr(board_router, "board_proxy", fake)
    return fake


# ── Hub 端点契约 ────────────────────────────────────────────────


def test_board_render_29_cards(client, board_api):
    """渲染数据契约：#/board 读 /api/board → columns，各列卡数与 29 卡基准一致。"""
    r = client.get("/api/board", params={"workspace": "demo"}, auth=_auth())
    assert r.status_code == 200, r.text
    cols = r.json()["columns"]
    assert len(cols["backlog"]) == EPICS
    got = {c: len(cols[c]) for c in FLOW_COUNTS}
    assert got == FLOW_COUNTS
    assert sum(len(v) for v in cols.values()) == TOTAL


def test_board_summaries_aggregate(client, board_api):
    """汇总契约：/api/board/summaries 一次聚合多 workspace。"""
    r = client.get(
        "/api/board/summaries", params={"workspaces": "demo,other"}, auth=_auth()
    )
    assert r.status_code == 200, r.text
    sums = r.json()["summaries"]
    assert set(sums) == {"demo", "other"}
    assert sums["demo"]["columns"]["backlog"]


def test_board_task_events(client, board_api):
    """详情契约：/api/tasks/{id}/events → events[] 含 from/to/timestamp（SPA showDetail 读）。"""
    r = client.get(
        "/api/tasks/t-planned-1/events", params={"workspace": "demo"}, auth=_auth()
    )
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["id"] == "t-planned-1"
    assert d["events"] and d["events"][0]["from"] == "planned"
    assert d["events"][0]["to"] == "in_progress"
    assert d["events"][0]["timestamp"]


def test_board_move_passthrough(client, board_api):
    """移卡链路：←/→ 按钮 POST /api/tasks/move → 透传 workspace 到 Board API。"""
    r = client.post(
        "/api/tasks/move",
        json={
            "id": "t-planned-1",
            "from": "planned",
            "to": "in_progress",
            "workspace": "demo",
        },
        auth=_auth(),
    )
    assert r.status_code == 200, r.text
    call = board_api.calls[-1]
    assert call["method"] == "POST"
    assert call["path"] == "/api/tasks/move"
    assert call["json_body"]["workspace"] == "demo"
    assert call["json_body"]["to"] == "in_progress"


def test_board_config(client, board_api):
    """配置契约：/api/config（SPA 工作区按钮数据源）。"""
    r = client.get("/api/config", auth=_auth())
    assert r.status_code == 200, r.text
    assert "demo" in r.json()["workspaces"]


# ── 真行为（29 卡基准 · 移卡 + 事件落盘）─────────────────────────


def _make_store(root: Path):
    from _board_store import COLUMNS, FileBoardStore

    board = root / ".ccc" / "board"
    board.mkdir(parents=True)
    for col in COLUMNS:
        (board / col).mkdir(parents=True, exist_ok=True)
    (board / "events").mkdir(parents=True, exist_ok=True)
    return FileBoardStore(root)


def test_board_store_29_cards_move_events(tmp_path):
    """真行为背书：铺 29 卡 → move_task（←/→ 后端等价）→ 事件落盘（详情数据源）。"""
    from _board_store import now_iso

    store = _make_store(tmp_path)
    ts = now_iso()
    for i in range(1, EPICS + 1):
        assert store.create_task(
            {"id": f"ep{i}", "title": f"大卡{i}", "card_kind": "epic", "created_at": ts},
            column="backlog",
        )
    for col, n in FLOW_COUNTS.items():
        for j in range(1, n + 1):
            ok = store.create_task(
                {
                    "id": f"t-{col}-{j}",
                    "title": f"{col} {j}",
                    "card_kind": "work",
                    "status": col,
                    "created_at": ts,
                },
                column=col,
            )
            assert ok, f"create {col}-{j} failed"

    # 渲染/汇总：各列计数
    assert len(store.list_tasks("backlog")) == EPICS
    for col, n in FLOW_COUNTS.items():
        assert len(store.list_tasks(col)) == n, f"{col} count"

    # 移卡：planned → in_progress（←/→ 按钮后端）
    assert store.move_task("t-planned-1", "planned", "in_progress")
    assert len(store.list_tasks("in_progress")) == FLOW_COUNTS["in_progress"] + 1
    assert len(store.list_tasks("planned")) == FLOW_COUNTS["planned"] - 1

    # 详情数据源：事件落盘 from/to/timestamp
    ev_file = tmp_path / ".ccc" / "board" / "events" / "t-planned-1.events.jsonl"
    lines = ev_file.read_text(encoding="utf-8").strip().splitlines()
    assert lines
    ev = json.loads(lines[-1])
    assert ev["from"] == "planned"
    assert ev["to"] == "in_progress"
    assert ev["timestamp"]


# ── A2 扩展：筛选透传 / 排序 / 拖拽稳定性 / epic 聚合数据源 ─────────────


def test_board_include_hidden_passthrough(client, board_api):
    """筛选无回归：显示已隐藏 → /api/board?include_hidden=1 透传 Board API。"""
    r = client.get(
        "/api/board",
        params={"workspace": "demo", "include_hidden": "1"},
        auth=_auth(),
    )
    assert r.status_code == 200, r.text
    call = board_api.calls[-1]
    assert call["params"].get("workspace") == "demo"
    assert call["params"].get("include_hidden") == "1"


def test_board_store_planned_sorted_by_created_at_id(tmp_path):
    """排序无回归：planned 流列按 (created_at, id) 升序（服务端排序，前端不重排）。"""
    store = _make_store(tmp_path)
    for i, cid in enumerate(["b", "a", "c"]):
        ts = f"2026-08-01T10:0{i}:00+08:00"
        ok = store.create_task(
            {
                "id": cid,
                "title": cid,
                "card_kind": "work",
                "status": "planned",
                "created_at": ts,
                "updated_at": ts,
            },
            column="planned",
        )
        assert ok, f"create {cid}"
    ids = [t["id"] for t in store.list_tasks("planned")]
    assert ids == ["b", "a", "c"], f"按 created_at 升序: {ids}"


def test_board_store_invalid_move_returns_false(tmp_path):
    """拖拽稳定性：白名单外迁移（in_progress→released 跳步）返回 False 不炸。"""
    from _board_store import now_iso

    store = _make_store(tmp_path)
    ts = now_iso()
    assert store.create_task(
        {"id": "t1", "title": "t", "card_kind": "work", "status": "in_progress", "created_at": ts},
        column="in_progress",
    )
    # 需经 testing→verified，跳步被 COLUMN_TRANSITIONS 拒绝，非崩溃
    assert store.move_task("t1", "in_progress", "released") is False


def test_board_store_epic_progress_source(tmp_path):
    """epic 聚合视图数据源：子卡一路到 released 后 released 列含它（前端进度计数）。"""
    from _board_store import now_iso

    store = _make_store(tmp_path)
    ts = now_iso()
    assert store.create_task(
        {"id": "ep1", "title": "大卡", "card_kind": "epic", "child_ids": ["w1", "w2"], "created_at": ts},
        column="backlog",
    )
    for wid in ("w1", "w2"):
        assert store.create_task(
            {"id": wid, "title": wid, "card_kind": "work", "status": "planned", "created_at": ts},
            column="planned",
        )
    for f, t in (
        ("planned", "in_progress"),
        ("in_progress", "testing"),
        ("testing", "verified"),
        ("verified", "released"),
    ):
        assert store.move_task("w1", f, t), f"{f}→{t}"
    released = [x["id"] for x in store.list_tasks("released")]
    assert "w1" in released
    assert "w2" not in released
