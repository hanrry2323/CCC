"""work 数据结构 + 契约 §2 状态机。

契约 §2 五态：`待分派 → 执行中 → 已回写 → 已关闭`；
失败路径：先附原因回 `待分派` 自动重试（最多 N 次）；用尽后才 `打回`。
人工仍可 `打回 → 待分派`。
非法状态转移一律抛 `IllegalTransitionError`。

用法：
    from server.engine.task import Work, State, IllegalTransitionError

    work = Work(id="w1", role="开发执行体")
    work.transition(State.RUNNING)          # 合法：待分派 → 执行中
    work.transition(State.DONE)             # 合法：执行中 → 已回写
    work.transition(State.REJECTED, problems=["缺测试"])  # 合法：打回（必附问题清单）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

try:
    from enum import StrEnum
except ImportError:
    class StrEnum(str, Enum):  # noqa: UP042
        pass


class State(StrEnum):
    """契约 §2 五态。"""

    TODO = "待分派"
    RUNNING = "执行中"
    DONE = "已回写"
    CLOSED = "已关闭"
    REJECTED = "打回"


# 合法转移表（契约 §2 + 打回→待分派 人工重派回环；已关闭为终态）
_LEGAL_TRANSITIONS: dict[State, frozenset[State]] = {
    State.TODO: frozenset({State.RUNNING}),
    State.RUNNING: frozenset({State.DONE, State.REJECTED, State.TODO}),
    # 机审失败：已回写 → 待分派（带原因自动重试），用尽后才打回
    State.DONE: frozenset({State.CLOSED, State.REJECTED, State.TODO}),
    State.REJECTED: frozenset({State.TODO}),
    State.CLOSED: frozenset(),
}


class IllegalTransitionError(Exception):
    """非法状态转移。"""


@dataclass
class Work:
    """一张可执行 work 卡。

    Attributes:
        id: 唯一标识。
        role: 目标执行体角色（契约 §7，如「开发执行体」）。
        title: 任务标题。
        state: 当前状态（契约 §2，默认待分派）。
        problems: 问题清单，进入「打回」时由 transition 填写。
        card_path: 任务卡文件路径（派发时注入执行体参数模板的 {card_path} 占位符）。
        executor: 卡头「执行体」绑定名（去括号后，如 Trae / OpenCode / Claude Code / Codex）；
            空字符串表示卡未指定，派发回退到 role-based 决策（T39）。
        dispatch: 派发方式（manual|engine，缺省 engine）。manual 卡由管理席派发，
            Engine 不自动拉（保持待分派，T53）。
    """

    id: str
    role: str
    title: str = ""
    state: State = State.TODO
    problems: list[str] = field(default_factory=list)
    card_path: str = ""
    executor: str = ""
    dispatch: str = "engine"
    type: str = "task"
    project: str = ""
    parent: str = ""
    acceptance: str = ""
    thread_id: str = ""
    retry_count: int = 0

    def transition(self, new_state: State, problems: list[str] | None = None) -> None:
        """按契约 §2 转移状态；非法跳转抛 `IllegalTransitionError`。

        Args:
            new_state: 目标状态。
            problems: 进入「打回」时必附的问题清单。

        Raises:
            IllegalTransitionError: 目标状态不在当前状态的合法转移集内，
                或进入「打回」未附问题清单。
        """
        allowed = _LEGAL_TRANSITIONS[self.state]
        if new_state not in allowed:
            raise IllegalTransitionError(
                f"非法状态转移: {self.state.value} → {new_state.value} "
                f"(合法目标: {[s.value for s in sorted(allowed, key=str)]})"
            )
        if new_state is State.REJECTED:
            if not problems:
                raise IllegalTransitionError("进入「打回」必须附问题清单")
            self.problems = list(problems)
        elif problems is not None:
            self.problems = list(problems)
        self.state = new_state
