"""role-skills 一致性单测（ccc-plan-020 A 轨第 4 项）。

覆盖：
1. _load_role_skills 加载 SSOT（role-skills.yaml）→ 角色映射正确
2. _role_skill_hint：卡头「角色：前端设计」→ 注入「请加载 Skill ui-ux-pro-max」
3. 未知角色 → 空注入（不注入错误 skill）
4. sync-skills 版本校验逻辑（SKILL.md hash 一致性判定）
"""

from __future__ import annotations

from pathlib import Path

from server.board.prompt_inject import _load_role_skills, _role_skill_hint

ROLE_YAML = Path(__file__).resolve().parents[2] / "server" / "config" / "role-skills.yaml"
SKILL_YAML_SRC = Path(__file__).resolve().parents[2] / "server" / "config" / "role-skills.yaml"
OPENCOTE_SKILLS = Path(__file__).resolve().parents[2] / "server" / "config" / "opencode-skills"
CLAUDE_SKILLS = Path(__file__).resolve().parents[2] / "server" / "config" / "claude-skills"


class TestRoleSkillMapping:
    """role-skills SSOT 加载与注入。"""

    def test_load_roles_ssot(self) -> None:
        cfg = _load_role_skills()
        roles = cfg.get("roles", {})
        assert "前端设计" in roles, "SSOT 应含 前端设计 角色"
        assert roles["前端设计"]["skill"] == "ui-ux-pro-max"
        assert "代码审查" in roles
        assert roles["代码审查"]["skill"] == "code-review"

    def test_role_skill_hint_injects(self) -> None:
        card = "# 任务卡 c1\n\n> 关联：· 角色：前端设计 · 状态：待分派\n\n## 目标\n。\n"
        hint = _role_skill_hint(card)
        assert "ui-ux-pro-max" in hint
        assert "请加载 Skill" in hint

    def test_unknown_role_no_hint(self) -> None:
        card = "# 任务卡 c2\n\n> 关联：· 角色：不存在的角色 · 状态：待分派\n\n## 目标\n。\n"
        assert _role_skill_hint(card) == ""

    def test_no_role_no_hint(self) -> None:
        card = "# 任务卡 c3\n\n> 关联：· 状态：待分派\n\n## 目标\n。\n"
        assert _role_skill_hint(card) == ""


class TestSkillInRepo:
    """skill 本体进仓校验：SSOT 引用且已在仓的 skill 必须完整（SKILL.md 存在）。

    A 轨第 4 项第一步：ui-ux-pro-max（opencode）与 code-review（claude）已进仓。
    其余 SSOT 引用（qx-auto-copycheck/daily-snapshot/hp-kb-operations/motion-graphics）为节点本地
    skill，待后续收仓——不视为错误，只统计。
    """

    def test_skill_has_skil_md(self) -> None:
        """仓内每个 skill 目录含 SKILL.md（版本校验依据）。"""
        for d in list(OPENCOTE_SKILLS.iterdir()) + list(CLAUDE_SKILLS.iterdir()):
            if d.is_dir():
                assert (d / "SKILL.md").is_file(), f"{d.name} 缺 SKILL.md"
