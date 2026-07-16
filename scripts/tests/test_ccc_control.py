"""tests for CCC control plane (_ccc_control.py)"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))

import _ccc_control as ctrl  # noqa: E402


@pytest.fixture()
def control_home(tmp_path, monkeypatch):
    monkeypatch.setattr(ctrl, "CONTROL_DIR", tmp_path)
    monkeypatch.setattr(ctrl, "CONTROL_FILE", tmp_path / "control.json")
    monkeypatch.setattr(ctrl, "DISABLED_SENTINEL", tmp_path / "DISABLED")
    monkeypatch.delenv("CCC_FOREGROUND", raising=False)
    return tmp_path


def test_default_mode_is_disabled(control_home):
    assert ctrl.get_mode() == "disabled"
    assert ctrl.is_disabled() is True
    assert ctrl.may_start_engine() is False
    assert ctrl.may_start_ui() is False


def test_ui_mode_allows_ui_not_engine(control_home):
    ctrl.set_mode("ui", reason="frontend")
    assert ctrl.get_mode() == "ui"
    assert ctrl.may_start_ui() is True
    assert ctrl.may_start_engine() is False
    assert ctrl.is_enabled() is False
    assert not ctrl.DISABLED_SENTINEL.exists()


def test_enable_disable_roundtrip(control_home):
    ctrl.set_mode("enabled", reason="test")
    assert ctrl.get_mode() == "enabled"
    assert ctrl.may_start_engine() is True
    assert ctrl.may_start_ui() is True
    assert not ctrl.DISABLED_SENTINEL.exists()

    data = json.loads(ctrl.CONTROL_FILE.read_text())
    assert data["mode"] == "enabled"
    assert data["policy"]["forbid_popen_engine"] is True

    ctrl.set_mode("disabled", reason="test stop")
    assert ctrl.get_mode() == "disabled"
    assert ctrl.DISABLED_SENTINEL.exists()
    assert ctrl.may_start_engine() is False
    assert ctrl.may_start_ui() is False


def test_legacy_disabled_sentinel_wins(control_home):
    ctrl.set_mode("enabled", reason="x")
    ctrl.DISABLED_SENTINEL.write_text("legacy\n")
    assert ctrl.get_mode() == "disabled"
    assert ctrl.may_start_engine() is False


def test_foreground_bypass(control_home, monkeypatch):
    assert ctrl.foreground_bypass() is False
    monkeypatch.setenv("CCC_FOREGROUND", "1")
    assert ctrl.foreground_bypass() is True


def test_status_dict(control_home):
    ctrl.set_mode("ui", reason="r")
    s = ctrl.status_dict()
    assert s["mode"] == "ui"
    assert s["enabled"] is False
    assert s["ui_allowed"] is True
    assert s["engine_allowed"] is False
