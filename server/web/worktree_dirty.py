"""执行中卡 worktree 改动指标（HTTP 看板徽章用）。

对 Engine worktree 跑 ``git status --porcelain`` 与 ``git diff --numstat``，
短超时 + 进程内短缓存，避免看板轮询打爆磁盘。

前端徽章：
- ΔN = 未提交改动**文件数**（不是大模型调用次数）
- +X/−Y = 行变更（工作区优先；干净时可用相对 origin/main 的已提交 diff）

无 worktree / 非 git / 失败 → 对应字段 None（前端不显示）。

注册表路径解析顺序：
1. 环境变量 ``EXECUTOR_REGISTRY_PATH``（可相对仓根）
2. ``CCC_CONFIG_ENV`` → ``load_config`` 取同名键（web-server 通常只注入 CCC_CONFIG_ENV）
``CCC_WORKTREE_BASE`` 同样可从 config.env 回落。
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
# config.env mtime 缓存，避免每请求 load_config
_config_fallback_cache: tuple[str, float, str, str] | None = None


def _project_root_from_config(cfg_path: Path) -> Path:
    """``…/server/config/config.env`` → 仓根 ``…/``。"""
    return cfg_path.resolve().parent.parent.parent


def _config_fallback() -> tuple[str, str]:
    """从 CCC_CONFIG_ENV 回落 registry 路径与 worktree_base（空串表示未配）。"""
    global _config_fallback_cache
    raw_cfg = os.environ.get("CCC_CONFIG_ENV", "").strip()
    if not raw_cfg:
        return "", ""
    cfg_path = Path(raw_cfg).expanduser()
    try:
        mtime = cfg_path.stat().st_mtime
    except OSError:
        return "", ""
    if (
        _config_fallback_cache is not None
        and _config_fallback_cache[0] == str(cfg_path.resolve())
        and _config_fallback_cache[1] == mtime
    ):
        return _config_fallback_cache[2], _config_fallback_cache[3]
    registry = ""
    wt_base = ""
    try:
        from server.config.loader import load_config

        cfg = load_config(cfg_path)
        registry = (cfg.get("EXECUTOR_REGISTRY_PATH") or "").strip()
        wt_base = (cfg.get("CCC_WORKTREE_BASE") or "").strip()
        root = _project_root_from_config(cfg_path)
        if registry and not Path(registry).expanduser().is_absolute():
            registry = str((root / registry).resolve())
    except Exception as exc:
        logger.warning("从 CCC_CONFIG_ENV 回落 worktree 配置失败: %s", exc)
        registry, wt_base = "", ""
    _config_fallback_cache = (str(cfg_path.resolve()), mtime, registry, wt_base)
    return registry, wt_base


def _registry_file() -> Path | None:
    """解析执行体注册表绝对路径；不存在返回 None。"""
    raw = os.environ.get("EXECUTOR_REGISTRY_PATH", "").strip()
    cfg_registry, _ = _config_fallback()
    if not raw:
        raw = cfg_registry
    if not raw:
        return None
    path = Path(raw).expanduser()
    if not path.is_absolute():
        cfg_env = os.environ.get("CCC_CONFIG_ENV", "").strip()
        if cfg_env:
            path = _project_root_from_config(Path(cfg_env).expanduser()) / path
        else:
            path = Path.cwd() / path
    try:
        path = path.resolve()
    except OSError:
        return None
    return path if path.is_file() else None


def _worktree_base_env() -> str:
    raw = os.environ.get("CCC_WORKTREE_BASE", "").strip()
    if raw:
        return raw
    _, wt = _config_fallback()
    return wt


def _load_worktree_bases() -> list[str]:
    """从执行体注册表收集非空 worktree_base（可后台 CLI 行）。"""
    global _bases_cache
    path = _registry_file()
    if path is None:
        return []
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
    env_base = _worktree_base_env()
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


def _numstat_sum(worktree: Path, args: list[str], timeout: float = 2.0) -> tuple[int, int] | None:
    """解析 ``git diff --numstat`` 的 +/- 行合计。"""
    try:
        proc = subprocess.run(
            ["git", "-C", str(worktree), *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    ins = dele = 0
    for ln in proc.stdout.splitlines():
        parts = ln.split("\t")
        if len(parts) < 3:
            continue
        a, b = parts[0], parts[1]
        if a.isdigit():
            ins += int(a)
        if b.isdigit():
            dele += int(b)
    return ins, dele


def count_line_churn(worktree: Path, timeout: float = 2.0) -> tuple[int, int] | None:
    """工作区相对 HEAD 的行变更（暂存+未暂存）。返回 (insertions, deletions)。

    ``git diff --numstat`` = WT vs index；``git diff --cached --numstat`` = index vs HEAD；
    两者相加 = WT vs HEAD（未跟踪文件不计行）。
    """
    wt = _numstat_sum(worktree, ["diff", "--numstat"], timeout=timeout)
    staged = _numstat_sum(worktree, ["diff", "--numstat", "--cached"], timeout=timeout)
    if wt is None and staged is None:
        return None
    wi, wd = wt or (0, 0)
    si, sd = staged or (0, 0)
    return wi + si, wd + sd


def count_branch_line_churn(worktree: Path, timeout: float = 2.0) -> tuple[int, int] | None:
    """相对 origin/main 的分支行变更（已提交 diff）。"""
    return _numstat_sum(
        worktree,
        ["diff", "--numstat", "origin/main...HEAD"],
        timeout=timeout,
    )


# work_id → (monotonic_ts, metrics)
_metrics_cache: dict[str, tuple[float, dict[str, int | None]]] = {}


def get_worktree_metrics(work_id: str, *, force: bool = False) -> dict[str, int | None]:
    """dirty 文件数 + 行变更（工作区 / 分支）。

    返回键：dirty_files, lines_insert, lines_delete, branch_insert, branch_delete。
    """
    wid = (work_id or "").strip()
    empty = {
        "dirty_files": None,
        "lines_insert": None,
        "lines_delete": None,
        "branch_insert": None,
        "branch_delete": None,
    }
    if not wid:
        return empty
    now = time.monotonic()
    if not force:
        hit = _metrics_cache.get(wid)
        if hit is not None and now - hit[0] < _CACHE_TTL_S:
            return hit[1]
    root = resolve_worktree_dir(wid)
    if root is None:
        val = empty
    else:
        dirty = count_dirty_files(root)
        churn = count_line_churn(root)
        branch = count_branch_line_churn(root)
        val = {
            "dirty_files": dirty,
            "lines_insert": None if churn is None else churn[0],
            "lines_delete": None if churn is None else churn[1],
            "branch_insert": None if branch is None else branch[0],
            "branch_delete": None if branch is None else branch[1],
        }
        # 与旧缓存对齐
        _dirty_cache[wid] = (now, dirty)
    _metrics_cache[wid] = (now, val)
    return val


def get_dirty_files(work_id: str, *, force: bool = False) -> int | None:
    """带 TTL 缓存的 dirty 文件数。"""
    return get_worktree_metrics(work_id, force=force).get("dirty_files")


def clear_dirty_cache() -> None:
    """测试用：清空缓存。"""
    global _bases_cache, _config_fallback_cache
    _dirty_cache.clear()
    _metrics_cache.clear()
    _bases_cache = None
    _config_fallback_cache = None
