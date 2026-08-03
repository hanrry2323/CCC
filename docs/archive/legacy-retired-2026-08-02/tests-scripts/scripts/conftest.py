"""Shared pytest fixtures — ensure scripts/ is on sys.path as import root."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent.parent / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


@pytest.fixture(autouse=True)
def _mute_ccc_desktop_notify(monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory):
    """pytest 默认静默 ccc-notify.sh：不弹 macOS 通知，告警落到临时目录。

    单测若需显式验证 mute 行为，可覆盖 CCC_NOTIFY / CCC_ALERT_DIR。
    """
    alert_dir = tmp_path_factory.mktemp("ccc-alerts")
    monkeypatch.setenv("CCC_NOTIFY", "0")
    monkeypatch.setenv("CCC_ALERT_DIR", str(alert_dir))
