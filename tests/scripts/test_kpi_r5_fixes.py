"""KPI R5: queue indep cohort + hygiene DoD ignores paper-report dirty."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))


def _load_eff():
    path = ROOT / "scripts" / "ccc-stress-efficiency-report.py"
    spec = importlib.util.spec_from_file_location("ccc_stress_efficiency_report", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["ccc_stress_efficiency_report"] = mod
    spec.loader.exec_module(mod)
    return mod


def _load_gate():
    path = ROOT / "scripts" / "ccc-stress-kpi-gate.py"
    spec = importlib.util.spec_from_file_location("ccc_stress_kpi_gate", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["ccc_stress_kpi_gate"] = mod
    spec.loader.exec_module(mod)
    return mod


EFF = _load_eff()
GATE = _load_gate()


def test_serial_successor_detection():
    assert EFF._is_serial_successor_work("epic-w1") is False
    assert EFF._is_serial_successor_work("epic-w2") is True
    assert EFF._is_serial_successor_work("stress-mx-x-util--abc-w2") is True
    assert EFF._is_serial_successor_work("no-suffix") is False


def test_hygiene_commit_with_paper_report_dirty(tmp_path: Path):
    """R4 qb e05 repro: docs/reports paper dirty must not dirty_block hygiene."""
    from _task_commit import ensure_task_commit

    ws = tmp_path / "qb"
    ws.mkdir()
    subprocess.run(["git", "init"], cwd=ws, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "t@t.com"], cwd=ws, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "config", "user.name", "t"], cwd=ws, check=True, capture_output=True
    )
    (ws / "README.md").write_text("x\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=ws, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init"], cwd=ws, check=True, capture_output=True
    )

    tid = "hygiene-w1"
    (ws / ".ccc" / "plans").mkdir(parents=True)
    (ws / ".ccc" / "phases").mkdir(parents=True)
    (ws / ".ccc" / "board" / "in_progress").mkdir(parents=True)
    (ws / ".ccc" / "reports").mkdir(parents=True)
    (ws / "docs" / "reports").mkdir(parents=True)

    (ws / ".ccc" / "plans" / f"{tid}.plan.md").write_text(
        "## 范围\n- `.ccc/board`\n## 验收\n- test -d .ccc/board\n",
        encoding="utf-8",
    )
    (ws / ".ccc" / "phases" / f"{tid}.phases.json").write_text(
        json.dumps({"phase": 1, "scope": [".ccc/board"]}) + "\n",
        encoding="utf-8",
    )
    task = {
        "id": tid,
        "title": "看板卫生",
        "executor": "python",
        "description": "- pipeline: ops\n",
        "tags": ["ops"],
    }
    (ws / ".ccc" / "board" / "in_progress" / f"{tid}.jsonl").write_text(
        json.dumps(task) + "\n", encoding="utf-8"
    )
    (ws / ".ccc" / "reports" / f"{tid}.report.md").write_text(
        "# board_ops\nALL SELF-CHECKS PASSED\n", encoding="utf-8"
    )
    (ws / "docs" / "reports" / "paper-intent-probe-latest.md").write_text(
        "noise\n", encoding="utf-8"
    )

    ok, why, h = ensure_task_commit(ws, tid)
    assert ok, why
    assert h
    # paper report must remain unstaged (dir or file form in porcelain)
    st = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=ws,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "docs" in st.stdout
    # commit message is hygiene DoD — paper path must not be in HEAD tree as new
    show = subprocess.run(
        ["git", "show", "--name-only", "--pretty=format:", "HEAD"],
        cwd=ws,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "paper-intent-probe-latest.md" not in show.stdout
    assert ".ccc/reports" in show.stdout or f"{tid}.report.md" in show.stdout


def test_r4_replay_indep_gate_would_pass():
    """Scientific check: R4-like queues → PASS under indep queue gate."""

    def pct(vals, p):
        if not vals:
            return None
        s = sorted(vals)
        if len(s) == 1:
            return float(s[0])
        k = (len(s) - 1) * (p / 100.0)
        f = int(k)
        c = min(f + 1, len(s) - 1)
        return s[f] + (s[c] - s[f]) * (k - f)

    works = [
        {"id": "d-e08-w1", "queue_wait_s": 0.0},
        {"id": "d-e05-w1", "queue_wait_s": 0.0},
        {"id": "d-e04-w1", "queue_wait_s": 1.0},
        {"id": "d-e01-w1", "queue_wait_s": 0.0},
        {"id": "d-e03-w1", "queue_wait_s": 1.0},
        {"id": "d-util-w1", "queue_wait_s": 12.0},
        {"id": "d-util-w2", "queue_wait_s": 505.0},
        {"id": "q-e08-w1", "queue_wait_s": 0.0},
        {"id": "q-e05-w1", "queue_wait_s": 0.0},
        {"id": "q-e04-w1", "queue_wait_s": 0.0},
        {"id": "q-e01-w1", "queue_wait_s": 234.0},
        {"id": "q-e03-w1", "queue_wait_s": 1.0},
        {"id": "q-util-w1", "queue_wait_s": 247.0},
        {"id": "q-util-w2", "queue_wait_s": 703.0},
    ]
    for w in works:
        w["serial_successor"] = EFF._is_serial_successor_work(w["id"])
    indep = [w["queue_wait_s"] for w in works if not w["serial_successor"]]
    all_q = [w["queue_wait_s"] for w in works]

    rep = {
        "run": "replay-r4",
        "generated_at": "2026-07-23T00:00:00+08:00",
        "work_columns": {"released": 13, "abnormal": 1, "in_progress": 0},
        "epic_split_status": {"done": 11, "failed": 1},
        "epics": [{"id": f"e{i}", "split_status": "done"} for i in range(11)]
        + [{"id": "f", "split_status": "failed"}],
        "works": works,
        "dispatch": {"ok": 12, "n": 12, "rows": [{}] * 12},
        "time_agg": {
            "queue_wait_s": {
                "p50": pct(all_q, 50),
                "p95": pct(all_q, 95),
                "n": len(all_q),
            },
            "queue_wait_indep_s": {
                "p50": pct(indep, 50),
                "p95": pct(indep, 95),
                "n": len(indep),
            },
            "gate_wall_s": {"p50": 47, "p95": 60, "n": 13},
            "e2e_work_s": {"p50": 400, "p95": 775, "n": 13},
            "dev_wall_s": {"p50": 9, "p95": 239, "n": 13},
        },
        "opencode_timings": {"duration_s_fill_rate": 1.0},
        "dev_path": {"dirty_result_n": 0},
        "bottlenecks_hint": [],
    }
    result = GATE.evaluate(rep, GATE.load_scorecard())
    assert result["verdict"] == "PASS", (
        result["primary_fail"],
        [(g["id"], g["actual"], g["ok"]) for g in result["gates"] if not g["ok"]],
    )
    qgate = next(g for g in result["gates"] if g["id"] == "queue_wait_p95_s")
    assert qgate["path"] == "time_agg.queue_wait_indep_s.p95"
    assert qgate["ok"] is True
    assert float(qgate["actual"]) <= 300
