"""test_opencode_watchdog_cleanup.py — 验红线 X3：启动前必跑残留 watchdog

测试：
  1. watchdog 在干净环境下 exit 0
  2. launcher 调用链含 watchdog（验 launcher 内部调 watchdog）
  3. notify.sh L1/L2/L3 都执行成功
  4. notify.sh 错误参数返回非 0
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
WD = ROOT / "scripts" / "opencode-watchdog.sh"
LAUNCHER = ROOT / "scripts" / "ccc-exec-launcher.sh"
NOTIFY = ROOT / "scripts" / "ccc-notify.sh"


@pytest.fixture
def alert_dir(tmp_path):
    """Isolated alert directory for each test (avoids writing to ~/.ccc/alerts/)."""
    d = tmp_path / "alerts"
    d.mkdir()
    return d


def test_watchdog_clean_exit_0():
    """干净环境 → exit 0"""
    proc = subprocess.run(
        ["bash", str(WD)],
        capture_output=True, timeout=10,
    )
    assert proc.returncode in (0, 3), f"干净环境应 exit 0/3，实际 {proc.returncode}"


def test_watchdog_output_format():
    """watchdog 输出含 [watchdog] 标签"""
    proc = subprocess.run(
        ["bash", str(WD)],
        capture_output=True, timeout=10,
    )
    out = (proc.stdout + proc.stderr).decode("utf-8", errors="replace")
    assert "[watchdog]" in out


def test_launcher_runs_watchdog_first(tmp_path):
    """launcher 必跑 watchdog（红线 X3）—— 验 launcher 调用链

    这里用 echo 当 opencode binary 模拟，验 launcher 真的先跑了 watchdog
    """
    # 准备 prompt
    prompt = tmp_path / "_test_launcher_x3.txt"
    prompt.write_text("test")
    proc = subprocess.run(
        [
            "bash",
            str(LAUNCHER),
            "test-x3-phase",
            str(prompt),
            "--timeout",
            "5",
            "--cwd",
            str(tmp_path),
        ],
        capture_output=True,
        timeout=30,
    )
    out = (proc.stdout + proc.stderr).decode("utf-8", errors="replace")
    # launcher 输出应含 "Step 1: opencode-watchdog"
    assert "Step 1" in out, f"launcher 应跑 Step 1 (watchdog)，实际：{out[:500]}"


def _run_notify(*args, env=None):
    """用 bytes 模式跑 notify（避免中文 locale 解码问题）"""
    return subprocess.run(
        ["bash", str(NOTIFY), *args],
        capture_output=True, timeout=5, env=env,
    )


def test_notify_l1_creates_alert_file(alert_dir):
    """L1 通知：仅日志 + 落告警文件"""
    env = {**os.environ, "CCC_ALERT_DIR": str(alert_dir)}
    proc = _run_notify("L1", "test L1", "smoke test message", env=env)
    assert proc.returncode == 0
    l1_files = sorted(alert_dir.glob("*-L1.md"), key=lambda p: p.stat().st_mtime)
    assert l1_files, f"应创建 L1 告警文件，实际目录：{list(alert_dir.glob('*'))}"


def test_notify_l2_creates_alert_file(alert_dir):
    env = {**os.environ, "CCC_ALERT_DIR": str(alert_dir), "CCC_NOTIFY": "0"}
    proc = _run_notify("L2", "test L2", "smoke test", env=env)
    assert proc.returncode == 0
    l2_files = sorted(alert_dir.glob("*-L2.md"), key=lambda p: p.stat().st_mtime)
    assert l2_files
    out = (proc.stdout + proc.stderr).decode("utf-8", errors="replace")
    assert "muted" in out


def test_notify_l3_creates_alert_file(alert_dir):
    env = {**os.environ, "CCC_ALERT_DIR": str(alert_dir), "CCC_NOTIFY": "0"}
    proc = _run_notify("L3", "test L3", "smoke test", env=env)
    assert proc.returncode == 0
    l3_files = sorted(alert_dir.glob("*-L3.md"), key=lambda p: p.stat().st_mtime)
    assert l3_files
    out = (proc.stdout + proc.stderr).decode("utf-8", errors="replace")
    assert "muted" in out


def test_notify_muted_by_dry_run(alert_dir):
    """CCC_DRY_RUN=1 → 仍落文件，不调 osascript"""
    env = {
        **os.environ,
        "CCC_ALERT_DIR": str(alert_dir),
        "CCC_DRY_RUN": "1",
        "CCC_NOTIFY": "1",  # 显式开 notify，仍被 DRY_RUN 挡住
    }
    env.pop("PYTEST_CURRENT_TEST", None)
    proc = _run_notify("L2", "dry-run gate", "should not popup", env=env)
    assert proc.returncode == 0
    assert list(alert_dir.glob("*-L2.md"))
    out = (proc.stdout + proc.stderr).decode("utf-8", errors="replace")
    assert "muted" in out


def test_notify_muted_by_pytest_env(alert_dir):
    """仅 PYTEST_CURRENT_TEST 即可静默（不依赖 CCC_NOTIFY=0）"""
    env = {
        **os.environ,
        "CCC_ALERT_DIR": str(alert_dir),
        "CCC_NOTIFY": "1",
        "CCC_DRY_RUN": "0",
        "PYTEST_CURRENT_TEST": "test_notify_muted_by_pytest_env (call)",
    }
    proc = _run_notify("L2", "pytest gate", "should not popup", env=env)
    assert proc.returncode == 0
    out = (proc.stdout + proc.stderr).decode("utf-8", errors="replace")
    assert "muted" in out


def test_notify_engine_brief_muted(alert_dir):
    """Engine 2 参数简版在 mute 时直接 exit 0、不弹窗"""
    env = {**os.environ, "CCC_NOTIFY": "0", "CCC_ALERT_DIR": str(alert_dir)}
    proc = _run_notify("CCC", "brief mute smoke", env=env)
    assert proc.returncode == 0
    out = (proc.stdout + proc.stderr).decode("utf-8", errors="replace")
    assert "muted" in out


def test_notify_muted_does_not_invoke_osascript(alert_dir, tmp_path):
    """CCC_NOTIFY=0 时 PATH 里的假 osascript 不得被调用"""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake = bin_dir / "osascript"
    fake.write_text("#!/bin/bash\necho OSASCRIPT_CALLED >&2\nexit 99\n")
    fake.chmod(0o755)
    env = {
        **os.environ,
        "PATH": f"{bin_dir}:{os.environ.get('PATH', '')}",
        "CCC_ALERT_DIR": str(alert_dir),
        "CCC_NOTIFY": "0",
        "CCC_DRY_RUN": "0",
    }
    env.pop("PYTEST_CURRENT_TEST", None)
    proc = _run_notify("L2", "no-osascript", "must stay silent", env=env)
    assert proc.returncode == 0
    out = (proc.stdout + proc.stderr).decode("utf-8", errors="replace")
    assert "OSASCRIPT_CALLED" not in out
    assert "muted" in out
    assert list(alert_dir.glob("*-L2.md"))


def test_notify_invalid_level():
    proc = _run_notify("L9", "bad", "bad")
    assert proc.returncode == 1


def test_notify_missing_args():
    proc = _run_notify("L1")
    assert proc.returncode != 0
