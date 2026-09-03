"""CardStateStore CAS/锁/原子写契约测试（B0）。

覆盖：版本 CAS、状态 CAS、提交 CAS、卡锁互斥、并发竞争、原子写、
冲突保留原文、history 记录、git commit/push/远端复核、非法状态阻断。
"""

from __future__ import annotations

import subprocess
import sys
import threading
from pathlib import Path
from typing import Callable

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from server.engine.card_state_store import (
    CardCASConflict,
    CardCommitError,
    CardLockError,
    CardPushError,
    CardStateStore,
    CardValidationError,
)

CARD_REL = "docs/dispatch/tst/tst501-state-store.md"


def _header(state: str, version: int = 0) -> str:
    ver = f" · 状态版本：{version}" if version else ""
    return (
        "# 任务卡 tst501 · 状态收口测试\n"
        f"> 关联：TEST · 执行体：DSH · 验收：DSH · 状态：{state}{ver}"
        " · 派发：engine · 项目：tst · 日期：2026-09-03\n"
        "\n"
        "## 目标\nx\n\n"
        "## 验收标准\nx\n"
    )


@pytest.fixture()
def store(tmp_path: Path) -> CardStateStore:
    args = ["git", "init", "-b", "main", str(tmp_path)]
    subprocess.run(args, capture_output=True, text=True, check=True)
    remote = tmp_path.parent / f"{tmp_path.name}-remote.git"
    subprocess.run(["git", "init", "--bare", str(remote)], capture_output=True, text=True, check=True)
    subprocess.run(["git", "-C", str(tmp_path), "remote", "add", "origin", str(remote)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "test@example.com"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "test"], check=True)
    card = tmp_path / CARD_REL
    card.parent.mkdir(parents=True, exist_ok=True)
    card.write_text(_header("待分派"), encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "--", CARD_REL], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "commit", "-m", "seed card"],
        check=True,
        capture_output=True,
    )
    subprocess.run(["git", "-C", str(tmp_path), "push", "-u", "origin", "main"], check=True, capture_output=True)
    return CardStateStore(tmp_path, dispatch_dir="docs/dispatch", data_dir=tmp_path / ".ccc-state")


def test_version_cas_conflict_preserves_original(store: CardStateStore) -> None:
    original = store.read_snapshot(CARD_REL)
    before = original.text
    with pytest.raises(CardCASConflict):
        store.transition(
            CARD_REL,
            target="执行中",
            expected_state="待分派",
            expected_version=original.version + 1,  # stale
            expected_commit=None,
            actor="test",
        )
    assert store.read_snapshot(CARD_REL).text == before


def test_state_cas_conflict_preserves_original(store: CardStateStore) -> None:
    snap = store.read_snapshot(CARD_REL)
    before = snap.text
    with pytest.raises(CardCASConflict):
        store.transition(
            CARD_REL,
            target="执行中",
            expected_state="打回",  # stale
            expected_version=snap.version,
            expected_commit=None,
            actor="test",
        )
    assert store.read_snapshot(CARD_REL).text == before


def test_commit_cas_conflict_preserves_original(store: CardStateStore) -> None:
    snap = store.read_snapshot(CARD_REL)
    before = snap.text
    with pytest.raises(CardCASConflict):
        store.transition(
            CARD_REL,
            target="执行中",
            expected_state="待分派",
            expected_version=snap.version,
            expected_commit="0" * 40,  # stale
            actor="test",
        )
    assert store.read_snapshot(CARD_REL).text == before


def test_success_transition_bumps_version_and_commits(store: CardStateStore) -> None:
    snap = store.read_snapshot(CARD_REL)
    receipt = store.transition(
        CARD_REL,
        target="执行中",
        expected_state="待分派",
        expected_version=snap.version,
        expected_commit=None,
        actor="test",
    )
    assert receipt.new_version == snap.version + 1
    assert receipt.new_state == "执行中"
    assert receipt.new_commit
    after = store.read_snapshot(CARD_REL)
    assert after.state == "执行中"
    assert after.version == snap.version + 1
    store.reverify_remote(after, commit=receipt.new_commit)


