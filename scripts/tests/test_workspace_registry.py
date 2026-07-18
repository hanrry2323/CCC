"""v0.42.1: workspace registry + ensure_engine registers path"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))


def _mk_board_ws(tmp_path: Path, name: str = "proj") -> Path:
    root = tmp_path / name
    (root / ".ccc" / "board" / "backlog").mkdir(parents=True)
    return root


def test_register_workspace_idempotent(tmp_path, monkeypatch):
    monkeypatch.setenv("CCC_ALLOW_EPHEMERAL_REGISTRY", "1")
    from _workspace_registry import register_workspace, list_registered_paths

    root = _mk_board_ws(tmp_path, "qb")
    reg = tmp_path / ".ccc" / "workspaces.json"
    r1 = register_workspace(root, name="qb", registry=reg)
    assert r1["ok"] and r1["added"] is True
    r2 = register_workspace(root, name="qb", registry=reg)
    assert r2["ok"] and r2["added"] is False
    paths = list_registered_paths(reg)
    assert paths == [root.resolve()]
    data = json.loads(reg.read_text())
    assert len(data["workspaces"]) == 1


def test_register_rejects_no_board(tmp_path):
    from _workspace_registry import register_workspace

    bare = tmp_path / "bare"
    bare.mkdir()
    reg = tmp_path / "workspaces.json"
    out = register_workspace(bare, registry=reg)
    assert out["ok"] is False


def test_register_rejects_ephemeral(tmp_path, monkeypatch):
    monkeypatch.delenv("CCC_ALLOW_EPHEMERAL_REGISTRY", raising=False)
    from _workspace_registry import register_workspace, is_ephemeral_path

    # tmp_path itself is under pytest-of-* → ephemeral
    root = _mk_board_ws(tmp_path, "proj")
    assert is_ephemeral_path(root) is True
    reg = tmp_path / "workspaces.json"
    out = register_workspace(root, registry=reg)
    assert out["ok"] is False
    assert "ephemeral" in out.get("error", "")


def test_prune_missing_and_unregister(tmp_path, monkeypatch):
    monkeypatch.setenv("CCC_ALLOW_EPHEMERAL_REGISTRY", "1")
    from _workspace_registry import (
        register_workspace,
        prune_missing,
        unregister_workspace,
        list_registered_paths,
    )

    alive = _mk_board_ws(tmp_path, "alive")
    reg = tmp_path / "workspaces.json"
    assert register_workspace(alive, name="alive", registry=reg)["ok"]
    # Inject ghost (missing) — prune must remove it. alive is under pytest-of
    # so also ephemeral; after prune fleet may be empty in this fixture.
    data = json.loads(reg.read_text())
    data["workspaces"].append({"name": "ghost", "path": str(tmp_path / "no-such")})
    reg.write_text(json.dumps(data))

    dry = prune_missing(dry_run=True, registry=reg)
    assert any(p["name"] == "ghost" for p in dry["pruned"])
    assert any(p.get("reason") == "missing" for p in dry["pruned"])

    applied = prune_missing(dry_run=False, registry=reg)
    assert any(p["name"] == "ghost" for p in applied["pruned"])
    assert all(p.name != "ghost" for p in list_registered_paths(reg))
    # alive pruned as ephemeral under pytest tmp
    assert applied["kept"] == 0

    # Unregister by name on a fresh registration (allow_ephemeral via env)
    other = _mk_board_ws(tmp_path, "other")
    # Direct write to skip ephemeral prune dance
    reg.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "workspaces": [{"name": "other", "path": str(other.resolve())}],
            }
        )
    )
    un = unregister_workspace("other", registry=reg)
    assert un["ok"] and un["removed"] == 1
    assert list_registered_paths(reg) == []


def test_ensure_engine_registers_workspace(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("CCC_ALLOW_EPHEMERAL_REGISTRY", "1")
    import _ccc_control as ctrl
    import _engine_wake as wake
    import _workspace_registry as wr

    ctrl.CONTROL_DIR = tmp_path / ".ccc"
    ctrl.CONTROL_FILE = ctrl.CONTROL_DIR / "control.json"
    ctrl.DISABLED_SENTINEL = ctrl.CONTROL_DIR / "DISABLED"
    wake.WAKE_FILE = tmp_path / ".ccc" / "engine.wake"
    wr.REGISTRY_FILE = tmp_path / ".ccc" / "workspaces.json"

    root = _mk_board_ws(tmp_path, "xianyu")
    ctrl.set_mode("ui", reason="t", source="t")
    with patch.object(wake, "_bootstrap_engine_launchd", return_value=(False, "no_plist")):
        out = wake.ensure_engine_for_task(
            reason="task_dispatch",
            task_id="t1",
            workspace=root,
            workspace_name="xianyu",
            start_launchd=True,
        )
    assert out["mode_after"] == "enabled"
    assert out["workspace_reg"]["ok"] is True
    assert wr.REGISTRY_FILE.is_file()
    assert any(p == root.resolve() for p in wr.list_registered_paths(wr.REGISTRY_FILE))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
