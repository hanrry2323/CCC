"""engine/failure_router.py — 失败分类与重试预算。

方案 1.1（2026-07-24）ccc-engine.py 拆分第二阶段 + 2.3 门禁硬约束。

本模块承载：
- 异常分类（transient / permanent / quarantine）
- 统一重试 budget（MAX_TASK_RETRY_BUDGET，跨 product/review/hang/phase 各层）
- Tester 结果文件解析（门禁硬约束）

调用方（2026-07-24 本批未替换）：ccc-engine.py 内 _try_launch_planned /
_relaunch_allowed / _run_reviewer_tester_gate 等在重试前先调 increment_retry_count
检查 budget。后续 commit 逐步替换。

未搬（强耦合，需后续独立 commit）：
- _quarantine_with_notify (ccc-engine.py:644-705)
- _handle_short_path_failure (ccc-engine.py:568-643)
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from _board_store import FileBoardStore

# 统一重试预算：单卡总重试次数上限（跨 product/review/hang/phase 各层）
MAX_TASK_RETRY_BUDGET = 8


class RetryBudgetExceeded(Exception):
    """单卡重试预算耗尽。"""


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


def get_retry_budget(ws: Path, tid: str, store: FileBoardStore | None = None) -> int:
    """获取 task 已用重试次数。

    Args:
        ws: workspace 路径
        tid: task id
        store: 可选 FileBoardStore；为 None 时用 ws 自己创建

    Returns: task JSONL 中 retry_count 字段；缺失返回 0
    """
    if store is None:
        from _board_store import FileBoardStore

        store = FileBoardStore(ws)
    col, task = store.find_task(tid)
    if not task:
        return 0
    raw = task.get("retry_count", 0)
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 0


# 2026-07-24：in-process 计数缓存（store 无 update_task 时用）
# 键：(ws, tid)，值：已递增次数
_inproc_retry: dict[tuple[str, str], int] = {}


def increment_retry_count(
    ws: Path,
    tid: str,
    store: FileBoardStore | None = None,
) -> int:
    """递增 task 的重试计数器，返回新值。

    超过 MAX_TASK_RETRY_BUDGET 时抛 RetryBudgetExceeded。

    注：本批实现优先用 in-process 计数缓存（_inproc_retry），fallback 到
    store.find_task 的 retry_count 字段。store 无 update_task 方法，
    后续 commit 加 store.update_task 后才会真持久化到 task JSONL。
    """
    key = (str(ws.resolve()), tid)
    persisted = get_retry_budget(ws, tid, store)
    inproc = _inproc_retry.get(key, 0)
    current = max(persisted, inproc)
    new_count = current + 1
    if new_count > MAX_TASK_RETRY_BUDGET:
        raise RetryBudgetExceeded(
            f"task {tid} retry budget exceeded: "
            f"{new_count}/{MAX_TASK_RETRY_BUDGET}"
        )
    _inproc_retry[key] = new_count
    return new_count


def can_retry(ws: Path, tid: str, store: FileBoardStore | None = None) -> bool:
    """检查 task 是否还在重试预算内（不递增）。"""
    used = get_retry_budget(ws, tid, store)
    return used < MAX_TASK_RETRY_BUDGET


# ── Tester 结果检查（2026-07-24 方案 2.3.2）───────────────────


def _tester_result_file(ws: Path, tid: str) -> Path:
    """tester 结果文件路径。"""
    return ws / ".ccc" / "verdicts" / f"{tid}.tester.md"


def parse_tester_result(ws: Path, tid: str) -> str | None:
    """解析 tester 结果文件。

    Returns: 'PASS' | 'FAIL' | 'SKIP' | None（文件不存在）
    """
    tf = _tester_result_file(ws, tid)
    if not tf.is_file():
        return None
    try:
        content = tf.read_text(encoding="utf-8")
    except OSError:
        return None
    for line in content.splitlines():
        low = line.strip().lower()
        if low.startswith("**result:**") or low.startswith("result:"):
            raw = line.strip().split(":", 1)[1].strip().strip("*").strip()
            return raw.split()[0].upper() if raw else None
    return None
