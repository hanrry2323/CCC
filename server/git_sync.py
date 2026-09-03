"""生产仓自动对齐 origin/main（薄同步，供 Engine / board-scheduler）。

人只 push 卡到 GitHub；2017 侧自行 fetch/ff-only，避免「卡已推但 Engine 看不见」。

策略（零硬编码远程名时可配）：
1. ``git fetch --no-write-fetch-head <remote> <branch>``
2. 尝试 ``git merge --ff-only <remote>/<branch>``
3. 若工作树有本地改动导致 ff 失败：对 ``docs/dispatch`` 下**本地未改**的路径
   从 ``<remote>/<branch>`` checkout 更新（含新卡）；已脏路径（Engine 正在回写的卡）跳过。
   未跟踪的 .md 新卡若 mtime 距今 < 宽限窗（默认 300s，env
   ``CCC_ALIGN_GRACE_SECONDS`` 可调）则不清除，仅告警一次（同文件去重）——
   纵深防御：即使出卡方忘记提交，卡也不会无声死亡；超宽限仍存在才按原逻辑移除。

不 force、不 reset --hard、不动 ignored 配置。
"""

from __future__ import annotations

import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from server.engine.card_state_store import CardLockError, protected_git_lock

logger = logging.getLogger("ccc.git_sync")


class SyncLockedError(RuntimeError):
    """卡状态写入/Git 提交正在进行，本轮不得覆盖主仓卡。"""


def _protected_force_align(repo: Path, ref: str, dispatch_subdir: str) -> dict[str, int]:
    """拿到全局 Git 写锁才允许强制对齐；拿不到则跳过本轮，保护提交中的卡。

    返回的 dict 在锁不可得时额外带 ``{"locked": 1}``，调用方据此报告
    ``blocked``，且不得 checkout/reset/unlink。
    """
    try:
        with protected_git_lock(repo, blocking=False):
            return _force_align_dispatch(repo, ref, dispatch_subdir)
    except CardLockError as exc:
        logger.warning("git sync 跳过 dispatch 强制对齐（卡提交锁占用）: %s", exc)
        return {"removed": 0, "grace_kept": 0, "locked": 1}

# 已告警过「疑似出卡未提交」的未跟踪文件绝对路径（同文件去重，进程生命周期内有效）
_GRACE_WARNED: set[str] = set()

# 未跟踪新卡对齐宽限窗默认秒数（env CCC_ALIGN_GRACE_SECONDS 可调）
_DEFAULT_GRACE_SECONDS = 300.0


def _align_grace_seconds() -> float:
    """宽限窗秒数：env ``CCC_ALIGN_GRACE_SECONDS``，缺省 300s；非法值回退缺省，负值按 0。"""
    raw = (os.environ.get("CCC_ALIGN_GRACE_SECONDS") or "").strip()
    if not raw:
        return _DEFAULT_GRACE_SECONDS
    try:
        return max(0.0, float(raw))
    except ValueError:
        logger.warning("CCC_ALIGN_GRACE_SECONDS=%r 非法，回退 %ss", raw, _DEFAULT_GRACE_SECONDS)
        return _DEFAULT_GRACE_SECONDS


