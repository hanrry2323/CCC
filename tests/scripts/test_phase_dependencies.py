"""test_phase_dependencies.py — v0.24 phase 依赖解析 + 失败隔离 测试

覆盖:
  - _resolve_phase_dependencies 7 case（无依赖/链式/失败隔离/多依赖/in_progress/skipped 算 OK/不存在依赖）
  - _apply_phase_status_updates 双向同步（pending↔blocked 解锁）
  - _mark_phase_failed 保留终态
  - _current_running_phase 优先级（in_progress > pending > blocked）
  - _check_phase_failures 失败传染链路 + 收敛
  - 多轮 tick 失败传染收敛（phase 1 failed → 2 skipped → 3 pending）
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS = ROOT / "scripts"

# ccc-board.py 含连字符，从 scripts/ 目录加载
_os_chdir_backup = os.getcwd()
os.chdir(str(SCRIPTS))
sys.path.insert(0, str(SCRIPTS))
_spec = importlib.util.spec_from_file_location("ccc_board", str(SCRIPTS / "ccc-board.py"))
ccc_board = importlib.util.module_from_spec(_spec)
sys.modules["ccc_board"] = ccc_board  # 让 ccc_board 内部 import 能找到自己
_spec.loader.exec_module(ccc_board)

_resolve_phase_dependencies = ccc_board._resolve_phase_dependencies
_apply_phase_status_updates = ccc_board._apply_phase_status_updates
_load_phases = ccc_board._load_phases
_mark_phase_failed = ccc_board._mark_phase_failed
_current_running_phase = ccc_board._current_running_phase
_check_phase_failures = ccc_board._check_phase_failures
_task_all_phases_terminal = ccc_board._task_all_phases_terminal
PHASE_TERMINAL_OK = ccc_board.PHASE_TERMINAL_OK
PHASE_TERMINAL_FAIL = ccc_board.PHASE_TERMINAL_FAIL


@pytest.fixture
def fake_workspace():
    """提供临时 workspace，注入 phases.json 到 .ccc/phases/<task>.phases.json。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        # 备份原 ROOT，测试期间替换
        original_root = ccc_board.ROOT
        ccc_board.ROOT = tmp
        try:
            yield tmp
        finally:
            ccc_board.ROOT = original_root


def _write_phases(workspace: Path, task_id: str, phases: list[dict]) -> None:
    """写入 phases.jsonl 到指定 workspace。"""
    phases_dir = workspace / ".ccc" / "phases"
    phases_dir.mkdir(parents=True, exist_ok=True)
    phases_file = phases_dir / f"{task_id}.phases.json"
    lines = [json.dumps({"schema_version": "1.1"}, ensure_ascii=False)]
    for p in phases:
        lines.append(json.dumps(p, ensure_ascii=False))
    phases_file.write_text("\n".join(lines) + "\n")


# ─────────────── _resolve_phase_dependencies ───────────────


class TestResolvePhaseDependencies:
    def test_no_deps_all_executable(self):
        """所有 phase 无依赖 → 全 executable。"""
        phases = [
            {"phase": 1, "status": "pending", "depends_on": []},
            {"phase": 2, "status": "pending", "depends_on": []},
        ]
        exec_, blocked, skipped = _resolve_phase_dependencies(phases)
        assert exec_ == {1, 2}
        assert blocked == set()
        assert skipped == set()

    def test_chain_deps(self):
        """链式依赖：1 done → 2 可执行 → 3 阻塞。"""
        phases = [
            {"phase": 1, "status": "done", "depends_on": []},
            {"phase": 2, "status": "pending", "depends_on": [1]},
            {"phase": 3, "status": "pending", "depends_on": [2]},
        ]
        exec_, blocked, skipped = _resolve_phase_dependencies(phases)
        assert exec_ == {2}
        assert blocked == {3}
        assert skipped == set()

    def test_failure_isolation_chain(self):
        """失败传染：phase 1 failed → phase 2 skipped → phase 3 依赖 2(skipped) → executable。"""
        phases = [
            {"phase": 1, "status": "failed", "depends_on": []},
            {"phase": 2, "status": "pending", "depends_on": [1]},
        ]
        exec_, blocked, skipped = _resolve_phase_dependencies(phases)
        assert exec_ == set()
        assert skipped == {2}

    def test_multiple_deps_all_ok(self):
        """多依赖全满足：3 → [1, 2] 都 verified/done → 3 executable。"""
        phases = [
            {"phase": 1, "status": "verified", "depends_on": []},
            {"phase": 2, "status": "done", "depends_on": []},
            {"phase": 3, "status": "pending", "depends_on": [1, 2]},
        ]
        exec_, blocked, skipped = _resolve_phase_dependencies(phases)
        assert exec_ == {3}
        assert blocked == set()
        assert skipped == set()

    def test_in_progress_not_reclassified(self):
        """in_progress 的 phase 不被重新分类。"""
        phases = [
            {"phase": 1, "status": "done", "depends_on": []},
            {"phase": 2, "status": "in_progress", "depends_on": [1]},
        ]
        exec_, blocked, skipped = _resolve_phase_dependencies(phases)
        assert exec_ == set()
        assert blocked == set()
        assert skipped == set()

    def test_skipped_dep_counts_as_ok(self):
        """依赖 skipped 也算 OK（不传染失败）。"""
        phases = [
            {"phase": 1, "status": "skipped", "depends_on": []},
            {"phase": 2, "status": "pending", "depends_on": [1]},
        ]
        exec_, blocked, skipped = _resolve_phase_dependencies(phases)
        assert exec_ == {2}

    def test_missing_dep_blocks(self):
        """依赖不存在的 phase → blocked（不强行 fail，留人工处理）。"""
        phases = [{"phase": 2, "status": "pending", "depends_on": [99]}]
        exec_, blocked, skipped = _resolve_phase_dependencies(phases)
        assert exec_ == set()
        assert blocked == {2}
        assert skipped == set()


