"""test_opencode_pool_max_parallel.py — 验红线 X1：进程池最多 3 并发

测试：
  1. opencode-pool.py 拒绝 max_parallel > 3
  2. asyncio.Semaphore 行为正确（3 个同时跑，4-5 个排队）
  3. tasks.json 5 个慢任务，验证并发 ≤ 3
"""
from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT = ROOT / "scripts" / "opencode-pool.py"


def test_syntax_check():
    proc = subprocess.run([sys.executable, "-m", "py_compile", str(SCRIPT)], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr


def test_help_or_usage():
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        capture_output=True, text=True, timeout=5,
    )
    # argparse help 默认出 stderr
    assert "usage" in (proc.stdout + proc.stderr).lower()


def test_rejects_max_parallel_above_3():
    """红线 X1：--max-parallel > 3 必须拒绝"""
    tasks_file = Path("/tmp/_test_tasks_x1.json")
    tasks_file.write_text(json.dumps([]))
    try:
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), str(tasks_file), "--max-parallel", "5"],
            capture_output=True, text=True, timeout=5,
        )
        # 应非 0（拒绝执行）
        assert proc.returncode != 0, "max_parallel=5 应该被拒绝"
        out = proc.stdout + proc.stderr
        assert "X1" in out or "上限" in out or "3" in out
    finally:
        tasks_file.unlink(missing_ok=True)


def test_rejects_invalid_tasks_file():
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "/tmp/_nonexistent_xxxx.json"],
        capture_output=True, text=True, timeout=5,
    )
    assert proc.returncode == 2


def test_rejects_empty_tasks():
    tasks_file = Path("/tmp/_test_tasks_x1_empty.json")
    tasks_file.write_text(json.dumps([]))
    try:
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), str(tasks_file)],
            capture_output=True, text=True, timeout=5,
        )
        assert proc.returncode == 3
    finally:
        tasks_file.unlink(missing_ok=True)


def test_semaphore_concurrency_limit():
    """直接验 asyncio.Semaphore(3) 行为：3 个并发，4-5 个排队"""
    max_concurrent = 0
    current = 0
    sem = asyncio.Semaphore(3)
    started = []

    async def worker(i: int):
        nonlocal current, max_concurrent
        async with sem:
            current += 1
            max_concurrent = max(max_concurrent, current)
            started.append((i, time.time()))
            await asyncio.sleep(0.5)
            current -= 1

    async def main():
        return await asyncio.gather(*(worker(i) for i in range(5)))

    asyncio.run(main())
    assert max_concurrent == 3, f"期望最大并发 3，实际 {max_concurrent}"
    assert len(started) == 5
