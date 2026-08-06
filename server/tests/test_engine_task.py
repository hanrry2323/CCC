"""test_engine_task — 契约 §2 状态机：合法 / 非法转移。"""

from __future__ import annotations

import pytest

from server.engine.task import IllegalTransitionError, State, Work


class TestWorkStateMachine:
    """契约 §2 五态状态机。"""

    def test_happy_path_todo_to_closed(self) -> None:
        """待分派 → 执行中 → 已回写 → 已关闭（主链路）。"""
        work = Work(id="w1", role="开发执行体")
        assert work.state is State.TODO
        work.transition(State.RUNNING)
        work.transition(State.DONE)
        work.transition(State.CLOSED)
        assert work.state is State.CLOSED

    def test_running_rejected_attaches_problems(self) -> None:
        """执行中 → 打回，问题清单写入 work.problems。"""
        work = Work(id="w2", role="维护执行体", state=State.RUNNING)
        work.transition(State.REJECTED, problems=["缺测试", "README 深度不足"])
        assert work.state is State.REJECTED
        assert work.problems == ["缺测试", "README 深度不足"]

    def test_done_rejected_acceptance(self) -> None:
        """已回写 → 打回（验收打回，附问题清单）。"""
        work = Work(id="w3", role="开发执行体", state=State.DONE)
        work.transition(State.REJECTED, problems=["硬编码未清零"])
        assert work.state is State.REJECTED

    def test_done_to_todo_for_audit_retry(self) -> None:
        """已回写 → 待分派（机审失败自动重试，附原因）。"""
        work = Work(id="w3b", role="开发执行体", state=State.DONE)
        work.transition(State.TODO, problems=["机审：不通过"])
        assert work.state is State.TODO
        assert work.problems == ["机审：不通过"]

    def test_rejected_redispatch_to_todo(self) -> None:
        """打回 → 待分派（人工处理问题后重新派发）。"""
        work = Work(id="w4", role="开发执行体", state=State.REJECTED)
        work.transition(State.TODO)
        assert work.state is State.TODO

    def test_reject_requires_problems(self) -> None:
        """进入「打回」必须附问题清单。"""
        work = Work(id="w5", role="维护执行体", state=State.RUNNING)
        with pytest.raises(IllegalTransitionError):
            work.transition(State.REJECTED)

    def test_illegal_todo_to_done(self) -> None:
        """待分派 → 已回写（跳过执行中）：非法。"""
        work = Work(id="w6", role="开发执行体")
        with pytest.raises(IllegalTransitionError):
            work.transition(State.DONE)

    def test_illegal_done_to_running(self) -> None:
        """已回写 → 执行中：非法（状态不可回退）。"""
        work = Work(id="w7", role="开发执行体", state=State.DONE)
        with pytest.raises(IllegalTransitionError):
            work.transition(State.RUNNING)

    def test_closed_is_terminal(self) -> None:
        """已关闭为终态：任何转移都非法。"""
        work = Work(id="w8", role="维护执行体", state=State.CLOSED)
        for state in (State.TODO, State.RUNNING, State.DONE, State.REJECTED):
            with pytest.raises(IllegalTransitionError):
                work.transition(state)
