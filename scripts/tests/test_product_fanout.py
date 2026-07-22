"""Stage B: epic fanout apply without Claude."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _board_store import FileBoardStore  # noqa: E402
from _product_fanout import apply_fanout, parse_fanout_output, refresh_epic_completion  # noqa: E402


def _child(cid: str, scope: str):
    return {
        "id": cid,
        "title": f"Title {cid}",
        "description": "d",
        "plan_md": f"# {cid}\n\n## 验收\n- pytest -q {scope}\n",
        "phases": [
            {
                "phase": 1,
                "status": "pending",
                "description": "impl",
                "scope": [scope],
                "subtasks": {"1.1": "pending"},
                "timeout": 600,
                "commit": None,
                "notes": "",
            }
        ],
    }


def test_parse_fanout_output():
    out = """
---EPIC_BRIEF---
overview
---END_EPIC_BRIEF---
---CHILDREN---
[{"id": "e-w1", "title": "t", "description": "d", "plan_md": "# t\\n\\n## 验收\\n- x\\n", "phases": [{"phase": 1, "status": "pending", "description": "d", "scope": ["a.py"], "subtasks": {"1.1": "pending"}, "timeout": 60, "commit": null, "notes": ""}]}]
---END_CHILDREN---
"""
    brief, kids = parse_fanout_output(out)
    assert brief == "overview"
    assert kids[0]["id"] == "e-w1"


def test_parse_fanout_repairs_bare_quotes():
    # plan_md 内未转义 ASCII " — 真实 Claude 脏 JSON
    out = r"""
