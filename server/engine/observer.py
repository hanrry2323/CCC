"""Loop Observer只读巡查框架 — 每日/合入巡检任务。"""

from __future__ import annotations

import datetime
import json
import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from server.board.registry import load_projects
from server.board.loader import load_dispatch_cards, get_index_path
from server.board.plans import list_plans

logger = logging.getLogger("ccc.engine.observer")

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _get_current_state(cfg: dict[str, Any]) -> dict[str, Any]:
    """获取当前系统的状态：时间戳、最新的 git merge 提交、cards.index.jsonl 信息。"""
    now = time.time()
    git_commit = ""
    try:
        res = subprocess.run(
            ["git", "log", "origin/main", "--merges", "-n", "1", "--format=%H"],
            capture_output=True, text=True, timeout=5
        )
        if res.returncode == 0:
            git_commit = res.stdout.strip()
    except Exception:
        pass

    if not git_commit:
        try:
            res = subprocess.run(
                ["git", "log", "--merges", "-n", "1", "--format=%H"],
                capture_output=True, text=True, timeout=5
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
        return True, "force via config/env"

    data_dir = cfg.get("DATA_DIR", "")
    if not data_dir:
        data_dir = os.environ.get("CCC_DATA_DIR") or os.environ.get("DATA_DIR") or "data"

    last_run_path = Path(data_dir).resolve() / "observer" / "last-run.json"
    if not last_run_path.exists():
        return True, "first run"

    try:
        with open(last_run_path, "r", encoding="utf-8") as f:
            last_state = json.load(f)
    except Exception as e:
        return True, f"last-run error: {e}"

    # 1. 每日 1 次（超过 24 小时）
    last_ts = last_state.get("timestamp", 0.0)
    if current_state["timestamp"] - last_ts >= 86400:
        return True, f"24 hours passed since last run at {last_ts}"

    # 2. 合入后触发（Git merge 提交变更）
    last_commit = last_state.get("git_commit", "")
    curr_commit = current_state["git_commit"]
    if curr_commit and last_commit and curr_commit != last_commit:
        return True, f"new merge commit {curr_commit} (prev {last_commit})"

    # 3. cards.index.jsonl 发生变化
    last_mtime = last_state.get("cards_index_mtime", 0.0)
    last_size = last_state.get("cards_index_size", 0)
    curr_mtime = current_state["cards_index_mtime"]
    curr_size = current_state["cards_index_size"]
    if curr_mtime != last_mtime or curr_size != last_size:
        return True, f"cards.index.jsonl changed: mtime {curr_mtime} (prev {last_mtime}), size {curr_size} (prev {last_size})"

    return False, "thresholds not met"


DEFAULT_SCORING_RULES = {
    "broken_link": {"impact": 4, "frequency": 4},
    "drift": {"impact": 2, "frequency": 3},
    "missing_four_questions": {"impact": 2, "frequency": 1},
    "missing_section": {"impact": 3, "frequency": 2},
}


def check_missing_four_questions(card_id: str, file_path: Path) -> tuple[bool, str]:
    if not file_path.exists():
        return True, "file_not_found"
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        return True, str(e)
    if "## 维护区" not in content:
        return True, "no_maintenance_section"
    lines = content.splitlines()
    for idx, line in enumerate(lines):
        if "说明：" in line or "说明:" in line:
            rest = line.partition("说明：")[2].strip() or line.partition("说明:")[2].strip()
            if not rest:
                next_line_has_text = False
                for offset in range(1, 4):
                    if idx + offset < len(lines):
                        next_line = lines[idx + offset].strip()
                        if next_line and not next_line.startswith("-") and not next_line.startswith("1.") and not next_line.startswith("2.") and not next_line.startswith("3.") and not next_line.startswith("4.") and not next_line.startswith("#"):
                            next_line_has_text = True
                            break
                        if next_line.startswith("-") or next_line.startswith("1.") or next_line.startswith("2.") or next_line.startswith("3.") or next_line.startswith("4.") or next_line.startswith("#"):
                            break
                if not next_line_has_text:
                    return True, "empty_description"
    if "[是/否]" in content or "[有/无]" in content:
        return True, "unchecked_placeholders"
    return False, ""


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
        for p in projects_list:
            if p.taskable and p.prefix:
                prefix = p.prefix
                pattern = rf"##\s*业务线路\s*[（(]\s*{prefix}\s*[）)]"
                if not re.search(pattern, roadmap_content):
                    findings.append({
                        "id": f"missing_roadmap_section_{prefix}",
                        "title": f"项目 {prefix} 缺席 roadmap.md 的业务线路段落",
                        "project": prefix,
                        "type": "missing_section",
                        "cross_confirm": 0.5,
                        "acting_on": "docs/roadmap.md",
                        "evidence": "docs/roadmap.md:1"
                    })
        pattern_card = r"\|\s*\*\*([a-zA-Z0-9\-]+)\*\*\s*\|[^|]+\|\s*([^|\s]+)\s*\|"
        matches = re.findall(pattern_card, roadmap_content)
        roadmap_lines = roadmap_content.splitlines()
        for card_id_raw, r_status in matches:
            card_id_key = card_id_raw.lower()
            if card_id_key in cards_by_id:
                card = cards_by_id[card_id_key]
                real_status = card.get("state", "").strip()
                def normalize_state(s: str) -> str:
                    s = s.strip()
                    if s in ("已合入", "已关闭", "已完成", "released", "closed"):
                        return "closed"
                    if s in ("已回写", "verified", "testing", "待验收", "机审"):
                        return "verified"
                    if s in ("执行中", "in_progress", "开发中"):
                        return "in_progress"
                    if s in ("待分派", "pending", "planned"):
                        return "pending"
                    return s
                if normalize_state(r_status) != normalize_state(real_status):
                    line_no = 1
                    for idx, line in enumerate(roadmap_lines):
                        if f"**{card_id_raw}**" in line:
                            line_no = idx + 1
                            break
                    findings.append({
                        "id": f"status_drift_{card_id_key}",
                        "title": f"任务卡 {card_id_raw} 状态漂移：roadmap.md 标注「{r_status}」，但看板/卡文件实际状态为「{real_status}」",
                        "project": card.get("project", "ccc"),
                        "type": "drift",
                        "cross_confirm": 0.5,
                        "acting_on": "docs/roadmap.md",
                        "evidence": f"docs/roadmap.md:{line_no}"
                    })
    for plan in plans_list:
        plan_status = plan.get("status", "").strip()
        if plan_status == "已完成":
            cards_field = plan.get("cards", "")
            if cards_field:
                ref_cards = re.findall(r"([a-zA-Z]+[0-9]+)", cards_field)
                open_ref_cards = []
                for rc in ref_cards:
                    rc_key = rc.lower()
                    if rc_key in cards_by_id:
                        real_status = cards_by_id[rc_key].get("state", "")
                        if real_status not in ("已关闭", "已合入", "已完成", "released", "closed"):
                            open_ref_cards.append((rc, real_status))
                if open_ref_cards:
                    open_cards_str = ", ".join([f"{rc}({st})" for rc, st in open_ref_cards])
                    findings.append({
                        "id": f"completed_plan_open_cards_{plan['id']}",
                        "title": f"方案 {plan['id']} 已完成，但其关联卡未全部关闭: {open_cards_str}",
                        "project": plan.get("project", "ccc"),
                        "type": "broken_link",
                        "cross_confirm": 1.0,
                        "acting_on": plan.get("path", ""),
                        "evidence": f"{plan.get('path', '')}:1"
                    })
    for plan in plans_list:
        cards_field = plan.get("cards", "")
        if cards_field:
            ref_cards = re.findall(r"([a-zA-Z]+[0-9]+)", cards_field)
            missing_cards = []
            for rc in ref_cards:
                rc_key = rc.lower()
                if rc_key not in cards_by_id:
                    missing_cards.append(rc)
            if missing_cards:
                findings.append({
                    "id": f"plan_ref_missing_cards_{plan['id']}",
                    "title": f"方案 {plan['id']} 关联了不存在的任务卡: {', '.join(missing_cards)}",
                    "project": plan.get("project", "ccc"),
                    "type": "broken_link",
                    "cross_confirm": 0.5,
                    "acting_on": plan.get("path", ""),
                    "evidence": f"{plan.get('path', '')}:1"
                })
    for c in cards_list:
        state = c.get("state", "")
        if state in ("已关闭", "已合入", "closed", "released"):
            card_id = c.get("id", "")
            relative_path = c.get("path")
            if relative_path:
                file_path = project_root / relative_path
                missing, reason = check_missing_four_questions(card_id, file_path)
                if missing:
                    findings.append({
                        "id": f"missing_four_questions_{card_id.lower()}",
                        "title": f"已关闭任务卡 {card_id} 缺失或未完成维护区四问: {reason}",
                        "project": c.get("project", "ccc"),
                        "type": "missing_four_questions",
                        "cross_confirm": 0.5,
                        "acting_on": relative_path,
                        "evidence": f"{relative_path}:1"
                    })
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
    # 报告标题/表头承诺「按权重降序」，故在此自洽排序，不依赖调用方顺序
    ordered = sorted(findings, key=lambda x: x.get("weight", 0.0), reverse=True)
    lines = []
    lines.append(f"# 巡查风险报告 — {report_name}")
    lines.append(f"\n> 采集时间: {datetime.datetime.now().isoformat()} · 发现数: {len(ordered)}\n")
    lines.append("## 风险发现列表（按权重降序排序）\n")
    lines.append("| 权重 (Weight) | 交叉确认 (Cross-Confirm) | 影响 (Impact) | 频次 (Frequency) | 描述 (Title) | 项目 (Project) | 作用对象 (Acting On) | 证据 (Evidence) |")
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


def run_observer(cfg: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    """定时只读巡检入口。

    采集 registry/卡/方案快照，并在满足阈值时写入/更新快照。
    """
    current_state = _get_current_state(cfg)
    need_run, reason = should_run(cfg, current_state)

    if not need_run:
        logger.info("Loop Observer 跳过运行：%s", reason)
        return True, {"skipped": True, "reason": reason}

    logger.info("Loop Observer 开始运行：%s", reason)

    # 1. 读取只读快照数据
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

    # 2. 统计摘要
    cards_states: dict[str, int] = {}
    for c in cards_list:
        state = str(c.get("state", "未知"))
        cards_states[state] = cards_states.get(state, 0) + 1

    plans_states: dict[str, int] = {}
    for p in plans:
        state = str(p.get("status", "未知"))
        plans_states[state] = plans_states.get(state, 0) + 1

    findings = scan_findings(cfg, PROJECT_ROOT)
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
    
    notes_dir = PROJECT_ROOT / "docs" / "notes"
    try:
        notes_dir.mkdir(parents=True, exist_ok=True)
        report_path = notes_dir / f"{report_name}.md"
        report_path.write_text(report_md, encoding="utf-8")
        logger.info("patrol report saved to %s", report_path)
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
        return False, {"error": str(e)}

    return True, summary
