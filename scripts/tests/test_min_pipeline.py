"""最小可跑通 v1 — 长意图薄门禁 + 五态 + L3b 冻结 + verify 入口。"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))


def test_min_pipeline_default_on(monkeypatch):
    monkeypatch.delenv("CCC_MIN_PIPELINE", raising=False)
    from engine import min_pipeline as mp

    assert mp.enabled() is True
    assert mp.l3b_repair_queue_enabled() is False
    assert mp.flywheel_auto_open_enabled() is False


def test_min_pipeline_legacy_l3b(monkeypatch):
    monkeypatch.setenv("CCC_MIN_PIPELINE", "0")
    from engine import min_pipeline as mp

    import importlib

    importlib.reload(mp)
    assert mp.enabled() is False
    assert mp.l3b_repair_queue_enabled() is True
    monkeypatch.setenv("CCC_MIN_PIPELINE", "1")
    importlib.reload(mp)


def test_semantic_aliases():
    from engine.min_pipeline import column_of, semantic_of

    assert column_of("queued") == "backlog"
    assert column_of("verify") == "testing"
    assert column_of("done") == "released"
    assert column_of("blocked") == "abnormal"
    assert semantic_of("testing") == "verify"
    assert semantic_of("in_progress") == "code"


def test_long_intent_transfer_green(monkeypatch):
    """用户级长意图：多文件 plan 可通过 transfer（fanout 再拦 oversized work）。"""
    monkeypatch.delenv("CCC_MIN_PIPELINE", raising=False)
    from chat_server.services import transfer_gate

    files = [f"src/mod_{i}.py" for i in range(8)]
    body = {
        "title": "总体开发：跨模块能力闭环",
        "goal": "交付完整开发需求：实现、验收、必要说明",
        "acceptance": [
            "python3 -m pytest -q tests/test_mod_0.py",
            "python3 -c \"assert True\"",
        ],
        "pipeline": "dev",
        "feasibility": "ok",
        "project_id": "ccc-demo",
        "executor_intent": "opencode",
        "scope": files,
        "plan_md": (
            "# Plan\n\n## 目标\n总体开发需求\n\n## 范围\n"
            + "\n".join(f"- {f}" for f in files)
            + "\n\n## 验收\n"
            "- python3 -m pytest -q tests/test_mod_0.py\n"
            "- python3 -c \"assert True\"\n"
        ),
    }
    ok, errors = transfer_gate.validate_transfer_payload(body)
    assert ok, errors


def test_fanout_still_rejects_oversized_work_child():
    """内部 work 仍受 oversized 约束。"""
    from _product_fanout import detect_oversized_work_children

    children = [
        {
            "id": "w-big",
            "title": "过大 work",
            "card_kind": "work",
            "phases": [
                {"phase": 1, "scope": [f"a{i}.py" for i in range(6)]},
            ],
        }
    ]
    msg = detect_oversized_work_children(children, epic={"id": "e1"})
    assert msg and "oversized" in msg


def test_verify_role_exports():
    from board.roles import run_verify_gate, verify_role
    from engine.gates import run_verify_gate as gate_verify

    assert callable(verify_role)
    assert callable(run_verify_gate)
    assert callable(gate_verify)


def test_enqueue_skips_l3b_under_min_pipeline(tmp_path, monkeypatch):
    monkeypatch.delenv("CCC_MIN_PIPELINE", raising=False)
    monkeypatch.setenv("CCC_L3B_REPAIR_QUEUE", "0")
    import importlib
    import importlib.util

    # Load ccc_engine host
    p = SCRIPTS / "ccc-engine.py"
    spec = importlib.util.spec_from_file_location("ccc_engine_min_test", p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["ccc_engine_min_test"] = mod
    assert spec.loader is not None
    spec.loader.exec_module(mod)

    # Point repair queue to tmp so we can assert no write when skipped
    q = tmp_path / "repair-queue.jsonl"
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".ccc").mkdir(parents=True, exist_ok=True)

    ws = tmp_path / "ws"
    (ws / ".ccc" / "board" / "abnormal").mkdir(parents=True)
    mod._enqueue_post_exhaust_optimize(
        ws,
        "w1",
        reason="fail_loop_exhausted after budget",
        task={"parent_id": "e-long", "title": "长意图"},
    )
    # default home/.ccc/repair-queue — under tmp HOME
    rq = tmp_path / ".ccc" / "repair-queue.jsonl"
    assert not rq.is_file() or rq.read_text().strip() == ""


def test_kb_fast_path_skips_kb_role(tmp_path, monkeypatch):
    """min 路径：verified→released 不调 kb_role。"""
    monkeypatch.delenv("CCC_MIN_PIPELINE", raising=False)
    from _board_store import FileBoardStore
    from engine.gates import _run_verified_kb_gate
    import engine.gates as gates_mod

    ws = tmp_path / "app"
    for col in ("verified", "released", "testing", "planned", "backlog", "in_progress"):
        (ws / ".ccc" / "board" / col).mkdir(parents=True)
    store = FileBoardStore(ws)
    import json
    tid = "w-fast-done"
    (ws / ".ccc" / "board" / "verified" / f"{tid}.jsonl").write_text(
        json.dumps({"id": tid, "title": "done", "card_kind": "work"}) + "\n",
        encoding="utf-8",
    )
    called = {"n": 0}

    def _boom():
        called["n"] += 1
        raise AssertionError("kb_role must not run under min pipeline")

    monkeypatch.setattr(gates_mod, "kb_role", _boom)
    # ensure workspace_scope / _get_store see this ws
    monkeypatch.setenv("CCC_WORKSPACE", str(ws))
    _run_verified_kb_gate(ws)
    assert called["n"] == 0
    released = {t["id"] for t in FileBoardStore(ws).list_tasks("released")}
    assert tid in released
