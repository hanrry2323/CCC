"""跨 DATA_DIR 双 engine 并发机审防线回归测试（ccc082）。

背景：防双审共享面原只有两处，均锚定单个 DATA_DIR——
- ``DATA_DIR/engine.lock`` 单实例锁（不同 DATA_DIR 各持各锁，互不排斥）；
- ``{EXECUTOR_LOG_DIR}/{id}-audit.running`` 标记（log_dir 不同则互不可见）；
外加进程内 ``audit_pool.alive_ids()``（pool.py 模块级单例，天然进程私有）。
双 engine 各用不同 DATA_DIR 时全部失效 → 对同一卡并发机审（ccc078 多实例
风暴的等价小模型；加固前实验实锤：cross-log_dir alive=False → 双 claim）。

加固语义（保持向后兼容）：
- 机审标记（{id}-audit.running）经 ``_write_running_marker`` 同步镜像进用户级
  全局注册表 ``CCC_AUDIT_REGISTRY_DIR``（默认 ~/.ccc/data/audit-inflight）；
- ``_audit_marker_alive`` 本地未命中「或判死」后追加查注册表，任一共享面
  判在途即在途；死条目顺手回收（不破坏 mx055 修复的可重审语义）。
"""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

from server.engine.main import (
    _audit_inflight_registry_dir,
    _audit_marker_alive,
    _claim_running_marker,
    _clear_running_marker,
    _refresh_running_marker_child,
    _write_running_marker,
)

DEAD_PID = 99999999


def _spawn_live_child() -> subprocess.Popen[bytes]:
    """真实存活子进程（不依赖宽限期分支，判活走 PID 存活路径）。"""
    return subprocess.Popen(["sleep", "60"])


def test_cross_datarir_double_claim_blocked_by_registry(tmp_path: Path, monkeypatch) -> None:
    """加固核心回归：A/B 各用不同 DATA_DIR(log_dir)，A 机审在途 → B 必须判在途。

    加固前该场景 cross-log_dir alive=False → B 会再派机审（穿透复现实验证据，
    见本卡回写区）；加固后 B 经全局注册表看到 A 的在途登记。
    """
    monkeypatch.setenv("CCC_AUDIT_REGISTRY_DIR", str(tmp_path / "registry"))
    log_a = tmp_path / "dataA" / "logs"
    log_b = tmp_path / "dataB" / "logs"
    proc = _spawn_live_child()
    try:
        # engine A 视角：认领机审 + 子进程拉起刷新（生产同款两步）
        _claim_running_marker(log_a, "w1-audit", data_dir=str(tmp_path / "dataA"))
        _refresh_running_marker_child(log_a, "w1", proc.pid, phase="audit")
        # 注册表已镜像 A 的在途登记
        entry = _audit_inflight_registry_dir() / "w1-audit.running"
        assert entry.is_file(), f"注册表未镜像: {entry}"
        assert f"child_pid={proc.pid}" in entry.read_text(encoding="utf-8")
        # engine B 视角：log_dir_b 无标记，但经注册表判在途 → 不再派审
        assert _audit_marker_alive(log_b, "w1") is True
        # 对照：同 DATA_DIR 原防线不受影响
        assert _audit_marker_alive(log_a, "w1") is True
    finally:
        proc.kill()
        proc.wait()


def test_same_datarir_defense_unchanged(tmp_path: Path, monkeypatch) -> None:
    """向后兼容：同 log_dir 下本地标记判定优先且语义不变。"""
    monkeypatch.setenv("CCC_AUDIT_REGISTRY_DIR", str(tmp_path / "registry"))
    log_a = tmp_path / "dataA" / "logs"
    proc = _spawn_live_child()
    try:
        _claim_running_marker(log_a, "w2-audit", data_dir=str(tmp_path / "dataA"))
        _refresh_running_marker_child(log_a, "w2", proc.pid, phase="audit")
        assert _audit_marker_alive(log_a, "w2") is True
    finally:
        proc.kill()
        proc.wait()
    # 机审收尾（_run_audit_worker finally 同款）：子进程死 + 本地标记与注册表条目双清 → 可重审
    _clear_running_marker(log_a, "w2-audit")
    assert not (log_a / "w2-audit.running").exists()
    assert not (_audit_inflight_registry_dir() / "w2-audit.running").exists()
    assert _audit_marker_alive(log_a, "w2") is False