---EPIC_BRIEF---
b
---END_EPIC_BRIEF---
---CHILDREN---
[{"id": "e-w1", "title": "t", "description": "d", "plan_md": "用于"冒烟测试"的标记\n\n## 验收\n- x", "phases": [{"phase": 1, "status": "pending", "description": "d", "scope": ["a.py"], "subtasks": {"1.1": "pending"}, "timeout": 60, "commit": null, "notes": ""}]}]
---END_CHILDREN---
"""
    brief, kids = parse_fanout_output(out)
    assert brief == "b"
    assert kids[0]["id"] == "e-w1"
    assert "冒烟" in kids[0]["plan_md"]


def test_apply_fanout_keeps_epic_in_backlog(tmp_path):
    store = FileBoardStore(tmp_path)
    assert store.create_task(
        {"id": "epic-a", "title": "Epic A", "description": "big"}, column="backlog"
    )
    epic = store.list_tasks("backlog")[0]
    r = apply_fanout(
        store,
        epic,
        children_raw=[
            _child("epic-a-w1", "src/a.py"),
            _child("epic-a-w2", "src/b.py"),
        ],
        epic_brief="# Epic A brief\n",
    )
    assert r["ok"]
    assert len(r["child_ids"]) == 2
    # parent still backlog
    assert store.find_task("epic-a")[0] == "backlog"
    _, parent = store.find_task("epic-a")
    assert parent["split_status"] == "planned"
    assert parent["color_group"]
    assert parent["child_ids"] == r["child_ids"]
    # children in planned
    assert store.find_task("epic-a-w1")[0] == "planned"
    assert (tmp_path / ".ccc/plans/epic-a-w1.plan.md").is_file()
    assert (tmp_path / ".ccc/phases/epic-a-w1.phases.json").is_file()
    # epic cannot move
    assert store.move_task("epic-a", "backlog", "planned") is False


def test_refresh_epic_done(tmp_path):
    store = FileBoardStore(tmp_path)
    store.create_task({"id": "e", "title": "E"}, column="backlog")
    apply_fanout(
        store,
        store.list_tasks("backlog")[0],
        children_raw=[_child("e-w1", "x.py")],
    )
    store.move_task("e-w1", "planned", "in_progress")
    store.move_task("e-w1", "in_progress", "testing")
    store.move_task("e-w1", "testing", "verified")
    store.move_task("e-w1", "verified", "released")
    assert refresh_epic_completion(store, "e") == "done"
    _, epic = store.find_task("e")
    assert epic["split_status"] == "done"
    assert epic.get("ui_hidden") is True
    assert store.list_tasks("backlog") == []


def test_refresh_epic_done_despite_in_progress_ghost(tmp_path):
    """子卡同时有 in_progress 幽灵与 released 真身时，epic 仍应 → done。"""
    import json

    store = FileBoardStore(tmp_path)
    store.create_task({"id": "eg", "title": "E"}, column="backlog")
    apply_fanout(
        store,
        store.list_tasks("backlog")[0],
        children_raw=[_child("eg-w1", "x.py")],
    )
    store.move_task("eg-w1", "planned", "in_progress")
    store.move_task("eg-w1", "in_progress", "testing")
    store.move_task("eg-w1", "testing", "verified")
    store.move_task("eg-w1", "verified", "released")
    # 模拟 unlink 失败留下的幽灵
    ghost = {
        "id": "eg-w1",
        "title": "ghost",
        "status": "in_progress",
        "card_kind": "work",
        "parent_id": "eg",
    }
    (tmp_path / ".ccc/board/in_progress/eg-w1.jsonl").write_text(
        json.dumps(ghost) + "\n", encoding="utf-8"
    )
    assert store.find_task("eg-w1")[0] == "in_progress"  # 先命中靠前柱
    assert store.resolve_task_column("eg-w1") == "released"
    assert refresh_epic_completion(store, "eg") == "done"
    _, eg = store.find_task("eg")
    assert eg.get("ui_hidden") is True


def test_refresh_epic_failed_on_abnormal(tmp_path):
    store = FileBoardStore(tmp_path)
    store.create_task({"id": "eb", "title": "E"}, column="backlog")
    apply_fanout(
        store,
        store.list_tasks("backlog")[0],
        children_raw=[_child("eb-w1", "a.py"), _child("eb-w2", "b.py")],
    )
    store.move_task("eb-w1", "planned", "in_progress")
    store.move_task("eb-w1", "in_progress", "abnormal")
    assert refresh_epic_completion(store, "eb") == "failed"
    assert store.find_task("eb")[0] == "backlog"
    _, epic = store.find_task("eb")
    assert epic["split_status"] == "failed"


def test_lint_fail_leaves_no_half_children(tmp_path):
    store = FileBoardStore(tmp_path)
    store.create_task({"id": "el", "title": "E"}, column="backlog")
    bad = _child("el-w1", "ok.py")
    bad["phases"][0]["scope"] = []  # empty scope → lint fail
    try:
        apply_fanout(
            store,
            store.list_tasks("backlog")[0],
            children_raw=[bad],
        )
        assert False, "expected ValueError"
    except ValueError as e:
        assert "phase_lint" in str(e) or "scope" in str(e).lower()
    assert store.list_tasks("planned") == []
    _, epic = store.find_task("el")
    assert epic["split_status"] == "pending"
    assert not epic.get("child_ids")


def test_seeded_phase_plan_preserves_epic_acceptance():
    from _product_fanout import _plan_md_for_seeded_phase

    epic = (
        "# Plan — probe\n\n## 范围\n- `scripts/a.py`\n\n"
        "## 验收\n- DRY_RUN=true .venv/bin/python scripts/a.py\n"
        "- test -f docs/reports/x.md\n"
    )
    ph = {
        "phase": 1,
        "description": "probe",
        "scope": ["scripts/a.py"],
    }
    out = _plan_md_for_seeded_phase(epic, ph, phase_num=1, title="w1")
    assert "DRY_RUN=true" in out
    assert "完成本 phase：probe" not in out


def test_seeded_phase_slice_inherits_epic_probes():
    """## Phase N 切片无探针时，须回灌 epic ## 验收，否则 plan_lint 拒扇出。"""
    from _product_fanout import _plan_md_for_seeded_phase
    from _intent_probe import extract_probe_commands

    epic = (
        "# Plan\n\n## Phase 1 — code\n- `scripts/feature_counter.py`\n"
        "- 实现 Counter\n\n"
        "## Phase 2 — docs\n- `docs/FEATURE_COUNTER.md`\n\n"
        "## 验收\n"
        "- DRY_RUN=true python3 scripts/feature_counter_probe.py\n"
        "- test -f docs/FEATURE_COUNTER.md\n"
    )
    ph = {"phase": 1, "description": "code", "scope": ["scripts/feature_counter.py"]}
    out = _plan_md_for_seeded_phase(epic, ph, phase_num=1, title="w1")
    probes = extract_probe_commands(out)
    assert any("feature_counter_probe" in c for c in probes), probes
