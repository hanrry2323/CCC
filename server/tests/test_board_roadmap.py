"""测试 server/board/roadmap.py — 线路图数据模型。"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from server.board.roadmap import (
    Draft,
    Milestone,
    Subproject,
    activate_subproject,
    active_linked_plans,
    compute_milestone_progress,
    sync_milestone_progress,
    create_draft,
    create_milestone,
    delete_milestone,
    edit_draft,
    list_drafts,
    list_milestones,
    list_roadmaps,
    parse_roadmap,
    promote_draft,
    remove_draft,
    update_milestone,
)


# ── 初始内容模板 ──

ROADMAP_INIT = """# Test 线路图

> 项目：test · 更新：2026-08-12

## 草案池

无。

## 里程碑

无。
"""

CLW_ROADMAP_INIT = """# clwarp 线路图

> 项目：clw · 更新：2026-08-12

## 草案池

无。

## 里程碑

无。
"""


# ── 解析测试（纯函数，不需要 mock） ──


class TestParseRoadmap:
    def test_parse_empty(self) -> None:
        result = parse_roadmap(
            """# Test 线路图
> 项目：test · 更新：2026-08-12

## 草案池

无。

## 里程碑

无。
""",
            project="test",
        )
        assert result["drafts"] == []
        assert result["milestones"] == []
        assert result["updated"] == "2026-08-12"

    def test_parse_with_drafts(self) -> None:
        result = parse_roadmap(
            """# Test 线路图
> 项目：test · 更新：2026-08-12

## 草案池

- 草案 A
- 草案 B

## 里程碑

无。
""",
            project="test",
        )
        assert len(result["drafts"]) == 2
        assert result["drafts"][0].title == "草案 A"
        assert result["drafts"][1].title == "草案 B"

    def test_parse_with_milestones(self) -> None:
        result = parse_roadmap(
            """# Test 线路图
> 项目：test · 更新：2026-08-12

## 草案池

无。

## 里程碑

### M1
- 状态：进行中
- 关联方案：test-plan-001, test-plan-002
- 描述：第一个里程碑

### M2
- 状态：草案
- 关联方案：test-plan-003
- 描述：第二个里程碑
""",
            project="test",
        )
        assert len(result["milestones"]) == 2
        m1 = result["milestones"][0]
        assert m1.title == "M1"
        assert m1.status == "进行中"
        assert m1.linked_plans == ["test-plan-001", "test-plan-002"]
        assert m1.description == "第一个里程碑"
        m2 = result["milestones"][1]
        assert m2.title == "M2"
        assert m2.status == "草案"

    def test_parse_milestone_minimal(self) -> None:
        result = parse_roadmap(
            """# Test 线路图
> 项目：test · 更新：2026-08-12

## 草案池

无。

## 里程碑

### M1
- 状态：草案
""",
            project="test",
        )
        assert len(result["milestones"]) == 1
        assert result["milestones"][0].title == "M1"
        assert result["milestones"][0].linked_plans == []
        assert result["milestones"][0].description == ""

    def test_parse_with_subprojects(self) -> None:
        """2026-08-16 子项目层：里程碑下结构化解耦为子项目。"""
        result = parse_roadmap(
            """# Test 线路图
> 项目：test · 更新：2026-08-16

## 草案池

无。

## 里程碑

### M1
- 状态：进行中
- 子项目：
  - 2.1 pipeline 源码回灌 SSOT · 状态：计划中 · 方案：test-plan-008
  - 2.2 双仓归一 · 状态：未启动
  - 2.7 可重建验证 · 状态：已完成

### M2
- 状态：待启动
- 子项目：
  - 3.1 健康三态探针
