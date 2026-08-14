"""测试 server/board/roadmap.py — 线路图数据模型。"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from server.board.roadmap import (
    Draft,
    Milestone,
    compute_milestone_progress,
    create_draft,
    create_milestone,
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
