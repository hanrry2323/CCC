"""test_advanced_review — T76 对抗式高级复审与破坏异常注入测试（第二轮加固验证）。

覆盖三类「1/1000 概率」边界隐患，全部以自动测试钉死：

1. 并发锁破坏 / 丢失更新：多线程高频并发 touch/rename/delete 同一 project 索引，
   断言最终索引全量一致（唯一标记条目绝不丢失、标题等于最后写入值）。
2. Setsid 自我误杀隔离：`_terminate_proc` 在 pgid 非法（<=1）或等于本进程组时
   绝不用 killpg，退化为单杀 proc.kill()，保证 Web 服务自身 100% 存活。
3. 流式中途中断清理：客户端断开（generator.close()）→ `_terminate_proc` 被调用、
   子进程 100% 终止、无进程组泄露。
"""

from __future__ import annotations

import os
import stat
import subprocess
import threading
import time

import pytest

from server.web import brain as brain_mod
from server.web import session_store

# ════════════════════════════════════════════════════════════
# 工具
# ════════════════════════════════════════════════════════════


def _patch_data_root(monkeypatch, tmp_path) -> None:
    """把 session_store 落盘根目录重定向到临时目录（隔离测试数据）。"""
    monkeypatch.setattr(session_store, "_data_root", lambda: tmp_path)


def _configure_brain(monkeypatch) -> None:
    """配置大脑所需环境变量（对齐 test_brain_stream._configure_brain）。"""
    monkeypatch.setenv("CCC_BRAIN_MODEL", "flash")
    monkeypatch.setenv("CCC_BRAIN_BASE_URL", "http://127.0.0.1:6100")
    monkeypatch.setenv("CCC_BRAIN_AUTH_TOKEN", "ccc-relay-flash")


class _FakeProc:
    """模拟 Popen：poll/kill/wait 无副作用，记录是否被单杀。"""

    def __init__(self, pid: int):
        self.pid = pid
        self._killed = False
        self._rc = None

    def poll(self):
        return self._rc if self._killed else None

    def kill(self):
        self._killed = True
        self._rc = -9

    def wait(self, timeout=None):
        return self._rc


# ════════════════════════════════════════════════════════════
# 1. session_store 索引事务原子性：并发锁破坏 / 丢失更新
# ════════════════════════════════════════════════════════════


class TestSessionStoreConcurrency:
    """touch/rename/delete 必须在单把锁内全流程原子，绝不允许丢失更新。"""

    def test_concurrent_touch_rename_no_lost_update(self, monkeypatch, tmp_path):
        """10 线程 × 30 迭代并发 touch+rename 不同 thread：最终索引全量一致。"""
        _patch_data_root(monkeypatch, tmp_path)
        project = "proj-a"
        n_workers, iters = 10, 30
        barrier = threading.Barrier(n_workers)
        errors: list[Exception] = []

        def worker(w: int):
            try:
                barrier.wait(timeout=5)
                tid = f"t{w}"
                for i in range(iters):
                    session_store.touch_thread(project, tid, title=f"w{w}-i{i}")
                    session_store.rename_thread(project, tid, f"w{w}-final")
            except Exception as exc:  # noqa: BLE001 - 收集异常统一断言
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(w,)) for w in range(n_workers)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=60)
        assert not errors, f"并发写抛异常: {errors}"

        index = session_store.load_index(project)
        for w in range(n_workers):
            assert f"t{w}" in index, f"丢失更新：线程 {w} 的会话条目被并发覆写抹除"
            assert index[f"t{w}"]["title"] == f"w{w}-final", (
                f"丢失更新：线程 {w} 最终标题 {index[f't{w}']['title']!r} 非 {f'w{w}-final'!r}"
            )

    def test_shared_marker_survives_concurrent_renames(self, monkeypatch, tmp_path):
        """唯一标记会话在 8 线程并发 rename 其他会话时绝不丢失、标题不倒退。"""
        _patch_data_root(monkeypatch, tmp_path)
        project = "proj-b"
        session_store.touch_thread(project, "marker", title="marker-orig")

        n_renamers = 8
        barrier = threading.Barrier(n_renamers + 1)

        def renamer(w: int):
            barrier.wait(timeout=5)
            for i in range(50):
                session_store.rename_thread(project, f"other{w}", f"r{w}-{i}")

        def toucher():
            barrier.wait(timeout=5)
            for i in range(50):
                session_store.touch_thread(project, "marker", title=f"marker-{i}")

        threads = [threading.Thread(target=renamer, args=(w,)) for w in range(n_renamers)]
        threads.append(threading.Thread(target=toucher))
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=60)

        index = session_store.load_index(project)
        assert "marker" in index, "丢失更新：标记会话被并发 rename 的整表覆写抹除"
        assert index["marker"]["title"] == "marker-49", (
            f"标题倒退/被覆写：标记会话标题为 {index['marker']['title']!r}"
        )

    def test_concurrent_delete_same_thread(self, monkeypatch, tmp_path):
        """5 线程并发删除同一 thread：无异常，最终索引一致地不再含该条目。"""
        _patch_data_root(monkeypatch, tmp_path)
        project = "proj-c"
        session_store.touch_thread(project, "dup", title="dup")
        n = 5
        barrier = threading.Barrier(n)
        errors: list[Exception] = []

        def deleter(_: int):
            try:
                barrier.wait(timeout=5)
                session_store.delete_thread(project, "dup")
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=deleter, args=(i,)) for i in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=60)
        assert not errors, f"并发删除抛异常: {errors}"
        assert "dup" not in session_store.load_index(project)