def test_local_stale_but_registry_live_child_blocks(tmp_path: Path, monkeypatch) -> None:
    """本地标记残留死标记、另一 DATA_DIR 正在审 → 注册表挡住重审。"""
    monkeypatch.setenv("CCC_AUDIT_REGISTRY_DIR", str(tmp_path / "registry"))
    log_a = tmp_path / "dataA" / "logs"
    log_b = tmp_path / "dataB" / "logs"
    # 本地视角：只有超宽限期的死标记（engine_pid 恒活被排除）
    marker = log_a / "w3-audit.running"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(f"engine_pid={os.getpid()}\npid={os.getpid()}\n", encoding="utf-8")
    old = time.time() - 3600
    os.utime(marker, (old, old))
    assert _marker_stale(marker)
    # 另一 engine 经注册表在审同一卡（活子进程）
    proc = _spawn_live_child()
    try:
        _write_running_marker(
            log_a.parent.parent / "dataX" / "logs",
            "w3-audit",
            engine_pid=os.getpid(),
            child_pid=proc.pid,
        )
        assert _audit_marker_alive(log_a, "w3") is True  # 注册表兜底挡双审
        assert _audit_marker_alive(log_b, "w3") is True
    finally:
        proc.kill()
        proc.wait()


def _marker_stale(marker: Path) -> bool:
    return time.time() - marker.stat().st_mtime > 900


def test_registry_dead_entry_expires_and_cleans(tmp_path: Path, monkeypatch) -> None:
    """mx055 语义不被注册表破坏：死条目（无存活工作者 PID + 超宽限）→ 可重审且条目回收。"""
    monkeypatch.setenv("CCC_AUDIT_REGISTRY_DIR", str(tmp_path / "registry"))
    reg_dir = _audit_inflight_registry_dir()
    reg_dir.mkdir(parents=True, exist_ok=True)
    entry = reg_dir / "w4-audit.running"
    entry.write_text(f"engine_pid={DEAD_PID}\npid={DEAD_PID}\nchild_pid={DEAD_PID}\n", encoding="utf-8")
    old = time.time() - 3600
    os.utime(entry, (old, old))
    assert _audit_marker_alive(tmp_path / "any-logs", "w4") is False
    assert not entry.exists(), "死条目应被顺手回收"


def test_clear_running_marker_removes_registry_entry(tmp_path: Path, monkeypatch) -> None:
    """机审收尾 _clear_running_marker 同步清注册表，防跨 DATA_DIR 假在途。"""
    monkeypatch.setenv("CCC_AUDIT_REGISTRY_DIR", str(tmp_path / "registry"))
    log_a = tmp_path / "dataA" / "logs"
    _claim_running_marker(log_a, "w5-audit", data_dir=str(tmp_path / "dataA"))
    entry = _audit_inflight_registry_dir() / "w5-audit.running"
    assert entry.is_file()
    _clear_running_marker(log_a, "w5-audit")
    assert not (log_a / "w5-audit.running").exists()
    assert not entry.exists()


def test_plain_running_marker_not_mirrored(tmp_path: Path, monkeypatch) -> None:
    """执行认领（plain {id}.running）不进注册表——本卡只加固机审面，最小改动。"""
    monkeypatch.setenv("CCC_AUDIT_REGISTRY_DIR", str(tmp_path / "registry"))
    log_a = tmp_path / "dataA" / "logs"
    _write_running_marker(log_a, "w6", engine_pid=os.getpid())
    assert (log_a / "w6.running").is_file()
    assert list(_audit_inflight_registry_dir().glob("*")) == []
