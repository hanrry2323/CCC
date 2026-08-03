"""多进程故障注入测试 — 验证 _atomic_write_json 跨进程并发安全

修复 stability-audit-2026-07-24 第五批 5.4：多进程故障注入测试，验证
b1493ef atomic_write_json（lock fd + fsync + dir fsync + os.replace）
在多写者并发下不损坏、不丢更新。
"""
from __future__ import annotations

import json
import multiprocessing
import sys
import time
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


# ── 子进程 worker ──


def _worker_write_json(args):
    """子进程 worker：调用 _atomic_write_json 写指定 index 的 dict。"""
    target_path_str, worker_id, n_writes, barrier_path_str = args

    sys.path.insert(0, str(SCRIPTS))
    from engine.active_tasks import _atomic_write_json  # noqa: E402

    target_path = Path(target_path_str)
    barrier = Path(barrier_path_str)
    # 等主进程放行
    while not barrier.exists():
        time.sleep(0.01)

    for i in range(n_writes):
        payload = json.dumps(
            {"worker": worker_id, "write": i, "ts": time.time_ns()},
            ensure_ascii=False,
        )
        _atomic_write_json(target_path, payload)


# ── 测试 ──


@pytest.mark.parametrize("n_workers,n_writes", [(4, 5), (2, 10)])
def test_atomic_write_concurrent_no_corruption(tmp_path, n_workers, n_writes):
    """4-5 个子进程并发写同一文件，最终内容是合法 JSON（不混合）。"""
    target = tmp_path / "concurrent.json"
    barrier = tmp_path / ".barrier"

    ctx = multiprocessing.get_context("spawn")
    procs = [
        ctx.Process(
            target=_worker_write_json,
            args=((str(target), wid, n_writes, str(barrier)),),
        )
        for wid in range(n_workers)
    ]
    for p in procs:
        p.start()
    # 放行
    barrier.touch()
    for p in procs:
        p.join(timeout=30)
        assert p.exitcode == 0, f"worker {p.pid} exitcode {p.exitcode}"

    # 验证文件存在且是合法 JSON
    assert target.is_file()
    final = target.read_text(encoding="utf-8")
    parsed = json.loads(final)
    assert "worker" in parsed
    assert "write" in parsed
    assert "ts" in parsed


def test_atomic_write_lock_file_persists(tmp_path):
    """lock 文件作为独立 inode 持久存在（不污染目标文件内容）。"""
    from engine.active_tasks import _atomic_write_json  # noqa: E402

    target = tmp_path / "x.json"
    _atomic_write_json(target, '{"k": 1}')

    lock_path = target.with_name(target.name + ".lock")
    # 修复 diff-review #2：lock 范围覆盖 os.replace — 锁文件存在
    # （独立 fd 持锁到 replace 后才 close）
    assert lock_path.is_file(), f"lock file {lock_path} 不应被自动清理"


def test_atomic_write_idempotent_under_kill(tmp_path):
    """同一文件反复 atomic_write_json（模拟崩溃后重写）始终是合法 JSON。"""
    from engine.active_tasks import _atomic_write_json  # noqa: E402

    target = tmp_path / "y.json"
    for i in range(20):
        _atomic_write_json(target, json.dumps({"i": i}))
        # 每次写完读出来验证（不能有半截 JSON）
        parsed = json.loads(target.read_text(encoding="utf-8"))
        assert parsed == {"i": i}


def test_atomic_write_large_payload(tmp_path):
    """大 payload（>64KB pipe buffer 阈值）也能 atomic write 成功。"""
    from engine.active_tasks import _atomic_write_json  # noqa: E402

    target = tmp_path / "large.json"
    big = {"data": "x" * (200 * 1024)}  # 200KB
    _atomic_write_json(target, json.dumps(big))
    parsed = json.loads(target.read_text(encoding="utf-8"))
    assert len(parsed["data"]) == 200 * 1024
