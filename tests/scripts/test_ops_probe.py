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
    local_resources,
    docs_debt_scan,
    PORT_GROUPS,
)


def test_parse_infra_machines_and_ports():
    data = parse_infra()
    assert "machines" in data
    names = {m["name"] for m in data["machines"]}
    assert "M1" in names
    assert 7777 in data["ports"]
    assert 7775 in data["ports"]
    # deprecated strikethrough port should be skipped
    assert 8084 not in data["ports"]


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
