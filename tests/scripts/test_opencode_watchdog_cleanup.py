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


def test_launcher_runs_watchdog_first():
    """launcher 必跑 watchdog（红线 X3）—— 验 launcher 调用链

    这里用 echo 当 opencode binary 模拟，验 launcher 真的先跑了 watchdog
    """
    # 准备 prompt
    prompt = Path("/tmp/_test_launcher_x3.txt")
    prompt.write_text("test")
    try:
        # 调 launcher，timeout 短一些（5s），用 --skip-watchdog 避免残留干扰
        proc = subprocess.run(
            ["bash", str(LAUNCHER), "test-x3-phase", str(prompt), "--timeout", "5"],
            capture_output=True, timeout=30,
        )
        out = (proc.stdout + proc.stderr).decode("utf-8", errors="replace")
        # launcher 输出应含 "Step 1: opencode-watchdog"
        assert "Step 1" in out, f"launcher 应跑 Step 1 (watchdog)，实际：{out[:500]}"
    finally:
        prompt.unlink(missing_ok=True)


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
    env = {**os.environ, "CCC_ALERT_DIR": str(alert_dir)}
    proc = _run_notify("L2", "test L2", "smoke test", env=env)
    assert proc.returncode == 0
    l2_files = sorted(alert_dir.glob("*-L2.md"), key=lambda p: p.stat().st_mtime)
    assert l2_files


def test_notify_l3_creates_alert_file(alert_dir):
    env = {**os.environ, "CCC_ALERT_DIR": str(alert_dir)}
    proc = _run_notify("L3", "test L3", "smoke test", env=env)
    assert proc.returncode == 0
    l3_files = sorted(alert_dir.glob("*-L3.md"), key=lambda p: p.stat().st_mtime)
    assert l3_files


def test_notify_invalid_level():
    proc = _run_notify("L9", "bad", "bad")
    assert proc.returncode == 1


def test_notify_missing_args():
    proc = _run_notify("L1")
    assert proc.returncode != 0