""",
            project="test",
        )
        assert len(result["milestones"]) == 2
        m1 = result["milestones"][0]
        assert len(m1.subprojects) == 3
        sp = m1.subprojects[0]
        assert sp.id == "2.1"
        assert sp.title == "pipeline 源码回灌 SSOT"
        assert sp.status == "计划中"
        assert sp.plan_id == "test-plan-008"
        assert m1.subprojects[1].status == "未启动"
        assert m1.subprojects[1].plan_id == ""
        assert m1.subprojects[2].status == "已完成"
        m2 = result["milestones"][1]
        assert len(m2.subprojects) == 1
        assert m2.subprojects[0].id == "3.1"
        assert m2.subprojects[0].status == "未启动"
        assert m2.subprojects[0].plan_id == ""


# ── list_roadmaps 测试（读真实文件系统，只读） ──


class TestListRoadmaps:
    def test_list_returns_prefixes(self) -> None:
        rdms = list_roadmaps()
        # ccc 是 platform 类项目，list_roadmaps 跳过平台自研项目
        assert "ccc" not in rdms
        assert "clw" in rdms
        assert "hp" in rdms
        assert "qb" in rdms
        assert "mx" in rdms
        assert "xy" in rdms


# ── 草案 CRUD 测试（用 tmp_path + mock，不写生产文件） ──


class TestDraftCRUD:
    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path: Path, request: pytest.FixtureRequest) -> None:
        """每个测试方法独立创建前置条件：临时 roadmap.md + mock _roadmap_path。"""
        self.roadmap_path = tmp_path / "roadmap.md"
        self.roadmap_path.parent.mkdir(parents=True, exist_ok=True)
        self.roadmap_path.write_text(ROADMAP_INIT, encoding="utf-8")

        patcher = patch("server.board.roadmap._roadmap_path")
        self.mock_roadmap_path = patcher.start()
        self.mock_roadmap_path.side_effect = lambda project: self.roadmap_path
        request.addfinalizer(patcher.stop)

    def test_create_and_list(self) -> None:
        create_draft("test", "测试草案")
        drafts = list_drafts("test")
        titles = [d.title for d in drafts]
        assert "测试草案" in titles

    def test_create_duplicate(self) -> None:
        create_draft("test", "测试草案")
        result = create_draft("test", "测试草案")
        assert "error" in result

    def test_promote_draft(self) -> None:
        create_draft("test", "测试草案")
        # promote_draft 已弃用 → 返回 error
        result = promote_draft("test", "测试草案")
        assert "error" in result
        assert "弃用" in result.get("error", "")
        # 草案仍在池中（未移除）
        drafts = list_drafts("test")
        assert "测试草案" in [d.title for d in drafts]

    def test_edit_draft(self) -> None:
        """人审调整动作统一化：节点① 改草案文字（再确认转方案）。"""
        create_draft("test", "旧草案")
        result = edit_draft("test", 0, "新草案")
        assert "error" not in result
        titles = [d.title for d in list_drafts("test")]
        assert titles == ["新草案"]

    def test_edit_draft_duplicate(self) -> None:
        """改后与其它草案重名 → 拒绝。"""
        create_draft("test", "草案A")
        create_draft("test", "草案B")
        result = edit_draft("test", 0, "草案B")
        assert "error" in result
        # 原样未变
        assert [d.title for d in list_drafts("test")] == ["草案A", "草案B"]

    def test_edit_draft_index_oob(self) -> None:
        create_draft("test", "草案A")
        result = edit_draft("test", 5, "草案B")
        assert "error" in result
        assert "越界" in result.get("error", "")

    def test_remove_draft(self) -> None:
        """人审调整动作统一化：节点① 取消草案 = 直接移除条目。"""
        create_draft("test", "草案A")
        create_draft("test", "草案B")
        result = remove_draft("test", 0)
        assert "error" not in result
        assert result.get("removed") == "草案A"
        assert [d.title for d in list_drafts("test")] == ["草案B"]

    def test_remove_draft_index_oob(self) -> None:
        create_draft("test", "草案A")
        result = remove_draft("test", 3)
        assert "error" in result
        assert "越界" in result.get("error", "")


# ── 里程碑 CRUD 测试（用 tmp_path + mock） ──


class TestMilestoneCRUD:
    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path: Path, request: pytest.FixtureRequest) -> None:
        """每个测试方法独立创建前置条件（修复 Bug 12：测试顺序依赖）。"""
        self.roadmap_path = tmp_path / "roadmap.md"
        self.roadmap_path.parent.mkdir(parents=True, exist_ok=True)
        self.roadmap_path.write_text(CLW_ROADMAP_INIT, encoding="utf-8")

        patcher = patch("server.board.roadmap._roadmap_path")
        self.mock_roadmap_path = patcher.start()
        self.mock_roadmap_path.side_effect = lambda project: self.roadmap_path
        request.addfinalizer(patcher.stop)

    def test_create_milestone(self) -> None:
        result = create_milestone(
            "clw",
            "测试里程碑",
            status="草案",
            linked_plans=["clw-plan-001"],
            description="测试描述",
        )
        assert result.get("ok") is True
        mss = list_milestones("clw")
        found = next(m for m in mss if m.title == "测试里程碑")
        assert found.linked_plans == ["clw-plan-001"]
        assert found.description == "测试描述"

    def test_create_duplicate_milestone(self) -> None:
        create_milestone("clw", "测试里程碑", status="草案")
        result = create_milestone("clw", "测试里程碑", status="草案")
        assert "error" in result

    def test_update_milestone(self) -> None:
        create_milestone("clw", "测试里程碑", status="草案")
        result = update_milestone("clw", "测试里程碑", status="进行中")
        assert result.get("ok") is True
        mss = list_milestones("clw")
        found = next(m for m in mss if m.title == "测试里程碑")
        assert found.status == "进行中"

    def test_update_milestone_not_found(self) -> None:
        result = update_milestone("clw", "不存在的里程碑", status="已完成")
        assert "error" in result

    def test_milestone_target_date_roundtrip(self) -> None:
        """2026-08-14 加固：里程碑 target_date 可写可读。"""
        create_milestone("clw", "带日期里程碑", status="待启动", target_date="2026-10-01")
        found = next(m for m in list_milestones("clw") if m.title == "带日期里程碑")
        assert found.target_date == "2026-10-01"
        # 更新日期
        update_milestone("clw", "带日期里程碑", target_date="2026-11-01")
        found = next(m for m in list_milestones("clw") if m.title == "带日期里程碑")
        assert found.target_date == "2026-11-01"
        assert "目标日期：2026-11-01" in self.roadmap_path.read_text(encoding="utf-8")

    def test_draft_source_roundtrip(self) -> None:
        """2026-08-14 加固：草案 source/created 标记可写可读。"""
        create_draft("clw", "老板意向草案", source="老板意图")
        found = list_drafts("clw")[0]
        assert found.title == "老板意向草案"
        assert found.source == "老板意图"
        assert found.created  # 非空（默认今天）
        # 写入格式含来源标记
        assert "[老板意图]" in self.roadmap_path.read_text(encoding="utf-8")

    def test_delete_milestone_ok(self) -> None:
        """人审统一化：DELETE 里程碑（仅无关联方案）。"""
        create_milestone("clw", "可删除里程碑", status="待启动", linked_plans=[])
        result = delete_milestone("clw", "可删除里程碑")
        assert "error" not in result
        assert result.get("removed") == "可删除里程碑"
        assert [m.title for m in list_milestones("clw")] == []

    def test_delete_milestone_with_plans_rejected(self) -> None:
        """有关联方案 → 拒绝删除（需先解绑）。"""
        create_milestone("clw", "有方案里程碑", status="待启动", linked_plans=["clw-plan-001"])
        result = delete_milestone("clw", "有方案里程碑")
        assert "error" in result
        assert "关联方案" in result.get("error", "")
        # 未被删除
        assert [m.title for m in list_milestones("clw")] == ["有方案里程碑"]

    def test_delete_milestone_not_found(self) -> None:
        result = delete_milestone("clw", "不存在")
        assert "error" in result


# ── 进度计算测试（用 tmp_path + mock） ──


class TestComputeProgress:
    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path: Path, request: pytest.FixtureRequest) -> None:
        self.roadmap_path = tmp_path / "roadmap.md"
        self.roadmap_path.parent.mkdir(parents=True, exist_ok=True)
        self.roadmap_path.write_text(CLW_ROADMAP_INIT, encoding="utf-8")

        patcher = patch("server.board.roadmap._roadmap_path")
        self.mock_roadmap_path = patcher.start()
        self.mock_roadmap_path.side_effect = lambda project: self.roadmap_path
        request.addfinalizer(patcher.stop)

    def test_empty_plans(self) -> None:
        create_milestone("clw", "空方案里程碑2", status="草案", linked_plans=["clw-plan-999"])
        result = compute_milestone_progress("clw", "空方案里程碑2")
        assert result["total"] == 1
        assert result["progress_pct"] == 0

    def test_no_linked_plans(self) -> None:
        create_milestone("clw", "空方案里程碑", status="草案", linked_plans=[])
        result = compute_milestone_progress("clw", "空方案里程碑")
        assert result["total"] == 0
        assert result["progress_pct"] == 0


# ── 往返测试（写→读→验证，用 tmp_path mock _repo_root） ──


class TestRoundtrip:
    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path: Path, request: pytest.FixtureRequest) -> None:
        """每个测试方法独立创建前置条件（修复 Bug 11 + 12）。"""
        self.mock_root = tmp_path / "repo"
        projects_dir = self.mock_root / "docs" / "projects"
        (projects_dir / "ccc").mkdir(parents=True, exist_ok=True)
        (projects_dir / "clw").mkdir(parents=True, exist_ok=True)
        self.ccc_roadmap = projects_dir / "ccc" / "roadmap.md"
        self.clw_roadmap = projects_dir / "clw" / "roadmap.md"
        self.ccc_roadmap.write_text(ROADMAP_INIT.replace("项目：test", "项目：ccc"), encoding="utf-8")
        self.clw_roadmap.write_text(CLW_ROADMAP_INIT, encoding="utf-8")

        patcher = patch("server.board.roadmap._repo_root", return_value=self.mock_root)
        self.mock_repo_root = patcher.start()
        request.addfinalizer(patcher.stop)

    def test_parse_write_parse(self) -> None:
        """写数据到临时 roadmap.md，然后读回验证。"""
        create_milestone("clw", "循环测试", status="进行中", linked_plans=["clw-plan-001"], description="X")
        create_draft("clw", "新草案")
        drafts = list_drafts("clw")
        mss = list_milestones("clw")
        assert "新草案" in [d.title for d in drafts]
        assert "循环测试" in [m.title for m in mss]
        # 验证 list_roadmaps 在 mock 环境中也能工作
        rdms = list_roadmaps()
        assert "clw" in rdms

    def test_subproject_roundtrip_and_activate(self) -> None:
        """子项目解析/写盘往返不丢；activate_subproject 设状态+方案并同步 linked_plans。"""
        self.clw_roadmap.write_text(
            """# clwarp 线路图
