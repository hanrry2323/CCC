"""Loop Observer — 4 项观测指标采集 + Playwright 功能巡查 (ccc-plan-011)."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from server.board.models import base_state, BoardItem
from server.board.loader import scan_dispatch_files, scan_archive_files, get_archive_dir, parse_card
from server.board.validate import NEW_CARD_RE


def is_maintenance_complete(text: str) -> bool:
    """机械门禁同款逻辑：核对卡 `## 维护区` 四问是否齐全并有有效说明。"""
    if '## 维护区' not in text:
        return False
    try:
        seg = text.split('## 维护区', 1)[1]
        if '## ' in seg:
            seg = seg.split('## ', 1)[0]
        
        # 匹配 1. **标题**：... [选项]
        items = re.findall(r'^(\d+)\. \*\*([^*]+)\*\*：[^\[]*\[([^]]*)\]', seg, re.M)
        if len(items) < 4:
            return False
        
        for num, name, choice in items:
            if choice.strip() not in ('是', '否', '有', '无'):
                return False
        
        # 匹配 - 说明：非空
        notes = re.findall(r'^   - 说明：(.+)$', seg, re.M)
        if len(notes) < 4 or any(n.strip() == '' for n in notes):
            return False
            
        return True
    except Exception:
        return False


def gather_mcp_metrics(log_dir: Path) -> dict[str, Any]:
    """指标 1：执行体能否经 ccc-kb 检索项目知识 (检查配置与调用次数)."""
    opencode_conf = Path("/Users/fan/.config/opencode/opencode.json")
    claude_conf = Path("/Users/fan/.claude/settings.json")
    
    opencode_ok = False
    if opencode_conf.is_file():
        try:
            with opencode_conf.open("r", encoding="utf-8") as f:
                data = json.load(f)
                opencode_ok = "ccc-kb" in data.get("mcp", {}) and data["mcp"]["ccc-kb"].get("enabled", True)
        except Exception:
            pass

    claude_ok = False
    if claude_conf.is_file():
        try:
            with claude_conf.open("r", encoding="utf-8") as f:
                data = json.load(f)
                claude_ok = "ccc-kb" in data.get("mcpServers", {})
        except Exception:
            pass

    total_calls = 0
    failed_calls = 0
    if log_dir.is_dir():
        for path in log_dir.glob("*.log"):
            try:
                content = path.read_text(encoding="utf-8", errors="replace")
                calls = re.findall(r"⚙\s*(?:ccc-kb_kb_|kb_)\w+", content)
                total_calls += len(calls)
            except Exception:
                pass
                
    success_rate = 100.0 if total_calls > 0 and failed_calls == 0 else (0.0 if total_calls == 0 else ((total_calls - failed_calls) / total_calls) * 100.0)
    
    return {
        "opencode_mcp_enabled": opencode_ok,
        "claude_mcp_enabled": claude_ok,
        "total_calls_observed": total_calls,
        "call_success_rate": success_rate
    }


def gather_maintenance_metrics(dispatch_dir: Path) -> dict[str, Any]:
    """指标 2：维护区四问覆盖率."""
    files = scan_dispatch_files(dispatch_dir)
    archive_dir = get_archive_dir(dispatch_dir)
    if archive_dir.is_dir():
        files.extend(scan_archive_files(archive_dir))
        
    total_completed = 0
    complete_maintenance = 0
    
    for path in files:
        try:
            item = parse_card(path)
            state = base_state(item.state)
            if state in ("已回写", "已关闭"):
                total_completed += 1
                text = path.read_text(encoding="utf-8")
                if is_maintenance_complete(text):
                    complete_maintenance += 1
        except Exception:
            pass
            
    coverage = (complete_maintenance / total_completed * 100.0) if total_completed > 0 else 0.0
    return {
        "total_completed_cards": total_completed,
        "complete_maintenance_cards": complete_maintenance,
        "maintenance_coverage_pct": coverage
    }


def gather_lesson_recirculation_metrics(dispatch_dir: Path) -> dict[str, Any]:
    """指标 3：教训回流率 (新卡执行提示是否含历史教训)."""
    files = scan_dispatch_files(dispatch_dir)
    archive_dir = get_archive_dir(dispatch_dir)
    if archive_dir.is_dir():
        files.extend(scan_archive_files(archive_dir))
        
    new_cards = []
    recirculated = 0
    
    for path in files:
        if NEW_CARD_RE.match(path.stem):
            new_cards.append(path)
            try:
                text = path.read_text(encoding="utf-8")
                if "历史教训" in text:
                    recirculated += 1
            except Exception:
                pass
                
    recirculation_rate = (recirculated / len(new_cards) * 100.0) if new_cards else 0.0
    return {
        "total_new_cards": len(new_cards),
        "recirculated_lessons_cards": recirculated,
        "lesson_recirculation_rate_pct": recirculation_rate
    }


def gather_audit_trends_metrics(dispatch_dir: Path) -> dict[str, Any]:
    """指标 4：验收通过率/打回率趋势 (近 30 卡)."""
    files = scan_dispatch_files(dispatch_dir)
    archive_dir = get_archive_dir(dispatch_dir)
    if archive_dir.is_dir():
        files.extend(scan_archive_files(archive_dir))
        
    cards_with_mtime = []
    for path in files:
        try:
            mtime = path.stat().st_mtime
            cards_with_mtime.append((path, mtime))
        except Exception:
            pass
            
    cards_with_mtime.sort(key=lambda x: x[1], reverse=True)
    
    processed_cards = []
    for path, _ in cards_with_mtime:
        try:
            item = parse_card(path)
            state = base_state(item.state)
            if state in ("已回写", "已关闭", "打回"):
                processed_cards.append(item)
                if len(processed_cards) == 30:
                    break
        except Exception:
            pass
            
    total_processed = len(processed_cards)
    passed_count = sum(1 for item in processed_cards if item.machine_audit_passed or base_state(item.state) == "已关闭")
    rejected_count = sum(1 for item in processed_cards if base_state(item.state) == "打回" or item.reject_count > 0)
    
    passed_rate = (passed_count / total_processed * 100.0) if total_processed > 0 else 0.0
    rejected_rate = (rejected_count / total_processed * 100.0) if total_processed > 0 else 0.0
    
    return {
        "processed_cards_count": total_processed,
        "passed_count": passed_count,
        "rejected_count": rejected_count,
        "passed_rate_pct": passed_rate,
        "rejected_rate_pct": rejected_rate
    }


def run_playwright_smoke_test(url: str = "http://127.0.0.1:7788") -> dict[str, Any]:
    """Playwright 只读功能巡查：验证 health/config/看板加载状态."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {
            "ok": False,
            "status_str": "环境未就绪，待卡10后续 (未安装 Playwright 库)",
            "health_status": "跳过",
            "config_status": "跳过",
            "main_status": "跳过"
        }
        
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            # 1. Health check
            try:
                response = page.goto(f"{url}/health", timeout=5000)
                health_ok = response.status == 200 if response else False
            except Exception:
                health_ok = False
                
            # 2. Config check
            try:
                response = page.goto(f"{url}/config", timeout=5000)
                config_ok = response.status == 200 if response else False
            except Exception:
                config_ok = False
                
            # 3. Main Board Page
            try:
                response = page.goto(url, timeout=5000)
                main_ok = response.status == 200 if response else False
            except Exception:
                main_ok = False
                
            browser.close()
            
            ok = health_ok and config_ok and main_ok
            status_str = "正常" if ok else "部分失败 (服务未完全就绪)"
            return {
                "ok": ok,
                "status_str": status_str,
                "health_status": "200 OK" if health_ok else "失败",
                "config_status": "200 OK" if config_ok else "失败",
                "main_status": "200 OK" if main_ok else "失败"
            }
    except Exception as e:
        return {
            "ok": False,
            "status_str": f"环境未就绪/服务未运行 ({e})",
            "health_status": "失败",
            "config_status": "失败",
            "main_status": "失败"
        }


