"""F-CON-01 / Phase 2: opencode 槽位 — 同进程 + 跨进程 flock 不漂移。"""
from __future__ import annotations

import multiprocessing as mp
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS = ROOT / "scripts"
ENGINE = SCRIPTS / "ccc-engine.py"


@pytest.fixture
def slot_file(tmp_path, monkeypatch):
    path = tmp_path / "opencode_slots.json"
    monkeypatch.setenv("CCC_OPENCODE_SLOTS_FILE", str(path))
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    return path


def test_slot_helpers_use_cross_process_module():
    """F-CON-01: engine 通过 engine.slots 间接对接 board.slots（跨进程 flock）。"""
    src = ENGINE.read_text(encoding="utf-8")
    # engine.slots 是薄包装；底层 board.slots 用 fcntl flock 保证跨进程一致
    assert "from engine.slots import" in src
    assert "_try_acquire_opencode_slot" in src
    assert "_release_opencode_slot" in src
    # engine.slots 模块也必须暴露同名 helper（ccc-engine.legacy 别名）
    from engine import slots as _slots_mod

    assert hasattr(_slots_mod, "try_acquire_opencode_slot")
    assert hasattr(_slots_mod, "release_opencode_slot")
    # 底层走 board.slots（保证 flock 跨进程）
    import board.slots as _bs

    assert hasattr(_bs, "try_acquire")
    assert hasattr(_bs, "release")


def test_acquire_release_roundtrip(slot_file):
    from board.slots import release, snapshot, try_acquire

    assert try_acquire("a", max_slots=2, state_path=slot_file)
    assert try_acquire("b", max_slots=2, state_path=slot_file)
    assert not try_acquire("c", max_slots=2, state_path=slot_file)
    assert release("a", state_path=slot_file) == 1
    assert try_acquire("c", max_slots=2, state_path=slot_file)
    assert release("b", state_path=slot_file) == 1
    assert release("c", state_path=slot_file) == 1
    assert snapshot(slot_file)["count"] == 0


def test_concurrent_threads_never_exceed_max(slot_file):
    from board.slots import try_acquire

    max_c = 3
    with ThreadPoolExecutor(max_workers=12) as ex:
        futs = [
            ex.submit(try_acquire, f"t{i}", max_slots=max_c, state_path=slot_file)
            for i in range(20)
        ]
        acquired = [f.result() for f in futs]
    assert sum(1 for x in acquired if x) == max_c


def _worker_acquire_hold(
    path: str, prefix: str, n: int, max_slots: int, result_q, hold_evt
):
    """子进程：尝试 n 次 acquire，汇报后保持存活直到 hold_evt，避免被 sibling reap。"""
    sys.path.insert(0, str(SCRIPTS))
    os.environ["CCC_OPENCODE_SLOTS_FILE"] = path
    from board.slots import try_acquire

    ok = 0
    for i in range(n):
        if try_acquire(f"{prefix}-{i}", max_slots=max_slots, state_path=Path(path)):
            ok += 1
    result_q.put(ok)
    hold_evt.wait(timeout=30)


def test_two_processes_slot_count_no_drift(slot_file):
    """2 进程并发占槽：存活期间不超卖；退出后 reap 归零。"""
    from board.slots import snapshot

    max_slots = 4
    ctx = mp.get_context("spawn")
    result_q = ctx.Queue()
    hold_evt = ctx.Event()
    procs = [
        ctx.Process(
            target=_worker_acquire_hold,
            args=(str(slot_file), "p0", 10, max_slots, result_q, hold_evt),
        ),
        ctx.Process(
            target=_worker_acquire_hold,
            args=(str(slot_file), "p1", 10, max_slots, result_q, hold_evt),
        ),
    ]
    for p in procs:
        p.start()

    got = [result_q.get(timeout=15) for _ in range(2)]
    assert sum(got) == max_slots
    # 两侧仍存活 → count 应等于已占用槽位数
    snap = snapshot(slot_file)
    assert snap["count"] == max_slots, f"live holders should keep count, got {snap}"

    hold_evt.set()
    for p in procs:
        p.join(timeout=15)
        assert p.exitcode == 0

    snap2 = snapshot(slot_file)
    assert snap2["count"] == 0, f"dead pid slots should reap, got {snap2}"


def test_release_returns_zero_when_not_held(slot_file):
    """F-CON-02: 释放未持有 slot 返 0（不动 count）。"""
    from board.slots import release, snapshot

    snap0 = snapshot(slot_file)
    assert release("ghost", state_path=slot_file) == 0
    snap1 = snapshot(slot_file)
    assert snap1["count"] == snap0["count"]


def test_same_workspace_exclusion(slot_file, monkeypatch):
    """engine.slots.try_acquire_opencode_slot：同 workspace 不同 task 互斥。"""
    import sys
    sys.path.insert(0, str(SCRIPTS))
    monkeypatch.setenv("CCC_OPENCODE_SLOTS_FILE", str(slot_file))
    from engine.slots import (
        try_acquire_opencode_slot,
        release_opencode_slot,
    )

    ws = "/tmp/some-ws"
    k1 = f"{ws}|taskA"
    k2 = f"{ws}|taskB"
    k3 = "/tmp/other-ws|taskC"
    try:
        assert try_acquire_opencode_slot(k1)
        # 同 ws 另一个 task 被拒
        assert not try_acquire_opencode_slot(k2)
        # 不同 ws 可占
        assert try_acquire_opencode_slot(k3)
        # release k1 后同 ws 可占
        assert release_opencode_slot(k1) == 1
        assert try_acquire_opencode_slot(k2)
    finally:
        release_opencode_slot(k1)
        release_opencode_slot(k2)
        release_opencode_slot(k3)


def test_count_proxy_cache_invalidation(slot_file, monkeypatch):
    """engine.slots.OpenCodeCountProxy TTL 缓存 + invalidate 立即失效。"""
    import sys
    sys.path.insert(0, str(SCRIPTS))
    monkeypatch.setenv("CCC_OPENCODE_SLOTS_FILE", str(slot_file))
    from engine.slots import (
        OpenCodeCountProxy,
        try_acquire_opencode_slot,
        release_opencode_slot,
    )
    monkeypatch.setenv("CCC_SLOT_CACHE_TTL", "60")
    import engine.slots as _slots_mod
    _slots_mod._SLOT_CACHE_TTL = 60.0
    OpenCodeCountProxy.invalidate()

    try:
        # 空 → count = 0
        OpenCodeCountProxy.invalidate()
        assert int(OpenCodeCountProxy()) == 0
        try_acquire_opencode_slot("/tmp/x|a")
        # acquire 后 invalidate → 读到 1
        assert int(OpenCodeCountProxy()) == 1
        release_opencode_slot("/tmp/x|a")
        assert int(OpenCodeCountProxy()) == 0
    finally:
        release_opencode_slot("/tmp/x|a")
