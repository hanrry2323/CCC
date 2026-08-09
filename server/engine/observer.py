"""Loop Observer 只读巡查 Agent — 治理一致性巡查逻辑 (ccc028)

依据：ccc-plan-011 阶段二 2.2 + 探查 F 真实失配样本。
对 路线图 (roadmap.md) <-> 计划 (plans) <-> 看板 (dispatch cards) 三层进行一致性校验。
"""

from __future__ import annotations

import os
import re
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

from server.board.registry import load_projects
from server.board.loader import load_dispatch_cards, parse_card, scan_dispatch_files, get_archive_dir, scan_archive_files
from server.board.plans import list_plans

logger = logging.getLogger("ccc.observer")


def get_base_state(state: str) -> str:
    """状态归一化：取括号前的基础状态（打回/待分派/执行中/已回写/已关闭）。"""
    if not state or state.strip() == "未知":
        return "未知"
    return re.split(r"[（(]", state, maxsplit=1)[0].strip()


def parse_card_related(content: str) -> str:
    """解析卡正文中的 '关联：' 字段。"""
    for line in content.splitlines():
        line = line.strip()
        if not line.startswith(">"):
            continue
        body = line.lstrip("> ").strip()
        for part in re.split(r"·", body):
            part = part.strip()
            m = re.match(r"^\s*关联\s*[:：]\s*(.+?)\s*$", part)
            if m:
                return m.group(1).strip()
    return ""


