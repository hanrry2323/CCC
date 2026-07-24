"""hang_detected classification from acceptance probes + multi-root serial."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

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
    (ws / ".ccc" / "board" / "in_progress").mkdir(parents=True)
    (ws / ".ccc" / "plans").mkdir(parents=True)
    return ws


def test_is_hang_probe_exit_124():
    from _intent_probe import is_hang_probe_failure

    assert is_hang_probe_failure({"ok": False, "rc": 124}) is True
    assert is_hang_probe_failure({"ok": False, "rc": 1, "error": "assert"}) is False


def test_is_hang_probe_hang_detected_marker():
    from _intent_probe import is_hang_probe_failure

    assert (
        is_hang_probe_failure(
            {"ok": False, "rc": 1, "stdout": "… HANG_DETECTED timeout …"}
        )
        is True
    )


def test_acceptance_hang_detected_reason(ws_git: Path, monkeypatch):
    from _acceptance_gate import check_acceptance

    tid = "stress-3-w1"
    (ws_git / ".ccc" / "board" / "in_progress" / f"{tid}.jsonl").write_text(
        json.dumps({"id": tid, "title": "hang", "card_kind": "work"}) + "\n",
        encoding="utf-8",
    )
    (ws_git / ".ccc" / "plans" / f"{tid}.plan.md").write_text(
        "## 验收\n```bash\npython3 -c 'print(1)'\n```\n",
        encoding="utf-8",
    )

    def _fake_run(ws, cmds, **kwargs):
        return False, [
            {
                "cmd": cmds[0],
                "rc": 124,
                "ok": False,
                "stdout": "HANG_DETECTED\n",
                "error": "exit 124",
            }
        ]

    monkeypatch.setattr("_acceptance_gate._run_cmds", _fake_run)
    r = check_acceptance(ws_git, tid, commit="HEAD")
    assert r["ok"] is False
    assert r["reason"] == "hang_detected"


def test_related_event_for_hang_reason():
    from _failure_ledger import related_event_for_reason

    assert related_event_for_reason("hang_detected pid=1") == "hang_detected"
    assert related_event_for_reason("acceptance_cmd_failed") == "quarantine"


def test_force_serial_multi_root_scopes():
    import ast
    from pathlib import Path as _Path

    src = (ROOT / "scripts" / "ccc-engine.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    ns: dict = {"Path": _Path}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in (
            "_top_level_roots",
            "_force_serial_multi_root",
        ):
            exec(
                compile(ast.Module(body=[node], type_ignores=[]), "<eng>", "exec"),
                ns,
            )
    force = ns["_force_serial_multi_root"]
    phases = [
        {"phase": 1, "scope": ["src/worker/manager.py"], "depends_on": []},
        {"phase": 2, "scope": ["dashboard/backend/main.py"], "depends_on": []},
        {"phase": 3, "scope": ["tests/regress/test_stress2_e2e.py"], "depends_on": []},
    ]
    assert force(phases, {1, 2, 3}) is True
    same = [
        {"phase": 1, "scope": ["src/a.py"], "depends_on": []},
        {"phase": 2, "scope": ["src/b.py"], "depends_on": []},
    ]
    assert force(same, {1, 2}) is False

def test_classify_failure_category_hang():
    from _failure_learning import classify_failure_category

    assert classify_failure_category("acceptance hang_detected exit 124") == "hang"
