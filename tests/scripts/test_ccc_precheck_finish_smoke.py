"""test_ccc_precheck_finish_smoke.py — v1.2.0 流程跑通 T1.7

覆盖 ccc-precheck.sh / ccc-finish.sh 的 5 项门控的关键路径:
1. ccc-precheck.sh 缺少 state.md → FAIL（红线 10 强制）
2. ccc-precheck.sh 含完整 state.md/profile.md/plan/phases → PASS
3. ccc-precheck.sh phases.json 非 JSONL → FAIL（红线 5）
4. ccc-finish.sh report.md 不存在 → FAIL（Lesson 4）
5. ccc-finish.sh 完整 4 文件契约 → PASS
6. ccc-finish.sh verdict.md < 3 probes → FAIL（红线 11）
7. ccc-finish.sh --fill-verdict-ref 自动回填
"""
from __future__ import annotations
import json
import os
import re
import subprocess
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
PRECHECK = ROOT / "scripts" / "ccc-precheck.sh"
FINISH = ROOT / "scripts" / "ccc-finish.sh"


def _run(args, cwd):
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=False)


def _make_plan(ws, task):
    """Make a minimal plan.md with all required fields."""
    plan_dir = ws / ".ccc" / "plans"
    plan_dir.mkdir(parents=True, exist_ok=True)
    plan = plan_dir / f"{task}.plan.md"
    plan.write_text(textwrap.dedent(f"""
        # Plan: {task}
        ## 范围
        - **目标**: 测试任务
        - **只改文件**: `scripts/demo.sh` `tests/test_demo.sh`
        - **执行方式**: auto
        - **Phase 数**: 1
        ## 改动 1: demo
        ### 做什么
        demo
        ### 怎么做
        demo
        ### 验收
        demo
        ## Commit 计划
        | Phase | 改动 | Commit |
        |-------|------|--------|
        | 1 | demo | feat: demo |
        """).strip() + "\n")
    return plan


def _make_phases(ws, task, status="pending"):
    phases_dir = ws / ".ccc" / "phases"
    phases_dir.mkdir(parents=True, exist_ok=True)
    pf = phases_dir / f"{task}.phases.json"
    pf.write_text(json.dumps({"phase": 1, "name": "demo", "status": status,
                              "subtasks": {"1.1": status}, "commit": None, "notes": ""}) + "\n")
    return pf


def _make_profile(ws):
    (ws / ".ccc").mkdir(exist_ok=True)
    (ws / ".ccc" / "profile.md").write_text("# profile\n")
    return ws / ".ccc" / "profile.md"


def _make_state(ws):
    (ws / ".ccc").mkdir(exist_ok=True)
    (ws / ".ccc" / "state.md").write_text("# state\n")
    return ws / ".ccc" / "state.md"


@pytest.fixture
def workspace(tmp_path):
    """Make a temp git repo acting as workspace."""
    ws = tmp_path / "ws"
    ws.mkdir()
    _run(["git", "init", "-b", "main"], cwd=ws)
    _run(["git", "config", "user.email", "t@x"], cwd=ws)
    _run(["git", "config", "user.name", "T"], cwd=ws)
    (ws / "README.md").write_text("# x\n")
    _run(["git", "add", "README.md"], cwd=ws)
    _run(["git", "commit", "-m", "init"], cwd=ws)
    return ws


# ===== ccc-precheck.sh =====

def test_precheck_fails_without_state(workspace):
    """红线 10: 缺 state.md → Gate 1 FAIL."""
    task = "no-state"
    _make_profile(workspace)
    _make_plan(workspace, task)
    _make_phases(workspace, task)

    res = _run(["bash", str(PRECHECK), str(workspace), task, "--skip-watchdog"], cwd=workspace)
    assert res.returncode == 1, f"expected FAIL, got {res.returncode}\n{res.stdout}"
    assert "state.md 不存在" in res.stdout
    assert "红线 10" in res.stdout


def test_precheck_fails_without_profile(workspace):
    """红线 7: 缺 profile.md → Gate 2 FAIL."""
    task = "no-profile"
    _make_state(workspace)
    _make_plan(workspace, task)
    _make_phases(workspace, task)

    res = _run(["bash", str(PRECHECK), str(workspace), task, "--skip-watchdog"], cwd=workspace)
    assert res.returncode == 1
    assert "profile.md 不存在" in res.stdout


