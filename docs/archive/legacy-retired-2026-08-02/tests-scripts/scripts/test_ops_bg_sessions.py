"""v0.62.0 阶段 3:Hub 透出长任务状态 + _ops_probe 域 helper 单测。

覆盖 _build_bg_sessions_domain 的 4 种分支:
  1. None 输入 → ok=None 占位
  2. 全活 → ok=True
  3. 全死 → ok=False
  4. 部分活 → ok=None(混合)

端点级测试(/api/ops/bg-sessions)留 v0.62.0 阶段 5 smoke 覆盖
(需要 TestClient 启 chat_server,工作量超出阶段 3 范围)。
"""
from __future__ import annotations


def test_bg_sessions_none_input():
    """v0.62.0:_build_bg_sessions_domain(None) → ok=None 占位。"""
    from _ops_probe import _build_bg_sessions_domain

    out = _build_bg_sessions_domain(None)
    assert out["ok"] is None
    assert out["count"] == 0
    assert out["sessions"] == []
    assert "未拉取" in out["note"]


def test_bg_sessions_all_alive():
    """全活 session → ok=True,alive_count == count。"""
    from _ops_probe import _build_bg_sessions_domain

    sessions = [
        {"task_id": "t1", "role": "reviewer", "session_id": "aaa", "alive": True},
        {"task_id": "t2", "role": "product", "session_id": "bbb", "alive": True},
    ]
    out = _build_bg_sessions_domain(sessions)
    assert out["ok"] is True
    assert out["count"] == 2
    assert out["alive_count"] == 2
    assert out["sessions"] == sessions


def test_bg_sessions_all_dead():
    """全死 session → ok=False,alive_count == 0。"""
    from _ops_probe import _build_bg_sessions_domain

    sessions = [
        {"task_id": "t1", "alive": False},
        {"task_id": "t2", "alive": False},
    ]
    out = _build_bg_sessions_domain(sessions)
    assert out["ok"] is False
    assert out["count"] == 2
    assert out["alive_count"] == 0


def test_bg_sessions_partial_alive():
    """部分活 → ok=None(混合,既不 True 也不 False)。"""
    from _ops_probe import _build_bg_sessions_domain

    sessions = [
        {"task_id": "t1", "alive": True},
        {"task_id": "t2", "alive": False},
        {"task_id": "t3", "alive": True},
    ]
    out = _build_bg_sessions_domain(sessions)
    assert out["ok"] is None
    assert out["count"] == 3
    assert out["alive_count"] == 2


def test_bg_sessions_empty_list():
    """空列表(无 session)→ ok=None(走 `if not sessions` 早 return,占位语义)。

    边界:empty list 实际是 falsy,被 `if not sessions` 捕获返 ok=None。
    区别于 None(None 也走同一分支)和正常 list(走 alive_count 计算)。
    """
    from _ops_probe import _build_bg_sessions_domain

    out = _build_bg_sessions_domain([])
    assert out["ok"] is None
    assert out["count"] == 0
    assert "未拉取" in out["note"]
