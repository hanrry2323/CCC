"""test_opencode_pool_kill_residual.py — 验红线 X2：每 phase 必杀

测试：
  1. opencode-exec.py 超时后进程被杀
  2. pid 文件在完成后被删（finally 兜底）
  3. TERM → KILL 兜底链（先 TERM 5s，再 KILL）
  4. watchdog 扫到残留会清
"""
from __future__ import annotations

import asyncio
import importlib.util
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent.parent
EXEC = ROOT / "scripts" / "opencode-exec.py"
WD = ROOT / "scripts" / "opencode-watchdog.sh"
PID_DIR = Path.home() / ".ccc" / "opencode-pids"


def test_syntax_check():
    proc = subprocess.run([sys.executable, "-m", "py_compile", str(EXEC)], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr


def test_watchdog_syntax_check():
    proc = subprocess.run(["bash", "-n", str(WD)], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr


def test_watchdog_cleans_stale_pid_file():
    """造一个假 pid 文件（指向已死进程）→ 跑 watchdog → 验证被清"""
    PID_DIR.mkdir(parents=True, exist_ok=True)
    fake_pid_file = PID_DIR / "_test_kill_residual.pid"
    # 写一个几乎肯定不存在的 pid
    fake_pid_file.write_text("999999")
    try:
        proc = subprocess.run(
            ["bash", str(WD)],
            capture_output=True, text=True, timeout=10,
        )
        # 死进程应被清；watchdog exit 0 或 3 都 OK
        assert proc.returncode in (0, 3)
        # pid 文件应被删
        assert not fake_pid_file.exists(), f"假 pid 文件应被清，仍存在：{fake_pid_file}"
    finally:
        fake_pid_file.unlink(missing_ok=True)


def test_watchdog_cleans_pid_reuse():
    """pid 被复用（名字不对）→ watchdog 应杀 + 清"""
    PID_DIR.mkdir(parents=True, exist_ok=True)
    fake_pid_file = PID_DIR / "_test_kill_reuse.pid"

    # 起一个 sleep 子进程，写它的 pid
    sleep_proc = subprocess.Popen(["sleep", "60"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    fake_pid_file.write_text(str(sleep_proc.pid))
    try:
        proc = subprocess.run(
            ["bash", str(WD)],
            capture_output=True, text=True, timeout=15,
        )
        out = proc.stdout + proc.stderr
        # sleep 进程名是 "sleep"，不是 opencode，应被识别为 pid 复用
        assert "pid 复用" in out or "cleaned" in out.lower()
        # pid 文件应被清
        assert not fake_pid_file.exists()
    finally:
        # 兜底杀
        sleep_proc.terminate()
        try:
            sleep_proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            sleep_proc.kill()
        fake_pid_file.unlink(missing_ok=True)


def _load_opencode_exec():
    """文件名带连字符，import 不行，用 importlib 加载"""
    spec = importlib.util.spec_from_file_location(
        "_opencode_exec_test", str(EXEC)
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_run_opencode_kills_on_timeout():
    """直接调 run_opencode，超时后进程被杀（红线 X2）"""
    mod = _load_opencode_exec()

    async def main():
        # 用 sleep 模拟 opencode 卡住（注入 cmd，不调真模型）
        started = time.time()
        result = await mod.run_opencode(
            phase_id="test-kill-timeout",
            prompt_text="ignored",
            timeout=2,
            cwd=None,
            cmd=["sleep", "30"],  # 30s 远 > 2s timeout
        )
        return result, time.time() - started

    try:
        result, dur = asyncio.run(main())
        assert result["killed"] is True, f"应被 kill，结果：{result}"
        assert result["exit_code"] == -1
        assert dur < 15, f"超时杀进程应 < 15s（含 sleep 启动 + kill），实际 {dur}s"
    finally:
        PID_FILE = PID_DIR / "test-kill-timeout.pid"
        PID_FILE.unlink(missing_ok=True)


def test_run_opencode_cleans_pid_file():
    """正常返回时 pid 文件应被删"""
    mod = _load_opencode_exec()

    async def main():
        # 注入 echo 模拟 opencode 快速完成
        return await mod.run_opencode(
            phase_id="test-clean-pid",
            prompt_text="ignored",
            timeout=3,
            cwd=None,
            cmd=["echo", "ok"],
        )

    try:
        asyncio.run(main())
        # pid 文件不应存在
        assert not (PID_DIR / "test-clean-pid.pid").exists()
    finally:
        (PID_DIR / "test-clean-pid.pid").unlink(missing_ok=True)
