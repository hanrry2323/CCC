"""Tests for Sessionful Contract Loop helpers + FinOps summarize + DoD commit."""

from __future__ import annotations

import types
from pathlib import Path

import pytest

import _cost_telemetry as ct
import _product_session as mod
from _cost_telemetry import estimate_tokens, record_call, summarize_task_calls
from _product_session import format_work_artifacts, parse_work_artifacts
from _task_commit import ensure_task_commit, find_task_commit


def test_parse_and_format_work_artifacts_roundtrip():
    plan = "# T\n\n## 验收\n- run pytest\n"
    phases = [
        {
            "phase": 1,
            "status": "pending",
            "description": "do it",
            "scope": ["a.py"],
            "subtasks": {"1.1": "pending"},
            "timeout": 1800,
            "commit": None,
            "notes": "",
        }
    ]
    blob = format_work_artifacts(plan, phases)
    p2, ph2 = parse_work_artifacts(blob)
    assert "## 验收" in p2
    assert ph2[0]["phase"] == 1
    assert ph2[0]["scope"] == ["a.py"]


def test_parse_work_artifacts_missing_raises():
    with pytest.raises(RuntimeError, match="PLAN"):
        parse_work_artifacts("hello no markers")


def test_estimate_and_summarize(tmp_path, monkeypatch):
    tel = tmp_path / "cost-telemetry.jsonl"
    monkeypatch.setattr(ct, "_TELEMETRY_FILE", tel)
    assert estimate_tokens("abcd") == 1
    record_call(
        role="planner",
        provider_or_model="flash",
        prompt_tokens=10,
        completion_tokens=5,
        latency_ms=100,
        ok=True,
        task_id="tid-a",
        phase_id="p1",
    )
    record_call(
        role="executor",
        provider_or_model="opencode",
        prompt_tokens=20,
        completion_tokens=0,
        latency_ms=50,
        ok=False,
        task_id="tid-a",
    )
    s = summarize_task_calls("tid-a")
    assert s["calls"] == 2
    assert s["ok_calls"] == 1
    assert s["fail_calls"] == 1
    assert s["tokens_total"] == 35
    assert "planner" in s["by_role"]
    assert summarize_task_calls("missing")["calls"] == 0


def test_ensure_task_commit_auto(tmp_path):
    import subprocess

    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "t@t.com"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "t"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    (tmp_path / "f.txt").write_text("a\n")
    subprocess.run(["git", "add", "f.txt"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    assert find_task_commit(tmp_path, "never") == ""
    (tmp_path / "f.txt").write_text("b\n")
    ok, why, h = ensure_task_commit(tmp_path, "task-xyz", phase_num=1)
    assert ok, why
    assert why == "auto-committed"
    assert len(h) == 40
    assert find_task_commit(tmp_path, "task-xyz") == h


@pytest.mark.asyncio
async def test_contract_loop_repairs_in_session(monkeypatch, tmp_path):
    """Mock SDK: first turn bad parse, second turn good — same session."""

    class _TB:
        def __init__(self, text):
            self.text = text

    class _Asst:
        def __init__(self, text, sid="sess-1"):
            self.content = [_TB(text)]
            self.session_id = sid
            self.usage = {"input_tokens": 1, "output_tokens": 1}

    class _Res:
        def __init__(self, sid="sess-1"):
            self.session_id = sid
            self.is_error = False
            self.errors = None
            self.result = None
            self.usage = {}
            self.total_cost_usd = 0

    good = format_work_artifacts(
        "# X\n\n## 验收\n- ok\n",
        [
            {
                "phase": 1,
                "status": "pending",
                "description": "d",
                "scope": ["a.py"],
                "subtasks": {"1.1": "pending"},
                "timeout": 60,
                "commit": None,
                "notes": "",
            }
        ],
    )

    class _Client:
        n = 0

        def __init__(self, options=None):
            self.options = options

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def query(self, prompt):
            type(self).n += 1

        async def receive_response(self):
            if type(self).n == 1:
                yield _Asst("not a plan")
                yield _Res()
            else:
                yield _Asst(good)
                yield _Res()

    fake = types.ModuleType("claude_agent_sdk")
    fake.AssistantMessage = _Asst
    fake.ClaudeAgentOptions = lambda **kw: types.SimpleNamespace(**kw)
    fake.ClaudeSDKClient = _Client
    fake.ResultMessage = _Res
    fake.TextBlock = _TB
    monkeypatch.setitem(__import__("sys").modules, "claude_agent_sdk", fake)

    import _claude_cli as cli

    monkeypatch.setattr(cli, "resolve_claude_cli", lambda require=True: "/fake/claude")
    monkeypatch.setattr(ct, "_TELEMETRY_FILE", tmp_path / "tel.jsonl")

    def validate(text: str):
        parse_work_artifacts(text)

    def gate(text: str):
        p, ph = parse_work_artifacts(text)
        return format_work_artifacts(p, ph), (p, ph)

    result = await mod.run_contract_loop(
        prompt="make plan",
        workspace=tmp_path,
        task_id="t-loop",
        mode="work",
        model="flash",
        max_loops=3,
        validate_fn=validate,
        gate_fn=gate,
    )
    assert result["ok"] is True
    assert result["loops"] == 2
    assert "---PLAN---" in result["output"]
    assert _Client.n == 2