> 项目：clw · 更新：2026-08-16

## 草案池

无。

## 里程碑

### M1 · 测试
- 状态：待启动
- 子项目：
  - 2.1 pipeline 源码回灌 SSOT · 状态：计划中 · 方案：clw-plan-008
  - 2.2 双仓归一 · 状态：未启动
""",
            encoding="utf-8",
        )
        mss = list_milestones("clw")
        assert len(mss) == 1
        m1 = mss[0]
        assert len(m1.subprojects) == 2
        assert m1.subprojects[0].plan_id == "clw-plan-008"
        assert m1.subprojects[1].status == "未启动"

        # 激活 2.2：设状态+方案，并同步 linked_plans
        r = activate_subproject("clw", "M1 · 测试", "2.2", "clw-plan-009")
        assert r.get("ok") is True, r
        mss2 = list_milestones("clw")
        sp = mss2[0].subprojects[1]
        assert sp.status == "计划中"
        assert sp.plan_id == "clw-plan-009"
        assert "clw-plan-009" in mss2[0].linked_plans

        # 不存在的子项目/里程碑报错
        assert "error" in activate_subproject("clw", "M1 · 测试", "9.9", "x")
        assert "error" in activate_subproject("clw", "不存在的里程碑", "2.1", "x")

    def test_subproject_progress_reads_plan(self) -> None:
        """2026-08-16 机审修复：子项目进度读关联方案完成率；方案完成 → 进度推进 + 子项目状态同步。"""
        self.clw_roadmap.write_text(
            """# clwarp 线路图