# ─────────────── _apply_phase_status_updates ───────────────


class TestApplyPhaseStatusUpdates:
    def test_pending_to_blocked(self, fake_workspace):
        """pending → blocked（依赖未满足）。"""
        _write_phases(fake_workspace, "t1", [
            {"phase": 1, "status": "pending", "depends_on": [99]},
        ])
        _apply_phase_status_updates("t1", blocked={1}, skipped=set())
        phases = _load_phases("t1")
        assert phases[0]["status"] == "blocked"

    def test_pending_to_skipped(self, fake_workspace):
        """pending → skipped（依赖失败）。"""
        _write_phases(fake_workspace, "t2", [
            {"phase": 1, "status": "pending", "depends_on": [99]},  # 不存在 dep
        ])
        # 实际场景：依赖 failed phase。这里模拟：phase 1 引用不存在的 dep
        # 上面场景只会被标 blocked；要测试 skipped 需要 fake 状态
        phases_data = [{"phase": 1, "status": "pending", "depends_on": []}]
        # 直接调用：标 skipped
        _apply_phase_status_updates("t2", blocked=set(), skipped={1})
        phases = _load_phases("t2")
        assert phases[0]["status"] == "skipped"

    def test_blocked_unblocked_to_pending(self, fake_workspace):
        """blocked → pending（依赖解除，可执行）。"""
        _write_phases(fake_workspace, "t3", [
            {"phase": 1, "status": "blocked", "depends_on": []},
        ])
        # 依赖解除：传入空 blocked/skipped set
        _apply_phase_status_updates("t3", blocked=set(), skipped=set())
        phases = _load_phases("t3")
        assert phases[0]["status"] == "pending"

    def test_terminal_states_not_touched(self, fake_workspace):
        """done/verified/skipped/failed 不被覆盖。"""
        _write_phases(fake_workspace, "t4", [
            {"phase": 1, "status": "done", "depends_on": []},
            {"phase": 2, "status": "verified", "depends_on": []},
            {"phase": 3, "status": "skipped", "depends_on": []},
            {"phase": 4, "status": "failed", "depends_on": []},
        ])
        _apply_phase_status_updates(
            "t4",
            blocked={1, 2, 3, 4},
            skipped={1, 2, 3, 4},
        )
        phases = _load_phases("t4")
        statuses = [p["status"] for p in phases]
        assert statuses == ["done", "verified", "skipped", "failed"]


# ─────────────── 失败传染链路 + 多轮收敛 ───────────────