def _run(repo: Path, args: list[str], timeout: float = 60.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def resolve_repo_root(dispatch_dir: str | Path) -> Path:
    """``…/docs/dispatch`` → 仓根；其它路径则向上找 ``.git``。"""
    d = Path(dispatch_dir).expanduser().resolve()
    if d.name == "dispatch" and d.parent.name == "docs":
        return d.parent.parent
    cur = d if d.is_dir() else d.parent
    for p in [cur, *cur.parents]:
        if (p / ".git").exists():
            return p
    return cur


def _porcelain_paths(repo: Path) -> set[str]:
    res = _run(repo, ["status", "--porcelain", "-uall"])
    if res.returncode != 0:
        return set()
    out: set[str] = set()
    for ln in res.stdout.splitlines():
        if len(ln) < 4:
            continue
        path = ln[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[-1].strip()
        if path:
            out.add(path)
    return out


def sync_origin_main(
    repo_root: str | Path,
    *,
    remote: str | None = None,
    branch: str | None = None,
    dispatch_subdir: str = "docs/dispatch",
) -> dict[str, Any]:
    """对齐远程主分支；返回摘要（ok / method / detail）。"""
    repo = Path(repo_root).expanduser().resolve()
    remote = (remote or os.environ.get("CCC_AUTO_PULL_REMOTE") or "origin").strip() or "origin"
    branch = (branch or os.environ.get("CCC_AUTO_PULL_BRANCH") or "main").strip() or "main"
    summary: dict[str, Any] = {
        "ok": False,
        "method": "none",
        "remote": remote,
        "branch": branch,
        "repo": str(repo),
        "detail": "",
    }
    if not (repo / ".git").exists():
        summary["detail"] = "not a git repo"
        return summary

    try:
        # --no-write-fetch-head：不写 .git/FETCH_HEAD，避免与 deploy-ccc.sh 的
        # 拉取段并发无锁写同一文件导致「Cannot fast-forward to multiple branches」。
        fetched = _run(repo, ["fetch", "--no-write-fetch-head", remote, branch], timeout=120.0)
    except (OSError, subprocess.TimeoutExpired) as exc:
        summary["detail"] = f"fetch failed: {exc}"
        logger.warning("git sync fetch failed: %s", exc)
        return summary
    if fetched.returncode != 0:
        summary["detail"] = (fetched.stderr or fetched.stdout or "fetch nonzero").strip()[:300]
        logger.warning("git sync fetch nonzero: %s", summary["detail"])
        return summary

    ref = f"{remote}/{branch}"
    try:
        merged = _run(repo, ["merge", "--ff-only", ref], timeout=60.0)
    except (OSError, subprocess.TimeoutExpired) as exc:
        summary["detail"] = f"ff-only failed: {exc}"
        logger.warning("git sync ff-only failed: %s", exc)
        return summary

    if merged.returncode == 0:
        align = _protected_force_align(repo, ref, dispatch_subdir)
        if align.get("locked"):
            summary["ok"] = False
            summary["method"] = "blocked"
            summary["detail"] = "git sync blocked: 卡状态提交/Git 写锁占用，跳过 dispatch 强制对齐"
            logger.warning("git sync ff-only 后对齐被锁跳过: %s", summary["detail"])
            return summary
        summary["ok"] = True
        summary["method"] = "ff-only"
        summary["detail"] = (merged.stdout or "up to date").strip()[:300]
        logger.info("git sync ff-only ok: %s", summary["detail"] or "ok")
        return summary

    # ff 失败：卡文件始终以 main 为准——本地卡状态已迁到运行时 sidecar + 分支信封，
    # 主树只做 main 镜像（丢弃本地卡改动，杜绝 pull 冲突与批注被脏卡挡住的场景）。
    diff = _run(repo, ["diff", "--name-only", f"HEAD...{ref}", "--", dispatch_subdir])
    if diff.returncode != 0:
        summary["detail"] = (merged.stderr or "ff-only blocked; diff failed").strip()[:300]
        logger.warning("git sync blocked: %s", summary["detail"])
        return summary

    align = _protected_force_align(repo, ref, dispatch_subdir)
    removed_untracked = align["removed"]
    grace_kept = align["grace_kept"]
    sync_locked = bool(align.get("locked"))
    updated = diff.stdout.splitlines()
    updated = [rel.strip() for rel in updated if rel.strip()]

    if sync_locked:
        # 提交锁被占用：本轮跳过破坏性对齐与 retry-merge（进度归文件并保留候选卡）
        summary["ok"] = False
        summary["method"] = "blocked"
        summary["updated"] = updated
        summary["removed_untracked"] = 0
        summary["grace_kept"] = 0
        summary["detail"] = (
            "git sync blocked: 卡状态提交/Git 写锁占用，跳过 dispatch 强制对齐，"
            "保留待提交卡现场"
        ).strip()[:300]
        logger.warning("git sync dispatch 对齐被锁跳过: %s", summary["detail"])
        return summary

    # 清理后重试 ff-only（卡文件已对齐，剩余阻挡仅限非 dispatch 路径）
    merged_retry = _run(repo, ["merge", "--ff-only", ref], timeout=60.0)
    summary["ok"] = merged_retry.returncode == 0 or bool(updated) or not diff.stdout.strip()
    summary["method"] = "dispatch-checkout"
    summary["updated"] = updated
    summary["removed_untracked"] = removed_untracked
    summary["grace_kept"] = grace_kept
    summary["detail"] = (
        f"ff-only blocked; force-checked out {len(updated)} dispatch path(s), "
        f"removed {removed_untracked} untracked (grace-kept {grace_kept}); "
        f"retry ff rc={merged_retry.returncode}"
    ).strip()[:300]
    logger.warning("git sync dispatch force-sync: %s", summary["detail"])
    return summary


def _force_align_dispatch(repo: Path, ref: str, dispatch_subdir: str) -> dict[str, int]:
    """强制让 dispatch 目录与 ref 完全一致（主树只做 main 镜像）。

    树已干净（无 tracked/untracked 变化）→ 零触碰直接返回（避免文件 mtime 抖动
    导致看板缓存键每轮失效、/cards 反复全量重建吃 CPU）。
    否则清 staged 条目 → force checkout 全部 dispatch 路径 → 移除未跟踪文件。
    宽限窗纵深防御：未跟踪 .md 新卡 mtime 距今 < ``CCC_ALIGN_GRACE_SECONDS``
    （默认 300s）不清除，仅 warning 一次（同文件去重，含「疑似出卡未提交」提示）；
    超宽限仍存在才按原逻辑移除——即使出卡方忘记提交，卡也不会无声死亡。
    返回 ``{"removed": 移除数, "grace_kept": 宽限窗内保留数}``。
    """
    dirty = _run(
        repo,
        ["status", "--porcelain", "--", dispatch_subdir],
        timeout=30.0,
    )
    if dirty.returncode == 0 and not dirty.stdout.strip():
        return {"removed": 0, "grace_kept": 0}
    _run(repo, ["reset", "-q", "--", dispatch_subdir], timeout=30.0)
    _run(repo, ["checkout", "-f", ref, "--", dispatch_subdir], timeout=60.0)
    untracked = _run(
        repo,
        ["ls-files", "--others", "--exclude-standard", "--", dispatch_subdir],
        timeout=30.0,
    )
    grace = _align_grace_seconds()
    now = time.time()
    removed = 0
    grace_kept = 0
    for rel in untracked.stdout.splitlines():
        rel = rel.strip()
        if not rel:
            continue
        path = repo / rel
        age: float | None
        try:
            # 钳制负值：未来 mtime（时钟偏斜/回拨）按刚落盘处理，
            # 保证 grace=0（关闭宽限）时仍走原立即清除语义。
            age = max(0.0, now - path.stat().st_mtime)
        except OSError:
            age = None  # 文件已消失等：按原逻辑走移除尝试
        if age is not None and rel.endswith(".md") and age < grace:
            key = str(path)
            if key not in _GRACE_WARNED:
                _GRACE_WARNED.add(key)
                logger.warning(
                    "git sync 对齐跳过宽限窗内未跟踪新卡 %s（mtime 距今 %.0fs < %.0fs）"
                    "——疑似出卡未提交，暂不清除",
                    rel,
                    age,
                    grace,
                )
            grace_kept += 1
            continue
        try:
            path.unlink(missing_ok=True)
            removed += 1
        except OSError:
            logger.warning("git sync 清理未跟踪卡失败: %s", rel)
    return {"removed": removed, "grace_kept": grace_kept}


def auto_pull_enabled(cfg: dict[str, Any] | None = None) -> bool:
    """``CCC_AUTO_PULL``：``1/true/yes/on`` 开启。

    - ``cfg`` 含键 → 只看 cfg（生产 ``load_config`` 默认 1）
    - ``cfg`` 传入但不含键 → **关**（单测残缺 cfg，避免误 fetch 开发仓）
    - ``cfg is None`` → 看环境变量，缺省 1
    """
    if cfg is not None:
        if "CCC_AUTO_PULL" not in cfg:
            return False
        raw = str(cfg.get("CCC_AUTO_PULL") or "").strip().lower()
        return raw in ("1", "true", "yes", "on")
    raw = os.environ.get("CCC_AUTO_PULL", "1").strip().lower()
    return raw in ("1", "true", "yes", "on")