def run_observer(cfg: dict[str, Any] | None = None) -> tuple[bool, dict[str, Any]]:
    """执行治理一致性巡查，生成报告落 docs/notes/。"""
    cfg = cfg or {}
    
    # 1. 初始化路径
    repo_root = Path(cfg.get("REPO_ROOT") or Path(__file__).resolve().parents[2])
    dispatch_dir = repo_root / "docs" / "dispatch"
    notes_dir = repo_root / "docs" / "notes"
    notes_dir.mkdir(parents=True, exist_ok=True)
    
    # 2. 读取基准数据
    try:
        projects = load_projects()
        cards = load_dispatch_cards(dispatch_dir, include_archived=True)
        plans = list_plans(repo_root)
    except Exception as e:
        logger.exception("加载基准数据失败")
        return False, {"error": f"Failed to load base data: {e}"}

    # 3. 构建快速查找表
    card_by_id = {c.id: c for c in cards}
    plan_by_id = {p["id"]: p for p in plans}
    
    # 扫描所有卡文件构建路径映射
    card_paths: dict[str, tuple[str, Path]] = {}
    try:
        disk_files = scan_dispatch_files(dispatch_dir)
        try:
            archive_dir = get_archive_dir(dispatch_dir)
            archive_files = scan_archive_files(archive_dir)
        except Exception:
            archive_files = []
        all_card_files = disk_files + archive_files
        
        for path in all_card_files:
            try:
                item = parse_card(path)
                rel_path = str(path.relative_to(repo_root))
                card_paths[item.id] = (rel_path, path)
            except Exception:
                continue
    except Exception as e:
        logger.error(f"构建卡路径映射失败: {e}")

    findings: list[dict[str, str]] = []

    # ── 断言 1: 每个 taskable 项目 roadmap.md 有「业务线路（<prefix>）」段 ──
    roadmap_path = repo_root / "docs" / "roadmap.md"
    if roadmap_path.is_file():
        roadmap_content = roadmap_path.read_text(encoding="utf-8")
        for p in projects:
            if p.taskable and p.prefix and p.prefix != "ccc":
                prefix = p.prefix
                pattern = r"##\s*业务线路[（(]" + re.escape(prefix) + r"[）)]"
                if not re.search(pattern, roadmap_content):
                    findings.append({
                        "severity": "红旗",
                        "acting_on": "roadmap.md",
                        "evidence": "docs/roadmap.md:1",
                        "message": f"项目 {p.id} ({p.display}) 是 taskable 且有前缀 {prefix}，但在 roadmap.md 中缺失「业务线路（{prefix}）」段落。"
                    })
    else:
        findings.append({
            "severity": "红旗",
            "acting_on": "roadmap.md",
            "evidence": "docs/roadmap.md:1",
            "message": "roadmap.md 文件缺失。"
        })

    # ── 断言 2: 卡头「关联」字段是方案编号 (首版非 LLM 做判定/标记待 LLM) ──
    for card_id, (rel_path, path) in card_paths.items():
        try:
            content = path.read_text(encoding="utf-8")
            related = parse_card_related(content)
            if related:
                # 若不符合 <prefix>-plan-<NNN> 模式
                if not re.match(r"^[a-zA-Z0-9]+-plan-[0-9]{3}", related):
                    findings.append({
                        "severity": "蓝旗",
                        "acting_on": card_id,
                        "evidence": f"{rel_path}:3",
                        "message": f"卡头「关联」字段 '{related}' 不是规范的方案编号（需要 LLM 语义判定或手动修复）。"
                    })
        except Exception:
            continue

    # ── 断言 3: 方案「已完成」 → 关联卡全「已关闭」 ──
    for p in plans:
        if p.get("status") == "已完成":
            cards_str = p.get("cards", "")
            associated_card_ids = re.findall(r"[a-zA-Z0-9]+", cards_str)
            associated_card_ids = [cid for cid in associated_card_ids if cid.lower() != "无"]
            for cid in associated_card_ids:
                card = card_by_id.get(cid)
                if card:
                    base_state = get_base_state(card.state)
                    if base_state != "已关闭":
                        findings.append({
                            "severity": "红旗",
                            "acting_on": p["id"],
                            "evidence": f"{p['path']}:3",
                            "message": f"方案 {p['id']} 已设为「已完成」，但关联卡 {cid} 状态为「{card.state}」（未关闭）。"
                        })

    # ── 断言 4: 方案「关联卡」引用的卡存在 / 卡引用的方案存在 ──
    # 1. 方案 -> 卡
    for p in plans:
        cards_str = p.get("cards", "")
        associated_card_ids = re.findall(r"[a-zA-Z0-9]+", cards_str)
        associated_card_ids = [cid for cid in associated_card_ids if cid.lower() != "无"]
        for cid in associated_card_ids:
            if cid not in card_by_id:
                findings.append({
                    "severity": "红旗",
                    "acting_on": p["id"],
                    "evidence": f"{p['path']}:3",
                    "message": f"方案 {p['id']} 关联卡引用的 {cid} 不存在。"
                })
                
    # 2. 卡 -> 方案 (卡引用不存在方案，即 "60+ 卡引用不存在方案等" 漂移样本)
    for card_id, (rel_path, path) in card_paths.items():
        try:
            content = path.read_text(encoding="utf-8")
            related = parse_card_related(content)
            if related:
                # 提取潜在方案编号
                plan_match = re.match(r"^([a-zA-Z0-9]+-plan-[0-9]{3})", related)
                if plan_match:
                    ref_plan_id = plan_match.group(1)
                    if ref_plan_id not in plan_by_id:
                        findings.append({
                            "severity": "红旗",
                            "acting_on": card_id,
                            "evidence": f"{rel_path}:3",
                            "message": f"任务卡 {card_id} 引用的关联方案 {ref_plan_id} 不存在。"
                        })
        except Exception:
            continue

    # ── 断言 5: roadmap 段落卡状态 = 看板真实卡状态 (hp004-006 漂移样本) ──
    if roadmap_path.is_file():
        # 按行解析 docs/roadmap.md 中的任务卡行
        # 例如: | **hp004** | ... | 已回写 (外仓 main... |
        card_row_re = re.compile(r"\|\s*\*\*([a-zA-Z0-9_-]+)\*\*\s*\|([^|]+)\|\s*([^|]+)\s*\|")
        lines = roadmap_content.splitlines()
        for idx, line in enumerate(lines, start=1):
            match = card_row_re.match(line)
            if match:
                ref_card_id = match.group(1).strip()
                roadmap_status = match.group(3).strip()
                
                card = card_by_id.get(ref_card_id)
                if card:
                    base_roadmap_state = get_base_state(roadmap_status)
                    base_actual_state = get_base_state(card.state)
                    if base_roadmap_state != base_actual_state:
                        findings.append({
                            "severity": "红旗",
                            "acting_on": "roadmap.md",
                            "evidence": f"docs/roadmap.md:{idx}",
                            "message": f"任务卡 {ref_card_id} 在 roadmap.md 中标注的状态为「{roadmap_status}」，但看板/卡片真实状态为「{card.state}」（状态失配）。"
                        })

    # ── 断言 6: 已关闭卡缺维护区四问 ──
    for card_id, (rel_path, path) in card_paths.items():
        card = card_by_id.get(card_id)
        if card and get_base_state(card.state) == "已关闭":
            try:
                content = path.read_text(encoding="utf-8")
                
                # 查找 ## 维护区
                maint_match = re.search(r"##\s*维护区", content)
                if not maint_match:
                    findings.append({
                        "severity": "黄旗",
                        "acting_on": card_id,
                        "evidence": f"{rel_path}:1",
                        "message": f"已关闭任务卡 {card_id} 缺失「## 维护区」段落。"
                    })
                else:
                    # 查找是否有未勾选/未填写的占位符
                    # 寻找 ## 维护区 行号
                    maint_line = 1
                    for l_idx, line in enumerate(content.splitlines(), start=1):
                        if "##" in line and "维护区" in line:
                            maint_line = l_idx
                            break
                    
                    placeholders = ["[是/否]", "[有/无]"]
                    found_placeholder = False
                    for ph in placeholders:
                        if ph in content:
                            found_placeholder = True
                            break
                            
                    if found_placeholder:
                        findings.append({
                            "severity": "黄旗",
                            "acting_on": card_id,
                            "evidence": f"{rel_path}:{maint_line}",
                            "message": f"已关闭任务卡 {card_id} 的「## 维护区」包含未填写的勾选占位符（如 [是/否] 或 [有/无]）。"
                        })
            except Exception:
                continue

    # 4. 按 Severity 排序: 红旗 -> 黄旗 -> 蓝旗
    severity_order = {"红旗": 0, "黄旗": 1, "蓝旗": 2}
    findings.sort(key=lambda f: (severity_order.get(f["severity"], 9), f["acting_on"]))

    # 5. 生成报告落 docs/notes/
    today_str = datetime.today().strftime("%Y-%m-%d")
    report_filename = f"{today_str}-ccc-patrol.md"
    report_path = notes_dir / report_filename
    
    red_count = sum(1 for f in findings if f["severity"] == "红旗")
    yellow_count = sum(1 for f in findings if f["severity"] == "黄旗")
    blue_count = sum(1 for f in findings if f["severity"] == "蓝旗")
    
    report_lines = [
        f"# 治理一致性巡查报告 ({today_str})",
        "",
        f"> 报告类型：三层断链自动发现 · 状态：已完成 · 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "> 项目：ccc",
        "",
        "## 1. 巡查统计",
        "",
        f"- 检查项目数：{len(projects)}",
        f"- 检查计划数：{len(plans)}",
        f"- 检查任务卡数：{len(cards)}",
        f"- 发现风险总数：{len(findings)}",
        f"  - 红旗 (Severity High)：{red_count}",
        f"  - 黄旗 (Severity Medium)：{yellow_count}",
        f"  - 蓝旗 (Severity Low)：{blue_count}",
        "",
        "## 2. 风险发现明细",
        "",
        "| 级别 | 检查对象 | 证据 (文件:行号) | 问题描述 |",
        "|------|----------|-----------------|----------|",
    ]
    
    for f in findings:
        report_lines.append(
            f"| {f['severity']} | {f['acting_on']} | {f['evidence']} | {f['message']} |"
        )
        
    try:
        report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
        logger.info(f"巡查报告已生成：{report_path}")
    except Exception as e:
        logger.error(f"写入巡查报告失败: {e}")

    summary = {
        "ok": True,
        "checked_projects": len(projects),
        "checked_plans": len(plans),
        "checked_cards": len(cards),
        "findings_count": len(findings),
        "red_flags": red_count,
        "yellow_flags": yellow_count,
        "blue_flags": blue_count,
        "report_path": str(report_path.relative_to(repo_root))
    }

    return True, summary


def main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Consistency Patrol Agent")
    parser.add_argument("--config", help="Path to config file")
    parser.add_argument("--once", action="store_true", help="Run once")
    args = parser.parse_args(argv)
    
    cfg = {}
    if args.config:
        try:
            from server.config.loader import load_config
            cfg = load_config(args.config)
        except Exception as e:
            print(f"Error loading config: {e}")
            
    ok, summary = run_observer(cfg)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
