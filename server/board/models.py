"""board 视图数据模型（契约 §4）。

字段：ID / 状态 / 项目 / 执行体 / 分派时间 / 回写时间 / 打回次数。
线路图桶（P3 占位）：未开发 / 开发中 / 已开发待验收 / 已验收待确认 / 确认可用 / 有问题。
状态归桶：带括号变体（如 `打回（原因）`）按括号前基础态归桶；明细保留全串。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from server.board.registry import card_prefixes as _card_prefixes
from server.board.registry import forbidden_prefixes as _forbidden_prefixes

# 字段缺失时的容错值
UNKNOWN = "未知"
# 无「项目」字段且推导不出项目名时的归类（T53：旧卡兼容）
UNCLASSIFIED = "未分类"

# T54：PREFIXES / FORBIDDEN ← docs/projects/registry.yaml（禁止手维第二份）
PREFIXES: dict[str, str] = _card_prefixes()
FORBIDDEN_CARD_PREFIXES: frozenset[str] = _forbidden_prefixes()

# 契约 §2 五态（卡头唯一合法状态；校验用）
STATES: tuple[str, ...] = ("待分派", "执行中", "已回写", "已关闭", "打回")

# 看板列（派生视图）：「已回写」且无机审通过 →「机审」；已关闭置末
BOARD_COLUMNS: tuple[str, ...] = ("待分派", "执行中", "机审", "已回写", "打回", "已关闭")

# P3 线路图桶（占位；已验收待确认 为预留空桶）
ROADMAP_BUCKETS: tuple[str, ...] = (
    "未开发",
    "开发中",
    "已开发待验收",
    "已验收待确认",
    "确认可用",
    "有问题",
)

# 契约 §2 状态 → 线路图桶 映射（占位，P3 可调）
STATE_TO_ROADMAP: dict[str, str] = {
    "待分派": "未开发",
    "执行中": "开发中",
    "已回写": "已开发待验收",
    "已关闭": "确认可用",
    "打回": "有问题",
}


def base_state(state: str) -> str:
    """状态归一：取括号前基础态（与 loader `_strip_parenthetical` 同款逻辑）。

    - `打回（原因）` → `打回`；`待分派（实现）` → `待分派`；`已回写（有条件）` → `已回写`
    - 空值 / `未知` / 剥离后为空 → `未知`

    归桶/计数用基础态；明细（BoardItem.state / to_dict()）保留原文全串。
    """
    if not state or state.strip() == UNKNOWN:
        return UNKNOWN
    base = re.split(r"[（(]", state, maxsplit=1)[0].strip()
    return base or UNKNOWN


def machine_audit_passed_text(text: str) -> bool:
    """卡正文任一个 ``## 机审区`` 节内是否含通过标记。

    多轮机审会在同一节内追加多轮结论（历史不通过轮 + 通过轮），结论可远超
    20 行。只认首个锚点 + 短窗口会把多轮卡误判为未通过 → approve-merge 拒绝
    + 引擎反复重审（xy012 事故）。改为逐节检查至下一节标题，无行数上限。
    """
    if not text:
        return False
    lines = text.splitlines()
    n = len(lines)
    for i, line in enumerate(lines):
        if not line.strip().startswith("## 机审区"):
            continue
        for j in range(i + 1, n):
            cur = lines[j]
            if cur.strip().startswith("## "):
                break  # 下一节标题
            if "机审：通过" in cur or "✅" in cur or "判定：通过" in cur:
                return True
    return False


def board_column(state: str, machine_audit_ok: bool) -> str:
    """看板列：卡头五态派生；已回写且无机审通过 →「机审」。"""
    base = base_state(state)
    if base == "已回写" and not machine_audit_ok:
        return "机审"
    if base in BOARD_COLUMNS:
        return base
    return UNKNOWN


@dataclass(frozen=True)
class BoardItem:
    """一张任务卡派生出的看板视图行。

    Attributes:
        id: 任务卡 ID（如 T3）。
        title: 任务卡标题。
        state: 契约 §2 状态。
        project: 所属项目（「项目」字段优先，缺省从「关联」首段推导，推导不出归「未分类」）。
        executor: 执行体（括号前部分）。
        dispatched_at: 分派时间（元数据日期，YYYY-MM-DD）。
        written_at: 回写时间（回写区日期，YYYY-MM-DD）。
        reject_count: 打回次数（无显式字段按 0）。
        dispatch: 派发方式（manual|engine，缺省 engine；manual 卡由管理席派发，Engine 不自动拉）。
    """

    id: str
    title: str
    state: str = UNKNOWN
    project: str = UNCLASSIFIED
    executor: str = UNKNOWN
    dispatched_at: str = UNKNOWN
    written_at: str = UNKNOWN
    reject_count: int = 0
    dispatch: str = "engine"
    type: str = "task"
    parent: str = ""
    progress: str = ""
    thread_id: str = ""
    acceptance: str = UNKNOWN
    archived: bool = False
    machine_audit_passed: bool = False
    closed_at: str = ""

    def to_dict(self) -> dict[str, str | int | bool]:
        """转纯字典（JSON 可序列化）。"""
        col = board_column(self.state, self.machine_audit_passed)
        return {
            "id": self.id,
            "title": self.title,
            "state": self.state,
            "board_column": col,
            "machine_audit_passed": self.machine_audit_passed,
            "project": self.project,
            "executor": self.executor,
            "dispatched_at": self.dispatched_at,
            "written_at": self.written_at,
            "reject_count": self.reject_count,
            "dispatch": self.dispatch,
            "type": self.type,
            "parent": self.parent,
            "progress": self.progress,
            "thread_id": self.thread_id,
            "acceptance": self.acceptance,
            "archived": self.archived,
            "closed_at": self.closed_at,
        }
