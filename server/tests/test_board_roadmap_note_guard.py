"""测试 server/board/roadmap.py 子项目状态同步的「人工合入注记」守卫。

背景（2026-09-13 裁定 T1 · 卡 xy075）：`_sync_subproject_statuses` 按关联方案状态重算子项目时，
把卡级人工合入注记（如「已完成（xy060 合入）」，xy071 权威回填）降回「计划中」——写盘不 commit →
主树周期脏 → phase2 fail-closed 晾卡（xy073 实锤）。语义裁定：人工合入注记 > 方案级推算。

用例（判别测试，改码前跑 A 必红）：
- A 现值「已完成（xy060 合入）」+ 方案「部分执行」→ 注记不被降档（修复目标，改前必红）
- B 现值「计划中」+ 方案「已完成」→ 升级「已完成」（升级路径不被守卫误伤，两态应绿）
- C 现值「已完成（xy060 合入）」+ 方案「已完成」→ 保持已完成态（幂等）
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from server.board.roadmap import list_milestones, sync_milestone_progress


PLAN_REL = "docs/projects/xy/plans/009-frontend-showcase.md"


def _setup_xy(mock_root: Path, sp_status: str, plan_status: str) -> Path:
    """写临时 xy 仓：M6 线路图（单子项目，状态由参数给定）+ 方案 xy-plan-009 头部。"""
    projects_dir = mock_root / "docs" / "projects" / "xy"
    (projects_dir / "plans").mkdir(parents=True, exist_ok=True)
    roadmap = projects_dir / "roadmap.md"
    roadmap.write_text(
        f"""# xianyu 线路图
> 项目：xy · 更新：2026-09-13

## 草案池

无。

## 里程碑

### M6 · 前端展示台
- 状态：执行中
- 关联方案：xy-plan-009
- 子项目：
  - 6.1 内容库 API · 状态：{sp_status} · 方案：xy-plan-009
""",
        encoding="utf-8",
    )
    (projects_dir / "plans" / "009-frontend-showcase.md").write_text(
        f"""# 方案 · 前端展示台（M6）

> 项目：xy · 编号：xy-plan-009 · 状态：{plan_status} · 作者：x · 工具：pytest
> 创建：2026-08-20 · 更新：2026-09-13

## 目标

x
""",
        encoding="utf-8",
    )
    return roadmap


def _sp_status(mock_root: Path) -> str:
    return list_milestones("xy")[0].subprojects[0].status


@pytest.fixture()
def xy_repo(tmp_path: Path):
    """临时 xy 仓根（mock _repo_root），与既有 roadmap 往返测试同一隔离风格。"""
    mock_root = tmp_path / "repo"
    (mock_root / "docs" / "projects" / "xy").mkdir(parents=True, exist_ok=True)
    patcher = patch("server.board.roadmap._repo_root", return_value=mock_root)
    patcher.start()
    yield mock_root
    patcher.stop()


def test_note_survives_plan_partial(xy_repo: Path) -> None:
    """用例 A：现值带人工合入注记 + 方案「部分执行」→ 注记不被方案级降档（改码前必红）。

    方案部分执行时 target=计划中，修复前会把「已完成（xy060 合入）」改写成「计划中」并写盘
    （主树周期脏根因）。守卫后：内存状态与磁盘行都保持原注记。
    """
    roadmap = _setup_xy(xy_repo, sp_status="已完成（xy060 合入）", plan_status="部分执行")
    r = sync_milestone_progress("xy", PLAN_REL)
    assert r.get("ok") is True

    assert _sp_status(xy_repo) == "已完成（xy060 合入）", _sp_status(xy_repo)
    # 磁盘行保持原样（不得被降档写脏）
    on_disk = roadmap.read_text(encoding="utf-8")
    assert "状态：已完成（xy060 合入）" in on_disk
    assert "状态：计划中" not in on_disk


def test_planned_upgrades_when_plan_done(xy_repo: Path) -> None:
    """用例 B：现值「计划中」+ 方案「已完成」→ 升级「已完成」（升级路径不被守卫误伤）。"""
    _setup_xy(xy_repo, sp_status="计划中", plan_status="已完成")
    r = sync_milestone_progress("xy", PLAN_REL)
    assert r.get("ok") is True

    assert _sp_status(xy_repo) == "已完成", _sp_status(xy_repo)


def test_note_idempotent_when_plan_done(xy_repo: Path) -> None:
    """用例 C：现值带合入注记 + 方案「已完成」→ 保持已完成态（幂等，无降级）。"""
    _setup_xy(xy_repo, sp_status="已完成（xy060 合入）", plan_status="已完成")
    r = sync_milestone_progress("xy", PLAN_REL)
    assert r.get("ok") is True

    assert _sp_status(xy_repo).startswith("已完成"), _sp_status(xy_repo)
    # 幂等：连续同步不再变化
    _sp_status(xy_repo)
    before = _sp_status(xy_repo)
    sync_milestone_progress("xy", PLAN_REL)
    assert _sp_status(xy_repo) == before
