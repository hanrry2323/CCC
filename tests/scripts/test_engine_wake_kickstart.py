#!/usr/bin/env python3
"""ensure_engine_for_task must kickstart when Engine is dead; wake carries workspace."""

from __future__ import annotations

import json
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def wake_mod(monkeypatch, tmp_path):
    import sys

    scripts = Path(__file__).resolve().parents[2] / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    import _engine_wake as wake

    wake_file = tmp_path / "engine.wake"
    monkeypatch.setattr(wake, "WAKE_FILE", wake_file)
    return wake


def test_write_wake_includes_workspace(wake_mod, tmp_path):
    ws = tmp_path / "apps" / "qb"
    ws.mkdir(parents=True)
    path = wake_mod.write_wake(
        reason="task_dispatch",
        task_id="epic-1",
        workspace=ws,
    )
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["reason"] == "task_dispatch"
    assert data["task_id"] == "epic-1"
    assert Path(data["workspace"]).resolve() == ws.resolve()


def test_kickstart_invokes_launchctl(wake_mod, monkeypatch):
    calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        calls.append(list(cmd))
        return MagicMock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(wake_mod.subprocess, "run", fake_run)
    ok, note = wake_mod._kickstart_engine_launchd()
    assert ok is True
    assert note == "kickstart_ok"
    assert calls[0][0:3] == ["launchctl", "kickstart", "-k"]
    assert calls[0][3].endswith("/com.ccc.engine")


def test_ensure_engine_kickstarts_when_dead(wake_mod, monkeypatch, tmp_path):
    ctrl = types.ModuleType("_ccc_control")
    ctrl.get_mode = lambda: "enabled"  # type: ignore
    ctrl.set_mode = lambda *a, **k: None  # type: ignore
    monkeypatch.setitem(__import__("sys").modules, "_ccc_control", ctrl)

    monkeypatch.setattr(wake_mod, "_bootstrap_engine_launchd", lambda: (True, "bootstrap_ok"))
    # After bootstrap still dead → ensure calls kickstart
    monkeypatch.setattr(
        wake_mod,
        "is_engine_running",
        MagicMock(side_effect=[False, True]),
    )
    kicked = MagicMock(return_value=(True, "kickstart_ok"))
    monkeypatch.setattr(wake_mod, "_kickstart_engine_launchd", kicked)

    result = wake_mod.ensure_engine_for_task(
        reason="task_dispatch",
        task_id="human-supervised-1",
        start_launchd=True,
        workspace=tmp_path,
    )
    kicked.assert_called_once()
    assert result["engine_running"] is True
    assert "kickstart_ok" in result["launch_note"]
    data = json.loads(Path(result["wake_file"]).read_text(encoding="utf-8"))
    assert data["task_id"] == "human-supervised-1"
    assert "workspace" in data


def test_watchdog_exits_zero_not_78():
    """Contract: tick watchdog must os._exit(0) for launchd SuccessfulExit."""
    src = (Path(__file__).resolve().parents[2] / "scripts" / "ccc-engine.py").read_text(
        encoding="utf-8"
    )
    assert "os._exit(0)" in src
    assert "os._exit(78)" not in src
    assert "exit 0 for launchd" in src


def test_apply_wake_clears_degraded_and_prioritizes():
    src = (Path(__file__).resolve().parents[2] / "scripts" / "ccc-engine.py").read_text(
        encoding="utf-8"
    )
    assert "_intake_bypass_degraded" in src
    assert "_prioritize_wake_workspace" in src
    assert "_apply_wake_payload" in src
    assert "cleared degraded" in src
    assert "_INTAKE_BYPASS_TICKS" in src