def test_precheck_fails_on_invalid_jsonl(workspace):
    """红线 5: phases.json 不是 JSONL → Gate 4 FAIL."""
    task = "bad-jsonl"
    _make_state(workspace)
    _make_profile(workspace)
    _make_plan(workspace, task)
    pf = workspace / ".ccc" / "phases" / f"{task}.phases.json"
    pf.parent.mkdir(parents=True, exist_ok=True)
    pf.write_text("not-valid-json{\n")  # malformed

    res = _run(["bash", str(PRECHECK), str(workspace), task, "--skip-watchdog"], cwd=workspace)
    assert res.returncode == 1
    assert "phases.json" in res.stdout and "JSONL" in res.stdout


def test_precheck_passes_on_minimal_valid(workspace):
    """最小合规 plan: state + profile + plan + phases + watchdog skip → PASS."""
    task = "ok-task"
    _make_state(workspace)
    _make_profile(workspace)
    _make_plan(workspace, task)
    _make_phases(workspace, task)

    res = _run(["bash", str(PRECHECK), str(workspace), task, "--skip-watchdog"], cwd=workspace)
    assert res.returncode == 0, f"expected PASS, got {res.returncode}\n{res.stdout}\n{res.stderr}"
    assert "ccc-precheck PASS" in res.stdout


def test_precheck_with_phase_id_field(workspace):
    """兼容 phase_id 字段名（hello-ccc-demo 用过）。"""
    task = "phase-id-task"
    _make_state(workspace)
    _make_profile(workspace)
    _make_plan(workspace, task)
    pf = workspace / ".ccc" / "phases" / f"{task}.phases.json"
    pf.parent.mkdir(parents=True, exist_ok=True)
    pf.write_text(json.dumps({"phase_id": 1, "name": "demo", "status": "pending"}) + "\n")

    res = _run(["bash", str(PRECHECK), str(workspace), task, "--skip-watchdog"], cwd=workspace)
    assert res.returncode == 0, f"phase_id schema should be accepted:\n{res.stdout}"


# ===== ccc-finish.sh =====

def test_finish_fails_without_report(workspace):
    """Lesson 4: report.md 缺失 → Gate 1 FAIL."""
    task = "no-report"
    _make_state(workspace)
    _make_profile(workspace)
    _make_plan(workspace, task)
    _make_phases(workspace, task)
    # 不写 report.md / verdict.md

    res = _run(["bash", str(FINISH), str(workspace), task], cwd=workspace)
    assert res.returncode == 1
    assert "report.md 不存在或为空" in res.stdout


def test_finish_fails_when_verdict_has_under_3_probes(workspace):
    """红线 11: verdict.md < 3 probes → Gate 2 FAIL."""
    task = "few-probes"
    _make_state(workspace)
    _make_profile(workspace)
    _make_plan(workspace, task)
    _make_phases(workspace, task)

    # 写 report.md
    (workspace / ".ccc" / "reports").mkdir(parents=True, exist_ok=True)
    (workspace / ".ccc" / "reports" / f"{task}.report.md").write_text(
        f"# report\n> VERDICT: .ccc/verdicts/{task}.verdict.md\n"
    )

    # 写 verdict.md 仅 2 probes
    (workspace / ".ccc" / "verdicts").mkdir(parents=True, exist_ok=True)
    (workspace / ".ccc" / "verdicts" / f"{task}.verdict.md").write_text(textwrap.dedent("""
        # Verdict
        ## VERDICT: PASS
        ## Probe 1 — only 2 probes
        - result: PASS
        ## Probe 2 — still only 2
        - result: PASS
        """).strip())

    res = _run(["bash", str(FINISH), str(workspace), task], cwd=workspace)
    assert res.returncode == 1
    assert "verdict.md 仅" in res.stdout and "probe" in res.stdout


