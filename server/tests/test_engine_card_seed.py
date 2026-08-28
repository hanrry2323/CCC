"""test_engine_card_seed — ccc092 worktree 播种一致性：缺卡副本自愈 / 硬失败。

覆盖两分支：
- 分支①自愈：卡 commit 已进本地 main → 卡副本 copy 进 worktree 后放行；
- 分支②硬失败：卡 commit 未进本地 main（未 push）→ ERROR+alerts+打回，禁入重试循环。
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from server.engine import main as engine_main
from server.engine.main import (
    _SEED_HARDFAIL_MARKER,
    _card_rel_path_in_worktree,
    _ensure_worktree_card_seed,
    _local_main_has_card,
    _run_auto_worker,
    _self_heal_worktree_card,
)
from server.engine.store import InMemoryBoardStore
from server.engine.task import State, Work

CARD_REL = "docs/dispatch/ccc/ccc099-seed-fixture.md"
CARD_TEXT = "# 任务卡 ccc099 · 播种夹具\n\n## 目标\n\n（测试夹具数据，非真实任务）\n"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _init_main_repo(tmp_path: Path, with_card: bool) -> Path:
    """建一个本地 git 主仓（main 分支），可选含卡文件。"""
    repo = tmp_path / "mainrepo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    if with_card:
        card = repo / CARD_REL
        card.parent.mkdir(parents=True, exist_ok=True)
        card.write_text(CARD_TEXT, encoding="utf-8")
    (repo / "README.md").write_text("repo\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "init")
    return repo


def _make_work(tmp_path: Path) -> Work:
    prod_card = tmp_path / "prod" / CARD_REL
    return Work(id="ccc099", role="开发执行体", card_path=str(prod_card))


def _make_worktree(tmp_path: Path) -> str:
    wt = tmp_path / "wt" / "ccc099"
    wt.mkdir(parents=True)
    return str(wt)


class TestCardRelPath:
    def test_abs_card_path_yields_docs_rel(self, tmp_path: Path) -> None:
        assert _card_rel_path_in_worktree(str(tmp_path / "prod" / CARD_REL)) == CARD_REL

    def test_non_docs_path_returns_none(self) -> None:
        assert _card_rel_path_in_worktree("/x/y/other/foo.md") is None


class TestLocalMainHasCard:
    def test_true_when_commit_in_main(self, tmp_path: Path) -> None:
        repo = _init_main_repo(tmp_path, with_card=True)
        assert _local_main_has_card(repo, CARD_REL) is True

    def test_false_when_commit_absent(self, tmp_path: Path) -> None:
        repo = _init_main_repo(tmp_path, with_card=False)
        assert _local_main_has_card(repo, CARD_REL) is False

    def test_none_when_not_a_git_repo(self, tmp_path: Path) -> None:
        bogus = tmp_path / "bogus"
        bogus.mkdir()
        assert _local_main_has_card(bogus, CARD_REL) is None


class TestSelfHeal:
    def test_copies_card_from_local_main(self, tmp_path: Path) -> None:
        repo = _init_main_repo(tmp_path, with_card=True)
        wt = _make_worktree(tmp_path)
        healed, err = _self_heal_worktree_card(repo, wt, CARD_REL)
        assert healed, err
        assert (Path(wt) / CARD_REL).read_text(encoding="utf-8") == CARD_TEXT


class TestEnsureWorktreeCardSeed:
    def test_noop_when_card_present(self, tmp_path: Path) -> None:
        repo = _init_main_repo(tmp_path, with_card=True)
        wt = _make_worktree(tmp_path)
        (Path(wt) / CARD_REL).parent.mkdir(parents=True, exist_ok=True)
        (Path(wt) / CARD_REL).write_text("worktree 版本\n", encoding="utf-8")
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        work = _make_work(tmp_path)
        assert (
            _ensure_worktree_card_seed(work, wt, repo, log_dir, {"LOG_DIR": str(log_dir)}) is None
        )
        assert not (log_dir / "alerts").exists()

    def test_branch1_selfheal_when_commit_in_main(self, tmp_path: Path) -> None:
        """分支①：worktree 缺卡副本 + 本地 main 有该卡 commit → 自愈放行。"""
        repo = _init_main_repo(tmp_path, with_card=True)
        wt = _make_worktree(tmp_path)
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        work = _make_work(tmp_path)
        assert _ensure_worktree_card_seed(work, wt, repo, log_dir, {"LOG_DIR": str(log_dir)}) is None
        healed_card = Path(wt) / CARD_REL
        assert healed_card.is_file(), "自愈后 worktree 应有卡副本"
        assert healed_card.read_text(encoding="utf-8") == CARD_TEXT
        assert not (log_dir / "alerts").exists(), "自愈分支不应写告警文件"

    def test_branch2_hardfail_when_commit_absent(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """分支②：worktree 缺卡副本 + 卡 commit 未进本地 main → 硬失败+告警文件。"""
        monkeypatch.delenv("LOG_DIR", raising=False)
        repo = _init_main_repo(tmp_path, with_card=False)
        wt = _make_worktree(tmp_path)
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        work = _make_work(tmp_path)
        reasons = _ensure_worktree_card_seed(work, wt, repo, log_dir, {"LOG_DIR": str(log_dir)})
        assert reasons and len(reasons) == 1
        assert _SEED_HARDFAIL_MARKER in reasons[0]
        assert "未 push 或未合入" in reasons[0]
        alert = log_dir / "alerts" / f"missing-card-seed-{work.id}.txt"
        assert alert.is_file(), "硬失败必须落 alerts 告警文件"
        assert "人工" in alert.read_text(encoding="utf-8")

    def test_hardfail_when_probe_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """探测异常（非 git 主仓）→ 同样硬失败，不放行无卡 worktree。"""
        monkeypatch.delenv("LOG_DIR", raising=False)
        bogus = tmp_path / "bogus"
        bogus.mkdir()
        wt = _make_worktree(tmp_path)
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        work = _make_work(tmp_path)
        reasons = _ensure_worktree_card_seed(work, wt, bogus, log_dir, None)
        assert reasons and _SEED_HARDFAIL_MARKER in reasons[0]
        assert (log_dir / "alerts" / f"missing-card-seed-{work.id}.txt").is_file()


def _running_work_in_store(store: InMemoryBoardStore, tmp_path: Path, state: State) -> Work:
    work = _make_work(tmp_path)
    if state is not State.TODO:
        # 状态机：待分派 → 执行中 → （已回写/打回）；不跳步
        work.transition(State.RUNNING)
    if state in (State.DONE, State.REJECTED):
        work.transition(state)
    store.save_work(work)
    return work


class TestWorkerHardfailDirectReject:
    def test_auto_worker_rejects_without_retry(self, tmp_path: Path) -> None:
        """run 阶段：硬失败标记 → 直接 REJECTED，不进 infra 冷却/业务重试。"""
        store = InMemoryBoardStore()
        work = _running_work_in_store(store, tmp_path, State.RUNNING)
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        marker_reasons = [f"{_SEED_HARDFAIL_MARKER}：卡 x 的 commit 未进本地 main；需人工介入"]
        with (
            patch.object(engine_main, "_dispatch_and_collect", return_value=(False, marker_reasons)),
            patch.object(engine_main, "_dispatch_blocked_by_ledger", return_value=False),
        ):
            outcome = _run_auto_worker(work, None, store, {"DATA_DIR": str(tmp_path / "data")}, log_dir, 60)
        assert outcome.get("failed") == 1
        saved = store.list_work()[0]
        assert saved.state is State.REJECTED
        assert any(_SEED_HARDFAIL_MARKER in p for p in saved.problems)
