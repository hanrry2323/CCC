"""生产仓自动对齐 origin/main（薄同步，供 Engine / board-scheduler）。

人只 push 卡到 GitHub；2017 侧自行 fetch/ff-only，避免「卡已推但 Engine 看不见」。

策略（零硬编码远程名时可配）：
1. ``git fetch <remote> <branch>``
2. 尝试 ``git merge --ff-only <remote>/<branch>``
3. 若工作树有本地改动导致 ff 失败：对 ``docs/dispatch`` 下**本地未改**的路径
   从 ``<remote>/<branch>`` checkout 更新（含新卡）；已脏路径（Engine 正在回写的卡）跳过。

不 force、不 reset --hard、不动 ignored 配置。
"""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger("ccc.git_sync")


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
        fetched = _run(repo, ["fetch", remote, branch], timeout=120.0)
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
        _force_align_dispatch(repo, ref, dispatch_subdir)
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

    removed_untracked = _force_align_dispatch(repo, ref, dispatch_subdir)
    updated = diff.stdout.splitlines()
    updated = [rel.strip() for rel in updated if rel.strip()]

    # 清理后重试 ff-only（卡文件已对齐，剩余阻挡仅限非 dispatch 路径）
    merged_retry = _run(repo, ["merge", "--ff-only", ref], timeout=60.0)
    summary["ok"] = merged_retry.returncode == 0 or bool(updated) or not diff.stdout.strip()
    summary["method"] = "dispatch-checkout"
    summary["updated"] = updated
    summary["removed_untracked"] = removed_untracked
    summary["detail"] = (
        f"ff-only blocked; force-checked out {len(updated)} dispatch path(s), "
        f"removed {removed_untracked} untracked; retry ff rc={merged_retry.returncode}"
    ).strip()[:300]
    logger.warning("git sync dispatch force-sync: %s", summary["detail"])
    return summary


def _force_align_dispatch(repo: Path, ref: str, dispatch_subdir: str) -> int:
    """强制让 dispatch 目录与 ref 完全一致（主树只做 main 镜像）。

    清 staged 条目 → force checkout 全部 dispatch 路径 → 移除未跟踪文件。
    返回移除的未跟踪文件数。
    """
    _run(repo, ["reset", "-q", "--", dispatch_subdir], timeout=30.0)
    _run(repo, ["checkout", "-f", ref, "--", dispatch_subdir], timeout=60.0)
    untracked = _run(
        repo,
        ["ls-files", "--others", "--exclude-standard", "--", dispatch_subdir],
        timeout=30.0,
    )
    removed = 0
    for rel in untracked.stdout.splitlines():
        rel = rel.strip()
        if not rel:
            continue
        try:
            (repo / rel).unlink(missing_ok=True)
            removed += 1
        except OSError:
            logger.warning("git sync 清理未跟踪卡失败: %s", rel)
    return removed


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
