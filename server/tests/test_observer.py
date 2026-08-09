"""server/tests/test_observer.py — 逆向巡查与交叉验证单元测试 (S5 · 2026-08-09)
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from server.board.registry import ProjectEntry
from server.board.models import BoardItem
from server.engine.observer import run_patrol, write_report


@pytest.fixture
def mock_patrol_data():
    """构造用于测试巡查逻辑的 Mock 数据"""
    # 模拟项目注册表：项目 ccc 是 taskable 并且有 prefix "ccc"
    proj_ccc = ProjectEntry(
        prefix="ccc",
        id="CCC",
        name="CCC",
        display="ccc",
        taskable=True,
        forbidden=False,
        status="active",
        dossier="docs/projects/ccc/README.md",
        role="platform",
        path_m1=None,
        path_mac2017=None,
        location="mac2017-platform",
    )
    # 模拟项目 qb 也是 taskable，其 prefix 为 "qb"
    proj_qb = ProjectEntry(
        prefix="qb",
        id="qb",
        name="qb",
        display="qb",
        taskable=True,
        forbidden=False,
        status="active",
        dossier="docs/projects/qb/README.md",
        role="apps",
        path_m1=None,
        path_mac2017=None,
        location="mac2017-apps",
    )

    # 模拟开发卡
    card_ccc021 = BoardItem(
        id="ccc021",
        title="S8 转卡验收样例",
        state="已关闭",
        project="ccc",
    )

    # 模拟方案
    plan_010 = {
        "id": "ccc-plan-010",
        "project": "ccc",
        "num": "010",
        "slug": "s8",
        "title": "S8 转卡验收样例",
        "status": "部分执行",
        "author": "Claude Code",
        "tool": "pytest",
        "created": "2026-08-09",
        "updated": "2026-08-09",
        "cards": "ccc021",
        "path": "docs/projects/ccc/plans/010-s8.md",
        "acceptance": {"total": 5, "done": 5},
    }

    # 方案 002 已完成但关联卡为无
    plan_002 = {
        "id": "ccc-plan-002",
        "project": "ccc",
        "num": "002",
        "slug": "arch",
        "title": "Arch 方案",
        "status": "已完成",
        "author": "老板",
        "tool": "OpenCode",
        "created": "2026-08-08",
        "updated": "2026-08-08",
        "cards": "无",
        "path": "docs/projects/ccc/plans/002-arch-roadmap-upgrade.md",
        "acceptance": {"total": 1, "done": 1},
    }

    return [proj_ccc, proj_qb], [card_ccc021], [plan_010, plan_002]


def test_observer_patrol_logic(tmp_path, mock_patrol_data):
    """测试巡查与交叉验证核心逻辑"""
    mock_projects, mock_cards, mock_plans = mock_patrol_data

    # 创建必要的测试文件结构
    dispatch_dir = tmp_path / "docs" / "dispatch"
    dispatch_dir.mkdir(parents=True, exist_ok=True)
    
    # 建立 card ccc021 的物理 md 文件，里面故意遗漏 ## 维护区 以制造一个治理一致性异常
    card_file = dispatch_dir / "ccc/ccc021-s8.md"
    card_file.parent.mkdir(parents=True, exist_ok=True)
    card_file.write_text("""# 任务卡 ccc021 · S8 转卡验收样例
> 关联：阶段 3 P1 · 执行体：OpenCode · 状态：已关闭 · 项目：ccc
## 目标
测试目标
""", encoding="utf-8")

    # 创建一个 docs/roadmap.md 以避免缺失路线图警告，并故意不写 qb 规划段落
    roadmap_file = tmp_path / "docs" / "roadmap.md"
    roadmap_file.parent.mkdir(parents=True, exist_ok=True)
    roadmap_file.write_text("""# 发展路线图
## 业务线路（ccc）
| **ccc021** | 标题 | 已合入 |
""", encoding="utf-8")

    # 使用 Mock patch
    with patch("server.engine.observer.load_projects", return_value=tuple(mock_projects)), \
         patch("server.engine.observer.load_dispatch_cards", return_value=mock_cards), \
         patch("server.engine.observer.list_plans", return_value=mock_plans):

        findings = run_patrol(tmp_path)

        # 检查是否成功触发了各个异常
        # 1. 项目 qb 缺失 业务线路 规划段落 (Assertion 1)
        qb_missing = [f for f in findings if f["acting_on"] == "qb" and "缺失对应的 业务线路" in f["msg"]]
        assert len(qb_missing) == 1
        assert qb_missing[0]["severity"] == "YELLOW"

        # 2. 方案 ccc-plan-002 已完成但无关联卡
        plan002_issue = [f for f in findings if f["acting_on"] == "ccc-plan-002" and "没有关联任何开发卡" in f["msg"]]
        assert len(plan002_issue) == 1

        # 3. 交叉验证逻辑：
        # ccc-plan-010 因为关联卡 ccc021 已关闭但自身处于 "部分执行"，
        # 应该同时触发 governance (Assertion 3) 与 reverse (Assertion 3/7)。
        # 由此在 ccc-plan-010 以及 ccc021 上进行交叉确认升为 RED 红旗！
        red_findings = [f for f in findings if f["severity"] == "RED"]
        assert len(red_findings) > 0
        
        # 验证交叉确认标记是否设置
        for f in red_findings:
            assert f["cross_confirm"] == 1.0
            assert "【交叉确认】" in f["msg"]


def test_observer_report_generation(tmp_path):
    """测试巡查报告生成是否合规"""
    findings = [
        {
            "type": "governance",
            "assertion": 3,
            "acting_on": "ccc-plan-010",
            "severity": "RED",
            "msg": "【交叉确认】方案 ccc-plan-010 关联卡已全部关闭，但方案状态仍为 '部分执行'。",
            "evidence": "docs/projects/ccc/plans/010-s8.md:1",
            "cross_confirm": 1.0,
        },
        {
            "type": "reverse",
            "assertion": 3,
            "acting_on": "ccc-plan-002",
            "severity": "YELLOW",
            "msg": "方案 ccc-plan-002 处于已完成状态，但没有关联任何开发卡。",
            "evidence": "docs/projects/ccc/plans/002-arch-roadmap-upgrade.md:1",
            "cross_confirm": 0.0,
        }
    ]

    report_path = write_report(findings, tmp_path)
    assert report_path.exists()
    assert report_path.name == f"{Path(report_path).stem}.md"

    content = report_path.read_text(encoding="utf-8")
    assert "🔴 红旗 1 处" in content
    assert "🟡 黄旗 1 处" in content
    assert "✅ 交叉确认" in content
    assert "ccc-plan-010" in content