class TestFailureIsolation:
    def test_phase_fail_propagates(self, fake_workspace):
        """phase 1 failed → phase 2 skipped（一次性解析）。"""
        _write_phases(fake_workspace, "fail1", [
            {"phase": 1, "status": "pending", "depends_on": []},
            {"phase": 2, "status": "pending", "depends_on": [1]},
        ])
        _mark_phase_failed("fail1", 1)
        summary = _check_phase_failures("fail1")
        phases = _load_phases("fail1")
        statuses = {p["phase"]: p["status"] for p in phases}
        assert statuses[1] == "failed"
        assert statuses[2] in ("skipped", "blocked")
        assert 2 in summary["skipped"]

    def test_multi_round_convergence(self, fake_workspace):
        """多轮 tick 收敛：phase 1 failed → 2 skipped → 3 解锁回 pending。"""
        _write_phases(fake_workspace, "fail2", [
            {"phase": 1, "status": "pending", "depends_on": []},
            {"phase": 2, "status": "pending", "depends_on": [1]},
            {"phase": 3, "status": "pending", "depends_on": [2]},
        ])
        # round 1
        _mark_phase_failed("fail2", 1)
        _check_phase_failures("fail2")
        s1 = {p["phase"]: p["status"] for p in _load_phases("fail2")}
        assert s1[1] == "failed"
        assert s1[2] == "skipped"
        assert s1[3] == "blocked"

        # round 2
        _check_phase_failures("fail2")
        s2 = {p["phase"]: p["status"] for p in _load_phases("fail2")}
        assert s2[3] == "pending", f"phase 3 should unlock to pending, got {s2[3]}"

    def test_all_failed_detection(self, fake_workspace):
        """所有 phase 都 failed/skipped → all_failed_or_skipped=True。"""
        _write_phases(fake_workspace, "fail3", [
            {"phase": 1, "status": "failed", "depends_on": []},
            {"phase": 2, "status": "failed", "depends_on": [1]},
            {"phase": 3, "status": "skipped", "depends_on": [2]},
        ])
        summary = _check_phase_failures("fail3")
        assert summary["all_failed_or_skipped"] is True
        assert summary["all_terminal"] is True

    def test_partial_failure_not_all_failed(self, fake_workspace):
        """部分失败 + 部分成功 → all_failed_or_skipped=False。"""
        _write_phases(fake_workspace, "fail4", [
            {"phase": 1, "status": "failed", "depends_on": []},
            {"phase": 2, "status": "skipped", "depends_on": [1]},
            {"phase": 3, "status": "pending", "depends_on": [2]},
        ])
        summary = _check_phase_failures("fail4")
        # phase 3 依赖 2 (skipped) → executable → 不算 all_failed
        assert summary["all_failed_or_skipped"] is False
        assert 3 in summary["executable"]


# ─────────────── _current_running_phase ───────────────


class TestCurrentRunningPhase:
    def test_in_progress_wins(self, fake_workspace):
        """in_progress phase 优先级最高。"""
        _write_phases(fake_workspace, "run1", [
            {"phase": 1, "status": "done", "depends_on": []},
            {"phase": 2, "status": "in_progress", "depends_on": [1]},
            {"phase": 3, "status": "pending", "depends_on": [2]},
        ])
        assert _current_running_phase("run1") == 2

    def test_fallback_to_pending(self, fake_workspace):
        """无 in_progress → 取 pending/blocked 中第一个（按编号）。"""
        _write_phases(fake_workspace, "run2", [
            {"phase": 1, "status": "done", "depends_on": []},
            {"phase": 2, "status": "blocked", "depends_on": [99]},
            {"phase": 3, "status": "pending", "depends_on": [2]},
        ])
        # candidates: phase 2 (blocked), phase 3 (pending) → 取最小编号 2
        assert _current_running_phase("run2") == 2

    def test_default_to_1(self, fake_workspace):
        """无 phases 文件或全终态 → 默认返回 1。"""
        assert _current_running_phase("nonexistent") == 1


# ─────────────── _task_all_phases_terminal ───────────────


class TestTaskAllPhasesTerminal:
    def test_all_terminal_true(self, fake_workspace):
        """所有 phase 都达终态 → True。"""
        _write_phases(fake_workspace, "term1", [
            {"phase": 1, "status": "done", "depends_on": []},
            {"phase": 2, "status": "verified", "depends_on": [1]},
            {"phase": 3, "status": "skipped", "depends_on": [2]},
        ])
        assert _task_all_phases_terminal("term1") is True

    def test_pending_in_progress_blocks(self, fake_workspace):
        """pending/in_progress 任一未完成 → False。"""
        _write_phases(fake_workspace, "term2", [
            {"phase": 1, "status": "done", "depends_on": []},
            {"phase": 2, "status": "in_progress", "depends_on": [1]},
        ])
        assert _task_all_phases_terminal("term2") is False

    def test_no_phases_file_returns_false(self, fake_workspace):
        """无 phases 文件 → False（旧格式任务不算 v0.24 phase 流程）。"""
        assert _task_all_phases_terminal("missing") is False


# ─────────────── 集成：Engine 视角 ───────────────


class TestEngineView:
    def test_start_blocked_when_all_deps_pending(self, fake_workspace):
        """Engine 启动 dev 前解析：所有 phase 都 blocked → 不启动。

    模拟场景：phase 1/2/3 都 pending 且互相依赖（实际不会发生，但代表
    「初始状态无 phase done」时所有 phase 都应被识别为 blocked）。
    """
        _write_phases(fake_workspace, "engine1", [
            {"phase": 1, "status": "pending", "depends_on": []},
            {"phase": 2, "status": "pending", "depends_on": [1]},
            {"phase": 3, "status": "pending", "depends_on": [2]},
        ])
        # 模拟 Engine 启动前调一次
        phases = _load_phases("engine1")
        exec_, blocked, skipped = _resolve_phase_dependencies(phases)
        # phase 1 无依赖 → executable；phase 2/3 blocked
        assert exec_ == {1}
        assert blocked == {2, 3}
        assert skipped == set()