# ════════════════════════════════════════════════════════════
# 2. _terminate_proc 自我误杀隔离（killpg 物理保护）
# ════════════════════════════════════════════════════════════


class TestTerminateProcGuard:
    """killpg 前必须强校验 pgid>1 且 != 本进程组；非法一律降级单杀 proc.kill()。"""

    def test_own_process_group_never_killpg(self, monkeypatch):
        """pid 属于本进程组（fork→setsid 竞态窗口）：绝不允许 killpg 自杀。"""
        killpg_calls: list[tuple[int, int]] = []
        monkeypatch.setattr(
            brain_mod.os, "killpg", lambda pgid, sig: killpg_calls.append((pgid, sig))
        )
        fake = _FakeProc(os.getpid())  # 本测试进程自身 pid → getpgid 返回本进程组
        brain_mod._terminate_proc(fake)
        assert killpg_calls == [], "对自身进程组调用 killpg = 自我误杀，必须被拦截"
        assert fake._killed, "应退化为 proc.kill() 单杀"

    def test_pgid_zero_blocked(self, monkeypatch):
        """getpgid 返回 0（pgid<=1 非法）：拦截 killpg，降级单杀。"""
        killpg_calls: list[tuple[int, int]] = []
        monkeypatch.setattr(
            brain_mod.os, "killpg", lambda pgid, sig: killpg_calls.append((pgid, sig))
        )
        monkeypatch.setattr(brain_mod.os, "getpgid", lambda pid: 0)
        fake = _FakeProc(12345)
        brain_mod._terminate_proc(fake)
        assert killpg_calls == []
        assert fake._killed

    def test_getpgid_error_fallback(self, monkeypatch):
        """子进程已退出/pid 不存在：getpgid 抛 ProcessLookupError → 降级不崩溃。"""
        killpg_calls: list[tuple[int, int]] = []
        monkeypatch.setattr(
            brain_mod.os, "killpg", lambda pgid, sig: killpg_calls.append((pgid, sig))
        )

        def _boom(pid: int) -> int:
            raise ProcessLookupError("no such process")

        monkeypatch.setattr(brain_mod.os, "getpgid", _boom)
        fake = _FakeProc(2**20)
        brain_mod._terminate_proc(fake)  # 不应抛异常
        assert killpg_calls == []
        assert fake._killed

    def test_real_setsid_child_reaped(self):
        """正常路径（真 setsid 子进程）：killpg 主路径仍 100% 回收，且本测试进程存活。"""
        proc = subprocess.Popen(["sleep", "30"], preexec_fn=os.setsid)
        try:
            time.sleep(0.05)  # 等待子进程执行 setsid 脱离
            brain_mod._terminate_proc(proc)
            assert proc.poll() is not None, "setsid 子进程未被终止（killpg 主路径失效）"
            # 走到这里说明本测试进程（服务端等价物）安然无恙，未被误杀
        finally:
            if proc.poll() is None:
                proc.kill()


# ════════════════════════════════════════════════════════════
# 3. 流式中途中断清理（客户端断开 → 进程组 100% 回收）
# ════════════════════════════════════════════════════════════


class TestStreamInterruptCleanup:
    """generator 被中途关闭（客户端断开）：_terminate_proc 必须触发、子进程必须终止。"""

    def test_generator_close_terminates_child(self, monkeypatch, tmp_path):
        _configure_brain(monkeypatch)
        mock = tmp_path / "slow_claude"
        mock.write_text(
            "#!/usr/bin/env python3\n"
            "import sys, json, time\n"
            "print(json.dumps({'type': 'system', 'subtype': 'init', 'model': 'flash'}))\n"
            "sys.stdout.flush()\n"
            "time.sleep(60)\n",
            encoding="utf-8",
        )
        mock.chmod(mock.stat().st_mode | stat.S_IEXEC)
        monkeypatch.setenv("CCC_BRAIN_CLAUDE_BIN", str(mock))

        captured: dict[str, subprocess.Popen] = {}
        orig_terminate = brain_mod._terminate_proc

        def _capture(proc: subprocess.Popen):
            captured["proc"] = proc
            return orig_terminate(proc)

        monkeypatch.setattr(brain_mod, "_terminate_proc", _capture)

        gen = brain_mod.stream_brain_events("hi", [], session_key="")
        first = next(gen)  # 触发 spawn 并读到 meta 事件
        assert first[0] == "meta"
        gen.close()  # 模拟客户端断开：中途关闭 generator

        assert "proc" in captured, "_terminate_proc 未被调用（清理路径未触发）"
        assert captured["proc"].poll() is not None, (
            "流中断后子进程未被终止（存在进程组孤儿泄露风险）"
        )
