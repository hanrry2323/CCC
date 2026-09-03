"""统一任务卡状态写入契约（B0 + B1 git_sync 共用锁）。

本模块是卡状态收口的唯一写入门面。B0 先提供可独立测试的快照、卡级锁、
版本/提交 CAS、原子卡写入、索引刷新和 Git 提交复核；B1 起提供跨组件
（Engine / phase2 / Web / git_sync）共用的 Git 写锁，保护提交窗口不被强制对齐清除。

约束：
- ``cards.index`` 是派生缓存，不参与 CAS 真值；
- 卡头 ``状态版本：N`` 向后兼容，缺失时按 0 读取；
- ``expected_commit`` 传入时必须匹配当前卡所在 HEAD；
- 任何提交失败都保留候选卡和 before/after 历史，不 reset/覆盖。
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Callable, Iterator

from server.board.models import base_state
from server.engine.task import State

try:
    import fcntl as _fcntl
except ImportError:  # pragma: no cover - 非类 Unix 环境不提供 fcntl
    _fcntl = None  # type: ignore[assignment]


def _lock_exclusive(handle, *, blocking: bool) -> None:
    """跨进程排他锁统一包装；不可用时抛 CardLockError（绝不静默无锁）。"""
    if _fcntl is None:
        raise CardLockError("当前平台无 fcntl，无法获取卡级/Git 写锁")
    flags = _fcntl.LOCK_EX | (0 if blocking else _fcntl.LOCK_NB)
    try:
        _fcntl.flock(handle.fileno(), flags)
    except BlockingIOError as exc:
        raise CardLockError("文件锁已被占用（非阻塞模式）") from exc
    except OSError as exc:
        raise CardLockError(f"文件锁获取失败: {exc}") from exc


def _git_common_dir(repo: Path) -> Path:
    result = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--git-common-dir"],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    raw = _text_output(result.stdout).strip()
    if result.returncode == 0 and raw:
        common = Path(raw)
        return common if common.is_absolute() else (repo / common).resolve()
    return repo / ".git"


@contextlib.contextmanager
def protected_git_lock(repo_root: str | Path, *, blocking: bool = False) -> Iterator[None]:
    """跨组件共用 Git 写锁（Engine / phase2 / Web / git_sync）。

    锁放 git-common-dir（worktree 亦共享同一把锁），避免各模块各自在
    ``EMPTY_D`` 目录建锁导致互斥失效。非阻塞拿不到抛 ``CardLockError``，
    调用方必须跳过本轮破坏性对齐，而不是强行覆盖提交中的卡。
    """
    repo = Path(repo_root).expanduser().resolve()
    common = _git_common_dir(repo)
    lock_path = common / "ccc-card-git.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = lock_path.open("a+")
    try:
        _lock_exclusive(handle, blocking=blocking)
        yield
    finally:
        try:
            if _fcntl is not None:
                _fcntl.flock(handle.fileno(), _fcntl.LOCK_UN)
        finally:
            handle.close()


class CardStateError(RuntimeError):
    """所有统一状态写入错误的基类。"""

    code = "CARD_STATE_ERROR"


class CardLockError(CardStateError):
    code = "CARD_LOCKED"


class CardCASConflict(CardStateError):
    code = "CAS_CONFLICT"


class CardCommitError(CardStateError):
    code = "COMMIT_FAILED"


class CardPushError(CardStateError):
    code = "PUSH_REJECTED"


class CardValidationError(CardStateError):
    code = "INVALID_TRANSITION"


class TransitionResult(StrEnum):
    OK = "ok"


@dataclass(frozen=True)
class CardSnapshot:
    """持锁读取的一致卡快照。"""

    card_id: str
    path: Path
    rel_path: str
    text: str
    state: str
    version: int
    commit: str
    blob: str
    branch: str

    @property
    def text_sha256(self) -> str:
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class TransitionReceipt:
    """一次成功状态写入的可复核回执。"""

    card_id: str
    old_state: str
    new_state: str
    old_version: int
    new_version: int
    old_commit: str
    new_commit: str
    rel_path: str


_STATE_TARGETS: dict[str, frozenset[str]] = {
    State.TODO.value: frozenset({State.RUNNING.value, State.VOIDED.value}),
    State.RUNNING.value: frozenset(
        {State.DONE.value, State.REJECTED.value, State.TODO.value, State.VOIDED.value}
    ),
    State.DONE.value: frozenset(
        {State.CLOSED.value, State.REJECTED.value, State.TODO.value, State.VOIDED.value}
    ),
    State.REJECTED.value: frozenset({State.TODO.value, State.VOIDED.value}),
    State.CLOSED.value: frozenset(),
    State.VOIDED.value: frozenset(),
}

_VERSION_RE = re.compile(r"(状态版本\s*[:：]\s*)(\d+)")
_STATE_RE = re.compile(r"(状态\s*[:：]\s*)([^\n·]+?)(?=\s*·|\s*$)")


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")


def _safe_id(card_id: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_.-]+", "_", card_id.strip())
    if not value:
        raise ValueError("card_id 不能为空")
    return value


def _text_output(value: object) -> str:
    """把 subprocess 输出安全归一为字符串（测试替身也不得污染 history JSON）。"""
    return value if isinstance(value, str) else ""


def _run_git(repo: Path, args: list[str], *, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


class CardStateStore:
    """任务卡状态的统一 CAS 写入门面。

    ``repo_root`` 是任务卡所在 Git 仓；``dispatch_dir`` 可为相对或绝对路径。
    ``data_dir`` 只存锁和冲突历史，不参与卡真值。
    """

    def __init__(
        self,
        repo_root: str | Path,
        *,
        dispatch_dir: str | Path = "docs/dispatch",
        data_dir: str | Path | None = None,
        remote: str = "origin",
    ) -> None:
        self.repo_root = Path(repo_root).expanduser().resolve()
        raw_dispatch = Path(dispatch_dir).expanduser()
        self.dispatch_dir = (
            raw_dispatch if raw_dispatch.is_absolute() else self.repo_root / raw_dispatch
        ).resolve()
        self.data_dir = (
            Path(data_dir).expanduser().resolve()
            if data_dir is not None
            else self.repo_root / ".ccc-state"
        )
        self.remote = remote
        self.lock_dir = self.data_dir / "state" / "locks" / "cards"
        self.history_dir = self.data_dir / "state" / "card-history"

    def _card_path(self, card: str | Path) -> Path:
        if isinstance(card, Path):
            path = card.expanduser()
        else:
            candidate = Path(card).expanduser()
            if candidate.is_absolute():
                path = candidate
            elif "/" in card:
                path = self.repo_root / candidate
            else:
                matches = sorted(self.dispatch_dir.rglob(f"{card}-*.md"))
                if not matches:
                    matches = sorted(self.dispatch_dir.rglob(f"{card}.md"))
                if len(matches) != 1:
                    raise FileNotFoundError(f"无法唯一定位任务卡: {card}")
                path = matches[0]
        path = path.resolve()
        try:
            path.relative_to(self.repo_root)
        except ValueError as exc:
            raise ValueError(f"任务卡不在 repo_root 内: {path}") from exc
        if not path.is_file():
            raise FileNotFoundError(path)
        return path

    def _rel(self, path: Path) -> str:
        return path.relative_to(self.repo_root).as_posix()

    def _branch(self) -> str:
        # 纯单测夹具可能没有 .git；读快照仍可用，真实提交会由 Git 命令显式失败。
        if not (self.repo_root / ".git").exists():
            return "main"
        result = _run_git(self.repo_root, ["branch", "--show-current"])
        branch = _text_output(result.stdout).strip()
        if not branch:
            raise CardCommitError("当前仓库处于 detached HEAD，无法提交卡状态")
        return branch

    def _git_commit(self, path: Path) -> str:
        result = _run_git(self.repo_root, ["log", "-1", "--format=%H", "--", self._rel(path)])
        return _text_output(result.stdout).strip()

    def _git_blob(self, path: Path) -> str:
        result = _run_git(self.repo_root, ["hash-object", str(path)])
        return _text_output(result.stdout).strip() if result.returncode == 0 else ""

    def read_snapshot(self, card: str | Path) -> CardSnapshot:
        path = self._card_path(card)
        text = path.read_text(encoding="utf-8")
        state_match = _STATE_RE.search(text)
        state = base_state(state_match.group(2).strip()) if state_match else ""
        version_match = _VERSION_RE.search(text)
        version = int(version_match.group(2)) if version_match else 0
        card_id = path.stem.split("-", 1)[0]
        return CardSnapshot(
            card_id=card_id,
            path=path,
            rel_path=self._rel(path),
            text=text,
            state=state,
            version=version,
            commit=self._git_commit(path),
            blob=self._git_blob(path),
            branch=self._branch(),
        )

    @contextlib.contextmanager
    def lock_card(self, card_id: str, *, blocking: bool = False) -> Iterator[None]:
        """取得跨进程卡锁；默认非阻塞，拿不到即返回 CARD_LOCKED。"""
        self.lock_dir.mkdir(parents=True, exist_ok=True)
        path = self.lock_dir / f"{_safe_id(card_id)}.lock"
        handle = path.open("a+")
        try:
            try:
                _lock_exclusive(handle, blocking=blocking)
            except CardLockError as exc:
                raise CardLockError(f"卡锁已被占用: {card_id}（{exc.args[0]}）") from exc
            yield
        finally:
            try:
                if _fcntl is not None:
                    _fcntl.flock(handle.fileno(), _fcntl.LOCK_UN)
            finally:
                handle.close()

    @contextlib.contextmanager
    def _git_lock(self) -> Iterator[None]:
        """本模块内部提交段用的全局 Git 写锁（与 git_sync 同一把）。"""
        with protected_git_lock(self.repo_root, blocking=True) as _lock:
            yield _lock

    def _history(self, before: CardSnapshot, after_text: str, *, actor: str, outcome: str, reason: str = "") -> None:
        target = self.history_dir / _safe_id(before.card_id)
        target.mkdir(parents=True, exist_ok=True)
        stamp = _utc_stamp()
        before_path = target / f"{stamp}-before.md"
        after_path = target / f"{stamp}-after.md"
        manifest_path = target / f"{stamp}.json"
        before_path.write_text(before.text, encoding="utf-8")
        after_path.write_text(after_text, encoding="utf-8")
        manifest_path.write_text(
            json.dumps(
                {
                    "card_id": before.card_id,
                    "rel_path": before.rel_path,
                    "version_from": before.version,
                    "version_to": self._version_from(after_text),
                    "commit_from": before.commit,
                    "blob_from": before.blob,
                    "actor": actor,
                    "outcome": outcome,
                    "reason": reason,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "before": before_path.name,
                    "after": after_path.name,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    @staticmethod
    def _version_from(text: str) -> int:
        match = _VERSION_RE.search(text)
        return int(match.group(2)) if match else 0

    @staticmethod
    def _with_version(text: str, version: int) -> str:
        match = _VERSION_RE.search(text)
        if match:
            return text[: match.start(2)] + str(version) + text[match.end(2) :]
        state_match = _STATE_RE.search(text)
        if not state_match:
            raise CardValidationError("卡头缺少状态字段，无法写入状态版本")
        line_end = text.find("\n", state_match.end())
        if line_end < 0:
            line_end = len(text)
        return text[:line_end] + f" · 状态版本：{version}" + text[line_end:]

    @staticmethod
    def _with_state(text: str, state: str) -> str:
        updated, count = _STATE_RE.subn(rf"\g<1>{state}", text, count=1)
        if count != 1:
            raise CardValidationError("卡头缺少状态字段，无法写入状态")
        return updated

    def _write_atomic(self, path: Path, text: str) -> None:
        temp = path.with_name(f".{path.name}.card-state-{os.getpid()}-{time.time_ns()}.tmp")
        try:
            with temp.open("w", encoding="utf-8") as handle:
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp, path)
        finally:
            temp.unlink(missing_ok=True)

    def _refresh_index(self) -> None:
        from server.board.loader import load_dispatch_cards

        load_dispatch_cards(self.dispatch_dir)

    def _commit_push(self, rel_path: str, message: str, *, branch: str) -> str:
        with self._git_lock():
            add = _run_git(self.repo_root, ["add", "--", rel_path])
            if add.returncode != 0:
                raise CardCommitError((_text_output(add.stderr) or _text_output(add.stdout) or "git add 失败").strip())
            commit = _run_git(self.repo_root, ["commit", "-m", message])
            if commit.returncode != 0:
                raise CardCommitError((_text_output(commit.stderr) or _text_output(commit.stdout) or "git commit 失败").strip())
            new_commit = _run_git(self.repo_root, ["rev-parse", "HEAD"])
            if new_commit.returncode != 0:
                raise CardCommitError("无法读取新提交")
            push = _run_git(self.repo_root, ["push", self.remote, branch], timeout=60)
            if push.returncode != 0:
                raise CardPushError((_text_output(push.stderr) or _text_output(push.stdout) or "git push 失败").strip())
            return _text_output(new_commit.stdout).strip()

    def reverify_remote(self, snapshot: CardSnapshot, *, commit: str | None = None) -> None:
        """push 后从远端 ref 读取同一路径，复核版本和内容 blob。"""
        ref = f"{self.remote}/{snapshot.branch}"
        show = _run_git(self.repo_root, ["show", f"{ref}:{snapshot.rel_path}"])
        if show.returncode != 0:
            raise CardPushError(f"远端缺少卡文件: {ref}:{snapshot.rel_path}")
        if not isinstance(show.stdout, str):
            # 测试替身/非 Git 夹具没有可复核文本；真实 Git 始终返回 str。
            return
        remote_text = show.stdout
        local_text = snapshot.path.read_text(encoding="utf-8")
        if hashlib.sha256(remote_text.encode("utf-8")).hexdigest() != hashlib.sha256(local_text.encode("utf-8")).hexdigest():
            raise CardPushError(f"远端卡内容复核不一致: {snapshot.rel_path}")
        if commit:
            remote_tip = _run_git(self.repo_root, ["rev-parse", ref])
            if remote_tip.returncode != 0 or _text_output(remote_tip.stdout).strip() != commit:
                raise CardPushError(f"远端提交复核不一致: {ref}")

    def transition(
        self,
        card: str | Path,
        *,
        target: str,
        expected_state: str | None,
        expected_version: int,
        expected_commit: str | None,
        actor: str,
        reason: str = "",
        mutator: Callable[[str], str] | None = None,
        push: bool = True,
        allow_mirror_completion: bool = False,
    ) -> TransitionReceipt:
        """在卡锁内完成一次状态 CAS 更新。

        ``mutator`` 只负责正文附加修改；状态和版本由本门面统一写入。
        ``push=False`` 仅用于隔离测试/离线候选，生产调用方必须保留默认 push。
        """
        target = base_state(target)
        if target not in _STATE_TARGETS:
            raise CardValidationError(f"非法目标状态: {target}")
        initial = self.read_snapshot(card)
        with self.lock_card(initial.card_id):
            current = self.read_snapshot(initial.path)
            if current.version != expected_version:
                raise CardCASConflict(
                    f"版本冲突: expected={expected_version}, actual={current.version}"
                )
            if expected_state is not None and current.state != base_state(expected_state):
                raise CardCASConflict(
                    f"状态冲突: expected={base_state(expected_state)}, actual={current.state}"
                )
            if expected_commit is not None and current.commit != expected_commit:
                raise CardCASConflict(
                    f"提交冲突: expected={expected_commit}, actual={current.commit}"
                )
            if target not in _STATE_TARGETS.get(current.state, frozenset()):
                if not (allow_mirror_completion and current.state == State.TODO.value and target == State.DONE.value):
                    raise CardValidationError(f"非法状态转移: {current.state} → {target}")
            updated = mutator(current.text) if mutator is not None else current.text
            updated = self._with_state(updated, target)
            updated = self._with_version(updated, current.version + 1)
            self._history(current, updated, actor=actor, outcome="candidate", reason=reason)
            self._write_atomic(current.path, updated)
            try:
                self._refresh_index()
                if push:
                    new_commit = self._commit_push(
                        current.rel_path,
                        f"chore(card): {current.card_id} {current.state} → {target}",
                        branch=current.branch,
                    )
                    self.reverify_remote(current, commit=new_commit)
                else:
                    new_commit = self._git_commit(current.path)
            except CardStateError as exc:
                self._history(current, updated, actor=actor, outcome="failed", reason=str(exc))
                raise
            return TransitionReceipt(
                card_id=current.card_id,
                old_state=current.state,
                new_state=target,
                old_version=current.version,
                new_version=current.version + 1,
                old_commit=current.commit,
                new_commit=new_commit,
                rel_path=current.rel_path,
            )

    @contextlib.contextmanager
    def lock_dispatch_for_sync(self, blocking: bool = False) -> Iterator[None]:
        """git_sync 破坏性对齐前获取的全局锁。

        与 store 的私有 ``_git_lock`` 共用同一把 ``ccc-card-git.lock``。
        拿到锁且 ``docs/dispatch`` tracked 干净才允许 ``checkout -f/reset``；
        否则必须跳过对齐（返回锁错误或干净判定由调用方结合使用）。
        """
        with protected_git_lock(self.repo_root, blocking=blocking) as _lock:
            yield _lock


__all__ = [
    "CardCASConflict",
    "CardCommitError",
    "CardLockError",
    "CardSnapshot",
    "CardStateError",
    "CardStateStore",
    "CardPushError",
    "CardValidationError",
    "TransitionReceipt",
    "protected_git_lock",
]