def test_finish_passes_full_4_file(workspace):
    """完整 4 文件契约 + ≥3 probes + report VERDICT ref → PASS."""
    task = "full-pass"
    _make_state(workspace)
    _make_profile(workspace)
    _make_plan(workspace, task)
    pf = _make_phases(workspace, task, status="done")
    pf.write_text(json.dumps({"phase": 1, "name": "demo", "status": "done",
                              "subtasks": {"1.1": "done"}, "commit": "abc1234",
                              "notes": "completed"}) + "\n")

    # 写 report.md 含 > VERDICT 引用
    (workspace / ".ccc" / "reports").mkdir(parents=True, exist_ok=True)
    (workspace / ".ccc" / "reports" / f"{task}.report.md").write_text(textwrap.dedent(f"""
        # report
        > VERDICT: .ccc/verdicts/{task}.verdict.md
        ## 改动文件清单
        | 文件 | 改动类型 |
        |------|----------|
        | `scripts/demo.sh` | create |
        """).strip())

    # 写 verdict.md ≥3 probes
    (workspace / ".ccc" / "verdicts").mkdir(parents=True, exist_ok=True)
    (workspace / ".ccc" / "verdicts" / f"{task}.verdict.md").write_text(textwrap.dedent("""
        # Verdict
        ## VERDICT: PASS
        ## Probe 1 — file
        - result: PASS
        ## Probe 2 — content
        - result: PASS
        ## Probe 3 — boundary
        - result: PASS
        """).strip())

    res = _run(["bash", str(FINISH), str(workspace), task], cwd=workspace)
    # Gate 4 会因无实际 git 改动而 PASS（fallback: 无改动 = 无越界）
    # Gate 5: phases.json done = 1, plan phase = 1 → PASS
    # 注意: Gate 4 在无 working tree 改动 + 无匹配 commit 时会 log_pass
    assert res.returncode == 0, f"expected PASS, got {res.returncode}\n{res.stdout}\n{res.stderr}"
    assert "ccc-finish PASS" in res.stdout


def test_finish_fill_verdict_ref_appends(workspace):
    """--fill-verdict-ref 自动回填 VERDICT 引用到 report.md 顶部。"""
    task = "fill-ref"
    _make_state(workspace)
    _make_profile(workspace)
    _make_plan(workspace, task)
    _make_phases(workspace, task)

    # report.md 不含 > VERDICT 引用
    (workspace / ".ccc" / "reports").mkdir(parents=True, exist_ok=True)
    report_path = workspace / ".ccc" / "reports" / f"{task}.report.md"
    report_path.write_text("# report (no verdict ref yet)\n")

    # verdict.md 齐全
    (workspace / ".ccc" / "verdicts").mkdir(parents=True, exist_ok=True)
    (workspace / ".ccc" / "verdicts" / f"{task}.verdict.md").write_text(textwrap.dedent("""
        # Verdict
        ## VERDICT: PASS
        ## Probe 1
        ## Probe 2
        ## Probe 3
        """).strip())

    res = _run(["bash", str(FINISH), str(workspace), task, "--fill-verdict-ref"], cwd=workspace)
    # 该 task 的 report.md 已被改, 重新检查
    new_content = report_path.read_text()
    assert "> **VERDICT:" in new_content
    assert task in new_content


# ===== 集成: precheck + finish 都跑同一个 task =====

def test_precheck_then_finish_full_cycle(workspace):
    """完整周期: precheck PASS → 写 report/verdict → finish PASS。"""
    task = "cycle"
    _make_state(workspace)
    _make_profile(workspace)
    _make_plan(workspace, task)
    _make_phases(workspace, task, status="done")
    # 更新 phases done
    (workspace / ".ccc" / "phases" / f"{task}.phases.json").write_text(
        json.dumps({"phase": 1, "name": "d", "status": "done",
                    "subtasks": {"1.1": "done"}, "commit": "a1b2c3d", "notes": ""}) + "\n"
    )

    # 1) precheck
    r1 = _run(["bash", str(PRECHECK), str(workspace), task, "--skip-watchdog"], cwd=workspace)
    assert r1.returncode == 0, f"precheck FAIL: {r1.stdout}"

    # 2) 模拟 Executor 写 report + verdict
    (workspace / ".ccc" / "reports").mkdir(parents=True, exist_ok=True)
    (workspace / ".ccc" / "reports" / f"{task}.report.md").write_text(textwrap.dedent(f"""
        # report
        > VERDICT: .ccc/verdicts/{task}.verdict.md
        ## 改动文件清单
        | 文件 | 改动类型 |
        |------|----------|
        | `scripts/demo.sh` | create |
        """).strip())
    (workspace / ".ccc" / "verdicts").mkdir(parents=True, exist_ok=True)
    (workspace / ".ccc" / "verdicts" / f"{task}.verdict.md").write_text(textwrap.dedent("""
        # Verdict
        ## VERDICT: PASS
        ## Probe 1
        - PASS
        ## Probe 2
        - PASS
        ## Probe 3
        - PASS
        """).strip())

    # 3) finish
    r2 = _run(["bash", str(FINISH), str(workspace), task], cwd=workspace)
    assert r2.returncode == 0, f"finish FAIL: {r2.stdout}\n{r2.stderr}"
    assert "ccc-finish PASS" in r2.stdout