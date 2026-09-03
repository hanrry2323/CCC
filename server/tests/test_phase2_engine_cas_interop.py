"""B2：phase2 与 engine 并发改同一卡 → 一方 CAS 失败保留原文。"""

from __future__ import annotations

import subprocess
import threading
from pathlib import Path

import pytest

from server.engine.card_state_store import CardCASConflict, CardStateStore, CardValidationError
from server.engine.phase2 import set_card_state
from server.engine.task import State, Work


def _mk_repo(tmp_path: Path) -> tuple[Path, Path, CardStateStore]:
    args = ["git", "init", "-b", "main", str(tmp_path)]
    subprocess.run(args, capture_output=True, text=True, check=True)
    remote = tmp_path.parent / f"{tmp_path.name}-remote.git"
    subprocess.run(["git", "init", "--bare", str(remote)], capture_output=True, text=True, check=True)
    subprocess.run(["git", "-C", str(tmp_path), "remote", "add", "origin", str(remote)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "t@example.com"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "t"], check=True)
    card = tmp_path / "docs" / "dispatch" / "tst" / "tst998-cas-interop.md"
    card.parent.mkdir(parents=True, exist_ok=True)
    card.write_text(
        "# 任务卡 tst998 · CAS 互斥\n"
        "> 关联：TEST · 执行体：DSH · 验收：DSH · 状态：待分派 · 派发：engine · 项目：tst · 日期：2026-09-04\n"
        "\n## 目标\nx\n\n## 维护区\n\n1. 方案同步：[否] 无\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "-C", str(tmp_path), "add", "-A"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-qm", "seed"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "push", "-qu", "origin", "main"], check=True, capture_output=True)
    store = CardStateStore(tmp_path, dispatch_dir="docs/dispatch", data_dir=tmp_path / ".ccc-state")
    return tmp_path, card, store


def test_engine_vs_phase2_same_card_one_cas_wins(tmp_path: Path) -> None:
    """Engine 与 phase2 并发改同一卡：版本 CAS 只让一个提交成功，另一个保留原文。"""
    _repo, card_file, store = _mk_repo(tmp_path)
    snap = store.read_snapshot(card_file)

    # engine 侧先派发（待分派 → 执行中）
    store.transition(
        card_file,
        target="执行中",
        expected_state="待分派",
        expected_version=snap.version,
        expected_commit=None,
        actor="engine",
        reason="engine dispatch",
    )
    run_after = store.read_snapshot(card_file)

    # phase2 用 stale 的 version 尝试把卡从「待分派」直接打回 → 必须 CAS 失败
    with pytest.raises(CardCASConflict):
        store.transition(
            card_file,
            target="打回（机审：不通过）",
            expected_state="待分派",
            expected_version=snap.version,  # stale
            expected_commit=None,
            actor="phase2",
            reason="audit reject",
        )

    # 原文（执行中 + run_after.version）必须未被覆盖
    after = store.read_snapshot(card_file)
    assert after.state == "执行中"
    assert after.version == run_after.version
    assert "打回" not in after.text


def test_phase2_vs_engine_distinct_cards_proceed(tmp_path: Path) -> None:
    """不同卡互不阻塞：可并行 CAS 转移。"""
    repo, card_a, store = _mk_repo(tmp_path)
    card_b = repo / "docs" / "dispatch" / "tst" / "tst999-cas-interop.md"
    card_b.write_text(
        "# 任务卡 tst999 · CAS 并行\n"
        "> 关联：TEST · 执行体：DSH · 验收：DSH · 状态：待分派 · 派发：engine · 项目：tst · 日期：2026-09-04\n"
        "\n## 目标\nx\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "seed b"], check=True, capture_output=True)

    snap_a = store.read_snapshot(card_a)
    snap_b = store.read_snapshot(card_b)
    results: dict[str, str] = {}

    def _run(card: Path, snap, tag: str) -> None:
        try:
            store.transition(
                card,
                target="执行中",
                expected_state=snap.state,
                expected_version=snap.version,
                expected_commit=None,
                actor=tag,
            )
            results[tag] = "ok"
        except Exception as exc:  # noqa: BLE001
            results[tag] = str(exc)

    threads = [
        threading.Thread(target=_run, args=(card_a, snap_a, "engine-a")),
        threading.Thread(target=_run, args=(card_b, snap_b, "engine-b")),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert results.get("engine-a") == "ok"
    assert results.get("engine-b") == "ok"
    assert store.read_snapshot(card_a).state == "执行中"
    assert store.read_snapshot(card_b).state == "执行中"


def test_set_card_state_routes_through_store_and_bumps_version(tmp_path: Path) -> None:
    """phase2 set_card_state 经统一 store：成功推进版本并写机审区。"""
    _repo, card_file, store = _mk_repo(tmp_path)

    def _fake_phase2_store(_card_file=None):
        return store

    import server.engine.phase2 as phase2_mod

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(phase2_mod, "_phase2_store", _fake_phase2_store)
    try:
        # 合法路径：待分派 → 执行中（phase2 无派发，这里仅验证经 store 落盘）
        ok = set_card_state(card_file, "执行中", "PASS", "ok")
        assert ok is True
        after = store.read_snapshot(card_file)
        assert after.state == "执行中"
        assert after.version >= 1
    finally:
        monkeypatch.undo()
