"""KPI R4: short-path fail budget + feature_seed deterministic e04."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))


@pytest.fixture()
def ws_git(tmp_path: Path):
    ws = tmp_path / "app"
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
    for col in ("testing", "planned", "abnormal", "in_progress"):
        (ws / ".ccc" / "board" / col).mkdir(parents=True)
    (ws / ".ccc" / "plans").mkdir(parents=True)
    (ws / ".ccc" / "phases").mkdir(parents=True)
    (ws / ".ccc" / "reports").mkdir(parents=True)
    (ws / ".ccc" / "pids").mkdir(parents=True)
    return ws


def test_feature_seed_writes_probe_not_paper(ws_git: Path):
    from board.roles.script_seed import run_feature_seed, should_use_feature_seed

    tid = "feat-seed-w1"
    probe = "scripts/eff23r2_ccc_demo_feature_probe.py"
    task = {
        "id": tid,
        "title": "feature DRY_RUN 探针",
        "executor": "python",
        "card_kind": "work",
    }
    (ws_git / ".ccc" / "plans" / f"{tid}.plan.md").write_text(
        f"## Phase 1\n- `{probe}`\n禁止写 paper_intent_probe.py\n"
        f"## 验收\n- test -f {probe}\n- DRY_RUN=true python3 {probe}\n",
        encoding="utf-8",
    )
    (ws_git / ".ccc" / "phases" / f"{tid}.phases.json").write_text(
        json.dumps({"phase": 1, "scope": [probe]}) + "\n", encoding="utf-8"
    )
    (ws_git / ".ccc" / "board" / "in_progress" / f"{tid}.jsonl").write_text(
        json.dumps(task) + "\n", encoding="utf-8"
    )
    assert should_use_feature_seed(ws_git, task) is True
    r = run_feature_seed(ws_git, tid)
    assert r.get("ok") is True, r
    assert (ws_git / probe).is_file()
    assert not (ws_git / "scripts" / "paper_intent_probe.py").exists()
    body = (ws_git / probe).read_text()
    assert "paper_intent_probe" not in body or "not paper_intent" in body.lower()


def test_short_path_fail_budget_abnormals_after_max(ws_git: Path, monkeypatch):
    import importlib.util

    path = ROOT / "scripts" / "ccc-engine.py"
    spec = importlib.util.spec_from_file_location("ccc_engine_kpi_r4", path)
    assert spec and spec.loader
    eng = importlib.util.module_from_spec(spec)
    sys.modules["ccc_engine_kpi_r4"] = eng
    spec.loader.exec_module(eng)

    tid = "hygiene-storm-w1"
    store = MagicMock()
    store.find_task.side_effect = lambda t: (
        ("in_progress", {"id": tid, "note": ""})
        if store.move_task.call_count < 3
        else ("abnormal", {"id": tid, "note": ""})
    )
    # first two fails: in_progress; after budget: still call move
    cols = ["in_progress", "in_progress", "in_progress"]

    def _find(t):
        return (cols[min(store.move_task.call_count, len(cols) - 1)], {"id": tid, "note": ""})

    store.find_task.side_effect = _find
    monkeypatch.setattr(eng, "_log_stats", lambda *a, **k: None)
    monkeypatch.setattr(eng, "engine_log", lambda *a, **k: None)
    monkeypatch.setattr(eng, "_SHORT_PATH_FAIL_MAX", 3)

    for i in range(3):
        eng._handle_short_path_failure(  # noqa: SLF001
            ws_git, tid, store, label="app", path="board_ops", why=f"fail-{i}"
        )
    # third call should move to abnormal
    moves = [c.args for c in store.move_task.call_args_list]
    assert any(m[2] == "abnormal" for m in moves), moves
    fail_f = ws_git / ".ccc" / "pids" / f"{tid}.short_path_fails"
    assert fail_f.is_file()
    assert int(fail_f.read_text().splitlines()[0]) >= 3
