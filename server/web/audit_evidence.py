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
from server.board.models import base_state

logger = logging.getLogger("ccc.web.audit_evidence")

_CACHE_TTL_S = 45.0
# branch → (monotonic_ts, passed|None)
_branch_cache: dict[str, tuple[float, bool | None]] = {}
# 分支卡头状态缓存（2026-08-12 · 看板合成状态权威）
_state_cache: dict[str, tuple[float, str]] = {}


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
        if res.returncode == 0 and machine_audit_passed_text(res.stdout):
            # P0 硬化（2026-08-22）：机审真值 = 账本 machine_audit_pass；卡文仅作提示。
            # 卡文「机审：通过」但账本无记录（执行体自写伪造）→ 不算通过，防假关闭复发。
            import re as _re

            from server.board.audit_ledger import has_pass

            _m = _re.match(r"^([a-z]{2,4}\d{3})", branch.removeprefix("codex/"))
            card_id = _m.group(1) if _m else ""
            passed = has_pass(card_id) if card_id else False
    except Exception:
        passed = None
    _branch_cache[branch] = (now, passed)
    return passed


def branch_card_state(repo_root: Path, card_rel: str, branch: str) -> str:
    """分支 tip 卡头状态（已回写/已关闭/打回）；分支不存在/读取失败 → 空串。

    与 engine ``store._branch_envelope_state`` 同语义，供看板合成视图使用：
    磁盘 main 镜像未合入前永远旧值，终态真值在执行体 push 的 codex 分支卡里。
    """
    now = time.monotonic()
    hit = _state_cache.get(branch)
    if hit is not None and now - hit[0] < _CACHE_TTL_S:
        return hit[1]
    state = ""
    try:
        res = subprocess.run(
            ["git", "-C", str(repo_root), "show", f"origin/{branch}:{card_rel}"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if res.returncode == 0:
            from server.board.card_header import parse_metadata

            meta = parse_metadata(res.stdout)
            raw = (meta.get("状态") or "").strip()
            if base_state(raw) in ("已回写", "已关闭", "打回"):
                state = raw
    except Exception:
        state = ""
    _state_cache[branch] = (now, state)
    return state


def clear_audit_evidence_cache() -> None:
    _branch_cache.clear()
    _state_cache.clear()
