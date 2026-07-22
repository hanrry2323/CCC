"""Tests for ccc-daily-diff-review apply whitelist + orch gate."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS))


def _load_daily():
    path = SCRIPTS / "ccc-daily-diff-review.py"
    spec = importlib.util.spec_from_file_location("ccc_daily_diff_review", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def daily():
    return _load_daily()


def test_maybe_spawn_skips_without_apply(daily, tmp_path):
    out = daily.maybe_spawn(
        tmp_path, {"title": "x", "description": "y"}, "C", apply=False
    )
    assert out is None


def test_maybe_spawn_skips_decision_i(daily, tmp_path):
    out = daily.maybe_spawn(
        tmp_path, {"title": "x", "description": "y"}, "I", apply=True
    )
    assert out and out.get("skipped")
    assert "invent" in (out.get("reason") or "").lower()


def test_maybe_spawn_skips_decision_d(daily, tmp_path):
    out = daily.maybe_spawn(
        tmp_path, {"title": "x", "description": "y"}, "D", apply=True
    )
    assert out and out.get("skipped")


def test_maybe_spawn_rejects_orch(daily, tmp_path, monkeypatch):
    import _workspace_registry as wr

    orch = wr.orch_home()
    reg = tmp_path / "workspaces.json"
    reg.write_text(
        json.dumps(
            {
                "schema_version": "1.1",
                "workspaces": [
                    {"name": "CCC", "path": str(orch), "role": "orch", "engine": False}
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(wr, "REGISTRY_FILE", reg)
    out = daily.maybe_spawn(
        orch, {"title": "fix", "description": "d"}, "C", apply=True
    )
    assert out and out.get("skipped")
    reason = (out.get("reason") or "").lower()
    assert (
        out.get("code") == "ops-ammo-orch-forbidden"
        or "forbidden" in reason
        or "orch" in reason
    )


def test_maybe_spawn_creates_on_eligible(daily, tmp_path, monkeypatch):
    import _workspace_registry as wr
    import _engine_wake as ew

    app = tmp_path / "rev-app"
    (app / ".ccc" / "board" / "backlog").mkdir(parents=True)
    reg = tmp_path / "workspaces.json"
    reg.write_text(
        json.dumps(
            {
                "schema_version": "1.1",
                "workspaces": [
                    {
                        "name": "rev-app",
                        "path": str(app),
                        "role": "app",
                        "engine": True,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(wr, "REGISTRY_FILE", reg)
    monkeypatch.setattr(ew, "ensure_engine_for_task", lambda **k: {"ok": True})

    out = daily.maybe_spawn(
        app, {"title": "daily-fix: x", "description": "stat"}, "C", apply=True
    )
    assert out and out.get("created") is True
    assert out.get("workspace") == "rev-app"
