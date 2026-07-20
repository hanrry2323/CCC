"""Unit tests for scripts/_ops_probe.py"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from _ops_probe import (  # noqa: E402
    parse_infra,
    deploy_targets,
    local_resources,
    docs_debt_scan,
    PORT_GROUPS,
    fetch_router_usage,
)
import _ops_probe as op  # noqa: E402


def test_parse_infra_machines_and_ports():
    data = parse_infra()
    assert "machines" in data
    names = {m["name"] for m in data["machines"]}
    assert "M1" in names
    assert "Mac 2017" in names
    mac = next(m for m in data["machines"] if m["name"] == "Mac 2017")
    assert mac["ip"] == "192.168.3.116"
    assert "Server" in mac["role"] or "CCC" in mac["role"]
    assert 7777 in data["ports"]
    assert 7775 in data["ports"]
    assert 4000 in data["ports"]
    assert 4002 in data["ports"]
    assert data["ports"][7777]["host"] == "192.168.3.116"
    assert data["ports"][7777]["machine"] == "Mac 2017"
    # deprecated strikethrough port should be skipped
    assert 8084 not in data["ports"]


def test_deploy_targets_mac2017_is_ccc_server():
    d = deploy_targets()
    assert "Hub/Engine 在 Mac 2017" in d["dev"]["notes"]
    t = next(x for x in d["targets"] if x["name"] == "Mac 2017")
    assert t["ip"] == "192.168.3.116"
    assert t["role"] == "CCC Server"
    labels = {c["label"] for c in t["checks"]}
    assert "Hub" in labels
    assert "router-anthropic" in labels


def test_local_resources_shape():
    r = local_resources()
    assert "host" in r
    assert "load" in r
    assert "disk" in r


def test_docs_debt_scan_ccc():
    root = str(SCRIPTS.parent)
    out = docs_debt_scan({"CCC": root})
    assert "findings" in out
    assert isinstance(out["findings"], list)


def test_patrol_alerts_list_shape(tmp_path, monkeypatch):
    import _ops_probe as op

    state = tmp_path / "patrol-state.json"
    state.write_text(
        json.dumps(
            [
                {
                    "ts": "2026-07-15T15:08:29+0800",
                    "boards": {"qb": {"bk": 1, "ab": 2}, "CCC": {"ab": 0}},
                }
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(op, "PATROL_STATE", state)
    alerts = op._patrol_alerts()
    assert any("qb" in a["title"] for a in alerts)


def test_port_groups_cover_ccc():
    ccc_ports = dict(PORT_GROUPS)["CCC"]
    assert 7777 in ccc_ports
    assert 7775 in ccc_ports


def test_fetch_router_usage_fail_soft(monkeypatch):
    """Router unreachable → zeros, not raise."""
    import urllib.error

    def boom(*_a, **_k):
        raise urllib.error.URLError("down")

    monkeypatch.setattr(op.urllib.request, "urlopen", boom)
    # bypass cache from other tests
    with op._CACHE_LOCK:
        op._CACHE.clear()
    out = op.fetch_router_usage(use_cache=False)
    assert out["ok"] is False
    assert out["tiers"]["flash"]["requests_today"] == 0
    assert out["tiers"]["code"]["requests_today"] == 0
    assert out["tiers"]["pro"]["requests_today"] == 0
    assert out.get("error")


def test_fetch_router_usage_parses_tiers(monkeypatch):
    class _Resp:
        def read(self):
            return json.dumps(
                {
                    "tiers": {
                        "flash": {"requests_today": 12, "tokens_today": 100},
                        "code": {"requests_today": 3, "tokens_today": 50},
                        "pro": {"requests_today": 0, "tokens_today": 0},
                    },
                    "requested": {
                        "flash": {"requests_today": 15, "tokens_today": 150},
                        "code": {"requests_today": 0, "tokens_today": 0},
                        "pro": {"requests_today": 0, "tokens_today": 0},
                    },
                    "attribution": "served_primary_tier",
                    "total": {"requests_today": 15, "tokens_today": 150},
                }
            ).encode()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(op.urllib.request, "urlopen", lambda *_a, **_k: _Resp())
    with op._CACHE_LOCK:
        op._CACHE.clear()
    out = op.fetch_router_usage(use_cache=False)
    assert out["ok"] is True
    assert out["tiers"]["flash"]["requests_today"] == 12
    assert out["tiers"]["code"]["requests_today"] == 3
    assert out["tiers"]["pro"]["requests_today"] == 0
    assert out["requested"]["flash"]["requests_today"] == 15
    assert out["attribution"] == "served_primary_tier"
    assert out["total"]["requests_today"] == 15
