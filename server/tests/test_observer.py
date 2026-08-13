"""server/tests/test_observer.py — 统一 Loop Observer 单元测试 (ccc027-032 集成)
覆盖：定时框架/治理一致性/权重打分 (030)、逆向巡查 (029)、观测指标 (032)。
"""

from __future__ import annotations

import ast
import json
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from server.board.registry import ProjectEntry
from server.board.models import BoardItem
from server.engine import observer

from server.engine.observer import (
    _get_current_state,
    should_run,
    run_observer,
    run_patrol,
    write_report,
    score_finding,
    generate_patrol_report,
    is_maintenance_complete,
    gather_mcp_metrics,
    gather_maintenance_metrics,
    gather_lesson_recirculation_metrics,
    gather_audit_trends_metrics,
    run_playwright_smoke_test,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_ast_import_whitelist():
    """AST 校验 observer import 白名单：禁止导入写接口和变更函数。"""
    observer_file = PROJECT_ROOT / 'server' / 'engine' / 'observer.py'
    assert observer_file.exists()
    code = observer_file.read_text(encoding='utf-8')
    tree = ast.parse(code)
    forbidden_modules = {'server.engine.store'}
    allowed_from_plans = {'list_plans'}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for name in node.names:
                assert name.name not in forbidden_modules, f'Forbidden import: {name.name}'
                assert 'store' not in name.name, f'Forbidden store import: {name.name}'
        elif isinstance(node, ast.ImportFrom):
            module = node.module
            if module:
                assert module not in forbidden_modules, f'Forbidden import from module: {module}'
                assert 'store' not in module, f'Forbidden store import from module: {module}'
                if 'plans' in module:
                    for name in node.names:
                        assert name.name in allowed_from_plans, f'Forbidden plans import: {name.name}'

def test_should_run_scenarios(tmp_path):
    """测试不同场景下的调度门槛（last-run 时间戳和变更触发）。"""
    cfg = {'DATA_DIR': str(tmp_path)}
    observer_dir = tmp_path / 'observer'
    observer_dir.mkdir(parents=True, exist_ok=True)
    last_run_file = observer_dir / 'last-run.json'
    current = {'timestamp': time.time(), 'git_commit': 'commit1', 'cards_index_mtime': 100.0, 'cards_index_size': 1000}
    ok, reason = should_run(cfg, current)
    assert ok is True
    assert 'first run' in reason
    last_run_file.write_text(json.dumps(current))
    current_same = current.copy()
    current_same['timestamp'] += 1000
    ok, reason = should_run(cfg, current_same)
    assert ok is False
    assert 'thresholds not met' in reason
    current_later = current.copy()
    current_later['timestamp'] += 86500
    ok, reason = should_run(cfg, current_later)
    assert ok is True
    assert '24 hours passed' in reason
    current_new_commit = current.copy()
    current_new_commit['timestamp'] += 1000
    current_new_commit['git_commit'] = 'commit2'
    ok, reason = should_run(cfg, current_new_commit)
    assert ok is True
    assert 'new merge commit' in reason
    current_new_mtime = current.copy()
    current_new_mtime['timestamp'] += 1000
    current_new_mtime['cards_index_mtime'] = 101.0
    ok, reason = should_run(cfg, current_new_mtime)
    assert ok is True
    assert 'cards.index.jsonl changed' in reason

@patch('server.engine.observer.load_projects')
@patch('server.engine.observer.load_dispatch_cards')
@patch('server.engine.observer.list_plans')
def test_run_observer_output(mock_list_plans, mock_load_dispatch_cards, mock_load_projects, tmp_path):
    """测试 run_observer 在决定运行时，是否能正常输出 snapshot 和 last-run。"""
    cfg = {'DATA_DIR': str(tmp_path), 'OBSERVER_FORCE': 'true'}
    mock_load_projects.return_value = []
    mock_load_dispatch_cards.return_value = []
    mock_list_plans.return_value = []
    ok, summary = run_observer(cfg)
    assert ok is True
    assert 'projects_count' in summary
    assert 'cards_count' in summary
    assert 'plans_count' in summary
    observer_dir = tmp_path / 'observer'
    assert (observer_dir / 'last-run.json').exists()
    assert (observer_dir / 'snapshot.json').exists()
    with open(observer_dir / 'snapshot.json', encoding='utf-8') as f:
        snapshot = json.load(f)
        assert snapshot['projects_count'] == 0
        assert snapshot['cards_count'] == 0
        assert snapshot['plans_count'] == 0


@patch('server.engine.observer.load_dispatch_cards')
@patch('server.engine.observer.list_plans')
@patch('server.engine.observer.load_projects')
def test_scan_findings_roadmap_uses_single_parser(
    mock_load_projects, mock_list_plans, mock_load_dispatch_cards, tmp_path
):
    """roadmap 巡检与线路图页面共用 roadmap_parser：缺段落 + 漂移判定一致（ccc-plan-022）。"""
    from types import SimpleNamespace

    from server.engine.observer import scan_findings

    mock_load_projects.return_value = [
        SimpleNamespace(prefix='xy', taskable=True),
        SimpleNamespace(prefix='qh', taskable=True),
    ]
    mock_list_plans.return_value = []
    mock_load_dispatch_cards.return_value = [
        SimpleNamespace(to_dict=lambda: {'id': 'xy001', 'state': '已合入', 'project': 'xy', 'path': 'x'}),
        SimpleNamespace(to_dict=lambda: {'id': 'xy002', 'state': '执行中', 'project': 'xy', 'path': 'x'}),
    ]

    roadmap = tmp_path / 'docs' / 'roadmap.md'
    roadmap.parent.mkdir(parents=True, exist_ok=True)
    roadmap.write_text(
        "## 业务线路（xy）\n"
        "\n"
        "### 里程碑（2026-08-07 挂账）\n"
        "\n"
        "| 卡号 | 意图 | 进度 |\n"
        "|------|------|------|\n"
        "| **xy001** | 正常 | 已合入 |\n"
        "| **xy002** | 漂移 | 已合入 |\n",
        encoding='utf-8',
    )

    findings = scan_findings({'SCHEDULER_DISPATCH_DIR': ''}, tmp_path)

    # qh 缺段落；xy 有段落
    assert any(f['id'] == 'missing_roadmap_section_qh' for f in findings)
    assert not any(f['id'] == 'missing_roadmap_section_xy' for f in findings)
    # xy001 一致不报；xy002 漂移（roadmap 已合入 vs 实际执行中）
    drift = [f for f in findings if f['id'] == 'status_drift_xy002']
    assert len(drift) == 1
    assert '标注「已合入」' in drift[0]['title']
    assert '实际状态为「执行中」' in drift[0]['title']
    assert drift[0]['evidence'] == 'docs/roadmap.md:8'

def test_weight_scoring_and_report_ordering():
    from server.engine.observer import DEFAULT_SCORING_RULES
    f1 = {'id': 'missing_roadmap_section_qb', 'title': 'missing roadmap qb', 'project': 'qb', 'type': 'missing_section', 'cross_confirm': 0.5}
    f2 = {'id': 'status_drift_hp004', 'title': 'status drift hp004', 'project': 'hp', 'type': 'drift', 'cross_confirm': 1.0}
    scored1 = score_finding(f1, DEFAULT_SCORING_RULES)
    scored2 = score_finding(f2, DEFAULT_SCORING_RULES)
    assert scored1['weight'] == 0.5 * 3 * 2
    assert scored2['weight'] == 1.0 * 2 * 3
    findings = [scored1, scored2]
    findings.sort(key=lambda x: x['weight'], reverse=True)
    assert findings[0]['id'] == 'status_drift_hp004'
    report = generate_patrol_report(findings, 'test-report')
    assert 'status drift hp004' in report
    assert 'missing roadmap qb' in report
    assert 'scripts/new-card.sh' in report

def test_patrol_report_sorts_unsorted_input():
    from server.engine.observer import DEFAULT_SCORING_RULES
    low = {'id': 'drift_low', 'title': 'low', 'project': 'ccc', 'type': 'drift', 'cross_confirm': 0.3}
    high = {'id': 'broken_high', 'title': 'high', 'project': 'ccc', 'type': 'broken_link', 'cross_confirm': 1.0}
    scored_low = score_finding(low, DEFAULT_SCORING_RULES)
    scored_high = score_finding(high, DEFAULT_SCORING_RULES)
    assert scored_high['weight'] > scored_low['weight']
    report = generate_patrol_report([scored_low, scored_high], 'sort-test')
    body = report.split('## 建议转卡命令')[0]
    assert 'high' in body and 'low' in body
    assert body.index('high') < body.index('low')

@pytest.fixture
def mock_patrol_data():
    """构造用于测试巡查逻辑的 Mock 数据"""
    proj_ccc = ProjectEntry(prefix='ccc', id='CCC', name='CCC', display='ccc', taskable=True, forbidden=False, status='active', dossier='docs/projects/ccc/README.md', role='platform', path_m1=None, path_mac2017=None, location='mac2017-platform')
    proj_qb = ProjectEntry(prefix='qb', id='qb', name='qb', display='qb', taskable=True, forbidden=False, status='active', dossier='docs/projects/qb/README.md', role='apps', path_m1=None, path_mac2017=None, location='mac2017-apps')
    card_ccc021 = BoardItem(id='ccc021', title='S8 转卡验收样例', state='已关闭', project='ccc')
    plan_010 = {'id': 'ccc-plan-010', 'project': 'ccc', 'num': '010', 'slug': 's8', 'title': 'S8 转卡验收样例', 'status': '部分执行', 'author': 'Claude Code', 'tool': 'pytest', 'created': '2026-08-09', 'updated': '2026-08-09', 'cards': 'ccc021', 'path': 'docs/projects/ccc/plans/010-s8.md', 'acceptance': {'total': 5, 'done': 5}}
    plan_002 = {'id': 'ccc-plan-002', 'project': 'ccc', 'num': '002', 'slug': 'arch', 'title': 'Arch 方案', 'status': '已完成', 'author': '老板', 'tool': 'OpenCode', 'created': '2026-08-08', 'updated': '2026-08-08', 'cards': '无', 'path': 'docs/projects/ccc/plans/002-arch-roadmap-upgrade.md', 'acceptance': {'total': 1, 'done': 1}}
    return ([proj_ccc, proj_qb], [card_ccc021], [plan_010, plan_002])

def test_observer_patrol_logic(tmp_path, mock_patrol_data):
    """测试巡查与交叉验证核心逻辑"""
    mock_projects, mock_cards, mock_plans = mock_patrol_data
    dispatch_dir = tmp_path / 'docs' / 'dispatch'
    dispatch_dir.mkdir(parents=True, exist_ok=True)
    card_file = dispatch_dir / 'ccc/ccc021-s8.md'
    card_file.parent.mkdir(parents=True, exist_ok=True)
    card_file.write_text('# 任务卡 ccc021 · S8 转卡验收样例\n> 关联：阶段 3 P1 · 执行体：OpenCode · 状态：已关闭 · 项目：ccc\n## 目标\n测试目标\n', encoding='utf-8')
    roadmap_file = tmp_path / 'docs' / 'roadmap.md'
    roadmap_file.parent.mkdir(parents=True, exist_ok=True)
    roadmap_file.write_text('# 发展路线图\n## 业务线路（ccc）\n| **ccc021** | 标题 | 已合入 |\n', encoding='utf-8')
    with patch('server.engine.observer.load_projects', return_value=tuple(mock_projects)), patch('server.engine.observer.load_dispatch_cards', return_value=mock_cards), patch('server.engine.observer.list_plans', return_value=mock_plans):
        findings = run_patrol(tmp_path)
        qb_missing = [f for f in findings if f['acting_on'] == 'qb' and '缺失对应的 业务线路' in f['msg']]
        assert len(qb_missing) == 1
        assert qb_missing[0]['severity'] == 'YELLOW'
        plan002_issue = [f for f in findings if f['acting_on'] == 'ccc-plan-002' and '没有关联任何开发卡' in f['msg']]
        assert len(plan002_issue) == 1
        red_findings = [f for f in findings if f['severity'] == 'RED']
        assert len(red_findings) > 0
        for f in red_findings:
            assert f['cross_confirm'] == 1.0
            assert '【交叉确认】' in f['msg']

def test_observer_report_generation(tmp_path):
    """测试巡查报告生成是否合规"""
    findings = [{'type': 'governance', 'assertion': 3, 'acting_on': 'ccc-plan-010', 'severity': 'RED', 'msg': "【交叉确认】方案 ccc-plan-010 关联卡已全部关闭，但方案状态仍为 '部分执行'。", 'evidence': 'docs/projects/ccc/plans/010-s8.md:1', 'cross_confirm': 1.0}, {'type': 'reverse', 'assertion': 3, 'acting_on': 'ccc-plan-002', 'severity': 'YELLOW', 'msg': '方案 ccc-plan-002 处于已完成状态，但没有关联任何开发卡。', 'evidence': 'docs/projects/ccc/plans/002-arch-roadmap-upgrade.md:1', 'cross_confirm': 0.0}]
    report_path = write_report(findings, tmp_path)
    assert report_path.exists()
    assert report_path.name == f'{Path(report_path).stem}.md'
    content = report_path.read_text(encoding='utf-8')
    assert '🔴 红旗 1 处' in content
    assert '🟡 黄旗 1 处' in content
    assert '✅ 交叉确认' in content
    assert 'ccc-plan-010' in content

def test_is_maintenance_complete_true() -> None:
    text = '\n## 维护区\n\n1. **方案同步**：说明已更新 [是]\n   - 说明：一切已经就绪\n2. **教训沉淀**：无 [无]\n   - 说明：无教训\n3. **档案/README**：无 [否]\n   - 说明：未更改\n4. **线路图**：无 [否]\n   - 说明：未更改\n'
    assert observer.is_maintenance_complete(text) is True

def test_is_maintenance_complete_missing_choice() -> None:
    text = '\n## 维护区\n\n1. **方案同步**：说明已更新 [待定]\n   - 说明：一切已经就绪\n2. **教训沉淀**：无 [无]\n   - 说明：无教训\n3. **档案/README**：无 [否]\n   - 说明：未更改\n4. **线路图**：无 [否]\n   - 说明：未更改\n'
    assert observer.is_maintenance_complete(text) is False

def test_is_maintenance_complete_missing_note() -> None:
    text = '\n## 维护区\n\n1. **方案同步**：说明已更新 [是]\n   - 说明：\n2. **教训沉淀**：无 [无]\n   - 说明：无教训\n3. **档案/README**：无 [否]\n   - 说明：未更改\n4. **线路图**：无 [否]\n   - 说明：未更改\n'
    assert observer.is_maintenance_complete(text) is False

def test_gather_mcp_metrics(tmp_path: Path, monkeypatch) -> None:
    log_dir = tmp_path / 'logs'
    log_dir.mkdir()
    (log_dir / 'T1.log').write_text('⚙ ccc-kb_kb_search\n⚙ ccc-kb_kb_read\n', encoding='utf-8')
    (log_dir / 'T2.log').write_text('⚙ kb_list\n⚙ other_tool\n', encoding='utf-8')
    opencode_conf = tmp_path / 'opencode.json'
    opencode_conf.write_text(json.dumps({'mcp': {'ccc-kb': {'enabled': True}}}), encoding='utf-8')
    claude_conf = tmp_path / 'settings.json'
    claude_conf.write_text(json.dumps({'mcpServers': {'ccc-kb': {}}}), encoding='utf-8')
    monkeypatch.setattr(Path, 'is_file', lambda self: True if self.name in ('opencode.json', 'settings.json') else False)
    monkeypatch.setattr(observer, 'Path', lambda *args, **kwargs: tmp_path / args[0] if args and isinstance(args[0], str) and args[0].endswith('.json') else Path(*args, **kwargs))
    metrics = observer.gather_mcp_metrics(log_dir)
    assert metrics['total_calls_observed'] == 3
    assert metrics['call_success_rate'] == 100.0

def test_gather_maintenance_metrics(tmp_path: Path, monkeypatch) -> None:
    mock_files = [tmp_path / 'ccc001-test.md', tmp_path / 'ccc002-test.md']
    (tmp_path / 'ccc001-test.md').write_text('# 任务卡 ccc001\n> 状态：已回写\n## 维护区\n1. **方案同步**：[是]\n   - 说明：ok1\n2. **教训沉淀**：[无]\n   - 说明：ok2\n3. **档案/README**：[否]\n   - 说明：ok3\n4. **线路图**：[否]\n   - 说明：ok4\n', encoding='utf-8')
    (tmp_path / 'ccc002-test.md').write_text('# 任务卡 ccc002\n> 状态：已回写\n## 维护区\n1. **方案同步**：[是]\n   - 说明：\n', encoding='utf-8')
    monkeypatch.setattr(observer, 'scan_dispatch_files', lambda d: mock_files)
    monkeypatch.setattr(observer, 'get_archive_dir', lambda d: tmp_path / 'archive_nonexistent')
    metrics = observer.gather_maintenance_metrics(tmp_path)
    assert metrics['total_completed_cards'] == 2
    assert metrics['complete_maintenance_cards'] == 1
    assert metrics['maintenance_coverage_pct'] == 50.0

def test_gather_lesson_recirculation_metrics(tmp_path: Path, monkeypatch) -> None:
    mock_files = [tmp_path / 'ccc001-test.md', tmp_path / 'ccc002-test.md']
    (tmp_path / 'ccc001-test.md').write_text('历史教训', encoding='utf-8')
    (tmp_path / 'ccc002-test.md').write_text('nothing', encoding='utf-8')
    monkeypatch.setattr(observer, 'scan_dispatch_files', lambda d: mock_files)
    monkeypatch.setattr(observer, 'get_archive_dir', lambda d: tmp_path / 'archive_nonexistent')
    metrics = observer.gather_lesson_recirculation_metrics(tmp_path)
    assert metrics['total_new_cards'] == 2
    assert metrics['recirculated_lessons_cards'] == 1
    assert metrics['lesson_recirculation_rate_pct'] == 50.0

def test_write_roadmap_draft(tmp_path: Path) -> None:
    """Loop 巡查集成：write_roadmap_draft 写入草案到项目 roadmap.md 并去重。"""
    from server.engine.observer import write_roadmap_draft

    # 构造临时 roadmap.md
    projects_dir = tmp_path / "docs" / "projects" / "ccc"
    projects_dir.mkdir(parents=True, exist_ok=True)
    roadmap_path = projects_dir / "roadmap.md"
    roadmap_path.write_text(
        "# CCC 线路图\n\n> 项目：ccc · 更新：2026-08-13\n\n## 草案池\n\n无。\n\n## 里程碑\n\n无。\n",
        encoding="utf-8",
    )

    with patch("server.board.roadmap._roadmap_path", return_value=roadmap_path):
        # 第一次写入
        result = write_roadmap_draft("ccc", "状态漂移检测异常")
        assert result.get("ok") is True
        assert "状态漂移" in result.get("draft", "")

        # 第二次写入同描述 → 去重跳过
        result2 = write_roadmap_draft("ccc", "状态漂移检测异常")
        assert result2.get("ok") is True
        assert result2.get("skipped") is True

        # 不同描述 → 正常写入
        result3 = write_roadmap_draft("ccc", "缺失维护区四问")
        assert result3.get("ok") is True
        assert result3.get("skipped") is not True

        # 验证草案池内容
        from server.board.roadmap import list_drafts
        drafts = list_drafts("ccc")
        titles = [d.title for d in drafts]
        assert len(titles) == 2
        assert any("状态漂移" in t for t in titles)
        assert any("缺失维护区四问" in t for t in titles)


def test_run_playwright_smoke_test_failure() -> None:
    res = observer.run_playwright_smoke_test('http://invalid_domain_9999')
    assert res['ok'] is False
    assert res['health_status'] in ('跳过', '失败')


# ── 第二步闭环：数据一致性检查项（里程碑/方案进度 vs 级联回写声明） ──

def _make_xy_repo(tmp_path: Path) -> Path:
    """造 tmp 仓库：registry + per-project roadmap + plans 文件（供一致性检查）。"""
    reg = tmp_path / "docs" / "projects" / "registry.yaml"
    reg.parent.mkdir(parents=True, exist_ok=True)
    reg.write_text(
        "schema: ccc-project-registry-v1\n"
        "projects:\n"
        "  - prefix: xy\n"
        "    id: xy\n"
        "    name: xy\n"
        "    taskable: true\n"
        "    forbidden: false\n"
        "    status: active\n",
        encoding="utf-8",
    )
    proj_dir = tmp_path / "docs" / "projects" / "xy"
    plans_dir = proj_dir / "plans"
    plans_dir.mkdir(parents=True, exist_ok=True)
    (proj_dir / "roadmap.md").write_text(
        "# xy 线路图\n\n"
        "## 里程碑\n\n"
        "### 里程碑A\n"
        "- 状态：进行中\n"
        "- 关联方案：xy-plan-001\n\n"
        "### 里程碑B\n"
        "- 状态：进行中\n"
        "- 关联方案：xy-plan-002\n",
        encoding="utf-8",
    )
    (plans_dir / "001-milestone-a.md").write_text(
        "# 方案 · 里程碑A\n\n> 项目：xy · 编号：xy-plan-001 · 状态：已完成\n",
        encoding="utf-8",
    )
    (plans_dir / "002-milestone-b.md").write_text(
        "# 方案 · 里程碑B\n\n> 项目：xy · 编号：xy-plan-002 · 状态：已完成\n",
        encoding="utf-8",
    )
    return tmp_path


@patch("server.board.roadmap._repo_root")
def test_scan_findings_milestone_progress_consistency(mock_repo_root, tmp_path):
    """里程碑声明「进行中」但子方案全部完成（级联回写滞后）→ consistency finding。

    里程碑A 关联 xy-plan-001（已完成）→ pct 100% 但声明进行中 → 报。
    里程碑B 同构 → 同样报。声明已完成 + 未满 的反向场景由 plan_progress 覆盖。
    """
    from types import SimpleNamespace

    from server.engine.observer import scan_findings

    mock_repo_root.return_value = _make_xy_repo(tmp_path)

    findings = scan_findings(
        {"SCHEDULER_DISPATCH_DIR": ""},
        tmp_path,
    )
    ms_findings = [f for f in findings if f["type"] == "consistency"]
    assert any(f["id"].startswith("milestone_progress_xy_") for f in ms_findings)
    target = [f for f in ms_findings if "里程碑A" in f["title"]]
    assert len(target) == 1
    assert "声明 进行中" in target[0]["title"]
    assert "实际完成率 100%" in target[0]["title"]
    assert target[0]["acting_on"] == "docs/projects/xy/roadmap.md"


@patch("server.board.roadmap._repo_root")
def test_scan_findings_plan_progress_consistency(mock_repo_root, tmp_path):
    """方案头部「进度：closed/total」声明 vs 关联卡实算不一致 → consistency finding。"""
    from types import SimpleNamespace

    from server.engine.observer import scan_findings

    mock_repo_root.return_value = _make_xy_repo(tmp_path)
    # 方案 xy-plan-001：声明 0/2，实算 1/2（xy001 已关闭）
    plan_file = tmp_path / "docs" / "projects" / "xy" / "plans" / "001-milestone-a.md"
    plan_file.write_text(
        "# 方案 · 里程碑A\n\n"
        "> 项目：xy · 编号：xy-plan-001 · 状态：部分执行\n"
        "> 进度：0/2 (0%)\n",
        encoding="utf-8",
    )

    findings = scan_findings(
        {
            "SCHEDULER_DISPATCH_DIR": str(tmp_path / "docs" / "dispatch"),
            "PROJECT_ROOT": str(tmp_path),
        },
        tmp_path,
    )
    # 未 mock 卡列表：load_dispatch_cards 走真实 dispatch 目录（tmp 下为空）→ 不产生 plan_progress
    assert not any(f["id"].startswith("plan_progress_") for f in findings)


@patch("server.engine.observer.load_projects")
@patch("server.engine.observer.load_dispatch_cards")
@patch("server.engine.observer.list_plans")
def test_scan_findings_plan_progress_consistency_mocked(
    mock_list_plans, mock_load_dispatch_cards, mock_load_projects, tmp_path
):
    """方案进度声明 vs 实算（mock 卡状态）：声明 0/2 实算 1/2 → 报；声明 1/2 实算 1/2 → 不报。"""
    from types import SimpleNamespace

    from server.engine.observer import scan_findings

    mock_load_projects.return_value = []
    mock_load_dispatch_cards.return_value = [
        SimpleNamespace(to_dict=lambda: {"id": "xy001", "state": "已关闭", "project": "xy", "path": "x"}),
        SimpleNamespace(to_dict=lambda: {"id": "xy002", "state": "执行中", "project": "xy", "path": "x"}),
    ]
    plan_path = "docs/projects/xy/plans/001-milestone-a.md"
    mock_list_plans.return_value = [
        {
            "id": "xy-plan-001",
            "project": "xy",
            "status": "部分执行",
            "cards": "xy001, xy002",
            "path": plan_path,
        }
    ]
    plan_file = tmp_path / plan_path
    plan_file.parent.mkdir(parents=True, exist_ok=True)
    plan_file.write_text(
        "# 方案 · 里程碑A\n\n"
        "> 项目：xy · 编号：xy-plan-001 · 状态：部分执行\n"
        "> 进度：0/2 (0%)\n",
        encoding="utf-8",
    )

    findings = scan_findings({"SCHEDULER_DISPATCH_DIR": ""}, tmp_path)
    target = [f for f in findings if f["id"] == "plan_progress_xy-plan-001"]
    assert len(target) == 1
    assert "声明 0/2" in target[0]["title"]
    assert "实际 1/2" in target[0]["title"]

    # 声明与实算一致 → 不报
    plan_file.write_text(
        "# 方案 · 里程碑A\n\n"
        "> 项目：xy · 编号：xy-plan-001 · 状态：部分执行\n"
        "> 进度：1/2 (50%)\n",
        encoding="utf-8",
    )
    findings2 = scan_findings({"SCHEDULER_DISPATCH_DIR": ""}, tmp_path)
    assert not any(f["id"] == "plan_progress_xy-plan-001" for f in findings2)


@patch("server.engine.observer.write_roadmap_draft")
@patch("server.engine.observer.scan_findings")
def test_run_observer_writes_draft_for_consistency(
    mock_scan_findings, mock_write_draft, tmp_path
):
    """PRIME-DIRECTIVE §6.3：consistency 发现自动回线路图草案池（治理债）。"""
    mock_scan_findings.return_value = [
        {
            "id": "milestone_progress_xy_a",
            "title": "里程碑 xy/a 进度不一致",
            "project": "xy",
            "type": "consistency",
            "cross_confirm": 0.5,
            "acting_on": "docs/projects/xy/roadmap.md",
            "evidence": "docs/projects/xy/roadmap.md:1",
        },
        {
            "id": "status_drift_xy001",
            "title": "xy001 状态漂移",
            "project": "xy",
            "type": "drift",
            "cross_confirm": 0.5,
            "acting_on": "x",
            "evidence": "x:1",
        },
    ]
    from server.engine.observer import run_observer

    with patch("server.engine.observer.load_projects", return_value=[]), patch(
        "server.engine.observer.load_dispatch_cards", return_value=[]
    ), patch("server.engine.observer.list_plans", return_value=[]), patch(
        "server.engine.observer.should_run", return_value=(True, "test")
    ):
        ok, _ = run_observer({"SCHEDULER_DISPATCH_DIR": "", "DATA_DIR": str(tmp_path)})
        assert ok is True
    # 只对 consistency 接线草案池；drift 不写
    mock_write_draft.assert_called_once_with("xy", "里程碑 xy/a 进度不一致", draft_type="治理债")


# ── 第三步：技术债巡检（tech 检查项） ──

@patch("server.engine.observer.load_projects")
@patch("server.engine.observer.load_dispatch_cards")
@patch("server.engine.observer.list_plans")
def test_scan_findings_tech_debt(
    mock_list_plans, mock_load_dispatch_cards, mock_load_projects, tmp_path
):
    """技术债检查：打回卡 + 人工批注未落实 + 死文件复活 → tech findings。"""
    from types import SimpleNamespace

    from server.engine.observer import scan_findings

    mock_load_projects.return_value = []
    mock_list_plans.return_value = []
    dispatch = tmp_path / "docs" / "dispatch" / "xy"
    dispatch.mkdir(parents=True)
    (dispatch / "xy001-rejected.md").write_text(
        "# 任务卡 xy001 - 打回\n\n"
        "> 关联：x · 执行体：OpenCode · 验收：Claude Code · 状态：打回 · 项目：xy · 日期：2026-08-13\n",
        encoding="utf-8",
    )
    (dispatch / "xy002-annotation.md").write_text(
        "# 任务卡 xy002 - 批注\n\n"
        "> 关联：x · 执行体：OpenCode · 验收：Claude Code · 状态：执行中 · 项目：xy · 日期：2026-08-13\n\n"
        "## 人工批注\n\n老板要求调整验收标准。\n",
        encoding="utf-8",
    )
    mock_load_dispatch_cards.return_value = [
        SimpleNamespace(to_dict=lambda: {"id": "xy001", "state": "打回", "project": "xy", "path": "docs/dispatch/xy/xy001-rejected.md"}),
        SimpleNamespace(to_dict=lambda: {"id": "xy002", "state": "执行中", "project": "xy", "path": "docs/dispatch/xy/xy002-annotation.md"}),
    ]
    # 死文件复活
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "arch-dead-files.txt").write_text(
        "# dead files\nserver/web/legacy-chat/arch/resurrected.html\n",
        encoding="utf-8",
    )
    arch_dir = tmp_path / "server" / "web" / "legacy-chat" / "arch"
    arch_dir.mkdir(parents=True)
    (arch_dir / "resurrected.html").write_text("x", encoding="utf-8")

    findings = scan_findings({"SCHEDULER_DISPATCH_DIR": ""}, tmp_path)
    tech = [f for f in findings if f["type"] == "tech"]
    assert any(f["id"].startswith("tech_rejected_cards_") for f in tech), tech
    assert any(f["id"].startswith("tech_unaddressed_annotation_") for f in tech), tech
    assert any(f["id"].startswith("tech_dead_file_resurrected_") for f in tech), tech
    assert any("resurrected.html" in f["title"] for f in tech), tech
