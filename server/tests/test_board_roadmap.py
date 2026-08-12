"""测试 server/board/roadmap.py — 线路图数据模型。"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from server.board.roadmap import (
    Draft,
    Milestone,
    compute_milestone_progress,
    create_draft,
    create_milestone,
    list_drafts,
    list_milestones,
    list_roadmaps,
    parse_roadmap,
    promote_draft,
    update_milestone,
)


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


class TestListRoadmaps:
    def test_list_returns_prefixes(self) -> None:
        rdms = list_roadmaps()
        assert "ccc" in rdms
        assert "clw" in rdms
        assert "hp" in rdms
        assert "qb" in rdms
        assert "mx" in rdms
        assert "xy" in rdms


class TestDraftCRUD:
    def _clean_ccc(self) -> None:
        Path("docs/projects/ccc/roadmap.md").write_text(
            "# CCC 线路图\n\n> 项目：ccc · 更新：2026-08-12\n\n## 草案池\n\n无。\n\n## 里程碑\n\n无。\n",
            encoding="utf-8",
        )

    def test_create_and_list(self) -> None:
        self._clean_ccc()
        create_draft("ccc", "测试草案")
        drafts = list_drafts("ccc")
        titles = [d.title for d in drafts]
        assert "测试草案" in titles

    def test_create_duplicate(self) -> None:
        result = create_draft("ccc", "测试草案")
        assert "error" in result

    def test_promote_draft(self) -> None:
        result = promote_draft("ccc", "测试草案")
        assert result.get("ok") is True
        assert result.get("milestone") == "测试草案"
        # 草案已从草案池移除
        drafts = list_drafts("ccc")
        assert "测试草案" not in [d.title for d in drafts]
        # 里程碑已创建
        mss = list_milestones("ccc")
        assert "测试草案" in [m.title for m in mss]


class TestMilestoneCRUD:
    def _clean_clw(self) -> None:
        """每个测试前重置 clw roadmap，避免测试间残留。"""
        Path("docs/projects/clw/roadmap.md").write_text(
            "# clwarp 线路图\n\n> 项目：clw · 更新：2026-08-12\n\n## 草案池\n\n无。\n\n## 里程碑\n\n无。\n",
            encoding="utf-8",
        )

    def test_create_milestone(self) -> None:
        self._clean_clw()
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
        result = create_milestone("clw", "测试里程碑", status="草案")
        assert "error" in result

    def test_update_milestone(self) -> None:
        result = update_milestone("clw", "测试里程碑", status="进行中")
        assert result.get("ok") is True
        mss = list_milestones("clw")
        found = next(m for m in mss if m.title == "测试里程碑")
        assert found.status == "进行中"

    def test_update_milestone_not_found(self) -> None:
        result = update_milestone("clw", "不存在的里程碑", status="已完成")
        assert "error" in result


class TestComputeProgress:
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


class TestRoundtrip:
    def _clean(self) -> None:
        Path("docs/projects/clw/roadmap.md").write_text(
            "# clwarp 线路图\n\n> 项目：clw · 更新：2026-08-12\n\n## 草案池\n\n无。\n\n## 里程碑\n\n无。\n",
            encoding="utf-8",
        )
        Path("docs/projects/ccc/roadmap.md").write_text(
            """# CCC 线路图

> 项目：ccc · 更新：2026-08-12

## 草案池

无。

## 里程碑

无。
""",
            encoding="utf-8",
        )

    def test_parse_write_parse(self) -> None:
        self._clean()
        # 写
        create_milestone("clw", "循环测试", status="进行中", linked_plans=["clw-plan-001"], description="X")
        create_draft("clw", "新草案")
        # 读
        drafts = list_drafts("clw")
        mss = list_milestones("clw")
        assert "新草案" in [d.title for d in drafts]
        assert "循环测试" in [m.title for m in mss]
        # 清理
        rdms = list_roadmaps()
        assert "clw" in rdms