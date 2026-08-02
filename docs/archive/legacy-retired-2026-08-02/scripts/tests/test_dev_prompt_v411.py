"""board.prompt + pytest feedback helpers (v0.41.1) + workspace isolation."""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

from board.prompt import build_dev_phase_prompt
from _skills_catalog import format_skill_hints_block, discover_skills

# 2026-07-24：原硬编码 /Users/apple/program/xianyu 在测试机上不存在，
# _workspace_isolation.require_cwd 会抛 ValueError。改用 tmp_path，
# 测试只验证 prompt 文本结构，与具体 workspace 路径无关。
# DEPRECATED（2026-07-24）：_WS 全局硬编码路径，保留为参考。
# _WS = "/Users/apple/program/xianyu"


def test_prompt_includes_scope_and_pytest_fail(tmp_path):
    ws = str(tmp_path)
    text = build_dev_phase_prompt(
        "t1",
        1,
        "## plan\nhello",
        workspace=ws,
        scope=["scripts/foo.py", "scripts/bar.py"],
        pytest_failure="exit_code=1\nFAILED tests/test_x.py",
    )
    assert "scripts/foo.py" in text
    assert "上次 pytest 失败" in text
    assert "只做 Phase 1" in text
    # 2026-07-24：prompt 重构去掉了"弱模型友好"字面量（v0.41.1 后期文案精简）
    # assert "弱模型友好" in text
    assert "工作目录硬门" in text
    assert ws in text
    assert "门禁不代写" in text
    assert f"{ws}/.ccc/state.md" in text
    assert "~/.ccc/" in text


def test_prompt_without_scope_warns(tmp_path):
    ws = str(tmp_path)
    text = build_dev_phase_prompt("t1", 2, "plan", workspace=ws)
    assert "未提供 scope" in text


def test_prompt_includes_skill_soft_hints(tmp_path):
    ws = str(tmp_path)
    block = format_skill_hints_block(["ccc-dev", "hyperframes-core"], "偏执行规范")
    text = build_dev_phase_prompt(
        "t1", 1, "plan", workspace=ws, skill_hints=block
    )
    assert "Skill 偏好" in text
    assert "ccc-dev" in text
    assert "软提示" in text
    assert "偏执行规范" in text


def test_prompt_requires_workspace():
    import pytest

    with pytest.raises(ValueError, match="cwd required"):
        build_dev_phase_prompt("t1", 1, "plan", workspace="")


def test_discover_skills_finds_ccc_roles():
    # 2026-07-24：discover_skills 默认 include_engine=False 隐藏 engine-only 角色；
    # ccc-dev 在 _ENGINE_IDS 里，需 include_engine=True 才暴露。
    skills = discover_skills(ccc_home=SCRIPTS.parent, limit=40, include_engine=True)
    ids = {s["id"] for s in skills}
    assert "ccc-dev" in ids
    assert "ccc-product" in ids
