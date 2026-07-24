"""engine/failure_router.py — 失败分类与重试预算。

方案 1.1（2026-07-24）ccc-engine.py 拆分第二阶段 + 2.3 门禁硬约束。

本模块承载：
- 异常分类（transient / permanent / quarantine）
- 统一重试 budget（MAX_TASK_RETRY_BUDGET，跨 product/review/hang/phase 各层）

未搬（强耦合，需后续独立 commit）：
- _quarantine_with_notify (ccc-engine.py:644-705, 60+ 行，与 _drop_active_task_and_slots 等全局状态紧耦合)
- _handle_short_path_failure (ccc-engine.py:568-643, 75 行)

Why not 一次拆完：failure_router 涉及 _log_stats / _ccc_notify / record_failure 等
横切关注点，搬动需引入回调或 DI 容器，工程浩大。
本批先建模块骨架 + 分类常量 + budget 常量，后续按文件单独 commit。
"""
from __future__ import annotations

from pathlib import Path

# 统一重试预算：单卡总重试次数上限（跨 product/review/hang/phase 各层）
MAX_TASK_RETRY_BUDGET = 8


_TRANSIENT_KEYWORDS = frozenset(
    {
        "timeout",
        "connection",
        "temporal",
        "retry",
        "rate limit",
        "5xx",
        "temporarily",
    }
)

_PERMANENT_KEYWORDS = frozenset(
    {
        "syntax error",
        "import error",
        "permission denied",
        "module not found",
        "name error",
    }
)


def classify_failure(exc: Exception | str) -> str:
    """分类异常为 transient / permanent / quarantine。

    Returns: 'transient' | 'permanent' | 'quarantine'
    """
    msg = str(exc).lower()
    if any(kw in msg for kw in _PERMANENT_KEYWORDS):
        return "permanent"
    if any(kw in msg for kw in _TRANSIENT_KEYWORDS):
        return "transient"
    return "quarantine"


def get_retry_budget(ws: Path, tid: str) -> int:
    """获取 task 已用重试次数（占位，后续从 store.find_task 读 retry_count）。

    Args:
        ws: workspace 路径
        tid: task id

    Returns: 当前 retry_count，未实现时返回 0
    """
    _ = (ws, tid)  # noqa: F841 — 占位实现
    # TODO[2.3]: 从 store.find_task(tid) 读 retry_count
    return 0


def can_retry(ws: Path, tid: str) -> bool:
    """检查 task 是否还在重试预算内（占位）。"""
    used = get_retry_budget(ws, tid)
    return used < MAX_TASK_RETRY_BUDGET
