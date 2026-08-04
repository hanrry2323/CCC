"""board 视图数据模型（契约 §4）。

字段：ID / 状态 / 项目 / 执行体 / 分派时间 / 回写时间 / 打回次数。
线路图桶（P3 占位）：未开发 / 开发中 / 已开发待验收 / 已验收待确认 / 确认可用 / 有问题。
状态归桶：带括号变体（如 `打回（原因）`）按括号前基础态归桶；明细保留全串。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# 字段缺失时的容错值
UNKNOWN = "未知"
# 无「项目」字段且推导不出项目名时的归类（T53：旧卡兼容）
UNCLASSIFIED = "未分类"

# T54 命名规则：项目前缀表（前缀 = 子目录名 = 文件名前缀；T-mapping.md 有完整映射）
# 展示名与缩写并存的项以前缀为准（`项目` 字段 = 前缀，与旧卡 `项目：ccc` 一致）。
PREFIXES: dict[str, str] = {
    "qb": "qb",
    "qh": "QuantHive",
    "ccc": "ccc",
    "mx": "medio-0",
    "xy": "xianyu",
    "hp": "知识库",
    "tst": "临时测试",
}

# 契约 §2 五态
STATES: tuple[str, ...] = ("待分派", "执行中", "已回写", "已关闭", "打回")

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

    def to_dict(self) -> dict[str, str | int]:
        """转纯字典（JSON 可序列化）。"""
        return {
            "id": self.id,
            "title": self.title,
            "state": self.state,
            "project": self.project,
            "executor": self.executor,
            "dispatched_at": self.dispatched_at,
            "written_at": self.written_at,
            "reject_count": self.reject_count,
            "dispatch": self.dispatch,
            "type": self.type,
            "parent": self.parent,
            "progress": self.progress,
        }
