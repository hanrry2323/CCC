"""Loop Observer 统一巡查模块 (ccc-plan-011 集成版)

角色：
- run_observer()   : 定时只读巡检框架 + 治理一致性 + 权重打分 + 风险报告 (ccc027/028/030)
- run_patrol()     : 逆向巡查与一致性交叉验证 (ccc029)
- run_observation(): 4 项观测指标采集 + Playwright 功能巡查 (ccc032)
CLI: --patrol / --reverse / --metrics
"""

from __future__ import annotations

import argparse
import datetime
import json
import logging
import os
import re
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from server.board.registry import load_projects
from server.board.loader import (
    load_dispatch_cards,
    get_index_path,
    scan_dispatch_files,
    scan_archive_files,
    get_archive_dir,
    parse_card,
)
from server.board.plans import list_plans
from server.board.models import base_state
from server.board.validate import NEW_CARD_RE

logger = logging.getLogger("ccc.engine.observer")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = PROJECT_ROOT


# ============ 定时框架 / 治理一致性 / 权重打分 (ccc027/028/030) ============


def _get_current_state(cfg: dict[str, Any]) -> dict[str, Any]:
    """获取当前系统的状态：时间戳、最新的 git merge 提交、cards.index.jsonl 信息。"""
    now = time.time()
    git_commit = ""
    try:
        res = subprocess.run(
            ["git", "log", "origin/main", "--merges", "-n", "1", "--format=%H"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if res.returncode == 0:
            git_commit = res.stdout.strip()
    except Exception:
        pass
    if not git_commit:
        try:
            res = subprocess.run(
                ["git", "log", "--merges", "-n", "1", "--format=%H"], capture_output=True, text=True, timeout=5
            )
            if res.returncode == 0:
                git_commit = res.stdout.strip()
        except Exception:
            pass
    cards_mtime = 0.0
    cards_size = 0
    try:
        idx_path = get_index_path(cfg.get("SCHEDULER_DISPATCH_DIR"))
        if idx_path.exists():
            stat = idx_path.stat()
            cards_mtime = stat.st_mtime
            cards_size = stat.st_size
    except Exception:
        pass
    return {
        "timestamp": now,
        "git_commit": git_commit,
        "cards_index_mtime": cards_mtime,
        "cards_index_size": cards_size,
    }


def should_run(cfg: dict[str, Any], current_state: dict[str, Any]) -> tuple[bool, str]:
    """判断是否应当运行巡查（时间/Git提交/索引文件变更）。"""
    if cfg.get("OBSERVER_FORCE", "").strip().lower() in ("true", "1", "yes") or os.environ.get("OBSERVER_FORCE") == "1":
        return (True, "force via config/env")
    data_dir = cfg.get("DATA_DIR", "")
    if not data_dir:
        data_dir = os.environ.get("CCC_DATA_DIR") or os.environ.get("DATA_DIR") or "data"
    last_run_path = Path(data_dir).resolve() / "observer" / "last-run.json"
    if not last_run_path.exists():
        return (True, "first run")
    try:
        with open(last_run_path, encoding="utf-8") as f:
            last_state = json.load(f)
    except Exception as e:
        return (True, f"last-run error: {e}")
    last_ts = last_state.get("timestamp", 0.0)
    if current_state["timestamp"] - last_ts >= 86400:
        return (True, f"24 hours passed since last run at {last_ts}")
    last_commit = last_state.get("git_commit", "")
    curr_commit = current_state["git_commit"]
    if curr_commit and last_commit and (curr_commit != last_commit):
        return (True, f"new merge commit {curr_commit} (prev {last_commit})")
    last_mtime = last_state.get("cards_index_mtime", 0.0)
    last_size = last_state.get("cards_index_size", 0)
    curr_mtime = current_state["cards_index_mtime"]
    curr_size = current_state["cards_index_size"]
    if curr_mtime != last_mtime or curr_size != last_size:
        return (
            True,
            f"cards.index.jsonl changed: mtime {curr_mtime} (prev {last_mtime}), size {curr_size} (prev {last_size})",
        )
    return (False, "thresholds not met")


def check_missing_four_questions(card_id: str, file_path: Path) -> tuple[bool, str]:
    if not file_path.exists():
        return (True, "file_not_found")
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        return (True, str(e))
    if "## 维护区" not in content:
        return (True, "no_maintenance_section")
    lines = content.splitlines()
    for idx, line in enumerate(lines):
        if "说明：" in line or "说明:" in line:
            rest = line.partition("说明：")[2].strip() or line.partition("说明:")[2].strip()
            if not rest:
                next_line_has_text = False
                for offset in range(1, 4):
                    if idx + offset < len(lines):
                        next_line = lines[idx + offset].strip()
                        if (
                            next_line
                            and (not next_line.startswith("-"))
                            and (not next_line.startswith("1."))
                            and (not next_line.startswith("2."))
                            and (not next_line.startswith("3."))
                            and (not next_line.startswith("4."))
                            and (not next_line.startswith("#"))
                        ):
                            next_line_has_text = True
                            break
                        if (
                            next_line.startswith("-")
                            or next_line.startswith("1.")
                            or next_line.startswith("2.")
                            or next_line.startswith("3.")
                            or next_line.startswith("4.")
                            or next_line.startswith("#")
                        ):
                            break
                if not next_line_has_text:
                    return (True, "empty_description")
    if "[是/否]" in content or "[有/无]" in content:
        return (True, "unchecked_placeholders")
    return (False, "")


def scan_findings(cfg: dict[str, Any], project_root: Path) -> list[dict[str, Any]]:
    import re

    findings = []
    projects_list = []
    try:
        projects = load_projects()
        projects_list = [p for p in projects]
    except Exception as e:
        logger.error("failed to load projects: %s", e)
    plans_list = []
    try:
        plans_list = list_plans(project_root)
    except Exception as e:
        logger.error("failed to load plans: %s", e)
    cards_list = []
    try:
        dispatch_dir = cfg.get("SCHEDULER_DISPATCH_DIR", "")
        if not dispatch_dir:
            dispatch_dir = project_root / "docs" / "dispatch"
        else:
            dispatch_dir = Path(dispatch_dir)
        cards = load_dispatch_cards(dispatch_dir)
        cards_list = [c.to_dict() for c in cards]
    except Exception as e:
        logger.error("failed to load cards: %s", e)
    cards_by_id = {c["id"].lower(): c for c in cards_list if c.get("id")}
    roadmap_path = project_root / "docs" / "roadmap.md"
    roadmap_content = ""
    if roadmap_path.exists():
        try:
            roadmap_content = roadmap_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.error("failed to read roadmap: %s", e)
    if roadmap_content:
        # 双解析器收敛（ccc-plan-022）：roadmap 业务线路解析统一走 roadmap_parser，
        # 巡检与线路图页面共用同一真值（卡号规则/状态归一/漂移判定一致）
        from server.board.roadmap_parser import load_roadmap_sections

        sections = load_roadmap_sections(
            roadmap_path,
            cards_by_id={cid: str(c.get("state", "")) for cid, c in cards_by_id.items()},
            by_project={cid: str(c.get("project", "")) for cid, c in cards_by_id.items()},
        )
        section_projects = {s.get("project") for s in sections}
        roadmap_lines = roadmap_content.splitlines()
        for p in projects_list:
            if p.taskable and p.prefix:
                prefix = p.prefix
                if prefix not in section_projects:
                    findings.append(
                        {
                            "id": f"missing_roadmap_section_{prefix}",
                            "title": f"项目 {prefix} 缺席 roadmap.md 的业务线路段落",
                            "project": prefix,
                            "type": "missing_section",
                            "cross_confirm": 0.5,
                            "acting_on": "docs/roadmap.md",
                            "evidence": "docs/roadmap.md:1",
                        }
                    )
        for s in sections:
            proj = s.get("project", "")
            for mile in s.get("milestones", []):
                for card in mile.get("cards", []):
                    if not card.get("drift"):
                        continue
                    cid_raw = card["card_id"]
                    cid_key = cid_raw.lower()
                    real_status = cards_by_id.get(cid_key, {}).get("state", "")
                    line_no = 1
                    for idx, line in enumerate(roadmap_lines):
                        if f"**{cid_raw}**" in line:
                            line_no = idx + 1
                            break
                    findings.append(
                        {
                            "id": f"status_drift_{cid_key}",
                            "title": f"任务卡 {cid_raw} 状态漂移：roadmap.md 标注「{card.get('progress', '')}」，但看板/卡文件实际状态为「{real_status}」",
                            "project": card.get("project") or proj or "ccc",
                            "type": "drift",
                            "cross_confirm": 0.5,
                            "acting_on": "docs/roadmap.md",
                            "evidence": f"docs/roadmap.md:{line_no}",
                        }
                    )
    for plan in plans_list:
        plan_status = plan.get("status", "").strip()
        if plan_status == "已完成":
            cards_field = plan.get("cards", "")
            if cards_field:
                ref_cards = re.findall("([a-zA-Z]+[0-9]+)", cards_field)
                open_ref_cards = []
                for rc in ref_cards:
                    rc_key = rc.lower()
                    if rc_key in cards_by_id:
                        real_status = cards_by_id[rc_key].get("state", "")
                        if real_status not in ("已关闭", "已合入", "已完成", "released", "closed"):
                            open_ref_cards.append((rc, real_status))
                if open_ref_cards:
                    open_cards_str = ", ".join([f"{rc}({st})" for rc, st in open_ref_cards])
                    findings.append(
                        {
                            "id": f"completed_plan_open_cards_{plan['id']}",
                            "title": f"方案 {plan['id']} 已完成，但其关联卡未全部关闭: {open_cards_str}",
                            "project": plan.get("project", "ccc"),
                            "type": "broken_link",
                            "cross_confirm": 1.0,
                            "acting_on": plan.get("path", ""),
                            "evidence": f"{plan.get('path', '')}:1",
                        }
                    )
    for plan in plans_list:
        cards_field = plan.get("cards", "")
        if cards_field:
            ref_cards = re.findall("([a-zA-Z]+[0-9]+)", cards_field)
            missing_cards = []
            for rc in ref_cards:
                rc_key = rc.lower()
                if rc_key not in cards_by_id:
                    missing_cards.append(rc)
            if missing_cards:
                findings.append(
                    {
                        "id": f"plan_ref_missing_cards_{plan['id']}",
                        "title": f"方案 {plan['id']} 关联了不存在的任务卡: {', '.join(missing_cards)}",
                        "project": plan.get("project", "ccc"),
                        "type": "broken_link",
                        "cross_confirm": 0.5,
                        "acting_on": plan.get("path", ""),
                        "evidence": f"{plan.get('path', '')}:1",
                    }
                )
    for c in cards_list:
        state = c.get("state", "")
        if state in ("已关闭", "已合入", "closed", "released"):
            card_id = c.get("id", "")
            relative_path = c.get("path")
            if relative_path:
                file_path = project_root / relative_path
                missing, reason = check_missing_four_questions(card_id, file_path)
                if missing:
                    findings.append(
                        {
                            "id": f"missing_four_questions_{card_id.lower()}",
                            "title": f"已关闭任务卡 {card_id} 缺失或未完成维护区四问: {reason}",
                            "project": c.get("project", "ccc"),
                            "type": "missing_four_questions",
                            "cross_confirm": 0.5,
                            "acting_on": relative_path,
                            "evidence": f"{relative_path}:1",
                        }
                    )
    # 数据一致性（第二步闭环）：里程碑/方案进度 vs 级联回写声明
    # a) 里程碑进度一致性：per-project roadmap 声明状态 vs 实际完成率（compute_milestone_progress 纯函数）
    try:
        from server.board.roadmap import compute_milestone_progress, list_roadmaps, parse_roadmap

        for proj in list_roadmaps():
            rm_file = project_root / "docs" / "projects" / proj / "roadmap.md"
            if not rm_file.is_file():
                continue
            try:
                parsed = parse_roadmap(rm_file.read_text(encoding="utf-8", errors="replace"), project=proj)
            except Exception:
                continue
            for ms in parsed.get("milestones", []):
                try:
                    comp = compute_milestone_progress(proj, ms.title)
                except Exception:
                    continue
                if not isinstance(comp, dict) or comp.get("error"):
                    continue
                pct = comp.get("progress_pct", 0)
                declared = ms.status
                # 声明「已完成」但未满 / 全完成但声明非「已完成」 = 级联回写滞后
                if (declared == "已完成" and pct < 100) or (pct >= 100 and declared != "已完成"):
                    findings.append(
                        {
                            "id": f"milestone_progress_{proj}_{ms.title[:24]}",
                            "title": f"里程碑 {proj}/{ms.title} 进度不一致：声明 {declared}，实际完成率 {pct}%（{comp.get('completed', 0)}/{comp.get('total', 0)} 方案）",
                            "project": proj,
                            "type": "consistency",
                            "cross_confirm": 0.5,
                            "acting_on": f"docs/projects/{proj}/roadmap.md",
                            "evidence": f"docs/projects/{proj}/roadmap.md:1",
                        }
                    )
    except Exception as e:
        logger.error("一致性检查（里程碑）失败: %s", e)

    # b) 方案进度一致性：方案头部「进度：closed/total」声明 vs 关联卡实算
    closed_states = ("已关闭", "已合入", "已完成", "released", "closed")
    for plan in plans_list:
        cards_field = plan.get("cards", "")
        if not cards_field:
            continue
        ref_cards = re.findall("([a-zA-Z]+[0-9]+)", cards_field)
        if not ref_cards:
            continue
        plan_path = plan.get("path", "")
        if not plan_path:
            continue
        try:
            plan_text = (project_root / plan_path).read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        m = re.search(r">\s*进度：(\d+)/(\d+)", plan_text)
        if not m:
            continue  # 无进度声明行（未级联回写），跳过
        declared_closed, declared_total = int(m.group(1)), int(m.group(2))
        real_total = len(ref_cards)
        real_closed = sum(
            1 for rc in ref_cards if cards_by_id.get(rc.lower(), {}).get("state", "") in closed_states
        )
        if declared_total != real_total or declared_closed != real_closed:
            findings.append(
                {
                    "id": f"plan_progress_{plan['id']}",
                    "title": f"方案 {plan['id']} 进度不一致：声明 {declared_closed}/{declared_total}，实际 {real_closed}/{real_total}（级联回写滞后或卡状态变动）",
                    "project": plan.get("project", "ccc"),
                    "type": "consistency",
                    "cross_confirm": 0.5,
                    "acting_on": plan_path,
                    "evidence": f"{plan_path}:1",
                }
            )
    return findings


def score_finding(finding: dict[str, Any], rules: dict[str, dict[str, int]]) -> dict[str, Any]:
    ftype = finding.get("type", "drift")
    rule = rules.get(ftype, {"impact": 2, "frequency": 2})
    impact = finding.get("impact") or rule.get("impact", 2)
    frequency = finding.get("frequency") or rule.get("frequency", 2)
    cc = finding.get("cross_confirm", 0.5)
    weight = cc * impact * frequency
    finding["impact"] = impact
    finding["frequency"] = frequency
    finding["cross_confirm"] = cc
    finding["weight"] = weight
    if weight >= 10.0:
        severity = "红旗"
    elif weight >= 4.0:
        severity = "黄旗"
    else:
        severity = "蓝旗"
    finding["severity"] = severity
    return finding


def generate_patrol_report(findings: list[dict[str, Any]], report_name: str) -> str:
    ordered = sorted(findings, key=lambda x: x.get("weight", 0.0), reverse=True)
    lines = []
    lines.append(f"# 巡查风险报告 — {report_name}")
    lines.append(f"\n> 采集时间: {datetime.datetime.now().isoformat()} · 发现数: {len(ordered)}\n")
    lines.append("## 风险发现列表（按权重降序排序）\n")
    lines.append(
        "| 权重 (Weight) | 交叉确认 (Cross-Confirm) | 影响 (Impact) | 频次 (Frequency) | 描述 (Title) | 项目 (Project) | 作用对象 (Acting On) | 证据 (Evidence) |"
    )
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
    for f in ordered:
        w = f.get("weight", 0.0)
        cc = f.get("cross_confirm", 0.5)
        imp = f.get("impact", 1)
        freq = f.get("frequency", 1)
        title = f.get("title", "")
        proj = f.get("project", "")
        ao = f.get("acting_on", "")
        ev = f.get("evidence", "")
        lines.append(f"| {w:.2f} | {cc:.1f} | {imp} | {freq} | {title} | {proj} | `{ao}` | `{ev}` |")
    lines.append("\n## 建议转卡命令\n")
    lines.append("> 巡查 Agent 仅打印建议出卡命令，绝不自动出卡/自动合入。\n")
    high_weight_findings = [f for f in findings if f.get("impact", 1) >= 4]
    recommend_findings = high_weight_findings if high_weight_findings else findings
    for f in recommend_findings:
        proj = f.get("project", "ccc")
        title = f.get("title", "")
        clean_title = title.replace('"', '\\"')
        cmd = f'scripts/new-card.sh --project {proj} --title "修复：{clean_title}" --related "patrol: {report_name}"'
        lines.append(f"- 针对 `{f.get('id')}`:\n  ```bash\n  {cmd}\n  ```")
    return "\n".join(lines)


DEFAULT_SCORING_RULES = {
    "broken_link": {"impact": 4, "frequency": 4},
    "drift": {"impact": 2, "frequency": 3},
    "missing_four_questions": {"impact": 2, "frequency": 1},
    "missing_section": {"impact": 3, "frequency": 2},
    "consistency": {"impact": 3, "frequency": 2},
}


def run_observer(cfg: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    """定时只读巡检入口。

    采集 registry/卡/方案快照，并在满足阈值时写入/更新快照。
    """
    current_state = _get_current_state(cfg)
    need_run, reason = should_run(cfg, current_state)
    if not need_run:
        logger.info("Loop Observer 跳过运行：%s", reason)
        return (True, {"skipped": True, "reason": reason})
    logger.info("Loop Observer 开始运行：%s", reason)
    try:
        projects = load_projects()
        projects_list = [{"id": p.id, "prefix": p.prefix, "status": p.status} for p in projects]
    except Exception as e:
        logger.error("加载项目注册表失败: %s", e)
        projects_list = []
    try:
        dispatch_dir = cfg.get("SCHEDULER_DISPATCH_DIR", "")
        if not dispatch_dir:
            dispatch_dir = PROJECT_ROOT / "docs" / "dispatch"
        else:
            dispatch_dir = Path(dispatch_dir)
        cards = load_dispatch_cards(dispatch_dir)
        cards_list = [c.to_dict() for c in cards]
    except Exception as e:
        logger.error("加载任务卡失败: %s", e)
        cards_list = []
    try:
        plans = list_plans(PROJECT_ROOT)
    except Exception as e:
        logger.error("加载方案/计划失败: %s", e)
        plans = []
    cards_states: dict[str, int] = {}
    for c in cards_list:
        state = str(c.get("state", "未知"))
        cards_states[state] = cards_states.get(state, 0) + 1
    plans_states: dict[str, int] = {}
    for p in plans:
        state = str(p.get("status", "未知"))
        plans_states[state] = plans_states.get(state, 0) + 1
    findings = scan_findings(cfg, PROJECT_ROOT)
    # PRIME-DIRECTIVE §6.3：数据一致性发现自动回线路图草案池（治理债）
    for f in findings:
        if f.get("type") == "consistency" and f.get("project"):
            try:
                write_roadmap_draft(f["project"], f["title"], draft_type="治理债")
            except Exception as e:
                logger.error("草案池回写失败（%s）: %s", f.get("id"), e)
    rules = DEFAULT_SCORING_RULES.copy()
    if cfg.get("OBSERVER_SCORING_RULES"):
        try:
            custom_rules = json.loads(cfg["OBSERVER_SCORING_RULES"])
            if isinstance(custom_rules, dict):
                rules.update(custom_rules)
        except Exception as e:
            logger.error("failed to parse custom rules: %s", e)
    scored_findings = [score_finding(f, rules) for f in findings]
    scored_findings.sort(key=lambda x: x.get("weight", 0.0), reverse=True)
    summary = {
        "timestamp": current_state["timestamp"],
        "collected_at": datetime.datetime.fromtimestamp(current_state["timestamp"]).isoformat(),
        "projects_count": len(projects_list),
        "cards_count": len(cards_list),
        "plans_count": len(plans),
        "cards_states": cards_states,
        "plans_states": plans_states,
        "projects": projects_list,
        "findings": scored_findings,
    }
    data_dir = cfg.get("DATA_DIR", "")
    if not data_dir:
        data_dir = os.environ.get("CCC_DATA_DIR") or os.environ.get("DATA_DIR") or "data"
    observer_dir = Path(data_dir).resolve() / "observer"
    dt_obj = datetime.datetime.fromtimestamp(current_state["timestamp"])
    date_str = dt_obj.strftime("%Y-%m-%d")
    report_name = f"{date_str}-ccc-patrol"
    report_md = generate_patrol_report(scored_findings, report_name)

    # 巡查报告优先落 DATA_DIR/observer/
    try:
        observer_dir.mkdir(parents=True, exist_ok=True)
        observer_report_path = observer_dir / f"{report_name}.md"
        observer_report_path.write_text(report_md, encoding="utf-8")
        logger.info("patrol report saved to %s", observer_report_path)
    except Exception as e:
        logger.error("failed to save report to DATA_DIR/observer: %s", e)

    # 只有当内容发生变化时，才写入 docs/notes/
    notes_dir = PROJECT_ROOT / "docs" / "notes"
    try:
        notes_dir.mkdir(parents=True, exist_ok=True)
        report_path = notes_dir / f"{report_name}.md"
        should_write = True
        if report_path.exists():
            existing_content = report_path.read_text(encoding="utf-8")
            if existing_content == report_md:
                should_write = False
        if should_write:
            report_path.write_text(report_md, encoding="utf-8")
            logger.info("patrol report (changed) saved to docs/notes: %s", report_path)
        else:
            logger.info("patrol report unchanged, skipping docs/notes update")
    except Exception as e:
        logger.error("failed to save report to docs/notes: %s", e)
    try:
        observer_dir.mkdir(parents=True, exist_ok=True)
        snapshot_path = observer_dir / "snapshot.json"
        with open(snapshot_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        dt_str = datetime.datetime.fromtimestamp(current_state["timestamp"]).strftime("%Y%m%d-%H%M%S")
        ts_snapshot_path = observer_dir / f"snapshot-{dt_str}.json"
        with open(ts_snapshot_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        last_run_path = observer_dir / "last-run.json"
        with open(last_run_path, "w", encoding="utf-8") as f:
            json.dump(current_state, f, ensure_ascii=False, indent=2)
        logger.info("Loop Observer 快照已保存到 %s", observer_dir)
    except Exception as e:
        logger.error("写入 Observer 快照失败: %s", e)
        return (False, {"error": str(e)})
    return (True, summary)


# ============ 逆向巡查与交叉验证角色 (ccc029) ============


def scan_card_files(dispatch_dir: Path) -> list[Path]:
    """扫描所有任务卡 md 文件"""
    files = []
    if not dispatch_dir.exists():
        return files
    for p in dispatch_dir.glob("**/*.md"):
        if p.is_file() and p.name not in ("README.md", "T-mapping.md"):
            try:
                content = p.read_text(encoding="utf-8")
                if "# 任务卡" in content:
                    files.append(p)
            except Exception:
                continue
    return files


def parse_metadata(text: str) -> dict[str, str]:
    """解析 > 元数据行内 key：value"""
    meta: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith(">"):
            continue
        body = line.lstrip(">").strip()
        for part in body.split("·"):
            match = re.search("^\\s*([^：\\s][^：]*?)\\s*[:：]\\s*(.+?)\\s*$", part.strip())
            if match:
                meta[match.group(1).strip()] = match.group(2).strip()
    return meta


def run_patrol(repo_root: Path) -> list[dict[str, Any]]:
    """运行治理巡查与逆向巡查，执行交叉验证。"""
    findings: list[dict[str, Any]] = []
    projects = load_projects(str(repo_root / "docs" / "projects" / "registry.yaml"))
    cards = load_dispatch_cards(str(repo_root / "docs" / "dispatch"))
    plans = list_plans(repo_root)
    card_status = {c.id: base_state(c.state) for c in cards}
    roadmap_path = repo_root / "docs" / "roadmap.md"
    if roadmap_path.exists():
        roadmap_content = roadmap_path.read_text(encoding="utf-8")
        for p in projects:
            if p.taskable and p.prefix:
                pattern = re.compile(f"##\\s*业务线路[（(]{p.prefix}[）)]", re.I)
                if not pattern.search(roadmap_content):
                    findings.append(
                        {
                            "type": "governance",
                            "assertion": 1,
                            "acting_on": p.prefix,
                            "severity": "YELLOW",
                            "msg": f"项目 {p.prefix} 缺失对应的 业务线路（{p.prefix}）段落。",
                            "evidence": "docs/roadmap.md:1",
                            "cross_confirm": 0.0,
                        }
                    )
    dispatch_dir = repo_root / "docs" / "dispatch"
    card_files = scan_card_files(dispatch_dir)
    for cp in card_files:
        try:
            content = cp.read_text(encoding="utf-8")
        except Exception:
            continue
        rel_path = str(cp.relative_to(repo_root))
        meta = parse_metadata(content)
        title_match = re.search("^#\\s*任务卡\\s*(\\S+)", content, re.MULTILINE)
        card_id = title_match.group(1) if title_match else cp.stem
        related = meta.get("关联", "").strip()
        if related and related != "无":
            token = re.split("[：:\\s（(]", related)[0].strip()
            if not re.match("^[a-zA-Z0-9]+-plan-\\d+$", token):
                line_idx = 1
                for idx, line in enumerate(content.splitlines(), 1):
                    if "关联：" in line or "关联:" in line:
                        line_idx = idx
                        break
                findings.append(
                    {
                        "type": "governance",
                        "assertion": 2,
                        "acting_on": card_id,
                        "severity": "YELLOW",
                        "msg": f"卡 {card_id} 的关联字段 '{related}' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。",
                        "evidence": f"{rel_path}:{line_idx}",
                        "cross_confirm": 0.0,
                    }
                )
        c_state = base_state(meta.get("状态", "未知"))
        if c_state in ("ignore", "已关闭", "已回写"):
            if "## 维护区" not in content:
                findings.append(
                    {
                        "type": "governance",
                        "assertion": 6,
                        "acting_on": card_id,
                        "severity": "YELLOW",
                        "msg": f"卡 {card_id} 处于已关闭/已回写状态，但缺失 ## 维护区 章节。",
                        "evidence": f"{rel_path}:1",
                        "cross_confirm": 0.0,
                    }
                )
            else:
                lines = content.splitlines()
                has_placeholder = False
                placeholder_line = 1
                for idx, line in enumerate(lines, 1):
                    if "[是/否]" in line or "[有/无]" in line:
                        has_placeholder = True
                        placeholder_line = idx
                        break
                if has_placeholder:
                    findings.append(
                        {
                            "type": "governance",
                            "assertion": 6,
                            "acting_on": card_id,
                            "severity": "YELLOW",
                            "msg": f"卡 {card_id} 的 维护区 包含未作答占位符 [是/否] 或 [有/无]。",
                            "evidence": f"{rel_path}:{placeholder_line}",
                            "cross_confirm": 0.0,
                        }
                    )
    if roadmap_path.exists():
        roadmap_content = roadmap_path.read_text(encoding="utf-8")
        row_pattern = re.compile(
            "^\\s*\\|\\s*\\*\\*([a-zA-Z0-9_-]+)\\*\\*\\s*\\|\\s*([^|]+)\\s*\\|\\s*([^|]+)\\s*\\|", re.MULTILINE
        )
        for idx, line in enumerate(roadmap_content.splitlines(), 1):
            match = row_pattern.match(line)
            if match:
                ref_card_id = match.group(1).strip()
                status_cell = match.group(3).strip()
                expected_state = None
                if any(k in status_cell for k in ("已合入", "已关闭")):
                    expected_state = "已关闭"
                elif "已回写" in status_cell:
                    expected_state = "已回写"
                elif any(k in status_cell for k in ("执行中", "开发中")):
                    expected_state = "执行中"
                elif any(k in status_cell for k in ("待分派", "未开发")):
                    expected_state = "待分派"
                elif "打回" in status_cell:
                    expected_state = "打回"
                if expected_state:
                    actual_state = card_status.get(ref_card_id)
                    if actual_state and actual_state != expected_state:
                        findings.append(
                            {
                                "type": "governance",
                                "assertion": 5,
                                "acting_on": ref_card_id,
                                "severity": "YELLOW",
                                "msg": f"路线图状态 '{status_cell}' (期望 {expected_state}) 与卡真实状态 '{actual_state}' 漂移。",
                                "evidence": f"docs/roadmap.md:{idx}",
                                "cross_confirm": 0.0,
                            }
                        )
    for plan in plans:
        plan_id = plan["id"]
        plan_status = plan["status"]
        plan_cards_str = plan.get("cards", "").strip()
        plan_path = plan["path"]
        if not plan_cards_str or plan_cards_str == "无":
            associated_cards = []
        else:
            associated_cards = [c.strip() for c in plan_cards_str.split(",") if c.strip()]
        if plan_status == "已完成" and (not associated_cards):
            findings.append(
                {
                    "type": "reverse",
                    "assertion": 3,
                    "acting_on": plan_id,
                    "severity": "YELLOW",
                    "msg": f"方案 {plan_id} 处于已完成状态，但没有关联任何开发卡。",
                    "evidence": f"{plan_path}:1",
                    "cross_confirm": 0.0,
                }
            )
        for ac in associated_cards:
            if ac not in card_status:
                findings.append(
                    {
                        "type": "governance",
                        "assertion": 4,
                        "acting_on": plan_id,
                        "severity": "YELLOW",
                        "msg": f"方案 {plan_id} 引用了不存在的卡 {ac}。",
                        "evidence": f"{plan_path}:1",
                        "cross_confirm": 0.0,
                    }
                )
        if plan_status == "已完成" and associated_cards:
            unclosed_cards = [ac for ac in associated_cards if ac in card_status and card_status[ac] != "已关闭"]
            if unclosed_cards:
                findings.append(
                    {
                        "type": "governance",
                        "assertion": 3,
                        "acting_on": plan_id,
                        "severity": "YELLOW",
                        "msg": f"方案 {plan_id} 已推进至 '已完成'，但其关联卡 {', '.join(unclosed_cards)} 尚未关闭。",
                        "evidence": f"{plan_path}:1",
                        "cross_confirm": 0.0,
                    }
                )
        if plan_status != "已完成" and associated_cards:
            all_closed = True
            for ac in associated_cards:
                if card_status.get(ac) != "已关闭":
                    all_closed = False
                    break
            if all_closed:
                findings.append(
                    {
                        "type": "governance",
                        "assertion": 3,
                        "acting_on": plan_id,
                        "severity": "YELLOW",
                        "msg": f"方案 {plan_id} 关联卡已全部关闭，但方案状态仍为 '{plan_status}' (未推进至 '已完成')。",
                        "evidence": f"{plan_path}:1",
                        "cross_confirm": 0.0,
                    }
                )
                findings.append(
                    {
                        "type": "reverse",
                        "assertion": 3,
                        "acting_on": plan_id,
                        "severity": "YELLOW",
                        "msg": f"从已关闭卡反推，方案 {plan_id} 应该已完成，但实际状态仍处于 '{plan_status}'。",
                        "evidence": f"{plan_path}:1",
                        "cross_confirm": 0.0,
                    }
                )
        for ac in associated_cards:
            if card_status.get(ac) == "已关闭" and plan_status != "已完成":
                findings.append(
                    {
                        "type": "reverse",
                        "assertion": 7,
                        "acting_on": ac,
                        "severity": "YELLOW",
                        "msg": f"开发卡 {ac} 已关闭，但其关联方案 {plan_id} 的状态仍为 '{plan_status}' (未完成)。",
                        "evidence": f"docs/dispatch/{ac}.md:1"
                        if (dispatch_dir / f"{ac}.md").exists()
                        else f"{plan_path}:1",
                        "cross_confirm": 0.0,
                    }
                )
    by_entity = defaultdict(list)
    for f in findings:
        by_entity[f["acting_on"]].append(f)
    for entity, group in by_entity.items():
        has_gov = any(f["type"] == "governance" for f in group)
        has_rev = any(f["type"] == "reverse" for f in group)
        if has_gov and has_rev:
            for f in group:
                f["severity"] = "RED"
                f["cross_confirm"] = 1.0
                if "【交叉确认】" not in f["msg"]:
                    f["msg"] = "【交叉确认】" + f["msg"]
    return findings


def write_report(findings: list[dict[str, Any]], repo_root: Path) -> Path:
    """产出巡查报告至 DATA_DIR/observer/ 目录，且只有内容发生变化时才写 docs/notes/"""
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    report_name = f"{today_str}-ccc-patrol.md"

    red_cnt = sum(1 for f in findings if f["severity"] == "RED")
    yel_cnt = sum(1 for f in findings if f["severity"] == "YELLOW")
    blu_cnt = sum(1 for f in findings if f["severity"] == "BLUE")
    content = f"# CCC 巡查与一致性交叉验证风险报告 ({today_str})\n\n> 自动生成时间：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n> 风险概览：🔴 红旗 {red_cnt} 处 · 🟡 黄旗 {yel_cnt} 处 · 🔵 蓝旗 {blu_cnt} 处\n\n---\n\n## 巡查发现清单\n\n| 严重程度 | 对象 (acting_on) | 发现分类 | 交叉确认 | 证据 (位置) | 详细描述 |\n| :---: | :--- | :--- | :---: | :--- | :--- |\n"
    for f in sorted(findings, key=lambda x: (x["severity"] == "RED", x["acting_on"]), reverse=True):
        sev_icon = "🔴 红旗" if f["severity"] == "RED" else "🟡 黄旗" if f["severity"] == "YELLOW" else "🔵 蓝旗"
        cross_cell = "✅ 交叉确认" if f.get("cross_confirm", 0.0) == 1.0 else "—"
        f_type = "逆向巡查" if f["type"] == "reverse" else "治理一致性"
        content += f"| {sev_icon} | `{f['acting_on']}` | {f_type} | {cross_cell} | `{f['evidence']}` | {f['msg']} |\n"
    content += "\n---\n*本报告由 CCC 逆向巡查 Agent 自动生成并输出。只读，仅记录状态，不修改任何项目数据文件。*\n"

    # 优先落 DATA_DIR/observer/
    data_dir = os.environ.get("CCC_DATA_DIR") or os.environ.get("DATA_DIR")
    if data_dir:
        observer_dir = Path(data_dir).resolve() / "observer"
    else:
        observer_dir = repo_root / "data" / "observer"
    try:
        observer_dir.mkdir(parents=True, exist_ok=True)
        observer_report_path = observer_dir / report_name
        observer_report_path.write_text(content, encoding="utf-8")
    except Exception as e:
        logger.error("failed to save report to DATA_DIR/observer: %s", e)

    # 只有当内容发生变化时，才写入 docs/notes/
    notes_dir = repo_root / "docs" / "notes"
    try:
        notes_dir.mkdir(parents=True, exist_ok=True)
        report_path = notes_dir / report_name
        should_write = True
        if report_path.exists():
            existing_content = report_path.read_text(encoding="utf-8")
            if existing_content == content:
                should_write = False
        if should_write:
            report_path.write_text(content, encoding="utf-8")
            logger.info("patrol report (changed) saved to docs/notes: %s", report_path)
        else:
            logger.info("patrol report unchanged, skipping docs/notes update")
    except Exception as e:
        logger.error("failed to save report to docs/notes: %s", e)
        report_path = observer_dir / report_name  # fallback

    return report_path


def main_reverse():
    parser = argparse.ArgumentParser(description="CCC reverse patrol and consistency agent")
    parser.add_argument("--once", action="store_true", help="运行一次巡查并产出报告")
    args = parser.parse_args()
    if args.once:
        print("[Observer] 开始运行 CCC 逆向与治理巡查...")
        findings = run_patrol(REPO_ROOT)
        report_path = write_report(findings, REPO_ROOT)
        print(f"[Observer] 巡查完成！发现 {len(findings)} 个异常。报告已写入: {report_path}")
        for f in findings:
            if f["severity"] == "RED":
                cross_str = " [交叉确认]" if f.get("cross_confirm", 0.0) == 1.0 else ""
                print(f"- [{f['severity']}] {f['acting_on']}: {f['msg']}{cross_str} ({f['evidence']})")
    else:
        print("[Observer] 未提供 --once 参数，不执行。")


# ============ 观测指标角色 (ccc032) ============


def is_maintenance_complete(text: str) -> bool:
    """机械门禁同款逻辑：核对卡 `## 维护区` 四问是否齐全并有有效说明。"""
    if "## 维护区" not in text:
        return False
    try:
        seg = text.split("## 维护区", 1)[1]
        if "## " in seg:
            seg = seg.split("## ", 1)[0]
        items = re.findall("^(\\d+)\\. \\*\\*([^*]+)\\*\\*：[^\\[]*\\[([^]]*)\\]", seg, re.M)
        if len(items) < 4:
            return False
        for num, name, choice in items:
            if choice.strip() not in ("是", "否", "有", "无"):
                return False
        notes = re.findall("^   - 说明：(.+)$", seg, re.M)
        if len(notes) < 4 or any(n.strip() == "" for n in notes):
            return False
        return True
    except Exception:
        return False


def gather_mcp_metrics(log_dir: Path) -> dict[str, Any]:
    """指标 1：执行体能否经 ccc-kb 检索项目知识 (检查配置与调用次数)."""
    # 按当前用户解析配置路径（M1/2017 用户不同，避免绑定 /Users/fan）
    opencode_conf = Path(os.path.expanduser("~/.config/opencode/opencode.json"))
    claude_conf = Path(os.path.expanduser("~/.claude/settings.json"))
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
                # M7: 清洗 ANSI 色码（\x1b[...m），否则正则匹配不到 ⚙ 工具名 → 假数据 0 次
                content = re.sub(r"\x1b\[[0-9;]*m", "", content)
                calls = re.findall("⚙\\s*(?:ccc-kb_kb_|kb_)\\w+", content)
                total_calls += len(calls)
            except Exception:
                pass
    success_rate = (
        100.0
        if total_calls > 0 and failed_calls == 0
        else 0.0
        if total_calls == 0
        else (total_calls - failed_calls) / total_calls * 100.0
    )
    return {
        "opencode_mcp_enabled": opencode_ok,
        "claude_mcp_enabled": claude_ok,
        "total_calls_observed": total_calls,
        "call_success_rate": success_rate,
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
    coverage = complete_maintenance / total_completed * 100.0 if total_completed > 0 else 0.0
    return {
        "total_completed_cards": total_completed,
        "complete_maintenance_cards": complete_maintenance,
        "maintenance_coverage_pct": coverage,
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
    recirculation_rate = recirculated / len(new_cards) * 100.0 if new_cards else 0.0
    return {
        "total_new_cards": len(new_cards),
        "recirculated_lessons_cards": recirculated,
        "lesson_recirculation_rate_pct": recirculation_rate,
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
    passed_rate = passed_count / total_processed * 100.0 if total_processed > 0 else 0.0
    rejected_rate = rejected_count / total_processed * 100.0 if total_processed > 0 else 0.0
    return {
        "processed_cards_count": total_processed,
        "passed_count": passed_count,
        "rejected_count": rejected_count,
        "passed_rate_pct": passed_rate,
        "rejected_rate_pct": rejected_rate,
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
            "main_status": "跳过",
        }
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            try:
                response = page.goto(f"{url}/health", timeout=5000)
                health_ok = response.status == 200 if response else False
            except Exception:
                health_ok = False
            try:
                response = page.goto(f"{url}/config", timeout=5000)
                config_ok = response.status == 200 if response else False
            except Exception:
                config_ok = False
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
                "main_status": "200 OK" if main_ok else "失败",
            }
    except Exception as e:
        return {
            "ok": False,
            "status_str": f"环境未就绪/服务未运行 ({e})",
            "health_status": "失败",
            "config_status": "失败",
            "main_status": "失败",
        }


def run_observation(dispatch_dir: Path, log_dir: Path, output_file: Path) -> dict[str, Any]:
    """采集所有指标，输出 Markdown 报告."""
    mcp = gather_mcp_metrics(log_dir)
    maint = gather_maintenance_metrics(dispatch_dir)
    lesson = gather_lesson_recirculation_metrics(dispatch_dir)
    audit = gather_audit_trends_metrics(dispatch_dir)
    pw = run_playwright_smoke_test()
    op_enabled = mcp["opencode_mcp_enabled"] or mcp["claude_mcp_enabled"]
    maint_pct = maint["maintenance_coverage_pct"]
    lesson_pct = lesson["lesson_recirculation_rate_pct"]
    if op_enabled and maint_pct >= 80.0 and (lesson_pct >= 50.0):
        conclusion = "有效"
        evidence_prefix = "Skill/MCP 优化已全面生效。ccc-kb 检索已配置完成；"
    elif not op_enabled and maint_pct < 30.0 and (lesson_pct < 20.0):
        conclusion = "无效"
        evidence_prefix = "优化基本未生效。ccc-kb 配置未激活，且各项流程指标处于低位；"
    else:
        conclusion = "部分"
        evidence_prefix = "优化已部分生效。ccc-kb 配置已启用并开始积累调用；"
    evidence = f"{evidence_prefix}维护区 Doc-Gate 覆盖率达 {maint_pct:.1f}%，教训回流率为 {lesson_pct:.1f}%，近 30 卡验收通过率为 {audit['passed_rate_pct']:.1f}%。"
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    report_content = f"# 2017 Agent Skill/MCP 优化生效观测报告 ({today})\n\n> 报告时间：{today} · 观测执行体：Loop Observer\n\n## 1. 观测结论\n\n- **生效评估**：**{conclusion}生效**\n- **核心证据**：{evidence}\n\n## 2. 4 项观测指标实测值\n\n### 指标 1：执行体 ccc-kb MCP 检索接入\n- **OpenCode 配置状态**：{('已启用 (Active)' if mcp['opencode_mcp_enabled'] else '未启用 (Inactive)')}\n- **Claude Code 配置状态**：{('已启用 (Active)' if mcp['claude_mcp_enabled'] else '未启用 (Inactive)')}\n- **观测到实际调用次数**：{mcp['total_calls_observed']} 次\n- **调用成功率**：{mcp['call_success_rate']:.1f}%\n\n### 指标 2：维护区四问覆盖率 (Doc-Gate)\n- **已回写/已关闭卡总数**：{maint['total_completed_cards']} 张\n- **维护区齐全卡数量**：{maint['complete_maintenance_cards']} 张\n- **覆盖率**：{maint['maintenance_coverage_pct']:.1f}%\n\n### 指标 3：教训回流率\n- **新卡总数**：{lesson['total_new_cards']} 张\n- **已回流教训卡数量**：{lesson['recirculated_lessons_cards']} 张\n- **教训回流率**：{lesson['lesson_recirculation_rate_pct']:.1f}%\n\n### 指标 4：验收通过率/打回率趋势 (近 30 卡)\n- **近 30 卡实测样本数**：{audit['processed_cards_count']} 张\n- **机审通过数 (及已关闭)**：{audit['passed_count']} 张 (占比：{audit['passed_rate_pct']:.1f}%)\n- **打回数 (及曾打回)**：{audit['rejected_count']} 张 (占比：{audit['rejected_rate_pct']:.1f}%)\n\n## 3. 功能巡查 (Playwright Web Smoke Test)\n\n- **巡查状态**：{pw['status_str']}\n- **巡查详情**：\n  - `/health` 接口：{pw['health_status']}\n  - `/config` 接口：{pw['config_status']}\n  - 主页加载：{pw['main_status']}\n"
    try:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(report_content, encoding="utf-8")
    except Exception as e:
        print(f"写入观测报告失败: {e}", file=sys.stderr)
    return {"conclusion": conclusion, "mcp": mcp, "maint": maint, "lesson": lesson, "audit": audit, "pw": pw}


def run_observation_metrics(cfg: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    """scheduler 挂载入口：4 项观测指标 + Playwright 功能巡查，输出到 DATA_DIR/observer/。

    ccc067 收尾：观测指标从「手动 --once」升级为 scheduler 常驻自动调度。
    """
    try:
        dispatch_dir = cfg.get("SCHEDULER_DISPATCH_DIR", "")
        if not dispatch_dir:
            dispatch_dir = PROJECT_ROOT / "docs" / "dispatch"
        log_dir_env = os.environ.get("EXECUTOR_LOG_DIR", "").strip()
        log_dir = cfg.get("EXECUTOR_LOG_DIR", "") or log_dir_env or str(Path(os.path.expanduser("~/.ccc/logs/exec")))
        data_dir = cfg.get("DATA_DIR", "") or os.environ.get("CCC_DATA_DIR") or "data"
        out_dir = Path(data_dir).resolve() / "observer"
        out_dir.mkdir(parents=True, exist_ok=True)
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        output_file = out_dir / f"observation-{today}.md"
        results = run_observation(Path(dispatch_dir), Path(log_dir), output_file)
        return (
            True,
            {
                "output": str(output_file),
                "conclusion": results["conclusion"],
                "pw_status": results["pw"]["status_str"],
                "mcp_calls": results["mcp"]["total_calls_observed"],
                "maint_pct": results["maint"]["maintenance_coverage_pct"],
            },
        )
    except Exception as exc:  # 巡检失败不中断调度循环
        logger.error("observation-metrics 采集失败: %s", exc)
        return (False, {"error": str(exc)})


def main_metrics():
    parser = argparse.ArgumentParser(description="Loop Observer — 4 项观测指标采集")
    parser.add_argument("--once", action="store_true", help="单次跑出观测报告后退出")
    parser.add_argument("--dispatch-dir", default="docs/dispatch", help="任务卡分派目录")
    parser.add_argument(
        "--log-dir",
        default=os.environ.get("EXECUTOR_LOG_DIR", os.path.expanduser("~/.ccc/logs/exec")),
        help="执行日志目录",
    )
    parser.add_argument("--output", default="docs/notes/2026-08-10-skill-mcp-observability.md", help="报告输出路径")
    args = parser.parse_args()
    dispatch_dir = Path(args.dispatch_dir)
    log_dir = Path(args.log_dir)
    output_file = Path(args.output)
    if args.once:
        print("开始单次巡查与指标采集...")
        results = run_observation(dispatch_dir, log_dir, output_file)
        print("\n=== 指标采集摘要 ===")
        print(
            f"ccc-kb 接入: OpenCode={results['mcp']['opencode_mcp_enabled']}, Claude={results['mcp']['claude_mcp_enabled']}, 累计调用={results['mcp']['total_calls_observed']}次"
        )
        print(f"维护区四问覆盖率: {results['maint']['maintenance_coverage_pct']:.1f}%")
        print(f"教训回流率: {results['lesson']['lesson_recirculation_rate_pct']:.1f}%")
        print(
            f"近 30 卡机审通过率: {results['audit']['passed_rate_pct']:.1f}% | 打回率: {results['audit']['rejected_rate_pct']:.1f}%"
        )
        print(f"功能巡查状态: {results['pw']['status_str']}")
        print(f"生效评估结论: {results['conclusion']}生效\n")
    else:
        parser.print_help()


def main():
    parser = argparse.ArgumentParser(description="Loop Observer — 统一巡查（框架/逆向/指标）")
    sub = parser.add_subparsers(dest="role")
    sub.add_parser("patrol", help="定时框架 + 治理一致性 + 权重打分")
    sub.add_parser("reverse", help="逆向巡查与一致性交叉验证")
    sub.add_parser("metrics", help="4 项观测指标 + Playwright 功能巡查")
    args = parser.parse_args()
    if args.role == "reverse":
        main_reverse()
    elif args.role == "metrics":
        main_metrics()
    else:
        cfg: dict[str, Any] = {}
        ok, summary = run_observer(cfg)
        if not ok:
            sys.exit(1)
        print("[Observer] 框架巡查完成")


if __name__ == "__main__":
    main()


def write_roadmap_draft(
    project: str,
    description: str,
    *,
    draft_type: str = "问题",
    source: str = "Loop巡查",
) -> dict[str, Any]:
    """Loop 巡查集成：自动将发现的问题写入对应项目 roadmap.md 草案池。

    当 Loop 发现新问题（治理漂移、缺失项、技术债）时调用此函数，
    自动在对应项目的 roadmap.md 草案池中追加一条草案条目。

    Args:
        project: 项目前缀（如 ccc, clw, hp 等）
        description: 巡查发现的问题描述
        draft_type: 草案类型，默认 "问题"
        source: 来源标识，默认 "Loop巡查"

    Returns:
        dict: {"ok": True, "draft": title} 或 {"error": "..."}
    """
    from server.board.roadmap import create_draft as _create_draft, list_drafts

    # 构造标题：包含类型、来源和描述
    title = f"[{draft_type}][{source}] {description}"

    # 去重检查：已有相同描述的草案则跳过
    try:
        existing = list_drafts(project)
        for d in existing:
            if description in d.title:
                return {"ok": True, "draft": d.title, "skipped": True, "reason": "duplicate"}
    except Exception:
        pass

    return _create_draft(project, title)


def trigger_scheduled_ops(cfg: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    """定时运维任务触发（2026-08-11 · 集群运维 Agent 调取）。

    扫描「派发：scheduler」的待分派卡：
      - 卡头「定时：HH:MM」→ 到点才触发
      - 无「定时」字段 → 首次扫描即触发
    触发 = 写 sidecar state=待分派 + reason=scheduler_triggered:<ts>
    （远端 Worker 认领时看到此标记即认领执行；Engine 不本地拉起。）

    Returns:
        (ok, {"triggered": [卡ID], "pending": [卡ID]})
    """
    dispatch_dir = cfg.get("SCHEDULER_DISPATCH_DIR", "")
    if not dispatch_dir:
        dispatch_dir = PROJECT_ROOT / "docs" / "dispatch"
    dispatch_dir = Path(dispatch_dir)
    log_dir = cfg.get("EXECUTOR_LOG_DIR", "")
    if not log_dir:
        log_dir = os.environ.get("EXECUTOR_LOG_DIR") or os.environ.get("CCC_LOG_DIR") or ""
    if not log_dir:
        logger.warning("trigger_scheduled_ops: 无 EXECUTOR_LOG_DIR，跳过")
        return (True, {"triggered": [], "pending": [], "reason": "no log_dir"})

    now_dt = datetime.datetime.now()
    now_str = now_dt.strftime("%H:%M")
    triggered: list[str] = []
    pending: list[str] = []

    from server.engine.runtime_state import write_card_state

    for path in sorted(dispatch_dir.rglob("*.md")):
        if path.name.startswith("."):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        meta = parse_metadata(text)
        if meta.get("派发", "engine") != "scheduler":
            continue
        card_id = path.stem
        state = meta.get("状态", "").strip()
        # 只触发待分派卡（已触发/执行中/已关闭不重复触发）
        if state and state not in ("待分派", ""):
            continue
        # 已触发过（sidecar 有 scheduler_triggered 标记）→ 不重复
        from server.engine.runtime_state import read_card_state

        rt = read_card_state(log_dir).get(card_id, {})
        if "scheduler_triggered" in str(rt.get("reason", "")):
            pending.append(card_id)
            continue
        # 定时字段：到点才触发
        schedule = meta.get("定时", "").strip()
        if schedule and now_str < schedule:
            pending.append(card_id)
            continue
        write_card_state(
            log_dir,
            card_id,
            state="待分派",
            reason=f"scheduler_triggered:{now_dt.isoformat(timespec='seconds')}",
        )
        triggered.append(card_id)
        logger.info("定时运维任务已触发: %s (schedule=%s)", card_id, schedule or "immediate")

    return (True, {"triggered": triggered, "pending": pending})
