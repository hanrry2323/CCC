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


def test_split_safe_and_chain_into_cmds():
    """test -f X && grep -q Y X must not collapse to only test -f."""
    from _intent_probe import extract_probe_commands

    section = (
        "## 验收\n"
        "- test -f docs/reports/stamp.md && grep -q GOLDEN_PATH_OK docs/reports/stamp.md\n"
    )
    probes = extract_probe_commands(section)
    assert "test -f docs/reports/stamp.md" in probes
    assert "grep -q GOLDEN_PATH_OK docs/reports/stamp.md" in probes
    # hostile chain still rejected as a whole (no partial rm)
    bad = extract_probe_commands("## 验收\n- python3 -c 'x' && rm -rf /\n")
    assert not any("rm " in p for p in bad)


def test_acceptance_runs_dry_run_probe(tmp_path: Path):
    from _acceptance_gate import check_acceptance

    ws = tmp_path / "app"
    ws.mkdir()
    subprocess.run(["git", "init"], cwd=ws, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "t@t"], cwd=ws, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "config", "user.name", "t"], cwd=ws, check=True, capture_output=True
    )
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
    subprocess.run(["git", "add", "-A"], cwd=ws, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init probe"], cwd=ws, check=True, capture_output=True
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


def test_transfer_accepts_strong_acceptance_even_if_plan_md_lacks_section():
    """Agent 常带草稿 plan_md；顶部 acceptance 已有强探针时不得因缺 ## 验收整单拒。"""
    from chat_server.services import transfer_gate as tg

    body = {
        "title": "探针连通烟测",
        "goal": "验证 transfer 门禁",
        "acceptance": [
            ".venv/bin/python -m pytest -q tests/unit/test_mvp_thresholds.py",
        ],
        "pipeline": "dev",
        "feasibility": "ok",
        "project_id": "qb",
        "executor_intent": "opencode",
        "plan_md": "# 烟测\n\n仅连通草稿，无验收节\n",
    }
    ok, errs = tg.validate_transfer_payload(body)
    assert ok, errs


def test_transfer_rejects_mixed_unit_and_paper_probe():
    from chat_server.services import transfer_gate as tg

    body = {
        "title": "momentum 净 edge",
        "goal": "CLOSE + 单测",
        "acceptance": [
            ".venv/bin/python -m pytest -q tests/unit/test_momentum_fees.py",
            "DRY_RUN=true .venv/bin/python scripts/paper_intent_probe.py --env paper",
        ],
        "pipeline": "dev",
        "feasibility": "ok",
        "project_id": "qb",
        "executor_intent": "opencode",
    }
    ok, errs = tg.validate_transfer_payload(body)
    assert not ok
    assert any(e["code"] == "acceptance_mixed_intent" for e in errs)


def test_transfer_rejects_too_many_probes():
    from chat_server.services import transfer_gate as tg

    body = {
        "title": "过多探针",
        "goal": "g",
        "acceptance": [
            ".venv/bin/python -m pytest -q tests/a.py",
            ".venv/bin/python -m pytest -q tests/b.py",
            ".venv/bin/python -m pytest -q tests/c.py",
            ".venv/bin/python -m pytest -q tests/d.py",
        ],
        "pipeline": "dev",
        "feasibility": "ok",
        "project_id": "qb",
        "executor_intent": "opencode",
    }
    ok, errs = tg.validate_transfer_payload(body)
    assert not ok
    assert any(e["code"] == "acceptance_too_wide" for e in errs)


def test_transfer_soft_trims_title_over_80():
    from chat_server.services import transfer_gate as tg

    long_title = "VIP-V5 纸面 DRY_RUN=true 可重放验收探针绿（STATUS「上线前」第 1 项 · 脚本+STATUS+regress+history 四件套）"
    assert len(long_title) > 80
    body = {
        "title": long_title,
        "goal": "探针绿",
        "acceptance": [
            "DRY_RUN=true .venv/bin/python scripts/paper_intent_probe.py --env paper",
        ],
        "pipeline": "dev",
        "feasibility": "ok",
        "project_id": "qb",
        "executor_intent": "opencode",
    }
    ok, errs = tg.validate_transfer_payload(body)
    assert ok, errs
    assert len(body["title"]) == 80


def test_transfer_probe_survives_plan_numbered_acceptance():
    """acceptance 子弹 + plan「## 验收」编号列表：不得因拼 blob 丢探针。"""
    from chat_server.services import transfer_gate as tg

    body = {
        "title": "跨阶段依赖扇出压测",
        "goal": "1→4 扇出 + depends_on",
        "acceptance": [
            "DRY_RUN=true python3 scripts/mid_fanout_w4_probe.py 退出码 0 且 stdout 含 INTEGRATION_OK",
            "DRY_RUN=true python3 scripts/mid_fanout_w3_combine.py 退出码 0",
        ],
        "pipeline": "dev",
        "feasibility": "ok",
        "project_id": "ccc-demo",
        "executor_intent": "opencode",
        "plan_md": (
            "# Plan\n\n## 步骤\nw1/w2/w3/w4\n\n## 验收\n"
            "1. DRY_RUN=true python3 scripts/mid_fanout_w4_probe.py 退出码 0\n"
            "2. git log --oneline -1 含 feat\n"
        ),
    }
    ok, errs = tg.validate_transfer_payload(body)
    assert ok, errs


def test_extract_numbered_acceptance_probes():
    from _intent_probe import extract_probe_commands

    section = (
        "## 验收\n"
        "1. DRY_RUN=true python3 scripts/mid_fanout_w4_probe.py 退出码 0 且 stdout 含 OK\n"
        "2. pytest tests/ -q\n"
    )
    probes = extract_probe_commands(section)
    assert any(p == "DRY_RUN=true python3 scripts/mid_fanout_w4_probe.py" for p in probes)
    assert any("pytest" in p for p in probes)


def test_strip_cjk_trailing_prose_from_probe():
    from _intent_probe import extract_probe_commands

    section = (
        "## 验收\n"
        "- DRY_RUN=true .venv/bin/python scripts/paper_intent_probe.py --env paper "
        "退出码 = 0；docs/reports/x.md 含六块\n"
    )
    probes = extract_probe_commands(section)
    assert probes == [
        "DRY_RUN=true .venv/bin/python scripts/paper_intent_probe.py --env paper"
    ]


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


def test_t1_seed_goal_from_transfer(tmp_path: Path):
    from chat_server.services import agent_mind

    ws = tmp_path / "t1"
    ws.mkdir()
    (ws / ".ccc" / "board" / "backlog").mkdir(parents=True)
    body = {
        "title": "纸面探针可重放",
        "goal": "paper green",
        "acceptance": ["DRY_RUN=true python3 scripts/paper_intent_probe.py"],
        "pipeline": "feature",
    }
    seeded = agent_mind.maybe_seed_goal_from_transfer(ws, body)
    assert seeded is not None
    assert seeded["status"] == "dispatched"
    assert "paper_intent_probe" in seeded["exit_condition"]
    # second identical transfer must not duplicate; still returns matched goal as dispatched
    again = agent_mind.maybe_seed_goal_from_transfer(ws, body)
    assert again is not None
    assert again["status"] == "dispatched"
    assert again["id"] == seeded["id"]
    d = agent_mind.load_decided(ws)
    assert len([g for g in d["goals"] if g.get("status") != "abandoned"]) == 1
    # hygiene skip
    assert (
        agent_mind.maybe_seed_goal_from_transfer(
            ws, {"title": "卫生清场", "pipeline": "ops", "acceptance": ["python3 -c '1'"]}
        )
        is None
    )


def test_t1_marks_existing_planned_dispatched(tmp_path: Path):
    from chat_server.services import agent_mind

    ws = tmp_path / "t1b"
    ws.mkdir()
    (ws / ".ccc" / "board" / "backlog").mkdir(parents=True)
    agent_mind.merge_decided(
        ws,
        {
            "goals": [
                {
                    "text": "P0 momentum 口径对齐：净 edge + CLOSE",
                    "exit_condition": "pytest -q",
                    "status": "planned",
                }
            ]
        },
    )
    out = agent_mind.maybe_seed_goal_from_transfer(
        ws,
        {
            "title": "P0 momentum 口径对齐：净 edge + CLOSE 平仓 + 单测 + paper 探针",
            "goal": "对齐净 edge",
            "acceptance": ["pytest -q"],
            "pipeline": "feature",
            "epic_id": "p0-momentum-edge-close-paper-74664552",
        },
    )
    assert out is not None
    assert out["status"] == "dispatched"
    unfinished = agent_mind.unfinished_product_goals(agent_mind.load_decided(ws))
    assert any(g.get("status") == "dispatched" for g in unfinished)
    assert agent_mind.next_product_goal(agent_mind.load_decided(ws)) is None


def test_next_product_goal_skips_dispatched(tmp_path: Path):
    from chat_server.services import agent_mind

    ws = tmp_path / "t1c"
    ws.mkdir()
    (ws / ".ccc" / "board" / "backlog").mkdir(parents=True)
    agent_mind.merge_decided(
        ws,
        {
            "goals": [
                {"text": "在飞意图 A", "status": "dispatched", "exit_condition": "x"},
                {"text": "待讨论意图 B", "status": "planned", "exit_condition": "y"},
            ]
        },
    )
    nxt = agent_mind.next_product_goal(agent_mind.load_decided(ws))
    assert nxt is not None
    assert "待讨论" in nxt["text"] or nxt["status"] == "planned"


def test_t2_regress_marks_probed(tmp_path: Path, monkeypatch):
    from board.context import set_workspace
    import board.roles.regress as regress_mod
    from chat_server.services import agent_mind

    ws = tmp_path / "t2"
    ws.mkdir()
    (ws / "scripts").mkdir()
    (ws / "scripts" / "ok_probe.py").write_text("print('ok')\n", encoding="utf-8")
    subprocess.run(["git", "init"], cwd=ws, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=ws, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=ws, check=True, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=ws, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=ws, check=True, capture_output=True)
    for col in ("released", "backlog"):
        (ws / ".ccc" / "board" / col).mkdir(parents=True)
    (ws / ".ccc" / "plans").mkdir(parents=True)
    tid = "released-t2"
    (ws / ".ccc" / "board" / "released" / f"{tid}.jsonl").write_text(
        json.dumps({"id": tid, "title": "纸面探针可重放", "card_kind": "work"}) + "\n",
        encoding="utf-8",
    )
    (ws / ".ccc" / "plans" / f"{tid}.plan.md").write_text(
        "## 验收\n- python3 scripts/ok_probe.py\n",
        encoding="utf-8",
    )
    seeded = agent_mind.maybe_seed_goal_from_transfer(
        ws,
        {
            "title": "纸面探针可重放",
            "goal": "g",
            "acceptance": ["python3 scripts/ok_probe.py"],
            "pipeline": "feature",
        },
    )
    assert seeded
    set_workspace(ws)
    monkeypatch.setenv("CCC_ROLE_LOCK_BYPASS", "1")
    monkeypatch.setattr(regress_mod, "CCC_HOME", ws, raising=False)
    out = regress_mod.regress_role()
    assert out["results"]["passed"] == 1
    assert seeded["id"] in (out["results"].get("probed_goals") or [])
    d = agent_mind.load_decided(ws)
    assert d["goals"][0]["status"] == "probed"


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
