"""分支信封机审证据（web 只读层）。

机审证据已 git 化：通过标记随 ``origin/codex/<分支>`` 卡文件走。
本模块用 ``git show`` 校验分支 tip 卡是否含「机审：通过」，TTL 缓存避免
看板轮询每 5s 重复跑 git（沿用 worktree_dirty 同款节流思路）。
"""

from __future__ import annotations

import logging
import subprocess
import time
from pathlib import Path

from server.board.models import machine_audit_passed_text

logger = logging.getLogger("ccc.web.audit_evidence")

_CACHE_TTL_S = 20.0
# branch → (monotonic_ts, passed|None)
_branch_cache: dict[str, tuple[float, bool | None]] = {}


def branch_card_audit_passed(
    repo_root: Path,
    card_rel: str,
    branch: str,
) -> bool | None:
    """分支 tip 卡含「机审：通过」→ True；分支不存在/读取失败 → None。"""
    now = time.monotonic()
    hit = _branch_cache.get(branch)
    if hit is not None and now - hit[0] < _CACHE_TTL_S:
        return hit[1]
    passed: bool | None = None
    try:
        res = subprocess.run(
            ["git", "-C", str(repo_root), "show", f"origin/{branch}:{card_rel}"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if res.returncode == 0:
            passed = machine_audit_passed_text(res.stdout)
    except Exception:
        passed = None
    _branch_cache[branch] = (now, passed)
    return passed


def clear_audit_evidence_cache() -> None:
    _branch_cache.clear()
