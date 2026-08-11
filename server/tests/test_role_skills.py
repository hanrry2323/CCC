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


class TestDispatchTimeInjection:
    """派发时动态注入（②）：改 yaml 后派发拿到最新映射（出卡时注入不覆盖，派发时刷新）。"""

    def test_role_skill_hint_reflects_updated_yaml(self, monkeypatch) -> None:
        """模拟 yaml 更新（新角色映射），_role_skill_hint 返回新 skill（派发时实时查）。"""
        card = "# 任务卡 c4\n\n> 关联：· 角色：前端设计 · 状态：待分派\n\n## 目标\n。\n"
        # 旧 yaml：前端设计 → ui-ux-pro-max
        assert "ui-ux-pro-max" in _role_skill_hint(card)
        # 模拟 yaml 更新：前端设计 → new-design-skill
        updated = {
            "roles": {
                "前端设计": {"skill": "new-design-skill", "skill_source": "opencode", "note": "updated"},
            }
        }
        monkeypatch.setattr("server.board.prompt_inject._load_role_skills", lambda: updated)
        assert "new-design-skill" in _role_skill_hint(card)
        assert "ui-ux-pro-max" not in _role_skill_hint(card)

    def test_dispatch_injection_block_contains_dynamic_hint(self, monkeypatch) -> None:
        """派发提示块含动态角色 hint（模拟 _dispatch_and_collect 的动态注入逻辑）。"""
        card_text = "# 任务卡 c5\n\n> 关联：· 角色：代码审查 · 状态：待分派\n\n## 目标\n。\n"
        updated = {
            "roles": {
                "代码审查": {"skill": "review-v2", "skill_source": "claude", "note": "updated"},
            }
        }
        monkeypatch.setattr("server.board.prompt_inject._load_role_skills", lambda: updated)
        dyn = _role_skill_hint(card_text)
        assert "review-v2" in dyn
        # 注入块组装（与 _dispatch_and_collect 相同逻辑）
        block = "\n## 项目提示\n基础提示\n" + dyn
        assert "review-v2" in block


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


class TestSyncSkillsCheck:
    """③ 节点 skill 存在性校验逻辑（sync-skills.py hash 一致性判定）。"""

    def test_hash_consistency_judgement(self, tmp_path: Path) -> None:
        """仓内 SKILL.md vs 节点 SKILL.md：内容一致→OK；内容不同→MISMATCH；缺失→MISMATCH。"""
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "sync_skills_mod", Path(__file__).resolve().parents[2] / "scripts" / "sync-skills.py"
        )
        assert spec is not None and spec.loader is not None
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)

        src = tmp_path / "src"
        node = tmp_path / "node"
        src.mkdir()
        (src / "demo-skill").mkdir(parents=True)
        (src / "demo-skill" / "SKILL.md").write_text("# demo\n", encoding="utf-8")

        src_hash = m.file_hash(src / "demo-skill" / "SKILL.md")

        # 一致 → 相等
        node.mkdir()
        (node / "demo-skill").mkdir(parents=True)
        (node / "demo-skill" / "SKILL.md").write_text("# demo\n", encoding="utf-8")
        node_hash = m.file_hash(node / "demo-skill" / "SKILL.md")
        assert src_hash == node_hash

        # 不同 → 不等
        (node / "demo-skill" / "SKILL.md").write_text("# demo changed\n", encoding="utf-8")
        node_hash2 = m.file_hash(node / "demo-skill" / "SKILL.md")
        assert src_hash != node_hash2

        # 缺失（节点无 SKILL.md）→ file_hash 抛 FileNotFoundError（sync 视为不一致/需下发）
        (node / "demo-skill" / "SKILL.md").unlink()
        try:
            m.file_hash(node / "demo-skill" / "SKILL.md")
            raised = False
        except FileNotFoundError:
            raised = True
        assert raised, "缺失 SKILL.md 应视为不一致（需 sync）"
