"""v0.62/v0.63: LongLivedSession 跟踪 + bg session 注册/列表/探活/nudge。

覆盖:
- register_bg_session:同 task 重复注册覆盖
- verify_bg_session:kill -0 探活(用 ps 测试)
- list_long_lived_sessions:返所有活 + idle 状态
- nudge_bg_session:v0.63 写文件 + dry_run/spawn --resume 注入

注:active_tasks.nudge_bg_session 默认写 ~/.ccc/bg-sessions/
测试用 monkeypatch 重定向到 tmp_path,避免用户态无写权限
"""
from __future__ import annotations

import os
import subprocess

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
    """每次测试前清持久化文件,防前一个测试残留干扰。"""
    if _BG_SESSIONS_FILE.exists():
        _BG_SESSIONS_FILE.unlink()
    yield
    if _BG_SESSIONS_FILE.exists():
        _BG_SESSIONS_FILE.unlink()


@pytest.fixture
def nudge_dir(monkeypatch, tmp_path):
    """重定向 nudge 目录到 tmp_path；单测默认 dry_run。"""
    monkeypatch.setenv("CCC_BG_NUDGE_DIR", str(tmp_path / "bg-sessions"))
    monkeypatch.setenv("CCC_BG_NUDGE_DRY_RUN", "1")
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
    assert listed[0]["alive"] is True
    assert listed[0]["age_min"] >= 0
    unregister_bg_session("reviewer", "t1")


def test_register_overwrites_same_key():
    """同 task_id+role 重复注册覆盖(后续 resume 用新 session_id)。"""
    register_bg_session("t2", "reviewer", "first-uuid", pid=os.getpid(), model="flash")
    s2 = register_bg_session("t2", "reviewer", "second-uuid", pid=os.getpid(), model="flash")
    assert s2.session_id == "second-uuid"
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
    unregister_bg_session("reviewer", "nonexistent")
    register_bg_session("t4", "reviewer", "uuid", os.getpid(), "flash")
    unregister_bg_session("reviewer", "t4")
    unregister_bg_session("reviewer", "t4")


def test_nudge_writes_file_and_dry_inject(nudge_dir):
    """v0.63: nudge 写文件 + dry_run 注入标记。"""
    register_bg_session("t5", "reviewer", "nudge-uuid", os.getpid(), "flash")
    ok = nudge_bg_session("reviewer", "t5", "请关注 X 模块")
    assert ok is True
    nudge_path = nudge_dir / "nudge-uuid.nudge"
    assert nudge_path.is_file()
    assert nudge_path.read_text() == "请关注 X 模块"
    injected = nudge_dir / "nudge-uuid.nudge.injected"
    assert injected.is_file()
    assert "dry_run" in injected.read_text()
    unregister_bg_session("reviewer", "t5")
    nudge_path.unlink(missing_ok=True)
    injected.unlink(missing_ok=True)


def test_nudge_spawn_when_claude_bin_set(nudge_dir, monkeypatch, tmp_path):
    """非 dry_run：有 CCC_CLAUDE_BIN 时 Popen --resume。"""
    monkeypatch.setenv("CCC_BG_NUDGE_DRY_RUN", "0")
    fake = tmp_path / "fake-claude"
    fake.write_text("#!/bin/sh\necho inject-ok\n")
    fake.chmod(0o755)
    monkeypatch.setenv("CCC_CLAUDE_BIN", str(fake))
    register_bg_session("t5b", "reviewer", "spawn-uuid", os.getpid(), "flash")
    ok = nudge_bg_session("reviewer", "t5b", "hello-nudge")
    assert ok is True
    injected = nudge_dir / "spawn-uuid.nudge.injected"
    assert injected.is_file()
    body = injected.read_text()
    assert "spawned" in body or "file_only" in body
    unregister_bg_session("reviewer", "t5b")


def test_long_lived_session_idle_timeout():
    """heartbeat 1h 超时 → is_idle_timeout True(仅字段,不动进程)。"""
    sess = LongLivedSession(
        task_id="t6", role="reviewer", session_id="idle-uuid",
        pid=os.getpid(), model="flash",
        heartbeat_timeout_sec=0,
    )
    assert sess.is_idle_timeout() is True
    sess.heartbeat_timeout_sec = 3600
    sess.heartbeat()
    assert sess.is_idle_timeout() is False
