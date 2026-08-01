"""conftest.py — pytest 配置

v0.28.0: 让 tests/test_phase_lint.py 的 TestRunLint 写文件不报 FileNotFoundError
"""
from __future__ import annotations

from pathlib import Path

import pytest


def pytest_configure(config):
    """pytest 启动时确保 phases 目录存在。

    test_phase_lint 用运行时 Path.cwd()/".ccc"/"phases"；而部分测试（test_audit_role 等）
    模块级 os.chdir(scripts) 不还原，会污染后续 cwd —— 故 cwd 与 SCRIPTS 两处都建。
    """
    cwd = Path.cwd()
    (cwd / ".ccc" / "phases").mkdir(parents=True, exist_ok=True)
    scripts_phases = Path(__file__).resolve().parent / ".ccc" / "phases"
    scripts_phases.mkdir(parents=True, exist_ok=True)


@pytest.fixture(autouse=True)
def _mute_ccc_desktop_notify(monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory):
    """pytest 默认静默 ccc-notify.sh：不弹 macOS 通知，告警落到临时目录。"""
    alert_dir = tmp_path_factory.mktemp("ccc-alerts")
    monkeypatch.setenv("CCC_NOTIFY", "0")
    monkeypatch.setenv("CCC_ALERT_DIR", str(alert_dir))
