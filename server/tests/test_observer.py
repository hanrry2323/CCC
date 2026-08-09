"""server/tests/test_observer.py — 治理一致性巡查 Agent 测试 (ccc028)"""

from __future__ import annotations

import ast
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from server.engine.observer import run_observer, get_base_state, parse_card_related
from server.board.registry import ProjectEntry
from server.board.models import BoardItem


def test_get_base_state():
    assert get_base_state("已关闭") == "已关闭"
    assert get_base_state("打回（原因）") == "打回"
    assert get_base_state("已回写(有条件)") == "已回写"
    assert get_base_state("未知") == "未知"
    assert get_base_state("") == "未知"


def test_parse_card_related():
    content = """# 任务卡 T1
> 关联：ccc-plan-011 · 执行体：OpenCode
"""
    assert parse_card_related(content) == "ccc-plan-011"
    
    content_no_related = """# 任务卡 T2
> 执行体：OpenCode · 状态：待分派
"""
    assert parse_card_related(content_no_related) == ""


def test_ast_import_whitelist():
    """AST 校验：巡查逻辑只读，禁止 import 写接口 (server.engine.store) 与 plans 的 create/update/convert。"""
    observer_path = Path(__file__).resolve().parents[1] / "engine" / "observer.py"
    assert observer_path.is_file()
    
    tree = ast.parse(observer_path.read_text(encoding="utf-8"))
    
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for name in node.names:
                assert "store" not in name.name
                assert "create" not in name.name
                assert "update" not in name.name
                assert "convert" not in name.name
        elif isinstance(node, ast.ImportFrom):
            assert node.module is not None
            assert "store" not in node.module
            for name in node.names:
                assert "create" not in name.name
                assert "update" not in name.name
                assert "convert" not in name.name


@patch("server.engine.observer.load_projects")
@patch("server.engine.observer.load_dispatch_cards")
@patch("server.engine.observer.list_plans")
@patch("server.engine.observer.scan_dispatch_files")
@patch("server.engine.observer.scan_archive_files")
def test_run_observer_with_drifts(
    mock_scan_archive,
    mock_scan_dispatch,
    mock_list_plans,
    mock_load_dispatch,
    mock_load_projects,
    tmp_path
):
    """验证巡查器对 6 类不一致或断链的真实拦截能力。"""
    # 构造临时 workspace 结构
    repo_root = tmp_path
    
    # Mock projects
    mock_load_projects.return_value = (
        ProjectEntry(
            prefix="xy", id="xianyu", name="xianyu", display="xianyu",
            taskable=True, forbidden=False, status="active", dossier=None,
            role="business", path_m1=None, path_mac2017=None
        ),
        ProjectEntry(
            prefix="qb", id="qb", name="qb", display="qb",
            taskable=True, forbidden=False, status="active", dossier=None,
            role="test", path_m1=None, path_mac2017=None
        )
    )
    
    # Mock plans: xy-plan-001 已完成，但关联的 xy001 未关闭
    # xy-plan-002 关联了不存在的卡 xy002
    mock_list_plans.return_value = [
        {
            "id": "xy-plan-001",
            "project": "xy",
            "status": "已完成",
            "cards": "xy001",
            "path": "docs/projects/xy/plans/001-video.md"
        },
        {
            "id": "xy-plan-002",
            "project": "xy",
            "status": "部分执行",
            "cards": "xy002",
            "path": "docs/projects/xy/plans/002-empty.md"
        }
    ]
    
    # Mock dispatch cards:
    # xy001 状态为 已回写 (未关闭)
    # qb001 状态为 已关闭，但缺失 ## 维护区
    mock_load_dispatch.return_value = [
        BoardItem(
            id="xy001", title="test card", state="已回写", project="xy",
            executor="opencode", dispatched_at="2026-08-09"
        ),
        BoardItem(
            id="qb001", title="test card qb", state="已关闭", project="qb",
            executor="opencode", dispatched_at="2026-08-09"
        )
    ]
    
    # 模拟真实文件写入
    docs_dir = repo_root / "docs"
    dispatch_dir = docs_dir / "dispatch"
    notes_dir = docs_dir / "notes"
    
    dispatch_dir.mkdir(parents=True, exist_ok=True)
    notes_dir.mkdir(parents=True, exist_ok=True)
    
    # xy001 card file with invalid/descriptions in 关联 field
    xy001_file = dispatch_dir / "xy001-test.md"
    xy001_file.write_text("""# 任务卡 xy001 · test card
> 关联：阶段 3 P1 · 状态：已回写 · 项目：xy · 日期：2026-08-09
""", encoding="utf-8")

    # qb001 card file with valid plan ref but missing ## 维护区
    qb001_file = dispatch_dir / "qb001-test.md"
    qb001_file.write_text("""# 任务卡 qb001 · test card qb
> 关联：qb-plan-001 · 状态：已关闭 · 项目：qb · 日期：2026-08-09
""", encoding="utf-8")

    # Mock file scanners to return our temporary files
    mock_scan_dispatch.return_value = [xy001_file, qb001_file]
    mock_scan_archive.return_value = []
    
    # 写入 docs/roadmap.md:
    # 1. 缺失 业务线路（qb）段落
    # 2. 故意制造 xy001 状态漂移 (roadmap 写 已关闭, 实际 xy001 是 已回写)
    roadmap_file = docs_dir / "roadmap.md"
    roadmap_file.write_text("""# CCC Roadmap
## 业务线路（xy）
| **xy001** | test | 已关闭 |
""", encoding="utf-8")

    # 4. 执行巡查
    with patch("server.engine.observer.Path") as mock_path:
        # 劫持 Path 使其定位到我们的临时目录
        def side_effect(*args, **kwargs):
            p = Path(*args, **kwargs)
            # 替换 repo_root / docs 等
            if "server/engine/observer.py" in str(p):
                return p
            # 如果是相对 repo_root 的，转换成 temp_path 的对应子路径
            if str(p).startswith("/Users/fan/program") or "ccc-dev-ws" in str(p):
                # 提取相对 docs/... 的部分
                parts = p.parts
                if "docs" in parts:
                    idx = parts.index("docs")
                    return repo_root / Path(*parts[idx:])
            return p
            
        mock_path.side_effect = side_effect
        mock_path.resolve = lambda: repo_root
        
        ok, summary = run_observer({"REPO_ROOT": str(repo_root)})
        
    assert ok is True
    assert summary["findings_count"] > 0
    assert summary["red_flags"] > 0
    assert summary["yellow_flags"] > 0
    assert summary["blue_flags"] > 0
    
    # 确认报告文件已生成且内容包含风险条目
    reports = list(notes_dir.glob("*-ccc-patrol.md"))
    assert len(reports) == 1
    report_content = reports[0].read_text(encoding="utf-8")
    
    # 检查报告中的主要发现
    assert "业务线路（qb）" in report_content  # 1. 业务线路缺失
    assert "xy001" in report_content           # 2. 状态漂移 / 方案未关闭卡
    assert "xy-plan-002" in report_content     # 3. 关联不存在的卡
    assert "qb001" in report_content           # 4. 维护区缺失