> 项目：clw · 更新：2026-08-16

## 草案池

无。

## 里程碑

### M1 · 测试
- 状态：进行中
- 子项目：
  - 2.1 子项目A · 状态：计划中 · 方案：clw-plan-008
""",
            encoding="utf-8",
        )
        # 方案不存在 → total=1 completed=0（进度不因「手写已完成」而虚高，读真实方案）
        prog = compute_milestone_progress("clw", "M1 · 测试")
        assert prog["total"] == 1 and prog["completed"] == 0
        # 建已完成方案 clw-plan-008 → completed=1，状态推导已完成
        plans_dir = self.mock_root / "docs" / "projects" / "clw" / "plans"
        plans_dir.mkdir(parents=True, exist_ok=True)
        (plans_dir / "008-a.md").write_text(
            "# 方案 · A\n\n> 项目：clw · 编号：clw-plan-008 · 状态：已完成 · 作者：x · 工具：pytest\n> 创建：2026-08-16 · 更新：2026-08-16\n\n## 目标\n\nx\n",
            encoding="utf-8",
        )
        prog2 = compute_milestone_progress("clw", "M1 · 测试")
        assert prog2["total"] == 1 and prog2["completed"] == 1
        assert prog2["status"] == "已完成"
        # sync_milestone_progress 同步子项目状态为已完成（写入 roadmap）
        r = sync_milestone_progress("clw", "docs/projects/clw/plans/008-a.md")
        assert r.get("ok") is True
        mss = list_milestones("clw")
        assert mss[0].subprojects[0].status == "已完成"

    def test_tail_preserved_on_write(self) -> None:
        """2026-08-16 机审缺陷4：序列化保留未识别尾部内容（blockquote 封板脚注），防巡逻写盘丢数据。"""
        self.clw_roadmap.write_text(
            """# clwarp 线路图
