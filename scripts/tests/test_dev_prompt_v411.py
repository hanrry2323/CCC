"""board.prompt + pytest feedback helpers (v0.41.1)"""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

from board.prompt import build_dev_phase_prompt
from _skills_catalog import format_skill_hints_block, discover_skills


def test_prompt_includes_scope_and_pytest_fail():
    text = build_dev_phase_prompt(
        "t1",
        1,
        "## plan\nhello",
        scope=["scripts/foo.py", "scripts/bar.py"],
        pytest_failure="exit_code=1\nFAILED tests/test_x.py",
    )
    assert "scripts/foo.py" in text
    assert "上次 pytest 失败" in text
    assert "只做 Phase 1" in text
    assert "弱模型友好" in text


def test_prompt_without_scope_warns():
    text = build_dev_phase_prompt("t1", 2, "plan")
    assert "未提供 scope" in text


def test_prompt_includes_skill_soft_hints():
    block = format_skill_hints_block(["ccc-dev", "hyperframes-core"], "偏执行规范")
    text = build_dev_phase_prompt(
        "t1", 1, "plan", skill_hints=block
    )
    assert "Skill 偏好" in text
    assert "ccc-dev" in text
    assert "软提示" in text
    assert "偏执行规范" in text


def test_discover_skills_finds_ccc_roles():
    skills = discover_skills(ccc_home=SCRIPTS.parent, limit=40)
    ids = {s["id"] for s in skills}
    assert "ccc-dev" in ids
    assert "ccc-product" in ids
