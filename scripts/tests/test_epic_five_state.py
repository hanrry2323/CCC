"""Epic five-state + alias + backlog sort + border HSL."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _board_store import (  # noqa: E402
    FileBoardStore,
    fill_task_defaults,
    task_border_hsl,
    validate_task_jsonl,
)
from _product_fanout import apply_fanout, refresh_epic_lifecycle  # noqa: E402


def _ts():
    return "2026-07-17T12:00:00+08:00"


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


def test_alias_active_blocked_normalize():
    d = fill_task_defaults(
        {
            "id": "e1",
            "title": "E",
            "status": "backlog",
            "created_at": _ts(),
            "updated_at": _ts(),
            "card_kind": "epic",
            "split_status": "active",
        },
        column="backlog",
    )
    assert d["split_status"] == "running"
    d2 = fill_task_defaults(
        {
            "id": "e2",
            "title": "E",
            "status": "backlog",
            "created_at": _ts(),
            "updated_at": _ts(),
            "card_kind": "epic",
            "split_status": "blocked",
        },
        column="backlog",
    )
    assert d2["split_status"] == "failed"


def test_validate_accepts_five_states_and_aliases():
    base = {
        "id": "e1",
        "title": "E",
        "status": "backlog",
        "created_at": _ts(),
        "updated_at": _ts(),
        "card_kind": "epic",
    }
    for ss in ("pending", "planned", "running", "done", "failed", "active", "blocked"):
        ok, errs = validate_task_jsonl({**base, "split_status": ss})
        assert ok, (ss, errs)


def test_backlog_sort_five_state(tmp_path):
    store = FileBoardStore(tmp_path)
    store.create_task({"id": "d-done", "title": "D"}, column="backlog")
    store.patch_task("d-done", {"split_status": "done", "color_group": "A"})
    store.create_task({"id": "f-fail", "title": "F"}, column="backlog")
    store.patch_task("f-fail", {"split_status": "failed", "color_group": "B"})
    store.create_task({"id": "p-pend", "title": "P"}, column="backlog")
    store.create_task({"id": "r-run", "title": "R"}, column="backlog")
    store.patch_task("r-run", {"split_status": "running", "color_group": "C"})
    ids = [t["id"] for t in store.list_tasks("backlog")]
    assert ids[-1] == "d-done"
    assert "f-fail" in ids
    assert ids.index("f-fail") < ids.index("d-done")
    assert ids.index("p-pend") < ids.index("f-fail")
    assert ids.index("r-run") < ids.index("f-fail")


def test_border_hsl_depth():
    epic = task_border_hsl("A", 0)
    work = task_border_hsl("A", 1)
    assert epic and "48%" in epic
    assert work and "62%" in work


def test_lifecycle_planned_running_failed(tmp_path):
    store = FileBoardStore(tmp_path)
    store.create_task({"id": "e", "title": "E"}, column="backlog")
    apply_fanout(
        store,
        store.list_tasks("backlog")[0],
        children_raw=[_child("e-w1", "a.py"), _child("e-w2", "b.py")],
    )
    assert refresh_epic_lifecycle(store, "e") == "planned"
    _, epic = store.find_task("e")
    assert epic["split_status"] == "planned"

    store.move_task("e-w1", "planned", "in_progress")
    assert refresh_epic_lifecycle(store, "e") == "running"

    store.move_task("e-w1", "in_progress", "abnormal")
    assert refresh_epic_lifecycle(store, "e") == "failed"
    assert store.find_task("e")[0] == "backlog"


def test_lifecycle_rewrites_blocked_alias_on_disk(tmp_path):
    """存量 blocked 盘面应被 refresh 改写为 failed（不只读路径归一）。"""
    import json

    store = FileBoardStore(tmp_path)
    store.create_task({"id": "e", "title": "E"}, column="backlog")
    apply_fanout(
        store,
        store.list_tasks("backlog")[0],
        children_raw=[_child("e-w1", "a.py")],
    )
    store.move_task("e-w1", "planned", "in_progress")
    store.move_task("e-w1", "in_progress", "abnormal")
    # 模拟旧盘面仍写 blocked
    path = tmp_path / ".ccc/board/backlog/e.jsonl"
    raw = json.loads(path.read_text().splitlines()[0])
    raw["split_status"] = "blocked"
    path.write_text(json.dumps(raw, ensure_ascii=False) + "\n", encoding="utf-8")
    assert refresh_epic_lifecycle(store, "e") == "failed"
    disk = json.loads(path.read_text().splitlines()[0])
    assert disk["split_status"] == "failed"
    """纯函数 epicLifecycleLabel 可被 Node 导入单测。"""
    import subprocess

    js = Path(__file__).resolve().parents[1] / "chat_server/frontend/js/epicLifecycle.js"
    r = subprocess.run(
        [
            "node",
            "--input-type=module",
            "-e",
            f"import {{ epicLifecycleLabel, normalizeEpicSplitStatus }} from '{js}';"
            "const assert = (c,m)=>{{if(!c)throw new Error(m);}};"
            "assert(epicLifecycleLabel('pending')==='未规划','pending');"
            "assert(epicLifecycleLabel('planned')==='已规划','planned');"
            "assert(epicLifecycleLabel('running')==='开发中','running');"
            "assert(epicLifecycleLabel('done')==='已完成','done');"
            "assert(epicLifecycleLabel('failed')==='失败','failed');"
            "assert(epicLifecycleLabel('active')==='开发中','active');"
            "assert(epicLifecycleLabel('blocked')==='失败','blocked');"
            "assert(normalizeEpicSplitStatus('active')==='running','norm active');"
            "assert(normalizeEpicSplitStatus('blocked')==='failed','norm blocked');"
            "console.log('ok');",
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert r.returncode == 0, r.stderr + r.stdout
