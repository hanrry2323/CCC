"""v0.42.1 plan adopt + scope backfill；v0.53.3 卫生白名单不误领养"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _plan_adopt import (
    find_plan_refs,
    extract_paths,
    synthesize_phases_from_plan,
    backfill_scopes,
    try_adopt_referenced_plan,
    phases_jsonl_from_plan,
)


SAMPLE = """# Plan

## 范围
- `src/a.py`

## Phase 1：写 writer
新建 `src/xianyu/storage/local_writer.py`

## Phase 2：改 pipeline
修改 `src/xianyu/orchestrator/pipeline.py`

## 验收
- pytest -q
"""

HYGIENE = """# Plan — 提交清场残留 .ccc 编排产物

## 范围
**白名单(必须入本次 commit)**:
- .ccc/board/events/v1-3-21-fa7272aa-w1.events.jsonl
- .ccc/plans/v1-3-21-fa7272aa-w1.plan.md
- .ccc/plans/v1-3-21-fa7272aa.plan.md
- .ccc/state.md
- .ccc/agent-mind/decided.json

## 禁止
- 禁止触碰 src/、tests/、config/、docs/、STATUS.md
- 禁止触发 data_engine / order_gateway

## 步骤
1. `git add .ccc/plans/v1-3-21-fa7272aa.plan.md`

## 验收
- git status --porcelain | wc -l 返回 0
"""


def test_find_plan_refs():
    text = "规划文件已写入 `.ccc/plans/qb-vip-v5-v6-checkout.plan.md`，包含"
    assert find_plan_refs(text) == ["qb-vip-v5-v6-checkout"]


def test_find_plan_refs_ignores_whitelist_paths():
    """卫生卡白名单罗列历史 plan 路径不得触发收养（c0399a8f 根因）。"""
    blob = (
        "本次 commit 仅包含:.ccc/plans/v1-3-21-fa7272aa-w1.plan.md;"
        ".ccc/plans/v1-3-21-fa7272aa.plan.md\n"
        "- `git add .ccc/plans/v1-3-21-fa7272aa.plan.md`\n"
    )
    assert find_plan_refs(blob) == []
    assert find_plan_refs(HYGIENE) == []


def test_synthesize_has_scope():
    phases = synthesize_phases_from_plan(SAMPLE)
    assert len(phases) == 2
    assert "local_writer.py" in phases[0]["scope"][0]
    assert phases[0]["scope"]
    assert phases[1]["scope"]


def test_synthesize_hygiene_keeps_ccc_scope():
    phases = synthesize_phases_from_plan(HYGIENE)
    assert len(phases) == 1
    scope = phases[0]["scope"]
    assert any(s.startswith(".ccc/") for s in scope)
    assert not any(s.startswith("src/") for s in scope)
    assert "STATUS.md" not in scope
    assert "提交清场残留" in phases[0]["description"]


def test_extract_paths_strips_forbidden():
    paths = extract_paths(HYGIENE)
    assert all(
        p.startswith(".ccc/") or p in (".ccc/state.md",)
        or p.startswith(".ccc/")
        for p in paths
    )
    assert "STATUS.md" not in paths
    assert not any(p.startswith("src/") for p in paths)


def test_backfill_empty_scope():
    phases = [
        {"phase": 1, "status": "pending", "description": "x", "scope": [], "subtasks": {"1.1": "pending"}}
    ]
    out = backfill_scopes(phases, SAMPLE)
    assert out[0]["scope"]


def test_phases_jsonl_from_plan():
    raw = phases_jsonl_from_plan(HYGIENE)
    lines = [ln for ln in raw.splitlines() if ln.strip()]
    assert json.loads(lines[0]).get("schema_version") == "1.1"
    ph = json.loads(lines[1])
    assert ph["scope"]
    assert any(str(s).startswith(".ccc/") for s in ph["scope"])


def test_try_adopt(tmp_path):
    ws = tmp_path / "proj"
    (ws / ".ccc" / "plans").mkdir(parents=True)
    (ws / ".ccc" / "phases").mkdir(parents=True)
    (ws / ".ccc" / "board" / "backlog").mkdir(parents=True)
    src = ws / ".ccc" / "plans" / "vip.plan.md"
    # 仅有 ### 验收清单（无 ## 验收）— 收养时应自动补硬门章节
    src.write_text(
        SAMPLE.replace("## 验收\n- pytest -q\n", "### 验收清单\n- [ ] pytest -q\n"),
        encoding="utf-8",
    )
    task = {
        "id": "ccc-1",
        "description": "见 `.ccc/plans/vip.plan.md`",
    }
    r = try_adopt_referenced_plan(ws, "ccc-1", task)
    assert r["ok"], r
    assert (ws / ".ccc" / "plans" / "ccc-1.plan.md").is_file()
    assert "## 验收" in (ws / ".ccc" / "plans" / "ccc-1.plan.md").read_text()
    assert (ws / ".ccc" / "phases" / "ccc-1.phases.json").is_file()


def test_try_adopt_skips_whitelist_only_refs(tmp_path):
    ws = tmp_path / "proj"
    (ws / ".ccc" / "plans").mkdir(parents=True)
    (ws / ".ccc" / "phases").mkdir(parents=True)
    (ws / ".ccc" / "plans" / "v1-3-21-fa7272aa.plan.md").write_text(
        "# old\n## 范围\n- `src/core/data_engine.py`\n## 验收\n- x\n",
        encoding="utf-8",
    )
    task = {
        "id": "ccc-hygiene",
        "description": HYGIENE,
        "title": "提交清场残留",
    }
    r = try_adopt_referenced_plan(ws, "ccc-hygiene", task)
    assert r.get("ok") is False
    assert r.get("reason") == "no_plan_ref"
    assert not (ws / ".ccc" / "phases" / "ccc-hygiene.phases.json").exists()


def test_extract_strips_cli_args():
    from _plan_adopt import _normalize_extracted_path

    assert (
        _normalize_extracted_path("scripts/startup_check.py --strict --env paper")
        == "scripts/startup_check.py"
    )
    text = (
        "## 范围\n"
        "- `scripts/paper_intent_probe.py`（新建）：封装 "
        "`scripts/startup_check.py --strict --env paper`\n"
    )
    paths = extract_paths(text)
    assert "scripts/paper_intent_probe.py" in paths
    assert "scripts/startup_check.py" in paths
    assert not any("--" in p for p in paths)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
