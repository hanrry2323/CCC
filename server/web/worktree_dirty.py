"""执行中卡 worktree 未提交改动计数（HTTP 看板徽章用）。

对 Engine worktree 跑 ``git status --porcelain``，短超时 + 进程内短缓存，
避免看板 8s 轮询打爆磁盘。无 worktree / 非 git / 失败 → 返回 None（前端不显示）。
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import time
from pathlib import Path

from server.engine.main import get_worktree_path

logger = logging.getLogger("ccc.web.worktree_dirty")

_CACHE_TTL_S = 4.0
# work_id → (monotonic_ts, dirty_files|None)
_dirty_cache: dict[str, tuple[float, int | None]] = {}
# registry path → (mtime, bases)
_bases_cache: tuple[str, float, list[str]] | None = None


def _load_worktree_bases() -> list[str]:
    """从 EXECUTOR_REGISTRY_PATH 收集非空 worktree_base（可后台 CLI 行）。"""
    global _bases_cache
    raw = os.environ.get("EXECUTOR_REGISTRY_PATH", "").strip()
    if not raw:
        return []
    path = Path(raw).expanduser()
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return []
    if _bases_cache is not None and _bases_cache[0] == str(path) and _bases_cache[1] == mtime:
        return _bases_cache[2]
    bases: list[str] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        for row in data.get("executors") or []:
            if not isinstance(row, dict):
                continue
            if row.get("分类") != "可后台 CLI":
                continue
            base = (row.get("worktree_base") or "").strip()
            if base and base not in bases:
                bases.append(base)
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("读取执行体注册表 worktree_base 失败: %s", exc)
        bases = []
    _bases_cache = (str(path), mtime, bases)
    return bases


def resolve_worktree_dir(work_id: str) -> Path | None:
    """解析卡对应 worktree 目录；不存在返回 None。"""
    wid = (work_id or "").strip()
    if not wid:
        return None
    for base in _load_worktree_bases():
        try:
            candidate = Path(get_worktree_path(base, wid)).expanduser().resolve()
        except (OSError, ValueError):
            continue
        if candidate.is_dir():
            return candidate
    # 兼容常见默认命名（注册表未配 worktree_base 时）
    env_base = os.environ.get("CCC_WORKTREE_BASE", "").strip()
    if env_base:
        try:
            candidate = Path(get_worktree_path(env_base, wid)).expanduser().resolve()
            if candidate.is_dir():
                return candidate
        except (OSError, ValueError):
            pass
    return None


def count_dirty_files(worktree: Path, timeout: float = 2.0) -> int | None:
    """``git status --porcelain`` 行数 = 改动文件数；失败返回 None。"""
    try:
        proc = subprocess.run(
            ["git", "-C", str(worktree), "status", "--porcelain", "-uall"],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    return sum(1 for ln in proc.stdout.splitlines() if ln.strip())


def get_dirty_files(work_id: str, *, force: bool = False) -> int | None:
    """带 TTL 缓存的 dirty 文件数。"""
    wid = (work_id or "").strip()
    if not wid:
        return None
    now = time.monotonic()
    if not force:
        hit = _dirty_cache.get(wid)
        if hit is not None and now - hit[0] < _CACHE_TTL_S:
            return hit[1]
    root = resolve_worktree_dir(wid)
    if root is None:
        val: int | None = None
    else:
        val = count_dirty_files(root)
    _dirty_cache[wid] = (now, val)
    return val


def clear_dirty_cache() -> None:
    """测试用：清空缓存。"""
    global _bases_cache
    _dirty_cache.clear()
    _bases_cache = None
