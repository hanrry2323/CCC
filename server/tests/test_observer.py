"""测试：observer 观测指标采集功能 (test_observer.py)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from server.engine import observer


def test_is_maintenance_complete_true() -> None:
    text = """
## 维护区

1. **方案同步**：说明已更新 [是]
   - 说明：一切已经就绪
2. **教训沉淀**：无 [无]
   - 说明：无教训
3. **档案/README**：无 [否]
   - 说明：未更改
4. **线路图**：无 [否]
   - 说明：未更改
"""
    assert observer.is_maintenance_complete(text) is True


def test_is_maintenance_complete_missing_choice() -> None:
    text = """
## 维护区

1. **方案同步**：说明已更新 [待定]
   - 说明：一切已经就绪
2. **教训沉淀**：无 [无]
   - 说明：无教训
3. **档案/README**：无 [否]
   - 说明：未更改
4. **线路图**：无 [否]
   - 说明：未更改
"""
    assert observer.is_maintenance_complete(text) is False


def test_is_maintenance_complete_missing_note() -> None:
    text = """
## 维护区

1. **方案同步**：说明已更新 [是]
   - 说明：
2. **教训沉淀**：无 [无]
   - 说明：无教训
3. **档案/README**：无 [否]
   - 说明：未更改
4. **线路图**：无 [否]
   - 说明：未更改
"""
    assert observer.is_maintenance_complete(text) is False


def test_gather_mcp_metrics(tmp_path: Path, monkeypatch) -> None:
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    
    # 模拟日志调用
    (log_dir / "T1.log").write_text("⚙ ccc-kb_kb_search\n⚙ ccc-kb_kb_read\n", encoding="utf-8")
    (log_dir / "T2.log").write_text("⚙ kb_list\n⚙ other_tool\n", encoding="utf-8")
    
    # Mock configs
    opencode_conf = tmp_path / "opencode.json"
    opencode_conf.write_text(json.dumps({"mcp": {"ccc-kb": {"enabled": True}}}), encoding="utf-8")
    
    claude_conf = tmp_path / "settings.json"
    claude_conf.write_text(json.dumps({"mcpServers": {"ccc-kb": {}}}), encoding="utf-8")
    
    monkeypatch.setattr(Path, "is_file", lambda self: True if self.name in ("opencode.json", "settings.json") else False)
    # Redirect global path inside functions
    monkeypatch.setattr(observer, "Path", lambda *args, **kwargs: tmp_path / args[0] if args and isinstance(args[0], str) and args[0].endswith(".json") else Path(*args, **kwargs))
    
    metrics = observer.gather_mcp_metrics(log_dir)
    assert metrics["total_calls_observed"] == 3
    assert metrics["call_success_rate"] == 100.0


def test_gather_maintenance_metrics(tmp_path: Path, monkeypatch) -> None:
    # We will test scan_dispatch_files with mocks or monkeypatch
    mock_files = [tmp_path / "ccc001-test.md", tmp_path / "ccc002-test.md"]
    (tmp_path / "ccc001-test.md").write_text("""# 任务卡 ccc001
> 状态：已回写
## 维护区
1. **方案同步**：[是]
   - 说明：ok1
2. **教训沉淀**：[无]
   - 说明：ok2
3. **档案/README**：[否]
   - 说明：ok3
4. **线路图**：[否]
   - 说明：ok4
""", encoding="utf-8")
    
    (tmp_path / "ccc002-test.md").write_text("""# 任务卡 ccc002
> 状态：已回写
## 维护区
1. **方案同步**：[是]
   - 说明：
""", encoding="utf-8")
    
    monkeypatch.setattr(observer, "scan_dispatch_files", lambda d: mock_files)
    monkeypatch.setattr(observer, "get_archive_dir", lambda d: tmp_path / "archive_nonexistent")
    
    metrics = observer.gather_maintenance_metrics(tmp_path)
    assert metrics["total_completed_cards"] == 2
    assert metrics["complete_maintenance_cards"] == 1
    assert metrics["maintenance_coverage_pct"] == 50.0


def test_gather_lesson_recirculation_metrics(tmp_path: Path, monkeypatch) -> None:
    mock_files = [tmp_path / "ccc001-test.md", tmp_path / "ccc002-test.md"]
    (tmp_path / "ccc001-test.md").write_text("历史教训", encoding="utf-8")
    (tmp_path / "ccc002-test.md").write_text("nothing", encoding="utf-8")
    
    monkeypatch.setattr(observer, "scan_dispatch_files", lambda d: mock_files)
    monkeypatch.setattr(observer, "get_archive_dir", lambda d: tmp_path / "archive_nonexistent")
    
    metrics = observer.gather_lesson_recirculation_metrics(tmp_path)
    assert metrics["total_new_cards"] == 2
    assert metrics["recirculated_lessons_cards"] == 1
    assert metrics["lesson_recirculation_rate_pct"] == 50.0


def test_run_playwright_smoke_test_failure() -> None:
    # 依赖环境：未安装 Playwright 库 → ImportError 分支返回「跳过」（环境未就绪，不阻塞）；
    # 库已安装但服务/域名不可达 → 运行失败返回「失败」。
    # 两种情况下 ok 均为 False，真实不变量是巡查未通过。
    res = observer.run_playwright_smoke_test("http://invalid_domain_9999")
    assert res["ok"] is False
    assert res["health_status"] in ("跳过", "失败")