> 项目：clw · 更新：2026-08-16

## 草案池

无。

## 里程碑

### M1 · 测试
- 状态：进行中
- 描述：测试。

> **项目封板（2026-08-15）**：历史使命已完成。
""",
            encoding="utf-8",
        )
        create_draft("clw", "新增草案")  # 触发 _write_roadmap
        out = self.clw_roadmap.read_text(encoding="utf-8")
        assert "项目封板" in out
        assert "新增草案" in out

    def test_promote_draft_to_plan_success(self) -> None:
        """草案→方案一键升级：从草案池取一条草案创建方案，并从草案池移除。"""
        from server.board.roadmap import promote_draft_to_plan

        create_draft("ccc", "测试草案升级")
        # promote_draft_to_plan 内部 import server.board.plans.create_plan
        with patch("server.board.plans.create_plan") as mock_create:
            mock_create.return_value = {"ok": True, "path": "docs/projects/ccc/plans/001-test.md", "id": "ccc-plan-001"}
            result = promote_draft_to_plan("ccc", index=0, author="test", tool="pytest")
            assert result.get("ok") is True
            assert result["plan"]["id"] == "ccc-plan-001"
            assert result["draft_title"] == "测试草案升级"
            # 草案已从池中移除
            drafts = list_drafts("ccc")
            assert "测试草案升级" not in [d.title for d in drafts]

    def test_promote_draft_to_plan_empty_pool(self) -> None:
        """空草案池返回错误。"""
        from server.board.roadmap import promote_draft_to_plan

        result = promote_draft_to_plan("ccc", index=0)
        assert "error" in result
        assert "草案池为空" in result["error"]

    def test_promote_draft_to_plan_index_oob(self) -> None:
        """草案索引越界返回错误。"""
        from server.board.roadmap import promote_draft_to_plan

        create_draft("ccc", "唯一草案")
        result = promote_draft_to_plan("ccc", index=5)
        assert "error" in result
        assert "越界" in result["error"]

    def test_promote_draft_to_plan_rollback_on_create_failure(self) -> None:
        """方案创建失败时，草案应回滚回池中。"""
        from server.board.roadmap import promote_draft_to_plan

        create_draft("ccc", "回滚测试草案")
        # promote_draft_to_plan 内部 import server.board.plans.create_plan
        with patch("server.board.plans.create_plan") as mock_create:
            mock_create.return_value = {"error": "方案创建失败"}
            result = promote_draft_to_plan("ccc", index=0)
            assert "error" in result
            assert "方案创建失败" in result["error"]
            # 草案应回滚回池中
            drafts = list_drafts("ccc")
            assert "回滚测试草案" in [d.title for d in drafts]

    def test_promote_draft_to_plan_with_plans_cross_ref(self) -> None:
        """promote_draft_to_plan 调用真正的 plans.create_plan（通过 _repo_root mock 隔离）。"""
        from server.board.roadmap import promote_draft_to_plan

        # 构造 registry.yaml 和 validate-plans.sh 使 create_plan 能通过
        reg = self.mock_root / "docs" / "projects" / "registry.yaml"
        reg.parent.mkdir(parents=True, exist_ok=True)
        reg.write_text(
            "schema: ccc-project-registry-v1\nprojects:\n  - prefix: clw\n    id: clw\n    name: clw\n    taskable: true\n    forbidden: false\n    status: active\n"
        )
        val = self.mock_root / "scripts" / "validate-plans.sh"
        val.parent.mkdir(parents=True, exist_ok=True)
        val.write_text("#!/usr/bin/env bash\nexit 0\n")
        val.chmod(0o755)

        create_draft("clw", "真实升级草稿")
        result = promote_draft_to_plan("clw", index=0, author="test", tool="pytest")
        assert result.get("ok") is True
        assert "plan" in result
        assert result["plan"]["id"] is not None
        # 草案已移除
        drafts = list_drafts("clw")
        assert "真实升级草稿" not in [d.title for d in drafts]
        # 033 F1：promote 产出「已确定」（Plan 调研态，非直接已确认）
        plan_path = self.mock_root / result["plan"]["path"]
        assert "状态：已确定" in plan_path.read_text(encoding="utf-8")

    def test_all_voided_milestone_returns_待启动(self) -> None:
        """全作废边界：关联方案全部作废 → 里程碑归「待启动」。"""
        plans_dir = self.mock_root / "docs" / "projects" / "clw" / "plans"
        plans_dir.mkdir(parents=True, exist_ok=True)
        for num, st in [("001", "作废"), ("002", "作废")]:
            (plans_dir / f"{num}-x.md").write_text(
                f"# 方案 · X\n\n> 项目：clw · 编号：clw-plan-{num} · 状态：{st} · 作者：t · 工具：t\n",
                encoding="utf-8",
            )
        create_milestone("clw", "全作废里程碑", status="进行中", linked_plans=["clw-plan-001", "clw-plan-002"])
        result = compute_milestone_progress("clw", "全作废里程碑")
        assert result["total"] == 0
        assert result["status"] == "待启动"

    def test_active_linked_plans_filters_voided(self) -> None:
        """active_linked_plans 过滤作废/已覆盖方案（展示用，保留活跃）。"""
        plans_dir = self.mock_root / "docs" / "projects" / "clw" / "plans"
        plans_dir.mkdir(parents=True, exist_ok=True)
        for num, st in [("001", "作废"), ("002", "已覆盖"), ("003", "已完成")]:
            (plans_dir / f"{num}-x.md").write_text(
                f"# 方案 · X\n\n> 项目：clw · 编号：clw-plan-{num} · 状态：{st} · 作者：t · 工具：t\n",
                encoding="utf-8",
            )
        active = active_linked_plans("clw", ["clw-plan-001", "clw-plan-002", "clw-plan-003", "clw-plan-999"])
        assert "clw-plan-003" in active
        assert "clw-plan-999" in active  # 方案文件不存在 → 保留
        assert "clw-plan-001" not in active
        assert "clw-plan-002" not in active