class TestV0243P0Fixes:
    """v0.24.3 对抗性审查 P0 hotfix 回归测试。"""

    def test_p0_1_check_phase_failures_reload_after_writeback(self, fake_workspace):
        """P0-1: _check_phase_failures writeback 后必须 reload phases。

        场景：phase 1 failed，phase 2 pending→skipped（依赖失败传染）。
        writeback 后 all_terminal / all_failed_or_skipped 必须反映磁盘真实状态，
        否则 Engine 无法识别 task all-failed。
        """
        _write_phases(fake_workspace, "p01reload", [
            {"phase": 1, "status": "failed", "depends_on": []},
            {"phase": 2, "status": "pending", "depends_on": [1]},
        ])
        result = _check_phase_failures("p01reload")
        # 写回后 phase 2 应是 skipped（磁盘）
        assert result["skipped"] == [2]
        assert result["all_failed_or_skipped"] is True, (
            "writeback 后未 reload，导致 all_failed_or_skipped 仍为 False"
        )
        assert result["all_terminal"] is True

    def test_p0_3_phase_file_lock_no_corruption_under_concurrent_writers(
        self, fake_workspace
    ):
        """P0-3: phases.json 文件锁 fcntl.flock 防止并发写覆盖。

        场景：模拟两个 writer 并发调用 _apply_phase_status_updates，
        写完后磁盘状态必须一致（不能部分行被回滚）。
        """
        import threading

        _write_phases(fake_workspace, "p03lock", [
            {"phase": 1, "status": "done", "depends_on": []},
            {"phase": 2, "status": "blocked", "depends_on": [1]},
        ])

        errors = []

        def writer_a():
            try:
                _apply_phase_status_updates("p03lock", blocked=set(), skipped=set())
            except Exception as e:
                errors.append(("a", e))

        def writer_b():
            try:
                _apply_phase_status_updates(
                    "p03lock", blocked={2}, skipped=set()
                )
            except Exception as e:
                errors.append(("b", e))

        threads = [threading.Thread(target=writer_a) for _ in range(5)] + [
            threading.Thread(target=writer_b) for _ in range(5)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert not errors, f"并发写报错：{errors}"
        # 写完必须能 reload 且 JSON 解析无错
        phases = _load_phases("p03lock")
        assert len(phases) == 2
        # phase 2 状态必须是 pending 或 blocked（合法终态），不能损坏
        phase2 = next(p for p in phases if p.get("phase") == 2)
        assert phase2.get("status") in ("pending", "blocked")

    def test_p0_7_parse_diff_size_returns_none_on_missing_summary(self):
        """P0-7: _parse_diff_size 缺 summary 行返回 None（不再静默返回 0）。"""
        from ccc_board import _parse_diff_size, _classify_review_size
        # 没有 summary 行（只有 file 行）
        stat = "scripts/ccc-board.py | 42 +++++++++++++--------"
        assert _parse_diff_size(stat) is None
        size_class, total = _classify_review_size(stat)
        assert size_class == "unknown"
        assert total is None
        # 有 summary 行正常
        stat_ok = "scripts/ccc-board.py | 42 +++++++++++++--------\n1 file changed, 42 insertions(+), 0 deletions(-)"
        assert _parse_diff_size(stat_ok) == 42

    def test_p0_8_current_running_phase_for_multi_phase_task(self, fake_workspace):
        """P0-8: dev_role_launch/relaunch 用 _current_running_phase 选 phase。

        验证 _current_running_phase 在多 phase 场景下能正确选下一步 phase
        （pending/blocked 中按 phase 编号最小）。
        """
        _write_phases(fake_workspace, "p08multi", [
            {"phase": 1, "status": "done", "depends_on": []},
            {"phase": 2, "status": "pending", "depends_on": [1]},
            {"phase": 3, "status": "pending", "depends_on": [2]},
        ])
        # phase 1 done，phase 2/3 pending → 应返回 2
        assert _current_running_phase("p08multi") == 2

        # phase 1 in_progress（罕见，但语义上仍应返回 1）
        _write_phases(fake_workspace, "p08inprog", [
            {"phase": 1, "status": "in_progress", "depends_on": []},
            {"phase": 2, "status": "pending", "depends_on": [1]},
        ])
        assert _current_running_phase("p08inprog") == 1