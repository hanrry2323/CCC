"""script_seed short path — mechanical intent probes skip OpenCode."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))


def test_should_use_script_seed_for_paper_probe(tmp_path: Path):
    from board.roles.script_seed import should_use_script_seed, run_script_seed

    ws = tmp_path / "qb"
    ws.mkdir()
    (ws / ".ccc" / "plans").mkdir(parents=True)
    (ws / ".ccc" / "board" / "in_progress").mkdir(parents=True)
    (ws / ".ccc" / "board" / "testing").mkdir(parents=True)
    (ws / ".git").mkdir()
    tid = "probe-w1"
    task = {
        "id": tid,
        "title": "实现纸面意图探针",
        "description": "paper_intent_probe DRY_RUN",
        "executor": "opencode",
        "tags": ["exec:opencode"],
    }
    (ws / ".ccc" / "plans" / f"{tid}.plan.md").write_text(
        "## 验收\n- DRY_RUN=true python3 scripts/paper_intent_probe.py --env paper\n",
        encoding="utf-8",
    )
    (ws / ".ccc" / "board" / "in_progress" / f"{tid}.jsonl").write_text(
        json.dumps(task) + "\n", encoding="utf-8"
    )
    assert should_use_script_seed(ws, task) is True

    # minimal git for commit attempt
    import subprocess

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

    r = run_script_seed(ws, tid)
    assert r["ok"] is True
    probe = ws / "scripts" / "paper_intent_probe.py"
    assert probe.is_file()
    text = probe.read_text(encoding="utf-8")
    assert "DRY_RUN" in text
    assert "startup_check" in text


def test_transfer_coerce_probe_to_python():
    from chat_server.services import transfer_gate as tg

    body = {
        "title": "纸面 DRY_RUN 意图探针",
        "goal": "落地 paper_intent_probe",
        "pipeline": "dev",
        "executor_intent": "opencode",
        "acceptance": [
            "DRY_RUN=true .venv/bin/python scripts/paper_intent_probe.py --env paper"
        ],
    }
    assert tg.resolve_executor_intent(body) == "python"