def test_validated_transition_rejects_illegal(store: CardStateStore) -> None:
    snap = store.read_snapshot(CARD_REL)
    store.transition(
        CARD_REL,
        target="执行中",
        expected_state="待分派",
        expected_version=snap.version,
        expected_commit=None,
        actor="test",
    )
    after = store.read_snapshot(CARD_REL)
    with pytest.raises(CardValidationError):
        store.transition(
            CARD_REL,
            target="已关闭",  # 执行中 → 已关闭 非法
            expected_state="执行中",
            expected_version=after.version,
            expected_commit=None,
            actor="test",
        )


def test_done_to_rejected_requires_problems(store: CardStateStore) -> None:
    snap = store.read_snapshot(CARD_REL)
    store.transition(
        CARD_REL,
        target="执行中",
        expected_state="待分派",
        expected_version=snap.version,
        expected_commit=None,
        actor="test",
    )
    after = store.read_snapshot(CARD_REL)
    store.transition(
        CARD_REL,
        target="已回写",
        expected_state="执行中",
        expected_version=after.version,
        expected_commit=None,
        actor="test",
    )
    done = store.read_snapshot(CARD_REL)
    store.transition(
        CARD_REL,
        target="打回",
        expected_state="已回写",
        expected_version=done.version,
        expected_commit=None,
        actor="test",
        reason="范围不一致",
    )
    assert store.read_snapshot(CARD_REL).state == "打回"


def test_atomic_write_preserves_text_on_conflict(store: CardStateStore) -> None:
    # 并发线程竞争：两个互不相同 actor 对同一卡各提交一次差异内容。
    # 只有一个应成功；即使失败也要保证原文未被截断/半写。
    snap = store.read_snapshot(CARD_REL)

    def _run() -> None:
        try:
            store.transition(
                CARD_REL,
                target="执行中",
                expected_state=snap.state,
                expected_version=snap.version,
                expected_commit=None,
                actor="race",
            )
        except (CardCASConflict, CardLockError):
            pass

    threads = [threading.Thread(target=_run) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    final = store.read_snapshot(CARD_REL)
    assert final.version == snap.version + 1
    assert final.text.endswith("\n")
    assert final.text.count("状态版本") == 1


def test_mutator_exception_does_not_write(store: CardStateStore) -> None:
    snap = store.read_snapshot(CARD_REL)
    before = snap.text

    def _bad_mutator(_text: str) -> str:
        raise ValueError("bad mutator")

    with pytest.raises(ValueError):
        store.transition(
            CARD_REL,
            target="执行中",
            expected_state="待分派",
            expected_version=snap.version,
            expected_commit=None,
            actor="test",
            mutator=_bad_mutator,
        )
    assert store.read_snapshot(CARD_REL).text == before


def test_card_lock_blocks_concurrent(store: CardStateStore) -> None:
    with store.lock_card("tst501"):
        with pytest.raises(CardLockError):
            with store.lock_card("tst501"):
                pass
    # 锁释放后可再拿
    with store.lock_card("tst501"):
        pass


def test_history_recorded(store: CardStateStore) -> None:
    snap = store.read_snapshot(CARD_REL)
    store.transition(
        CARD_REL,
        target="执行中",
        expected_state="待分派",
        expected_version=snap.version,
        expected_commit=None,
        actor="test",
    )
    history_dir = store.history_dir / "tst501"
    assert history_dir.is_dir()
    manifests = list(history_dir.glob("*.json"))
    assert len(manifests) >= 1
    import json as _json

    data = _json.loads(manifests[0].read_text(encoding="utf-8"))
    assert data["outcome"] == "candidate"
    assert data["version_from"] == snap.version
    assert data["version_to"] == snap.version + 1


def test_expected_commit_from_git_head(store: CardStateStore) -> None:
    snap = store.read_snapshot(CARD_REL)
    assert snap.commit  # 已提交初始卡
    store.transition(
        CARD_REL,
        target="执行中",
        expected_state="待分派",
        expected_version=snap.version,
        expected_commit=snap.commit,
        actor="test",
    )


def test_old_card_version_zero_read(store: CardStateStore) -> None:
    snap = store.read_snapshot(CARD_REL)
    assert snap.version == 0
