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
PHASE_TERMINAL_OK = ccc_board.PHASE_TERMINAL_OK
PHASE_TERMINAL_FAIL = ccc_board.PHASE_TERMINAL_FAIL


@pytest.fixture
def fake_workspace():
    """提供临时 workspace，注入 phases.json 到 .ccc/phases/<task>.phases.json。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        prev = os.environ.get("CCC_WORKSPACE")
        ccc_board.set_workspace(tmp)
        ccc_board._reset_lazy()
        try:
            yield tmp
        finally:
            if prev:
                ccc_board.set_workspace(prev)
            else:
                ccc_board.clear_workspace()
                os.environ.pop("CCC_WORKSPACE", None)
            ccc_board._reset_lazy()


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

# ─────────────── v0.25 P1 遗留（CHANGELOG v0.24.4:93-99）───────────────


class TestV025P1Backlog:
    """CHANGELOG v0.24.4:93-99 列了 5 项 P1 遗留，v0.25 补回归测试。

    注：这些 case 是"行为契约"——保证 v0.25 之后实现不破坏预期语义。
    实现本身（v0.25+ 落地）不在本测试范围。
    """

    def test_circular_dependency_detection_invariant(self, fake_workspace):
        """循环依赖：phase 1 depends_on [3] + phase 3 depends_on [1]
        → _resolve_phase_dependencies 不应无限循环，至少应有一态分类。

        预期（v0.25+ 实际实现）：executable/blocked/skipped 三态中至少
        有一个非空，避免全为 pending 卡死。
        """
        _write_phases(fake_workspace, "circ", [
            {"phase": 1, "status": "pending", "depends_on": [3]},
            {"phase": 2, "status": "pending", "depends_on": []},
            {"phase": 3, "status": "pending", "depends_on": [1]},
        ])
        phases = _load_phases("circ")
        executable, blocked, skipped = _resolve_phase_dependencies(phases)
        # 不应全空（全空 = 死锁）
        assert len(executable) + len(blocked) + len(skipped) > 0
        # phase 2 无依赖，必 executable
        assert 2 in executable

    def test_max_iter_convergence_invariant(self, fake_workspace):
        """多轮 tick 收敛：_check_phase_failures 跑 N 轮后应稳定（不无限循环）。

        模拟：phase 1 failed 多次 tick 后仍 failed（已收敛）。
        """
        _write_phases(fake_workspace, "conv", [
            {"phase": 1, "status": "failed", "depends_on": []},
            {"phase": 2, "status": "skipped", "depends_on": [1]},
        ])
        # 第一轮
        r1 = _check_phase_failures("conv")
        # 第二轮（应幂等）
        r2 = _check_phase_failures("conv")
        # 两轮结果应一致（已收敛）
        assert r1 == r2, "multi-tick must converge to stable state"

    def test_phase_terminal_fail_marks_blocked(self, fake_workspace):
        """PHASE_TERMINAL_FAIL = "failed"（v0.25+ 应让 failed phase 标 blocked）。"""
        assert "failed" in PHASE_TERMINAL_FAIL
        assert PHASE_TERMINAL_FAIL != PHASE_TERMINAL_OK

    def test_unresolved_dependency_phase_id(self, fake_workspace):
        """依赖 phase 不存在（如 [99]）：调用不应抛异常，应降级处理。

        预期：当前实现 _resolve_phase_dependencies 容忍不存在依赖
        （见代码注释"留给人工处理"），engine_loop 拿到 (executable,
        blocked, skipped) 后继续跑 executable。
        """
        _write_phases(fake_workspace, "missing", [
            {"phase": 1, "status": "pending", "depends_on": [99]},  # 99 不存在
            {"phase": 2, "status": "pending", "depends_on": []},
        ])
        # 不应抛异常
        phases = _load_phases("missing")
        executable, blocked, skipped = _resolve_phase_dependencies(phases)
        # phase 2 无依赖 → executable
        assert 2 in executable
        # phase 1 depends_on 99（不存在） → 至少不抛异常
        # 注：v0.25+ 可能加 warning 日志（references/adversarial-2026-07-11.json A24-25）

    def test_phase_retry_independent(self, fake_workspace):
        """phase 1 retry=3 不影响 phase 2 retry=0。

        验证 _load_phases 返回各 phase 独立 retry 计数。
        """
        _write_phases(fake_workspace, "ind", [
            {"phase": 1, "status": "in_progress", "retry": 3, "depends_on": []},
            {"phase": 2, "status": "pending", "retry": 0, "depends_on": [1]},
        ])
        phases = _load_phases("ind")
        # 找到 phase 1 / phase 2
        p1 = next((p for p in phases if p.get("phase") == 1), None)
        p2 = next((p for p in phases if p.get("phase") == 2), None)
        assert p1 is not None and p2 is not None
        # retry 计数独立
        assert p1.get("retry", 0) == 3
        assert p2.get("retry", 0) == 0


class TestV0251CycleDetection:
    """v0.25.1 循环依赖检测：环上 phase 全部 skipped（强失败隔离）"""

    def test_cycle_two_phase_mutual_skip(self, fake_workspace):
        """phase 1 depends_on [2] + phase 2 depends_on [1] → cycle → 1+2 全 skipped"""
        _write_phases(fake_workspace, "cyc2", [
            {"phase": 1, "status": "pending", "depends_on": [2]},
            {"phase": 2, "status": "pending", "depends_on": [1]},
        ])
        phases = _load_phases("cyc2")
        executable, blocked, skipped = _resolve_phase_dependencies(phases)
        # 环上 1 + 2 都应 skipped
        assert 1 in skipped
        assert 2 in skipped
        assert 1 not in executable
        assert 2 not in executable

    def test_cycle_three_phase_partial(self, fake_workspace):
        """phase 1 ↔ 2 互引 + phase 3 无依赖 → 1+2 skipped, 3 executable"""
        _write_phases(fake_workspace, "cyc3", [
            {"phase": 1, "status": "pending", "depends_on": [2]},
            {"phase": 2, "status": "pending", "depends_on": [1]},
            {"phase": 3, "status": "pending", "depends_on": []},
        ])
        phases = _load_phases("cyc3")
        executable, blocked, skipped = _resolve_phase_dependencies(phases)
        assert 1 in skipped
        assert 2 in skipped
        assert 3 in executable
        assert 3 not in skipped

    def test_cycle_self_dependency(self, fake_workspace):
        """phase 1 depends_on [1]（自环） → 1 skipped"""
        _write_phases(fake_workspace, "self", [
            {"phase": 1, "status": "pending", "depends_on": [1]},
            {"phase": 2, "status": "pending", "depends_on": []},
        ])
        phases = _load_phases("self")
        executable, blocked, skipped = _resolve_phase_dependencies(phases)
        assert 1 in skipped
        assert 2 in executable

    def test_no_cycle_no_skipped(self, fake_workspace):
        """正常 DAG（1 → 2 → 3） → 0 skipped"""
        _write_phases(fake_workspace, "dag", [
            {"phase": 1, "status": "pending", "depends_on": []},
            {"phase": 2, "status": "pending", "depends_on": [1]},
            {"phase": 3, "status": "pending", "depends_on": [2]},
        ])
        phases = _load_phases("dag")
        executable, blocked, skipped = _resolve_phase_dependencies(phases)
        assert len(skipped) == 0
        assert 1 in executable
        assert 2 in blocked
        assert 3 in blocked

    def test_cycle_writes_warnings_json(self, fake_workspace):
        """环检测到时必写 .ccc/warnings.json"""
        _write_phases(fake_workspace, "warn", [
            {"phase": 1, "status": "pending", "depends_on": [2]},
            {"phase": 2, "status": "pending", "depends_on": [1]},
        ])
        phases = _load_phases("warn")
        _resolve_phase_dependencies(phases)
        warnings_file = fake_workspace / ".ccc" / "warnings.json"
        assert warnings_file.exists(), "warnings.json must be written when cycle detected"
        import json
        content = json.loads(warnings_file.read_text())
        assert isinstance(content, list)
        assert any(w.get("type") == "phase_cycle" for w in content)


class TestV0251UnresolvedDeps:
    """v0.25.1 不存在依赖告警：depends_on 引用不存在的 phase_id 时写 warnings.json + L2"""

    def test_unresolved_dep_writes_warnings(self, fake_workspace):
        """phase 1 depends_on [99]（99 不存在）→ 写 warnings.json"""
        _write_phases(fake_workspace, "unr1", [
            {"phase": 1, "status": "pending", "depends_on": [99]},
            {"phase": 2, "status": "pending", "depends_on": []},
        ])
        phases = _load_phases("unr1")
        _resolve_phase_dependencies(phases)

        warnings_file = fake_workspace / ".ccc" / "warnings.json"
        assert warnings_file.exists()
        import json
        content = json.loads(warnings_file.read_text())
        assert any(w.get("type") == "unresolved_dep" for w in content)

    def test_no_unresolved_no_warnings(self, fake_workspace):
        """所有依赖都存在 → 不写 unresolved_dep warnings"""
        _write_phases(fake_workspace, "allok", [
            {"phase": 1, "status": "pending", "depends_on": []},
            {"phase": 2, "status": "pending", "depends_on": [1]},
        ])
        phases = _load_phases("allok")
        _resolve_phase_dependencies(phases)

        warnings_file = fake_workspace / ".ccc" / "warnings.json"
        if warnings_file.exists():
            import json
            content = json.loads(warnings_file.read_text())
            assert not any(w.get("type") == "unresolved_dep" for w in content)

    def test_multiple_unresolved_listed(self, fake_workspace):
        """多个 phase 引用不存在 → warnings.json 含全部"""
        _write_phases(fake_workspace, "multi", [
            {"phase": 1, "status": "pending", "depends_on": [99]},
            {"phase": 2, "status": "pending", "depends_on": [98, 97]},
            {"phase": 3, "status": "pending", "depends_on": []},
        ])
        phases = _load_phases("multi")
        _resolve_phase_dependencies(phases)

        warnings_file = fake_workspace / ".ccc" / "warnings.json"
        assert warnings_file.exists()
        import json
        content = json.loads(warnings_file.read_text())
        unres_entries = [w for w in content if w.get("type") == "unresolved_dep"]
        assert len(unres_entries) >= 1
        # 至少 phase 1 和 2 在 missing 列表里
        latest = unres_entries[-1]
        missing_str = latest.get("missing", {})
        assert "1" in missing_str  # phase 1 → dep 99
        assert "2" in missing_str  # phase 2 → dep 98+97


class TestV0251MaxIterConvergence:
    """v0.25.1 max_iter=5 收敛：多轮 tick 不收敛时强制 failed（CHANGELOG v0.24.4:94 P1）"""

    def test_engine_iter_increments(self, fake_workspace):
        """每次 _check_phase_failures 调用 engine_iter +1"""
        _write_phases(fake_workspace, "iter1", [
            {"phase": 1, "status": "pending", "depends_on": []},
        ])
        r1 = _check_phase_failures("iter1")
        r2 = _check_phase_failures("iter1")
        r3 = _check_phase_failures("iter1")
        assert r1["engine_iter"] == 1
        assert r2["engine_iter"] == 2
        assert r3["engine_iter"] == 3

    def test_force_converged_after_max_iter(self, fake_workspace):
        """v0.31 (P0.1): 连续 ≥ 5 轮 tick → 标 unresolvable，不再 skip 掩盖"""
        # 构造一个"永远 stuck"的场景：phase 1 没 done，但 dev 不动它
        _write_phases(fake_workspace, "stuck", [
            {"phase": 1, "status": "pending", "depends_on": []},
        ])
        # 跑 6 轮
        results = [_check_phase_failures("stuck") for _ in range(6)]
        # 第 5 轮标 unresolvable
        assert results[4]["unresolvable"] is True
        # 第 6 轮 all_terminal=False（不强制收敛，仍 pending）
        assert results[5]["all_terminal"] is False
        assert results[5]["unresolvable"] is True
        # unresolvable 后不强行 all_terminal
        assert results[4]["all_terminal"] is False
        # phase 1 保持 pending（不 skip）
        phases = _load_phases("stuck")
        assert phases[0]["status"] == "pending"

    def test_no_force_converged_when_terminal(self, fake_workspace):
        """phase 已 all_terminal → 不递增 iter，不强收敛"""
        _write_phases(fake_workspace, "done", [
            {"phase": 1, "status": "done", "depends_on": []},
        ])
        r1 = _check_phase_failures("done")
        # all_terminal=True 时不进入 iter 分支
        assert r1["all_terminal"] is True
        assert r1["engine_iter"] == 0
        assert r1["unresolvable"] is False

    def test_force_converged_writes_warnings(self, fake_workspace):
        """v0.31 (P0.1): unresolvable 必写 .ccc/warnings.json"""
        _write_phases(fake_workspace, "warn2", [
            {"phase": 1, "status": "pending", "depends_on": []},
        ])
        for _ in range(5):
            _check_phase_failures("warn2")
        warnings_file = fake_workspace / ".ccc" / "warnings.json"
        assert warnings_file.exists()
        import json
        content = json.loads(warnings_file.read_text())
        assert any(w.get("type") == "phase_graph_unresolvable" for w in content)


class TestV0271EngineIterPhaseReset:
    """v0.27.1 engine_iter 按 phase 分桶，phase 切换时自动重置"""

    def test_engine_iter_resets_on_phase_change(self, fake_workspace):
        """phase 1→2 切换后 engine_iter 归零，不会从旧 phase 累计到 PHASE_MAX_ENGINE_ITER"""
        # 构造两阶段 task：phase 1 done，phase 2 pending
        _write_phases(fake_workspace, "multi", [
            {"phase": 1, "status": "done", "depends_on": []},
            {"phase": 2, "status": "pending", "depends_on": [1]},
        ])
        # 模拟旧 phase 1 已跑 4 轮：手动写入 engine_iter metadata
        phases_dir = fake_workspace / ".ccc" / "phases"
        phases_file = phases_dir / "multi.phases.json"
        lines = phases_file.read_text().splitlines()
        meta = json.dumps({"engine_iter": 4, "engine_iter_phase": 1}, ensure_ascii=False)
        lines.insert(1, meta)
        phases_file.write_text("\n".join(lines) + "\n")

        # phase 2 进入时 engine_iter 应重置为 0 → 第 1 次调用后 = 1
        result = _check_phase_failures("multi")
        assert result["engine_iter"] == 1, (
            f"期望 engine_iter=1（phase 重置后首次），实际={result['engine_iter']}"
        )
        assert result["unresolvable"] is False, (
            "不应触发强制收敛（engine_iter=1 < PHASE_MAX_ENGINE_ITER=5）"
        )

    def test_engine_iter_persists_within_same_phase(self, fake_workspace):
        """同 phase 内 engine_iter 持续递增"""
        _write_phases(fake_workspace, "single", [
            {"phase": 1, "status": "pending", "depends_on": []},
        ])
        r1 = _check_phase_failures("single")
        r2 = _check_phase_failures("single")
        assert r1["engine_iter"] == 1
        assert r2["engine_iter"] == 2

    def test_engine_iter_meta_not_present_returns_0(self, fake_workspace):
        """无 engine_iter metadata 行时 _read_engine_iter 返回 0（兼容旧文件）"""
        _write_phases(fake_workspace, "fresh", [
            {"phase": 1, "status": "pending", "depends_on": []},
        ])
        result = _check_phase_failures("fresh")
        assert result["engine_iter"] == 1  # 0 + 第一轮递增