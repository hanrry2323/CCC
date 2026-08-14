"""board 视图数据模型（契约 §4）。

字段：ID / 状态 / 项目 / 执行体 / 分派时间 / 回写时间 / 打回次数。
线路图桶（P3 占位）：未开发 / 开发中 / 已开发待验收 / 已验收待确认 / 确认可用 / 有问题。
状态归桶：带括号变体（如 `打回（原因）`）按括号前基础态归桶；明细保留全串。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from server.board.registry import card_prefixes as _card_prefixes
from server.board.registry import forbidden_prefixes as _forbidden_prefixes

# 字段缺失时的容错值
UNKNOWN = "未知"
# 无「项目」字段且推导不出项目名时的归类（T53：旧卡兼容）
UNCLASSIFIED = "未分类"

# T54：PREFIXES / FORBIDDEN ← docs/projects/registry.yaml（禁止手维第二份）
PREFIXES: dict[str, str] = _card_prefixes()
FORBIDDEN_CARD_PREFIXES: frozenset[str] = _forbidden_prefixes()

# 契约 §2 六态（卡头唯一合法状态；校验用）
# 人审调整动作统一化（2026-08-14）：新增「作废」终态——人审取消单卡（待分派/执行中/已回写/打回均可作废）。
STATES: tuple[str, ...] = ("待分派", "执行中", "已回写", "已关闭", "打回", "作废")

# 看板列（派生视图）：「已回写」且无机审通过 →「机审」；已关闭/作废置末
BOARD_COLUMNS: tuple[str, ...] = ("待分派", "执行中", "机审", "已回写", "打回", "已关闭", "作废")

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
    """卡正文任一个 ``## 机审区`` 节内是否含通过标记（A 判定真值）。

    判定规则：
    1. 只认结论行：忽略表格行（以 `|` 开头的行）、小节标题（`###` 开头）、纯描述文本。
    2. 多轮追加：同一节内若有多轮结论，以该节内最后出现的结论行为准。
    3. 噪声排除：不认 `✅` 字符、`通过项`、`已闭环` 等，且「不通过」结论行（如 `机审：不通过`）优先于「通过」解析。
    4. 任一 `## 机审区` 节最后结论为通过 → True。
    """
    if not text:
        return False
    lines = text.splitlines()
    n = len(lines)
    any_section_passed = False

    i = 0
    while i < n:
        line_stripped = lines[i].strip()
        if line_stripped.startswith("## 机审区"):
            last_verdict = None  # None, "通过", or "不通过"
            j = i + 1
            while j < n:
                cur = lines[j]
                cur_stripped = cur.strip()
                if cur_stripped.startswith("## "):
                    break  # 下一主节标题

                # 忽略表格行、小节标题
                if cur_stripped.startswith("|") or cur_stripped.startswith("###"):
                    j += 1
                    continue

                # 规避 markdown 加粗干扰
                line_normalized = cur_stripped.replace("**", "").replace("*", "")

                # 匹配形如 `机审：通过` / `结论：通过` / `机审：不通过` / `结论：不通过`
                # 采用 (不通过|通过) 确保「不通过」优先匹配，避免被「通过」子串截断
                match = re.search(r"(机审|结论)\s*[:：]\s*(不通过|通过)", line_normalized)
                if not match:
                    # 兼容 agent 输出格式 `**机审**：<评审人>· 结果：**通过**`（clw011 事故）
                    # 「结果」字段在机审结论行内给出明确裁决 → 视为有效结论行
                    match = re.search(r"结果\s*[:：]\s*(不通过|通过)", line_normalized)
                if match:
                    last_verdict = match.group(2) if match.lastindex >= 2 else match.group(1)

                j += 1

            if last_verdict == "通过":
                any_section_passed = True

            i = j
        else:
            i += 1

    return any_section_passed


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
    thread_id: str = ""
    acceptance: str = UNKNOWN
    archived: bool = False
    machine_audit_passed: bool = False
    depends_on: list[str] = field(default_factory=list)
    closed_at: str = ""
    audit_status: str = ""
    approval: str = ""
    reason: str = ""

    def to_dict(self) -> dict[str, str | int | bool]:
        """转纯字典（JSON 可序列化）。"""
        col = board_column(self.state, self.machine_audit_passed)
        return {
            "id": self.id,
            "title": self.title,
            "state": self.state,
            "board_column": col,
            "machine_audit_passed": self.machine_audit_passed,
            "depends_on": list(self.depends_on),
            "project": self.project,
            "executor": self.executor,
            "dispatched_at": self.dispatched_at,
            "written_at": self.written_at,
            "reject_count": self.reject_count,
            "dispatch": self.dispatch,
            "type": self.type,
            "parent": self.parent,
            "thread_id": self.thread_id,
            "acceptance": self.acceptance,
            "archived": self.archived,
            "closed_at": self.closed_at,
            "audit_status": self.audit_status,
            "approval": self.approval,
            "reason": self.reason,
        }
