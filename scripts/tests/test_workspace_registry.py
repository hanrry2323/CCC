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


def test_register_workspace_idempotent(tmp_path):
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


def test_ensure_engine_registers_workspace(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
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
