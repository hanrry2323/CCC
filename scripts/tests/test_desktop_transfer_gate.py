"""Desktop transfer gate + executor registry + flow snapshot."""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

from chat_server.services import transfer_gate  # noqa: E402
from chat_server.services import flow_events  # noqa: E402
from executors.registry import normalize_executor, run_executor  # noqa: E402
from _board_store import FileBoardStore  # noqa: E402
from _product_fanout import apply_fanout  # noqa: E402


def test_gate_rejects_text_task_agent_track():
    body = {
        "title": "hp v0.1.0 版本正规化：VERSION+CHANGELOG+规划文",
        "goal": "VERSION+CHANGELOG+规划文对齐",
        "acceptance": ["grep -q v0.1.0 VERSION"],
        "pipeline": "dev",
        "feasibility": "ok",
        "project_id": "hp",
        "skill_ref": "skills/write-code", "prompt_ref": "prompts/write-code-prompt",
        "plan_md": (
            "# Plan\n\n## 范围\n- VERSION\n- CHANGELOG.md\n- docs/dev-plan.md\n\n"
            "## 验收\n- grep -q v0.1.0 VERSION\n"
        ),
        "scope": ["VERSION", "CHANGELOG.md", "docs/dev-plan.md"],
    }
    ok, errors = transfer_gate.validate_transfer_payload(body)
    assert not ok
    assert any(e["code"] == "text_task_agent_track" for e in errors)


def test_gate_accepts_long_intent_over_five_files_min_pipeline(monkeypatch):
    """最小路径：长意图 epic 不被 scope≤5 挡；oversized 改在 fanout 拦 work。"""
    monkeypatch.delenv("CCC_MIN_PIPELINE", raising=False)  # default on
    files = [f"src/m{i}.py" for i in range(6)]
    body = {
        "title": "总体能力升级：六模块串联",
        "goal": "完成跨模块总体开发需求",
        "acceptance": ["python3 -m pytest -q tests/test_m0.py"],
        "pipeline": "dev",
        "feasibility": "ok",
        "project_id": "qb",
        "skill_ref": "skills/write-code", "prompt_ref": "prompts/write-code-prompt",
        "scope": files,
        "plan_md": (
            "# Plan\n\n## 范围\n"
            + "\n".join(f"- {f}" for f in files)
            + "\n\n## 验收\n- python3 -m pytest -q tests/test_m0.py\n"
        ),
    }
    ok, errors = transfer_gate.validate_transfer_payload(body)
    assert ok, errors


def test_gate_rejects_scope_over_five_files_legacy(monkeypatch):
    monkeypatch.setenv("CCC_MIN_PIPELINE", "0")
    files = [f"src/m{i}.py" for i in range(6)]
    body = {
        "title": "一次改六个模块",
        "goal": "加能力",
        "acceptance": ["python3 -m pytest -q tests/test_m0.py"],
        "pipeline": "dev",
        "feasibility": "ok",
        "project_id": "qb",
        "skill_ref": "skills/write-code", "prompt_ref": "prompts/write-code-prompt",
        "scope": files,
        "plan_md": (
            "# Plan\n\n## 范围\n"
            + "\n".join(f"- {f}" for f in files)
            + "\n\n## 验收\n- python3 -m pytest -q tests/test_m0.py\n"
        ),
    }
    ok, errors = transfer_gate.validate_transfer_payload(body)
    assert not ok
    assert any(e["code"] == "plan_scope_too_wide" for e in errors)


def test_gate_accepts_small_code_card():
    body = {
        "title": "补 url_safety 单测",
        "goal": "拒绝广播地址",
        "acceptance": [
            "cargo test -p medio-core test_broadcast_ipv4_rejected -- --exact"
        ],
        "pipeline": "dev",
        "feasibility": "ok",
        "project_id": "medio-0",
        "skill_ref": "skills/write-code", "prompt_ref": "prompts/write-code-prompt",
        "scope": [
            "src/backend/core/src/infra/url_safety.rs",
        ],
        "plan_md": (
            "# Plan\n\n## 范围\n- src/backend/core/src/infra/url_safety.rs\n\n"
            "## 验收\n"
            "- cargo test -p medio-core test_broadcast_ipv4_rejected -- --exact\n"
        ),
    }
    ok, errors = transfer_gate.validate_transfer_payload(body)
    assert ok, errors


def test_gate_rejects_incomplete():
    ok, errors = transfer_gate.validate_transfer_payload(
        {"title": "x", "project_id": "demo"}
    )
    assert not ok
    codes = {e["code"] for e in errors}
    assert "missing_goal" in codes
    assert "missing_acceptance" in codes
    assert "missing_pipeline" in codes