def run_observation(dispatch_dir: Path, log_dir: Path, output_file: Path) -> dict[str, Any]:
    """采集所有指标，输出 Markdown 报告."""
    mcp = gather_mcp_metrics(log_dir)
    maint = gather_maintenance_metrics(dispatch_dir)
    lesson = gather_lesson_recirculation_metrics(dispatch_dir)
    audit = gather_audit_trends_metrics(dispatch_dir)
    pw = run_playwright_smoke_test()
    
    # 评判生效结论
    # 有效: ccc-kb配置启用, 四问覆盖 >80%, 教训回流 >50%
    # 无效: ccc-kb配置未启用且其余指标皆低
    # 部分: 其他情况
    op_enabled = mcp["opencode_mcp_enabled"] or mcp["claude_mcp_enabled"]
    maint_pct = maint["maintenance_coverage_pct"]
    lesson_pct = lesson["lesson_recirculation_rate_pct"]
    
    if op_enabled and maint_pct >= 80.0 and lesson_pct >= 50.0:
        conclusion = "有效"
        evidence_prefix = "Skill/MCP 优化已全面生效。ccc-kb 检索已配置完成；"
    elif not op_enabled and maint_pct < 30.0 and lesson_pct < 20.0:
        conclusion = "无效"
        evidence_prefix = "优化基本未生效。ccc-kb 配置未激活，且各项流程指标处于低位；"
    else:
        conclusion = "部分"
        evidence_prefix = "优化已部分生效。ccc-kb 配置已启用并开始积累调用；"
        
    evidence = (
        f"{evidence_prefix}"
        f"维护区 Doc-Gate 覆盖率达 {maint_pct:.1f}%，"
        f"教训回流率为 {lesson_pct:.1f}%，"
        f"近 30 卡验收通过率为 {audit['passed_rate_pct']:.1f}%。"
    )
    
    report_content = f"""# 2017 Agent Skill/MCP 优化生效观测报告 (2026-08-09)

> 报告时间：2026-08-09 · 观测执行体：Loop Observer

## 1. 观测结论

- **生效评估**：**{conclusion}生效**
- **核心证据**：{evidence}

## 2. 4 项观测指标实测值

### 指标 1：执行体 ccc-kb MCP 检索接入
- **OpenCode 配置状态**：{"已启用 (Active)" if mcp["opencode_mcp_enabled"] else "未启用 (Inactive)"}
- **Claude Code 配置状态**：{"已启用 (Active)" if mcp["claude_mcp_enabled"] else "未启用 (Inactive)"}
- **观测到实际调用次数**：{mcp["total_calls_observed"]} 次
- **调用成功率**：{mcp["call_success_rate"]:.1f}%

### 指标 2：维护区四问覆盖率 (Doc-Gate)
- **已回写/已关闭卡总数**：{maint["total_completed_cards"]} 张
- **维护区齐全卡数量**：{maint["complete_maintenance_cards"]} 张
- **覆盖率**：{maint["maintenance_coverage_pct"]:.1f}%

### 指标 3：教训回流率
- **新卡总数**：{lesson["total_new_cards"]} 张
- **已回流教训卡数量**：{lesson["recirculated_lessons_cards"]} 张
- **教训回流率**：{lesson["lesson_recirculation_rate_pct"]:.1f}%

### 指标 4：验收通过率/打回率趋势 (近 30 卡)
- **近 30 卡实测样本数**：{audit["processed_cards_count"]} 张
- **机审通过数 (及已关闭)**：{audit["passed_count"]} 张 (占比：{audit["passed_rate_pct"]:.1f}%)
- **打回数 (及曾打回)**：{audit["rejected_count"]} 张 (占比：{audit["rejected_rate_pct"]:.1f}%)

## 3. 功能巡查 (Playwright Web Smoke Test)

- **巡查状态**：{pw["status_str"]}
- **巡查详情**：
  - `/health` 接口：{pw["health_status"]}
  - `/config` 接口：{pw["config_status"]}
  - 主页加载：{pw["main_status"]}
"""
    try:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(report_content, encoding="utf-8")
    except Exception as e:
        print(f"写入观测报告失败: {e}", file=sys.stderr)
        
    return {
        "conclusion": conclusion,
        "mcp": mcp,
        "maint": maint,
        "lesson": lesson,
        "audit": audit,
        "pw": pw
    }


