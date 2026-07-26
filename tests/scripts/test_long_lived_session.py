"""v0.62.0 阶段 2:LongLivedSession 跟踪 + bg session 注册/列表/探活/nudge。

覆盖:
- register_bg_session:同 task 重复注册覆盖
- verify_bg_session:kill -0 探活(用 ps 测试)
- list_long_lived_sessions:返所有活 + idle 状态
- nudge_bg_session:v0.62.0 占位(写文件,nudge 不真触发)

注:active_tasks.nudge_bg_session 默认写 /Users/fan/.ccc/bg-sessions/
测试用 monkeypatch 重定向到 tmp_path,避免用户态无写权限
"""
from __future__ import annotations

import os
import subprocess

import os
import pytest

from engine.active_tasks import (
    LongLivedSession,
    _BG_SESSIONS_FILE,
    list_long_lived_sessions,
    nudge_bg_session,
    register_bg_session,
    unregister_bg_session,
    verify_bg_session,
)


@pytest.fixture(autouse=True)
def _clean_bg_state():
    """v0.62.0:每次测试前清持久化文件,防前一个测试残留干扰。"""
    if _BG_SESSIONS_FILE.exists():
        _BG_SESSIONS_FILE.unlink()
    yield
    if _BG_SESSIONS_FILE.exists():
        _BG_SESSIONS_FILE.unlink()


@pytest.fixture
def nudge_dir(monkeypatch, tmp_path):
    """重定向 nudge 目录到 tmp_path(env CCC_BG_NUDGE_DIR)。"""
    monkeypatch.setenv("CCC_BG_NUDGE_DIR", str(tmp_path / "bg-sessions"))
    return tmp_path / "bg-sessions"


def test_register_and_list():
    """注册 bg session + 列表返。"""
    unregister_bg_session("reviewer", "t1")  # 清理
    sess = register_bg_session(
        task_id="t1", role="reviewer",
        session_id="abc12345-uuid", pid=os.getpid(), model="flash",
    )
    assert sess.task_id == "t1"
    assert sess.role == "reviewer"
    assert sess.session_id == "abc12345-uuid"
    assert sess.pid == os.getpid()

    listed = list_long_lived_sessions()
    assert len(listed) == 1
    assert listed[0]["task_id"] == "t1"
    assert listed[0]["session_id"] == "abc12345-uuid"
    # 活着(pid 是当前测试进程,显然 alive)
    assert listed[0]["alive"] is True
    assert listed[0]["age_min"] >= 0
    unregister_bg_session("reviewer", "t1")


def test_register_overwrites_same_key():
    """同 task_id+role 重复注册覆盖(后续 resume 用新 session_id)。"""
    register_bg_session("t2", "reviewer", "first-uuid", pid=os.getpid(), model="flash")
    s2 = register_bg_session("t2", "reviewer", "second-uuid", pid=os.getpid(), model="flash")
    assert s2.session_id == "second-uuid"  # 覆盖了
    listed = list_long_lived_sessions()
    matching = [s for s in listed if s["task_id"] == "t2"]
    assert len(matching) == 1
    assert matching[0]["session_id"] == "second-uuid"
    unregister_bg_session("reviewer", "t2")


def test_verify_bg_session_alive_and_dead():
    """kill -0 探活:用真子进程模拟 alive / dead。"""
    proc = subprocess.Popen(["sleep", "60"])
    try:
        register_bg_session(
            "t3", "reviewer", "alive-uuid", proc.pid, "flash",
        )
        assert verify_bg_session("reviewer", "t3") is True
        proc.kill()
        proc.wait(timeout=2)
        with pytest.raises(ProcessLookupError):
            os.kill(proc.pid, 0)
    finally:
        unregister_bg_session("reviewer", "t3")


def test_unregister_idempotent():
    """重复 unregister 不报错(幂等)。"""
    unregister_bg_session("reviewer", "nonexistent")  # 不存在
    register_bg_session("t4", "reviewer", "uuid", os.getpid(), "flash")
    unregister_bg_session("reviewer", "t4")
    unregister_bg_session("reviewer", "t4")  # 二次删,不报错


def test_nudge_writes_file_v0_62_placeholder(nudge_dir):
    """v0.62.0 nudge 写文件占位(不真触发注入,v0.63.0 接管)。"""
    register_bg_session("t5", "reviewer", "nudge-uuid", os.getpid(), "flash")
    ok = nudge_bg_session("reviewer", "t5", "请关注 X 模块")
    assert ok is True
    nudge_path = nudge_dir / "nudge-uuid.nudge"
    assert nudge_path.is_file()
    assert nudge_path.read_text() == "请关注 X 模块"
    unregister_bg_session("reviewer", "t5")
    nudge_path.unlink(missing_ok=True)


def test_long_lived_session_idle_timeout():
    """heartbeat 1h 超时 → is_idle_timeout True(仅字段,不动进程)。"""
    sess = LongLivedSession(
        task_id="t6", role="reviewer", session_id="idle-uuid",
        pid=os.getpid(), model="flash",
        heartbeat_timeout_sec=0,  # 0 立即超时,避免 time.sleep
    )
    assert sess.is_idle_timeout() is True
    sess.heartbeat_timeout_sec = 3600
    sess.heartbeat()
    assert sess.is_idle_timeout() is False

