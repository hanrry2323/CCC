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

        # P1#12：observer 补 ccc 只读巡检（list_roadmaps 跳过 platform，ccc 数据成无人审计区）
        roadmap_projects = set(list_roadmaps())
        if (project_root / "docs" / "projects" / "ccc" / "roadmap.md").is_file():
            roadmap_projects.add("ccc")

        for proj in sorted(roadmap_projects):
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
                declared = ms.status
                computed = comp.get("status", declared)
                completed = comp.get("completed", 0)
                # P1#13：全态比对（此前只查两个极端，中间带长期分歧不可见）。
                # 排除 0 完成时 compute 保持原状态的设计性行为（无信息可比）。
                if completed > 0 and declared != computed:
                    findings.append(
                        {
                            "id": f"milestone_progress_{proj}_{ms.title[:24]}",
                            "title": f"里程碑 {proj}/{ms.title} 进度不一致：声明 {declared}，实际完成率 {comp.get('progress_pct', 0)}%（{completed}/{comp.get('total', 0)} 方案 → {computed}）",
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
        # 033 M6：作废卡剔除出 total（与 sync_plan_progress 口径一致），避免带作废卡方案误报「进度不一致」
        _card_states = [cards_by_id.get(rc.lower(), {}).get("state", "") for rc in ref_cards]
        real_total = sum(1 for s in _card_states if s != "作废")
        real_closed = sum(1 for s in _card_states if s in closed_states)
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

        # 033 阶段 2 M6：验收勾选 + 批准来源检查（P1-E 巡检补齐）
        _acc_unchecked = len(re.findall(r"^\s*[-*]\s+\[ \]", plan_text, re.M))
        if "状态：已完成" in plan_text and _acc_unchecked > 0:
            findings.append(
                {
                    "id": f"plan_accept_{plan['id']}",
                    "title": f"方案 {plan['id']} 已完成但验收标准 {_acc_unchecked} 项未勾选（033 验收归属：拍板前须勾选）",
                    "project": plan.get("project", "ccc"),
                    "type": "consistency",
                    "cross_confirm": 0.5,
                    "acting_on": plan_path,
                    "evidence": f"{plan_path}:1",
                }
            )
        from server.board.audit_ledger import has_action

        if "状态：待验收" in plan_text and not has_action("convert", plan["id"]):
            findings.append(
                {
                    "id": f"plan_approval_{plan['id']}",
                    "title": f"方案 {plan['id']} 待验收但无 convert 账本记录（批准来源缺失，033 批准真值化）",
                    "project": plan.get("project", "ccc"),
                    "type": "governance",
                    "cross_confirm": 0.5,
                    "acting_on": plan_path,
                    "evidence": f"{plan_path}:1",
                }
            )
    # 技术债（第三步 · PRIME-DIRECTIVE §6.2）：未关闭审查意见 + 废弃代码残留
    # a) 打回卡聚合（未关闭审查意见，按项目）
    rejected_by_proj: dict[str, list[str]] = {}
    for c in cards_list:
        if c.get("state") == "打回":
            rejected_by_proj.setdefault(c.get("project", "其他"), []).append(c.get("id", ""))
    for proj, ids in rejected_by_proj.items():
        findings.append(
            {
                "id": f"tech_rejected_cards_{proj}",
                "title": f"项目 {proj} 有 {len(ids)} 张打回卡待处理（未关闭审查意见）: {', '.join(ids[:5])}",
                "project": proj,
                "type": "tech",
                "cross_confirm": 0.5,
                "acting_on": "docs/dispatch",
                "evidence": "docs/dispatch:1",
            }
        )
    # b) 人工批注未落实（有真实批注但无「## 批注落实」段）
    for c in cards_list:
        rel = c.get("path", "")
        if not rel:
            continue
        card_file = project_root / rel
        if not card_file.is_file():
            continue
        try:
            ctext = card_file.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        if "## 人工批注" not in ctext:
            continue
        seg = ctext.split("## 人工批注", 1)[1].split("## ", 1)[0]
        if not seg.strip() or "老板对打回卡/审核的批注意见写这里" in seg:
            continue
        if "## 批注落实" not in ctext:
            findings.append(
                {
                    "id": f"tech_unaddressed_annotation_{c.get('id', '').lower()}",
                    "title": f"卡 {c.get('id')} 有真实人工批注但未见「## 批注落实」段",
                    "project": c.get("project", "ccc"),
                    "type": "tech",
                    "cross_confirm": 0.5,
                    "acting_on": rel,
                    "evidence": f"{rel}:1",
                }
            )
    # c) 方案审核引用缺失
    for plan in plans_list:
        plan_path = plan.get("path", "")
        if not plan_path:
            continue
        try:
            ptext = (project_root / plan_path).read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        m = re.search(r">\s*审核：([^\n]+)", ptext)
        if not m:
            continue
        ref_match = re.search(r"(docs/[^\s`）)]+\.md)", m.group(1))
        if ref_match and not (project_root / ref_match.group(1)).exists():
            findings.append(
                {
                    "id": f"tech_missing_review_ref_{plan['id']}",
                    "title": f"方案 {plan['id']} 审核引用文件缺失: {ref_match.group(1)}",
                    "project": plan.get("project", "ccc"),
                    "type": "tech",
                    "cross_confirm": 0.5,
                    "acting_on": plan_path,
                    "evidence": f"{plan_path}:1",
                }
            )
    # d) 死文件复活（scripts/arch-dead-files.txt 登记文件不得存在）
    dead_list = project_root / "scripts" / "arch-dead-files.txt"
    if dead_list.is_file():
        try:
            for line in dead_list.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if (project_root / line).exists():
                    findings.append(
                        {
                            "id": f"tech_dead_file_resurrected_{line[:24]}",
                            "title": f"已登记死文件复活: {line}",
                            "project": "ccc",
                            "type": "tech",
                            "cross_confirm": 0.5,
                            "acting_on": line,
                            "evidence": f"{line}:1",
                        }
                    )
        except Exception:
            pass
    # e) 孤儿卡：作废/已覆盖方案的关联卡仍是活跃态（未作废/未关闭）
    # 人审调整动作统一化（2026-08-14）：作废方案不得留孤儿卡；级联应已处理，这里兜底巡检。
    for plan in plans_list:
        plan_path = plan.get("path", "")
        plan_status = str(plan.get("status") or "").strip()
        if plan_status not in ("作废", "已覆盖"):
            continue
        if not plan_path:
            continue
        try:
            ptext = (project_root / plan_path).read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        m_cards = re.search(r">\s*关联卡：([^\n]*)", ptext)
        if not m_cards:
            continue
        cards_raw = m_cards.group(1).strip()
        if not cards_raw or cards_raw == "无":
            continue
        for cid in re.findall(r"([a-zA-Z]+[0-9]+(?:\-[a-zA-Z])?)", cards_raw):
            c = cards_by_id.get(cid.lower())
            if not c:
                continue
            cstate = base_state(str(c.get("state") or ""))
            if cstate not in ("已关闭", "作废"):
                findings.append(
                    {
                        "id": f"tech_orphan_card_{cid.lower()}",
                        "title": f"孤儿卡 {cid}：方案 {plan['id']} 已作废/已覆盖，但关联卡仍为「{cstate}」",
                        "project": c.get("project", "ccc"),
                        "type": "tech",
                        "cross_confirm": 0.5,
                        "acting_on": plan_path,
                        "evidence": f"{plan_path}:1",
                    }
                )
    # f) 下游前置已作废：卡的依赖/父卡是「作废」终态 → 提示老板定去留（已放行，不阻塞）
    # 人审调整动作统一化（2026-08-14）：作废卡不阻塞下游，但需人工确认下游是否继续。
    for c in cards_list:
        cid = c.get("id") or ""
        if not cid:
            continue
        cbase = base_state(str(c.get("state") or ""))
        if cbase in ("已关闭", "作废"):
            continue
        prereqs: list[tuple[str, str]] = []
        for dep_id in c.get("depends_on") or []:
            dep = cards_by_id.get(str(dep_id).lower())
            if dep and base_state(str(dep.get("state") or "")) == "作废":
                prereqs.append((str(dep_id), "依赖"))
        parent_id = str(c.get("parent") or "").strip()
        if parent_id:
            pcard = cards_by_id.get(parent_id.lower())
            if pcard and base_state(str(pcard.get("state") or "")) == "作废":
                prereqs.append((parent_id, "父卡"))
        for pid, kind in prereqs:
            findings.append(
                {
                    "id": f"tech_voided_prereq_{cid.lower()}_{kind}_{pid.lower()}",
                    "title": f"卡 {cid} 的{kind} {pid} 已作废——下游已放行，请确认 {cid} 是否继续",
                    "project": c.get("project", "ccc"),
                    "type": "tech",
                    "cross_confirm": 0.5,
                    "acting_on": c.get("path") or "",
                    "evidence": f"{c.get('path') or cid}:1",
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
    "tech": {"impact": 2, "frequency": 2},
}


def _auto_fix_deterministic(
    findings: list[dict[str, Any]], project_root: Path
) -> list[str]:
    """螺旋上升 P1-2：确定性漂移自动修复（幂等机械修复，非决策）。

    只处理可机械判定、修复即正确的漂移：
    - plan_progress_*：方案进度声明 vs 实算不一致 → sync_plan_progress 重算回写
    - milestone_progress_*：里程碑进度不一致 → sync_milestone_progress 重算
    - status_drift_*：卡状态与看板漂移 → 经 sync_plan_progress 级联修正方案进度

    护栏：
    - 只处理 NEW finding（按 id 去重，本次才出现才修）
    - 修复失败只记日志，不阻断巡检
    - 非确定性发现（tech/治理债）不在此列，走草案池

    Returns: 已自动修复的 finding id 列表。
    """
    fixed: list[str] = []
    for f in findings:
        ftype = f.get("type", "")
        fid = f.get("id", "")
        acting_on = f.get("acting_on", "") or ""
        project = f.get("project", "") or ""

        is_plan_progress = ftype == "consistency" and fid.startswith("plan_progress_")
        is_milestone_progress = ftype == "consistency" and fid.startswith("milestone_progress_")
        is_status_drift = ftype == "drift" and fid.startswith("status_drift_")
        if not (is_plan_progress or is_milestone_progress or is_status_drift):
            continue
        if not acting_on:
            continue

        try:
            # 通过 subprocess 调独立修复脚本（observer 代码层保持只读：
            # 白名单测试禁止 observer import plans 写接口，见 test_ast_import_whitelist）
            script = project_root / "scripts" / "auto-fix-plan-progress.py"
            if not script.is_file():
                logger.error("自动修复 %s 失败: 脚本不存在 %s", fid, script)
                continue
            rel = acting_on if acting_on.startswith("docs/") else acting_on
            proc = subprocess.run(
                [sys.executable, str(script), project_root, rel, project],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if proc.returncode == 0:
                fixed.append(fid)
                logger.info("自动修复 %s: 方案/里程碑进度已同步", fid)
            else:
                logger.warning("自动修复 %s 失败(rc=%d): %s", fid, proc.returncode, proc.stderr.strip()[:200])
        except Exception as e:  # noqa: BLE001
            logger.error("自动修复 %s 异常: %s", fid, e)
    return fixed


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
    # 螺旋上升 P1-2：确定性漂移自动修复（方案/里程碑进度重算，幂等机械修复）
    try:
        auto_fixed = _auto_fix_deterministic(findings, PROJECT_ROOT)
        if auto_fixed:
            logger.info("Loop 自动修复 %d 项确定性漂移: %s", len(auto_fixed), ",".join(auto_fixed))
    except Exception as e:  # noqa: BLE001
        logger.error("Loop 自动修复执行异常: %s", e)
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

    # PRIME-DIRECTIVE §6.3：一致性/技术债发现自动回草案池（治理债/技术债）。
    # ccc077 治理（2026-08-24）：CCC_LOOP_OBSERVER_DRAFTS 默认 off → 整轮跳过草稿写入
    # （每轮只记一次 DEBUG 日志）；on 时经 write_roadmap_draft 落
    # <DATA_DIR>/drafts/roadmap/<project>-draft.md，docs/projects 正文对自动链路只读，
    # 人工写路径不受影响。
    if _loop_drafts_enabled():
        for f in findings:
            if f.get("type") in ("consistency", "tech") and f.get("project"):
                draft_type = "技术债" if f.get("type") == "tech" else "治理债"
                try:
                    write_roadmap_draft(f["project"], f["title"], draft_type=draft_type, base_dir=data_dir)
                except Exception as e:
                    logger.error("草案池回写失败（%s）: %s", f.get("id"), e)
    else:
        _skipped_drafts = sum(
            1 for f in findings if f.get("type") in ("consistency", "tech") and f.get("project")
        )
        logger.debug(
            "CCC_LOOP_OBSERVER_DRAFTS 未开启，本轮跳过 %d 条巡查草稿写入（docs/projects 正文只读化）",
            _skipped_drafts,
        )
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
        # 对齐 docgate.verify_maintenance：勾选值接受 是/否/有/无 与 markdown checkbox [x]/[X]/[✓]
        # （否则 Doc-Gate 判完整、observer 判缺失 → 覆盖率漏计，2026-08-22 数据可信度审计 F3）
        _CHECKED = ("是", "否", "有", "无", "x", "X", "✓", "√")
        for num, name, choice in items:
            if choice.strip() not in _CHECKED:
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
    if log_dir.is_dir():
        for path in log_dir.glob("*.log"):
            try:
                content = path.read_text(encoding="utf-8", errors="replace")
                # M7: 清洗 ANSI 色码（\x1b[...m），否则正则匹配不到 ⚙ 工具名 → 假数据 0 次
                # 实测日志形态：`⚙ \x1b[0m ccc-kb_kb_search`（glyph 与工具名间夹色码复位）
                content = re.sub(r"\x1b\[[0-9;]*[A-Za-z]?", "", content)
                # 兼容两种痕迹形态：`⚙ ccc-kb_kb_search`（工具调用痕迹）与 `⚙️ kb_search`（emoji 变体）
                calls = re.findall(r"⚙[️️]?\s*(?:ccc-kb_kb_|hp-kb_|kb_)\w+", content)
                total_calls += len(calls)
            except Exception:
                pass
    # 失败数无法从原始日志判定（failed_calls 无来源）——不再伪造 100% 成功率；
    # call_success_rate=None 表示「无法从日志判定失败」，由消费端显式标注而非虚报。
    return {
        "opencode_mcp_enabled": opencode_ok,
        "claude_mcp_enabled": claude_ok,
        "total_calls_observed": total_calls,
        "call_success_rate": None,
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
    # 通过 ≠ 关闭：通过必须 machine_audit_passed=True（卡文真机审结论），
    # 已关闭但无机审通过 = 假关闭/门禁绕过，单列红旗计数，不混入「通过率」。
    # 此前 passed_count = machine_audit_passed OR state==已关闭，把「关闭率」冒充「机审通过率」，
    # 实测近 30 卡恒 100% 而真实机审通过率仅 52.8%——正是假关闭事故前的假绿指标。
    passed_count = sum(1 for item in processed_cards if item.machine_audit_passed)
    closed_count = sum(1 for item in processed_cards if base_state(item.state) == "已关闭")
    closed_without_audit = sum(
        1
        for item in processed_cards
        if base_state(item.state) == "已关闭" and not item.machine_audit_passed
    )
    rejected_count = sum(1 for item in processed_cards if base_state(item.state) == "打回" or item.reject_count > 0)
    passed_rate = passed_count / total_processed * 100.0 if total_processed > 0 else 0.0
    closed_rate = closed_count / total_processed * 100.0 if total_processed > 0 else 0.0
    rejected_rate = rejected_count / total_processed * 100.0 if total_processed > 0 else 0.0
    return {
        "processed_cards_count": total_processed,
        "passed_count": passed_count,
        "closed_count": closed_count,
        "closed_without_audit": closed_without_audit,
        "rejected_count": rejected_count,
        "passed_rate_pct": passed_rate,
        "closed_rate_pct": closed_rate,
        "rejected_rate_pct": rejected_rate,
    }


def gather_audit_hit_rate() -> dict[str, Any]:
    """指标 5：机审命中率台账（机审 v4 · 2026-08-14）。

    读 data/audit/ledger.jsonl，统计 hit 已判定记录的命中比例。
    """
    try:
        from server.board.audit_ledger import hit_rate

        return hit_rate()
    except Exception:
        return {"total": 0, "hits": 0, "misses": 0, "hit_rate": None, "error": "ledger 不可读"}


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
    audit_hit = gather_audit_hit_rate()
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
    # F1：成功率无法从日志判定 → 显式标注「未统计」，不虚报 100%
    _mcp_success_display = (
        "未统计（日志无法判定失败）" if mcp["call_success_rate"] is None else f"{mcp['call_success_rate']:.1f}%"
    )
    report_content = (
        f"# 2017 Agent Skill/MCP 优化生效观测报告 ({today})\n\n"
        f"> 报告时间：{today} · 观测执行体：Loop Observer\n\n"
        f"## 1. 观测结论\n\n- **生效评估**：**{conclusion}生效**\n- **核心证据**：{evidence}\n\n"
        f"## 2. 4 项观测指标实测值\n\n### 指标 1：执行体 ccc-kb MCP 检索接入\n"
        f"- **OpenCode 配置状态**：{('已启用 (Active)' if mcp['opencode_mcp_enabled'] else '未启用 (Inactive)')}\n"
        f"- **Claude Code 配置状态**：{('已启用 (Active)' if mcp['claude_mcp_enabled'] else '未启用 (Inactive)')}\n"
        f"- **观测到实际调用次数**：{mcp['total_calls_observed']} 次\n"
        f"- **调用成功率**：{_mcp_success_display}\n\n"
        f"### 指标 2：维护区四问覆盖率 (Doc-Gate)\n"
        f"- **已回写/已关闭卡总数**：{maint['total_completed_cards']} 张\n"
        f"- **维护区齐全卡数量**：{maint['complete_maintenance_cards']} 张\n"
        f"- **覆盖率**：{maint['maintenance_coverage_pct']:.1f}%\n\n"
        f"### 指标 3：教训回流率\n"
        f"- **新卡总数**：{lesson['total_new_cards']} 张\n"
        f"- **已回流教训卡数量**：{lesson['recirculated_lessons_cards']} 张\n"
        f"- **教训回流率**：{lesson['lesson_recirculation_rate_pct']:.1f}%\n\n"
        f"### 指标 4：验收通过率/打回率趋势 (近 30 卡)\n"
        f"- **近 30 卡实测样本数**：{audit['processed_cards_count']} 张\n"
        f"- **机审通过数 (真机审 flag=True)**：{audit['passed_count']} 张 (占比：{audit['passed_rate_pct']:.1f}%)\n"
        f"- **已关闭数**：{audit['closed_count']} 张 (关闭率：{audit['closed_rate_pct']:.1f}%)\n"
        f"- **已关闭但无机审通过 (假关闭红旗)**：{audit['closed_without_audit']} 张\n"
        f"- **打回数 (及曾打回)**：{audit['rejected_count']} 张 (占比：{audit['rejected_rate_pct']:.1f}%)\n\n"
        f"### 指标 5：机审命中率台账 (机审 v4 · 近 50 已判定)\n"
        f"- **已判定审计数**：{audit_hit['total']} 条\n"
        f"- **命中数**：{audit_hit['hits']} 条\n"
        f"- **未命中数**：{audit_hit['misses']} 条\n"
        f"- **命中率**：{('%.1f%%' % (audit_hit['hit_rate'] * 100)) if audit_hit['hit_rate'] is not None else '暂无'}\n\n"
        f"## 3. 功能巡查 (Playwright Web Smoke Test)\n\n"
        f"- **巡查状态**：{pw['status_str']}\n- **巡查详情**：\n"
        f"  - `/health` 接口：{pw['health_status']}\n"
        f"  - `/config` 接口：{pw['config_status']}\n"
        f"  - 主页加载：{pw['main_status']}\n"
    )
    try:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(report_content, encoding="utf-8")
    except Exception as e:
        print(f"写入观测报告失败: {e}", file=sys.stderr)
    return {"conclusion": conclusion, "mcp": mcp, "maint": maint, "lesson": lesson, "audit": audit, "audit_hit": audit_hit, "pw": pw}


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


def _loop_drafts_enabled() -> bool:
    """ccc077 治理：Loop 自动草稿写入开关（CCC_LOOP_OBSERVER_DRAFTS）。

    默认 off（生产行为保守化）：off 时 observer 不产生任何草稿文件写入，
    docs/projects/<p>/roadmap.md 正文对自动链路只读。
    接受 1/true/yes/on（大小写不敏感），其余一律视为 off。
    """
    return os.environ.get("CCC_LOOP_OBSERVER_DRAFTS", "").strip().lower() in ("1", "true", "yes", "on")


def _loop_drafts_dir(base_dir: str | os.PathLike[str] | None = None) -> Path:
    """ccc077 治理：巡查草稿专用目录 <data>/drafts/roadmap/。

    base_dir 显式传入时优先（run_observer 传 cfg 解析后的 DATA_DIR）；
    否则依次回退 CCC_DATA_DIR / DATA_DIR / PROJECT_ROOT/data（绝对路径兜底，
    避免相对 CWD 的 "data" 在调度器工作目录漂移时写错位置）。
    """
    if base_dir is not None:
        base = Path(base_dir)
    else:
        base = os.environ.get("CCC_DATA_DIR") or os.environ.get("DATA_DIR") or (PROJECT_ROOT / "data")
        base = Path(base)
    return base.resolve() / "drafts" / "roadmap"


def write_roadmap_draft(
    project: str,
    description: str,
    *,
    draft_type: str = "问题",
    source: str = "Loop巡查",
    base_dir: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    """Loop 巡查集成：将发现的问题写入巡查草稿池（ccc077 治理版）。

    ccc077（2026-08-24 地基加固）：自动链路与项目 roadmap 正文解耦——
    - 开关 CCC_LOOP_OBSERVER_DRAFTS 默认 off：直接跳过，零文件写入；
    - on 时追加式写入 <data>/drafts/roadmap/<project>-draft.md（每行一条草案），
      不再调用 server.board.roadmap.create_draft，不再触碰 docs/projects 正文
      （正文对自动链路只读化；人工流程对 roadmap 的写路径完全不变）。

    Args:
        project: 项目前缀（如 ccc, clw, hp 等）
        description: 巡查发现的问题描述
        draft_type: 草案类型，默认 "问题"
        source: 来源标识，默认 "Loop巡查"
        base_dir: 数据根目录（可选；run_observer 传 cfg 的 DATA_DIR）

    Returns:
        dict: {"ok": True, "draft": title, "path": ...}；
              off 时 {"ok": True, "skipped": True, "reason": "loop_observer_drafts_disabled"}；
              重复描述 {"ok": True, "skipped": True, "reason": "duplicate"}
    """
    title = f"[{draft_type}][{source}] {description}"

    # ccc077：默认 off → 直接跳过（不 import 写接口、不触碰任何文件）
    if not _loop_drafts_enabled():
        logger.debug("CCC_LOOP_OBSERVER_DRAFTS=off，跳过巡查草稿写入：%s", title)
        return {"ok": True, "skipped": True, "reason": "loop_observer_drafts_disabled"}

    from datetime import date

    drafts_dir = _loop_drafts_dir(base_dir)
    try:
        drafts_dir.mkdir(parents=True, exist_ok=True)
        draft_file = drafts_dir / f"{project}-draft.md"

        # 去重检查：文件中已有相同描述的草案行则跳过（保持原去重语义）
        existing_lines: list[str] = []
        if draft_file.is_file():
            existing_lines = [
                line for line in draft_file.read_text(encoding="utf-8").splitlines() if line.strip()
            ]
            for line in existing_lines:
                if description in line:
                    return {
                        "ok": True,
                        "draft": line.strip(),
                        "skipped": True,
                        "reason": "duplicate",
                        "path": str(draft_file),
                    }

        line = f"- [{draft_type}][{source}] {description} · 日期：{date.today().isoformat()}"
        if not existing_lines and not draft_file.exists():
            header = f"# {project} 巡查草稿池（loop-observer 自动写入 · ccc077 治理）\n\n"
            draft_file.write_text(header + line + "\n", encoding="utf-8")
        else:
            with open(draft_file, "a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        logger.info("巡查草稿已落 %s：%s", draft_file, title)
        return {"ok": True, "draft": title, "path": str(draft_file)}
    except Exception as e:
        logger.error("巡查草稿写入失败（%s/%s）: %s", project, description[:40], e)
        return {"error": str(e)}


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


if __name__ == "__main__":
    main()