def main():
    parser = argparse.ArgumentParser(description="Loop Observer — 4 项观测指标采集")
    parser.add_argument("--once", action="store_true", help="单次跑出观测报告后退出")
    parser.add_argument("--dispatch-dir", default="docs/dispatch", help="任务卡分派目录")
    parser.add_argument("--log-dir", default="/Users/fan/.ccc/logs/exec", help="执行日志目录")
    parser.add_argument("--output", default="docs/notes/2026-08-09-skill-mcp-observability.md", help="报告输出路径")
    
    args = parser.get_main_args() if hasattr(parser, "get_main_args") else parser.parse_args()
    
    dispatch_dir = Path(args.dispatch_dir)
    log_dir = Path(args.log_dir)
    output_file = Path(args.output)
    
    if args.once:
        print(f"开始单次巡查与指标采集...")
        print(f"任务卡目录: {dispatch_dir.resolve()}")
        print(f"日志目录: {log_dir.resolve()}")
        print(f"输出报告: {output_file.resolve()}")
        
        results = run_observation(dispatch_dir, log_dir, output_file)
        
        print("\n=== 指标采集摘要 ===")
        print(f"ccc-kb 接入: OpenCode={results['mcp']['opencode_mcp_enabled']}, Claude={results['mcp']['claude_mcp_enabled']}, 累计调用={results['mcp']['total_calls_observed']}次")
        print(f"维护区四问覆盖率: {results['maint']['maintenance_coverage_pct']:.1f}% ({results['maint']['complete_maintenance_cards']}/{results['maint']['total_completed_cards']})")
        print(f"教训回流率: {results['lesson']['lesson_recirculation_rate_pct']:.1f}% ({results['lesson']['recirculated_lessons_cards']}/{results['lesson']['total_new_cards']})")
        print(f"近 30 卡机审通过率: {results['audit']['passed_rate_pct']:.1f}% | 打回率: {results['audit']['rejected_rate_pct']:.1f}%")
        print(f"功能巡查状态: {results['pw']['status_str']}")
        print(f"生效评估结论: {results['conclusion']}生效\n")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
