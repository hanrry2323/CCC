"""v0.41: engine wake / baseline / daily review / claude dedupe helpers"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))


def test_ensure_engine_sets_enabled(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    import _ccc_control as ctrl
    import _engine_wake as wake

    ctrl.CONTROL_DIR = tmp_path / ".ccc"
    ctrl.CONTROL_FILE = ctrl.CONTROL_DIR / "control.json"
    ctrl.DISABLED_SENTINEL = ctrl.CONTROL_DIR / "DISABLED"
    wake.WAKE_FILE = tmp_path / ".ccc" / "engine.wake"

    ctrl.set_mode("disabled", reason="test", source="test")
    with patch.object(wake, "_bootstrap_engine_launchd", return_value=(False, "skip")):
        out = wake.ensure_engine_for_task(
            reason="task_dispatch", task_id="t1", start_launchd=True
        )
    assert out["mode_after"] == "enabled"
    assert out["control_changed"] is True
    assert wake.WAKE_FILE.is_file()
    payload = wake.consume_wake()
    assert payload and payload.get("task_id") == "t1"
    assert wake.consume_wake() is None


def test_ensure_engine_downgrades_invent(tmp_path, monkeypatch):
    """v0.42.4: invent 硬禁 → ensure_engine 降为 enabled。"""
    monkeypatch.setenv("HOME", str(tmp_path))
    import _ccc_control as ctrl
    import _engine_wake as wake

    ctrl.CONTROL_DIR = tmp_path / ".ccc"
    ctrl.CONTROL_FILE = ctrl.CONTROL_DIR / "control.json"
    ctrl.DISABLED_SENTINEL = ctrl.CONTROL_DIR / "DISABLED"
    wake.WAKE_FILE = tmp_path / ".ccc" / "engine.wake"

    # 先写入残留 invent（绕过 set_mode 硬禁）
    ctrl.CONTROL_FILE.parent.mkdir(parents=True, exist_ok=True)
    ctrl.CONTROL_FILE.write_text(
        json.dumps({"mode": "invent", "schema_version": "1.2"}) + "\n"
    )
    with patch.object(wake, "_bootstrap_engine_launchd", return_value=(True, "ok")):
        out = wake.ensure_engine_for_task(reason="task_dispatch", task_id="t2")
    assert out["mode_after"] == "enabled"
    assert out["control_changed"] is True
    assert ctrl.may_invent() is False


def test_baseline_collect(tmp_path):
    from _project_baseline import collect_baseline, baseline_prompt_for_claude
    import subprocess

    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "config", "user.name", "t"], cwd=tmp_path, check=True, capture_output=True
    )
    (tmp_path / "a.txt").write_text("x")
    subprocess.run(["git", "add", "a.txt"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "i"], cwd=tmp_path, check=True, capture_output=True
    )
    (tmp_path / "a.txt").write_text("y")
    bl = collect_baseline(tmp_path, project_id="t")
    assert bl["git"]["dirty"] is True
    assert bl["can_dispatch"] is True
    prompt = baseline_prompt_for_claude(bl)
    assert "项目基线" in prompt or "基线" in prompt


def test_daily_review_dry_run(tmp_path):
    import importlib.util
    import subprocess

    spec = importlib.util.spec_from_file_location(
        "daily", SCRIPTS / "ccc-daily-diff-review.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "config", "user.name", "t"], cwd=tmp_path, check=True, capture_output=True
    )
    (tmp_path / "f.txt").write_text("1")
    subprocess.run(["git", "add", "f.txt"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "i"], cwd=tmp_path, check=True, capture_output=True
    )
    rc = mod.main(["--workspace", str(tmp_path), "--dry-run"])
    assert rc == 0
    reports = list((tmp_path / ".ccc" / "reports").glob("daily-review-*.md"))
    assert reports


def test_result_delta_dedupe_logic():
    """Mirror claude_client rule: result text only if no assistant text."""
    saw = False
    deltas = []
    for evt in (
        {"type": "assistant", "text": "hello"},
        {"type": "result", "text": "hello"},
    ):
        if evt["type"] == "assistant" and evt["text"]:
            saw = True
            deltas.append(evt["text"])
        if evt["type"] == "result" and evt["text"] and not saw:
            deltas.append(evt["text"])
    assert deltas == ["hello"]
