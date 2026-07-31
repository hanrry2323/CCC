"""CCC 最小可跑通 v1 — 开关与五态别名。

权威：docs/product/loop-engineer-authority.md「最小可跑通 v1」。
默认 CCC_MIN_PIPELINE=1（开）。设 0/false/off 回退叠层自愈史径。
"""

from __future__ import annotations

import os
from typing import Final

# 产品语义 → 磁盘列（兼容现有 FileBoardStore）
SEMANTIC_TO_COLUMN: Final[dict[str, str]] = {
    "queued": "backlog",
    "plan": "planned",
    "code": "in_progress",
    "verify": "testing",
    "done": "released",
    "blocked": "abnormal",
}

COLUMN_TO_SEMANTIC: Final[dict[str, str]] = {
    "backlog": "queued",
    "planned": "plan",
    "in_progress": "code",
    "testing": "verify",
    "verified": "verify",  # 过渡列：仍算 verify 完成态前
    "released": "done",
    "abnormal": "blocked",
}


def enabled() -> bool:
    """最小可跑通热路径是否开启（默认 True）。"""
    raw = (os.environ.get("CCC_MIN_PIPELINE") or "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def l3b_repair_queue_enabled() -> bool:
    """L3b repair-queue 入队：最小路径下默认关；显式 CCC_L3B_REPAIR_QUEUE=1 才开。"""
    if not enabled():
        return True  # 史径：叠层自愈开
    raw = (os.environ.get("CCC_L3B_REPAIR_QUEUE") or "0").strip().lower()
    return raw in ("1", "true", "yes", "on")


def flywheel_auto_open_enabled() -> bool:
    """飞轮自动开下一目标：最小路径默认关。"""
    if not enabled():
        return True
    raw = (os.environ.get("CCC_FLYWHEEL_AUTO") or "0").strip().lower()
    return raw in ("1", "true", "yes", "on")


def semantic_of(column: str) -> str:
    return COLUMN_TO_SEMANTIC.get(str(column or "").strip(), str(column or ""))


def column_of(semantic: str) -> str:
    return SEMANTIC_TO_COLUMN.get(str(semantic or "").strip(), str(semantic or ""))


def semantic_counts(column_counts: dict[str, int]) -> dict[str, int]:
    """Map disk column counts → product five-state counts (for Hub/Desktop)."""
    out: dict[str, int] = {
        "queued": 0,
        "plan": 0,
        "code": 0,
        "verify": 0,
        "done": 0,
        "blocked": 0,
    }
    for col, n in (column_counts or {}).items():
        sem = semantic_of(str(col))
        if sem in out:
            out[sem] += int(n or 0)
        elif str(col) in out:
            out[str(col)] += int(n or 0)
    return out
