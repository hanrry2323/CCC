"""LPSN intent probe shared module + transfer/regress wiring."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))


def test_strip_env_and_allow_dry_run_venv():
    from _intent_probe import (
        extract_probe_commands,
        is_allowed_verify_cmd,
        looks_like_intent_probe,
    )

    cmd = "DRY_RUN=true .venv/bin/python scripts/paper_intent_probe.py"
    assert is_allowed_verify_cmd(cmd)
    assert looks_like_intent_probe(cmd)
    section = f"## 验收\n- `{cmd}`\n- pytest tests/ -q\n"
    probes = extract_probe_commands(section)
    assert cmd in probes
    assert any("pytest" in p for p in probes)


def test_reject_shell_meta():
    from _intent_probe import is_allowed_verify_cmd

    assert not is_allowed_verify_cmd("python3 -c 'x' && rm -rf /")
    assert not is_allowed_verify_cmd("pytest | tee out")


def test_acceptance_runs_dry_run_probe(tmp_path: Path):
    from _acceptance_gate import check_acceptance

    ws = tmp_path / "app"
    ws.mkdir()
    subprocess.run(["git", "init"], cwd=ws, check=True, capture_output=True)
    (ws / "scripts").mkdir()
    (ws / "scripts" / "paper_intent_probe.py").write_text(
        "import os,sys\n"
        "assert os.environ.get('DRY_RUN')=='true'\n"
        "print('ok')\n",
        encoding="utf-8",
    )
    (ws / ".ccc" / "plans").mkdir(parents=True)
    tid = "work-1"
    (ws / ".ccc" / "plans" / f"{tid}.plan.md").write_text(
        "## 验收\n"
        "- DRY_RUN=true python3 scripts/paper_intent_probe.py\n",
        encoding="utf-8",
    )
    r = check_acceptance(ws, tid, commit="HEAD")
    assert r["ok"] is True
    assert r["reason"] == "acceptance_cmds_ok"


def test_transfer_requires_probe_for_business():
    from chat_server.services import transfer_gate as tg

    body = {
        "title": "paper 可重放探针",
        "goal": "意图探针绿",
        "acceptance": ["README 写了 stamp"],
        "pipeline": "dev",
        "feasibility": "ok",
        "project_id": "demo",
        "executor_intent": "opencode",
    }
    ok, errs = tg.validate_transfer_payload(body)
    assert not ok
    assert any(e["code"] == "missing_intent_probe" for e in errs)

    body["acceptance"] = [
        "DRY_RUN=true python3 scripts/paper_intent_probe.py",
    ]
    ok, errs = tg.validate_transfer_payload(body)
    assert ok, errs


def test_transfer_hygiene_skips_probe():
    from chat_server.services import transfer_gate as tg

    body = {
        "title": "看板卫生清场",
        "goal": "归档 abnormal",
        "acceptance": ["`.ccc/board/abnormal/` 已清空"],
        "pipeline": "ops",
        "feasibility": "ok",
        "project_id": "demo",
        "executor_intent": "opencode",
    }
    ok, errs = tg.validate_transfer_payload(body)
    assert ok, errs
    assert tg.resolve_executor_intent(body) == "python"


def test_next_intent_gate_blocks(tmp_path: Path):
    from chat_server.services import agent_mind, transfer_gate as tg

    ws = tmp_path / "biz"
    ws.mkdir()
    agent_mind.merge_decided(
        ws,
        {
            "goals": [
                {
                    "id": "g1",
                    "text": "paper 日稳",
                    "exit_condition": "DRY_RUN=true python3 scripts/p.py",
                    "status": "planned",
                }
            ]
        },
        updated_by="human",
    )
    body = {
        "title": "完全另一条产品线",
        "goal": "做集群扩容",
        "acceptance": ["python3 -m pytest tests/ -q"],
        "pipeline": "dev",
        "feasibility": "ok",
        "project_id": "demo",
    }
    err = tg.check_next_intent_gate(body, ws)
    assert err and err["code"] == "intent_not_stable"

    body["supersede_goals"] = True
    assert tg.check_next_intent_gate(body, ws) is None


def test_regress_replays_probe(tmp_path: Path, monkeypatch):
    from board.context import set_workspace
    from board.roles import regress as regress_mod

    ws = tmp_path / "rws"
    ws.mkdir()
    subprocess.run(["git", "init"], cwd=ws, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "t@t.com"],
        cwd=ws,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "t"],
        cwd=ws,
        check=True,
        capture_output=True,
    )
    (ws / "scripts").mkdir()
    (ws / "scripts" / "ok_probe.py").write_text("print('ok')\n", encoding="utf-8")
    subprocess.run(["git", "add", "scripts"], cwd=ws, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init"], cwd=ws, check=True, capture_output=True
    )

    for col in ("released", "backlog"):
        (ws / ".ccc" / "board" / col).mkdir(parents=True)
    (ws / ".ccc" / "plans").mkdir(parents=True)
    (ws / ".ccc" / "reports").mkdir(parents=True)

    tid = "released-1"
    task = {
        "id": tid,
        "title": "probe work",
        "status": "released",
        "card_kind": "work",
    }
    (ws / ".ccc" / "board" / "released" / f"{tid}.jsonl").write_text(
        json.dumps(task) + "\n", encoding="utf-8"
    )
    (ws / ".ccc" / "plans" / f"{tid}.plan.md").write_text(
        "## 验收\n- python3 scripts/ok_probe.py\n",
        encoding="utf-8",
    )

    set_workspace(ws)
    monkeypatch.setenv("CCC_ROLE_LOCK_BYPASS", "1")
    # avoid notify noise
    monkeypatch.setattr(
        regress_mod,
        "CCC_HOME",
        ws,
        raising=False,
    )
    out = regress_mod.regress_role()
    assert out["results"]["checked"] == 1
    assert out["results"]["passed"] == 1
    assert out["results"]["probe_runs"] == 1


def test_agent_mind_structured_goals(tmp_path: Path):
    from chat_server.services import agent_mind

    ws = tmp_path / "m"
    ws.mkdir()
    (ws / ".ccc" / "board" / "backlog").mkdir(parents=True)
    out = agent_mind.merge_decided(
        ws,
        {
            "goals": [
                {
                    "text": "paper 可重放",
                    "exit_condition": "DRY_RUN=true python3 scripts/p.py",
                    "status": "planned",
                }
            ]
        },
    )
    assert out["goals"][0]["status"] == "planned"
    assert out["goals"][0]["exit_condition"]
    gid = out["goals"][0]["id"]
    agent_mind.mark_goal_status(ws, gid, "stable", updated_by="human")
    d = agent_mind.load_decided(ws)
    assert d["goals"][0]["status"] == "stable"
    assert agent_mind.unfinished_product_goals(d) == []
    dig = agent_mind.build_digest(ws, project_id="m", use_cache=False)
    assert "code_landed" in dig["digest"] or "intent_stable" in dig["digest"].lower() or "已稳定" in dig["digest"]


def test_phase_lint_require_probe():
    from phase_lint import validate_plan_acceptance

    ok, errs = validate_plan_acceptance(
        "# t\n\n## 验收\n- 文档写好了\n", require_probe=True
    )
    assert not ok
    assert any("intent probe" in e for e in errs)

    ok, errs = validate_plan_acceptance(
        "# t\n\n## 验收\n- python3 -m pytest tests/ -q\n", require_probe=True
    )
    assert ok, errs