def test_gate_rejects_feasibility_blocked():
    ok, errors = transfer_gate.validate_transfer_payload(
        {
            "title": "加一行 README",
            "goal": "加标记",
            "acceptance": ["grep DEMO"],
            "pipeline": "dev",
            "feasibility": "blocked",
            "feasibility_reason": "范围不清",
            "project_id": "ccc-demo",
            "skill_ref": "skills/write-code", "prompt_ref": "prompts/write-code-prompt",
        }
    )
    assert not ok
    assert any(e["code"] == "feasibility_blocked" for e in errors)


def test_gate_accepts_complete():
    body = {
        "title": "加一行 README",
        "goal": "在 README 加 DEMO 标记",
        "acceptance": ["python3 -m pytest -q tests/"],
        "pipeline": "dev",
        "feasibility": "ok",
        "project_id": "ccc-demo",
        "skill_ref": "skills/write-code", "prompt_ref": "prompts/write-code-prompt",
        "plan_md": (
            "# Plan\n\n## 目标\nx\n\n## 验收\n\n"
            "- python3 -m pytest -q tests/\n"
        ),
    }
    ok, errors = transfer_gate.validate_transfer_payload(body)
    assert ok, errors
    assert transfer_gate.resolve_skill_ref(body) == "skills/write-code"
    desc = transfer_gate.build_epic_description(body)
    assert "Transfer Gate" in desc
    assert "python" in desc
    plan = transfer_gate.build_plan_md(body)
    assert "## 验收" in plan


def test_gate_rejects_existence_only_acceptance():
    body = {
        "title": "假绿探针卡",
        "goal": "加能力",
        "acceptance": ["test -f src/strategies/momentum.py"],
        "pipeline": "dev",
        "feasibility": "ok",
        "project_id": "qb",
        "skill_ref": "skills/write-code", "prompt_ref": "prompts/write-code-prompt",
        "plan_md": (
            "# Plan\n\n## 目标\nx\n\n## 验收\n\n"
            "- test -f src/strategies/momentum.py\n"
        ),
    }
    ok, errors = transfer_gate.validate_transfer_payload(body)
    assert not ok
    codes = {e["code"] for e in errors}
    assert "acceptance_weak" in codes or "plan_acceptance_weak" in codes
    assert any(e.get("fix_hint") for e in errors)


def test_gate_allows_plan_without_acceptance_section_when_body_probes_strong():
    """顶部 acceptance 已有强探针时，草稿 plan 缺「## 验收」不整单 400（Hub 会补）。"""
    body = {
        "title": "缺验收节",
        "goal": "做一件事",
        "acceptance": ["python3 -m pytest -q tests/unit/test_x.py"],
        "pipeline": "dev",
        "feasibility": "ok",
        "project_id": "qb",
        "skill_ref": "skills/write-code", "prompt_ref": "prompts/write-code-prompt",
        "plan_md": "# Plan\n\n## 目标\n只写目标没有验收节\n",
    }
    ok, errors = transfer_gate.validate_transfer_payload(body)
    assert ok, errors


def test_gate_rejects_plan_without_acceptance_when_no_body_probes():
    """acceptance 提不出探针且 plan 缺 ## 验收 → 拒。"""
    body = {
        "title": "缺验收节",
        "goal": "做一件事",
        "acceptance": ["完成即可"],
        "pipeline": "dev",
        "feasibility": "ok",
        "project_id": "qb",
        "skill_ref": "skills/write-code", "prompt_ref": "prompts/write-code-prompt",
        "plan_md": "# Plan\n\n## 目标\n只写目标没有验收节\n",
    }
    ok, errors = transfer_gate.validate_transfer_payload(body)
    assert not ok
    codes = {e["code"] for e in errors}
    assert "missing_intent_probe" in codes or "plan_acceptance_weak" in codes
    assert any(e.get("fix_hint") for e in errors)


def test_plan_goal_conflict_close_downgrade():
    """goal 要 CLOSE/平仓，plan 却交给上层 → plan_goal_conflict。"""
    body = {
        "title": "momentum 口径：CLOSE + 净 edge",
        "goal": "momentum 发 CLOSE_LONG/CLOSE_SHORT 反向平仓，并用共享 round_trip_cost 算净 edge",
        "acceptance": ["python3 -m pytest tests/unit/test_momentum_fees.py -q"],
        "pipeline": "dev",
        "feasibility": "ok",
        "project_id": "qb",
        "skill_ref": "skills/write-code", "prompt_ref": "prompts/write-code-prompt",
        "plan_md": (
            "# Plan\n\n## 目标\n"
            "策略仍只发 OPEN；CLOSE 交给上层处理；不追踪仓位；保持 OPEN。\n\n"
            "## 验收\n\n"
            "- python3 -m pytest tests/unit/test_momentum_fees.py -q\n"
        ),
    }
    err = transfer_gate.validate_plan_goal_alignment(body)
    assert err is not None
    assert err["code"] == "plan_goal_conflict"
    ok, errors = transfer_gate.validate_transfer_payload(body)
    assert not ok
    assert any(e["code"] == "plan_goal_conflict" for e in errors)


