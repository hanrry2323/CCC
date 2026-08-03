"""KPI R3: short-path bypass same-ws mutex + commit scope + deterministic FAIL verdict."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

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
    for col in ("testing", "planned", "abnormal", "in_progress", "verified"):
        (ws / ".ccc" / "board" / col).mkdir(parents=True)
    (ws / ".ccc" / "plans").mkdir(parents=True)
    (ws / ".ccc" / "reports").mkdir(parents=True)
    (ws / ".ccc" / "verdicts").mkdir(parents=True)
    return ws


def test_deterministic_fail_writes_verdict(ws_git: Path):
    from board.context import set_workspace
    from board.roles import reviewer as rev

    set_workspace(ws_git)
    tid = "paper-fail-w1"
    task = {
        "id": tid,
        "title": "paper",
        "card_kind": "work",
        "complexity": "small",
        "schema_version": "1.2",
        "status": "testing",
    }
    (ws_git / ".ccc" / "board" / "testing" / f"{tid}.jsonl").write_text(
        json.dumps(task) + "\n"
    )
    (ws_git / ".ccc" / "plans" / f"{tid}.plan.md").write_text(
        "## 验收\n- test -f scripts/missing_probe.py\n",
        encoding="utf-8",
    )
    (ws_git / ".ccc" / "reports" / f"{tid}.result.json").write_text(
        json.dumps({"ok": True, "path": "script_seed"}) + "\n"
    )

    with patch.object(rev, "_detect_review_kind", return_value="script_seed"):
        with patch.object(rev, "_get_git_diff", return_value=("", "")):
            ok = rev._review_one_task(tid)  # noqa: SLF001
    assert ok is False
    v = (ws_git / ".ccc" / "verdicts" / f"{tid}.verdict.md").read_text()
    assert "**Verdict:** FAIL" in v
    assert "fixable" in v.lower() or "acceptance" in v.lower()


def test_ensure_task_commit_scopes_out_unrelated_dirty(ws_git: Path):
    from _task_commit import ensure_task_commit, find_task_commit

    tid = "scoped-w1"
    (ws_git / ".ccc" / "plans" / f"{tid}.plan.md").write_text(
        "## 范围\n- **只改文件**：\n- scripts/target.py\n",
        encoding="utf-8",
    )
    (ws_git / "scripts").mkdir(exist_ok=True)
    (ws_git / "scripts" / "target.py").write_text("x=1\n", encoding="utf-8")
    (ws_git / "unrelated_dirty.py").write_text("noise\n", encoding="utf-8")

    ok, why, h = ensure_task_commit(ws_git, tid)
    assert ok, why
    assert find_task_commit(ws_git, tid) == h
    # unrelated still dirty
    st = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=ws_git,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "unrelated_dirty.py" in st.stdout
    assert "target.py" not in st.stdout or "scripts/target.py" not in [
        ln[3:].strip() for ln in st.stdout.splitlines() if ln.strip()
    ]


def test_log_opencode_done_fills_when_wall_and_result_missing(tmp_path: Path, monkeypatch):
    import importlib.util

    path = ROOT / "scripts" / "ccc-engine.py"
    spec = importlib.util.spec_from_file_location("ccc_engine_kpi_r3", path)
    assert spec and spec.loader
    eng = importlib.util.module_from_spec(spec)
    sys.modules["ccc_engine_kpi_r3"] = eng
    spec.loader.exec_module(eng)

    ws = tmp_path / "ws"
    (ws / ".ccc" / "reports").mkdir(parents=True)
    logged = {}

    def _capture(ws, event, tid, **kw):
        logged.update(kw)
        logged["event"] = event

    monkeypatch.setattr(eng, "_log_stats", _capture)
    eng._log_opencode_done(  # noqa: SLF001
        ws, "t1", status="success", complexity="small", started_at=None, result=None
    )
    assert logged.get("duration_s") == 0.0
    assert logged.get("duration_from_wall") is True
