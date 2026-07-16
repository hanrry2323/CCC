"""v0.42.1 plan adopt + scope backfill"""

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


def test_find_plan_refs():
    text = "规划文件已写入 `.ccc/plans/qb-vip-v5-v6-checkout.plan.md`，包含"
    assert find_plan_refs(text) == ["qb-vip-v5-v6-checkout"]


def test_synthesize_has_scope():
    phases = synthesize_phases_from_plan(SAMPLE)
    assert len(phases) == 2
    assert "local_writer.py" in phases[0]["scope"][0]
    assert phases[0]["scope"]
    assert phases[1]["scope"]


def test_backfill_empty_scope():
    phases = [
        {"phase": 1, "status": "pending", "description": "x", "scope": [], "subtasks": {"1.1": "pending"}}
    ]
    out = backfill_scopes(phases, SAMPLE)
    assert out[0]["scope"]


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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
