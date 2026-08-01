"""Web Ops 页 relay 域优雅降级测试 — 三分支不白屏。

窗口 A（web 前端修复）新增前端行为测试。对应前端 renderRelay（opsPage.js:280）
的三分支：ok===false（relay_down 琥珀降级）/ ok is None（未拉取）/ ok is True（三档表）。

后端契约：_ops_probe._build_relay_domain 把 fetch_router_usage 输出映射到
domains.relay。这里 monkeypatch ops 路由顶层的 fetch_router_usage（ops.py:15），
断言无论 relay 死活，/api/ops/summary 恒 200（页面不崩 = 不白屏）。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from chat_server.app import create_app  # noqa: E402


def _auth():
    return ("ccc", "ccc")


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


def _stub_relay(client, monkeypatch, payload):
    """把 fetch_router_usage 换成固定 payload（fetch_router_usage(use_cache=...) 调用形态）。"""
    from chat_server.routers import ops as ops_router

    monkeypatch.setattr(ops_router, "fetch_router_usage", lambda **kw: payload)
    return client


def _summary(client):
    r = client.get("/api/ops/summary", auth=_auth())
    assert r.status_code == 200, r.text[:500]
    data = r.json()
    assert "domains" in data
    return data["domains"].get("relay")


def test_relay_down_ok_false(client, monkeypatch):
    """relay 不可达：domains.relay.ok is False + source==relay_down（前端琥珀降级不白屏）。"""
    _stub_relay(
        client,
        monkeypatch,
        {
            "ok": False,
            "source": "relay_down",
            "error": "relay 127.0.0.1:4100 unreachable: <urlopen error timed out>",
        },
    )
    relay = _summary(client)
    assert relay is not None
    assert relay["ok"] is False
    assert relay["source"] == "relay_down"
    assert relay["error"]


def test_relay_not_fetched_ok_none(client, monkeypatch):
    """未拉取：domains.relay.ok is None（前端「relay 状态未知」分支）。"""
    _stub_relay(client, monkeypatch, None)
    relay = _summary(client)
    assert relay is not None
    assert relay["ok"] is None


def test_relay_ok_true_tiers(client, monkeypatch):
    """正常：ok is True 且三档键 flash/Pro/code 存在（前端三档契约表数据源）。"""
    _stub_relay(
        client,
        monkeypatch,
        {
            "ok": True,
            "host": "127.0.0.1",
            "port": 4100,
            "tiers": {
                "flash": {"requests_today": 12, "tokens_today": 3400, "upstreams": 2, "healthy": 2},
                "Pro": {"requests_today": 3, "tokens_today": 900, "upstreams": 1, "healthy": 1},
                "code": {"requests_today": 7, "tokens_today": 2100, "upstreams": 3, "healthy": 2},
            },
            "total": {"upstreams": 6, "healthy": 5, "requests_today": 22, "tokens_today": 6400},
        },
    )
    relay = _summary(client)
    assert relay is not None
    assert relay["ok"] is True
    assert set(relay["tiers"]) == {"flash", "Pro", "code"}
    assert relay["total"]["upstreams"] == 6


def test_ops_daily_reports_shape(client, monkeypatch):
    """契约对齐：后端 daily 只发 reports 键 → summary 透传（前端 dailyItems 数据源）。"""
    import _ops_probe

    monkeypatch.setattr(
        _ops_probe,
        "list_daily_reviews",
        lambda *a, **k: {
            "reports": [
                {
                    "workspace": "demo",
                    "name": "r1",
                    "path": "/x/.ccc/daily/2026-08-01.md",
                    "mtime": "2026-08-01T09:00:00+08:00",
                    "size": 10,
                }
            ]
        },
    )
    r = client.get("/api/ops/summary", auth=_auth())
    assert r.status_code == 200, r.text[:500]
    daily = r.json().get("daily") or {}
    reports = daily.get("reports") or []
    assert any(x.get("workspace") == "demo" for x in reports)
