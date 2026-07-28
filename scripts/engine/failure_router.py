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

from dataclasses import dataclass
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

    2026-07-25 修 P0-1:默认无关键词命中按 transient(宁可错重试也不漏);
    caller 用 == "permanent" 显式拦截,== "transient" 显式重试,quarantine
    留给显式 caller 主动隔离,本函数不主动判。
    """
    msg = str(exc).lower()
    if any(kw in msg for kw in _PERMANENT_KEYWORDS):
        return "permanent"
    if any(kw in msg for kw in _TRANSIENT_KEYWORDS):
        return "transient"
    return "transient"  # P0-1 修复:由 transient 改为"宁可错重试"


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
    _, task = store.find_task(tid)
    if not task:
        return 0
    raw = task.get("retry_count", 0)
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 0


def increment_retry_count(
    ws: Path,
    tid: str,
    store: FileBoardStore | None = None,
) -> int:
    """递增 task 的重试计数器并持久化到 task JSONL，返回新值。

    读完当前 retry_count → +1 → 调 store.patch_task 写回 task JSONL。
    超过 MAX_TASK_RETRY_BUDGET 时抛 RetryBudgetExceeded。

    2026-07-28 重构：删 _inproc_retry 缓存，直接持久化到 store。
    利用现有 patch_task 做原子读-改-写（锁 + tempfile + rename）。
    """
    if store is None:
        from _board_store import FileBoardStore

        store = FileBoardStore(ws)
    current = get_retry_budget(ws, tid, store)
    new_count = current + 1
    if new_count > MAX_TASK_RETRY_BUDGET:
        raise RetryBudgetExceeded(
            f"task {tid} retry budget exceeded: "
            f"{new_count}/{MAX_TASK_RETRY_BUDGET}"
        )
    if not store.patch_task(tid, {"retry_count": new_count}):
        raise RuntimeError(
            f"task {tid} not found in store — "
            f"cannot persist retry_count={new_count}"
        )
    return new_count


# ── auto-refeed 纯函数（Phase A: 可测试边界）────────────────────


@dataclass
class RefeedDecision:
    """Result of _should_auto_refeed check."""

    should: bool = False
    reason: str = ""
    """Machine-readable skip reason; empty when should=True."""


_EXHAUSTED_KEYWORDS = frozenset(
    {
        "reviewer_fail_loop_exhausted",
        "tester_fail_loop_exhausted",
        "fail_loop_exhausted",
        "重试耗尽",
        "次全部失败",
        "missing plan",
        "缺 plan",
        "缺 phases",
    }
)


def should_auto_refeed(
    *,
    card_kind: str,
    reason: str,
    auto_retried: int,
    max_auto_retry: int = 2,
    has_pack_or_transient: bool = True,
) -> RefeedDecision:
    """Pure-function gate for _retry_abnormal_failures: should a card be auto-refeed?

    Returns RefeedDecision — ``.should`` True only when ALL rules pass.

    Rules (hard-coded):
    - epic cards never refeed
    - exhausted/permanent reason keywords → skip
    - ``has_pack_or_transient`` (caller provides pack-exists or transient keyword hit) → skip
    - ``auto_retried >= max_auto_retry`` → skip
    """
    if card_kind == "epic":
        return RefeedDecision(should=False, reason="epic")
    low = (reason or "").lower()
    if any(m.lower() in low for m in _EXHAUSTED_KEYWORDS):
        return RefeedDecision(should=False, reason="exhausted_keyword")
    if classify_failure(reason) == "permanent":
        return RefeedDecision(should=False, reason="permanent")
    if not has_pack_or_transient:
        return RefeedDecision(should=False, reason="no_pack_or_transient")
    if auto_retried >= max_auto_retry:
        return RefeedDecision(should=False, reason=f"max_retry_reached({auto_retried})")
    return RefeedDecision(should=True, reason="")


def can_retry(ws: Path, tid: str, store: FileBoardStore | None = None) -> bool:
    """检查 task 是否还在重试预算内（只读不写）。

    读 task JSONL 的 retry_count 字段。caller 仍负责递增
    (用 increment_retry_count)，本函数只读，适合调度前预探。
    """
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
