"""v0.51: Hub rejects orch dispatch; projects mark engine_eligible."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import HTTPException

SCRIPTS = Path(__file__).resolve().parents[1]
ROOT = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT))


def test_assert_dispatchable_rejects_orch(tmp_path, monkeypatch):
    monkeypatch.setenv("CCC_ALLOW_EPHEMERAL_REGISTRY", "1")
    from chat_server.routers import board as board_router
    import _workspace_registry as wr

    orch = tmp_path / "CCC"
    (orch / ".ccc" / "board" / "backlog").mkdir(parents=True)
    monkeypatch.setattr(wr, "orch_home", lambda: orch.resolve())
    monkeypatch.setattr(
        board_router,
        "_workspace_root",
        lambda _ws: orch.resolve(),
    )

    with pytest.raises(HTTPException) as ei:
        board_router._assert_dispatchable_workspace("CCC")
    assert ei.value.status_code == 400
    detail = str(ei.value.detail)
    assert "编排" in detail or "Cursor" in detail or "orch" in detail.lower()


def test_assert_dispatchable_allows_app(tmp_path, monkeypatch):
    monkeypatch.setenv("CCC_ALLOW_EPHEMERAL_REGISTRY", "1")
    from chat_server.routers import board as board_router
    import _workspace_registry as wr

    app = tmp_path / "xianyu"
    (app / ".ccc" / "board" / "backlog").mkdir(parents=True)
    reg = tmp_path / "workspaces.json"
    wr.register_workspace(app, name="xianyu", registry=reg)
    monkeypatch.setattr(wr, "REGISTRY_FILE", reg)
    monkeypatch.setattr(wr, "orch_home", lambda: tmp_path / "not-ccc")
    monkeypatch.setattr(
        board_router,
        "_workspace_root",
        lambda _ws: app.resolve(),
    )
    out = board_router._assert_dispatchable_workspace("xianyu")
    assert out == app.resolve()


def test_default_project_id_prefers_app(monkeypatch):
    from chat_server.routers import projects as proj

    proj.PROJECTS.clear()
    proj.PROJECTS.update(
        {
            "ccc": {
                "name": "CCC（编排）",
                "path": "/x/CCC",
                "role": "orch",
                "engine_eligible": False,
            },
            "xianyu": {
                "name": "xianyu",
                "path": "/x/xianyu",
                "role": "app",
                "engine_eligible": True,
            },
        }
    )
    monkeypatch.setattr(proj, "reload_projects", lambda: None)
    assert proj.default_project_id() == "xianyu"


def test_list_engine_paths_skips_orch(tmp_path, monkeypatch):
    monkeypatch.setenv("CCC_ALLOW_EPHEMERAL_REGISTRY", "1")
    import _workspace_registry as wr

    orch = tmp_path / "CCC"
    (orch / ".ccc" / "board" / "backlog").mkdir(parents=True)
    app = tmp_path / "app1"
    (app / ".ccc" / "board" / "backlog").mkdir(parents=True)
    reg = tmp_path / "workspaces.json"
    monkeypatch.setattr(wr, "orch_home", lambda: orch.resolve())
    wr.register_workspace(orch, name="CCC", role="orch", engine=False, registry=reg)
    wr.register_workspace(app, name="app1", registry=reg)

    paths = wr.list_engine_paths(reg)
    assert app.resolve() in paths
    assert orch.resolve() not in paths

    reg2 = tmp_path / "only-orch.json"
    wr.register_workspace(orch, name="CCC", role="orch", engine=False, registry=reg2)
    assert wr.list_engine_paths(reg2) == []