def test_plan_goal_alignment_ok_when_close_in_plan():
    body = {
        "title": "momentum CLOSE + 净 edge",
        "goal": "实现 CLOSE_LONG/CLOSE_SHORT 与净 edge（共享 round_trip_cost）",
        "acceptance": ["python3 -m pytest tests/unit/test_momentum_fees.py -q"],
        "pipeline": "dev",
        "feasibility": "ok",
        "project_id": "qb",
        "skill_ref": "skills/write-code", "prompt_ref": "prompts/write-code-prompt",
        "plan_md": (
            "# Plan\n\n## 目标\n"
            "在 momentum 内发 CLOSE_LONG/CLOSE_SHORT；抽取共享 cost；算净 edge。\n\n"
            "## 验收\n\n"
            "- python3 -m pytest tests/unit/test_momentum_fees.py -q\n"
        ),
    }
    assert transfer_gate.validate_plan_goal_alignment(body) is None
    ok, errors = transfer_gate.validate_transfer_payload(body)
    assert ok, errors


def test_executor_python_stub(tmp_path):
    r = run_executor(
        {
            "executor": "python",
            "cwd": str(tmp_path),
            "work_id": "w1",
            "executor_spec": {},
        }
    )
    assert r.ok
    assert r.executor == "python"
    assert (tmp_path / ".ccc" / "executor-python.ok").is_file()


def test_normalize_auto():
    assert normalize_executor("auto", pipeline="python-script") == "python"
    assert normalize_executor("auto", pipeline="dev") == "opencode"


def test_fanout_writes_executor(tmp_path):
    store = FileBoardStore(tmp_path)
    assert store.create_task(
        {
            "id": "epic-x",
            "title": "Epic",
            "tags": ["exec:python"],
            "description": "big",
        },
        column="backlog",
    )
    epic = store.list_tasks("backlog")[0]
    child = {
        "id": "epic-x-w1",
        "title": "W1",
        "description": "d",
        "plan_md": "# t\n\n## 验收\n- pytest tests/ -q\n",
        "phases": [
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
        "executor": "python",
    }
    r = apply_fanout(store, epic, children_raw=[child])
    assert r["ok"]
    _, work = store.find_task("epic-x-w1")
    assert work["executor"] == "python"


def test_flow_snapshot_from_board():
    board = {
        "backlog": [
            {
                "id": "e1",
                "title": "E",
                "card_kind": "epic",
                "split_status": "planned",
                "description": "## 目标\n做一件事\n\n## 验收\n- x\n",
            }
        ],
        "planned": [
            {
                "id": "e1-w1",
                "title": "W",
                "parent_id": "e1",
                "executor": "opencode",
                "depends_on_tasks": [],
            }
        ],
    }
    snap = flow_events.snapshot_from_board(board, epic_id="e1", project_id="demo")
    assert snap["epic"]["id"] == "e1"
    assert snap["works"][0]["executor"] == "opencode"
    assert snap["works"][0]["user_status"] == "排队"
    assert snap["works"][0]["executor_label"] == "写码"
    assert "goal_summary" in snap["epic"]
    assert snap.get("headline")


def test_client_request_id_idempotency(tmp_path, monkeypatch):
    """Hub API v1：同一 client_request_id 二次 lookup 返回同一 epic。"""
    monkeypatch.setattr(
        "chat_server.config.CHAT_DIR", tmp_path / "chat"
    )
    (tmp_path / "chat").mkdir(parents=True)
    pid = "ccc-demo"
    crid = "req-phase1-idem-001"
    assert flow_events.lookup_transfer_by_client_request(pid, crid) is None
    flow_events.remember_last_epic(
        pid, "epic-idem-1", "Idem", thread_id=f"{pid}::main", client_request_id=crid
    )
    hit = flow_events.lookup_transfer_by_client_request(pid, crid)
    assert hit is not None
    assert hit["epic_id"] == "epic-idem-1"
    flow_events.remember_last_epic(
        pid, "epic-idem-1", "Idem", thread_id=f"{pid}::main", client_request_id=crid
    )
    hit2 = flow_events.lookup_transfer_by_client_request(pid, crid)
    assert hit2["epic_id"] == "epic-idem-1"
