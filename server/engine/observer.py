"""server/engine/observer.py — 逆向巡查与一致性交叉验证 Agent (S5 · 2026-08-09)

通过对「线路图 ↔ 计划 ↔ 看板」三层进行比对，自动发现漂移、失配并进行交叉验证。
"""

from __future__ import annotations

import argparse
import os
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from server.board.registry import load_projects
from server.board.loader import load_dispatch_cards
from server.board.plans import list_plans
from server.board.models import base_state

REPO_ROOT = Path(__file__).resolve().parents[2]


def scan_card_files(dispatch_dir: Path) -> list[Path]:
    """扫描所有任务卡 md 文件"""
    files = []
    if not dispatch_dir.exists():
        return files
    for p in dispatch_dir.glob("**/*.md"):
        if p.is_file() and p.name not in ("README.md", "T-mapping.md"):
            try:
                # 检查是否为合法的任务卡卡头
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
            match = re.search(r"^\s*([^：\s][^：]*?)\s*[:：]\s*(.+?)\s*$", part.strip())
            if match:
                meta[match.group(1).strip()] = match.group(2).strip()
    return meta


def run_patrol(repo_root: Path) -> list[dict[str, Any]]:
    """运行治理巡查与逆向巡查，执行交叉验证。"""
    findings: list[dict[str, Any]] = []

    # 1. 加载数据
    projects = load_projects(str(repo_root / "docs" / "projects" / "registry.yaml"))
    cards = load_dispatch_cards(str(repo_root / "docs" / "dispatch"))
    plans = list_plans(repo_root)

    card_status = {c.id: base_state(c.state) for c in cards}

    # 2. 治理巡查 (Card 6) & 逆向巡查 (Card 7) 断言

    # 断言 1: roadmap.md 业务线路缺失 (Governance)
    roadmap_path = repo_root / "docs" / "roadmap.md"
    if roadmap_path.exists():
        roadmap_content = roadmap_path.read_text(encoding="utf-8")
        for p in projects:
            if p.taskable and p.prefix:
                # 正则匹配 ## 业务线路（<prefix>）
                pattern = re.compile(rf"##\s*业务线路[（(]{p.prefix}[）)]", re.I)
                if not pattern.search(roadmap_content):
                    findings.append({
                        "type": "governance",
                        "assertion": 1,
                        "acting_on": p.prefix,
                        "severity": "YELLOW",
                        "msg": f"项目 {p.prefix} 缺失对应的 业务线路（{p.prefix}）段落。",
                        "evidence": f"docs/roadmap.md:1",
                        "cross_confirm": 0.0,
                    })

    # 扫描卡文件提取细节
    dispatch_dir = repo_root / "docs" / "dispatch"
    card_files = scan_card_files(dispatch_dir)

    for cp in card_files:
        try:
            content = cp.read_text(encoding="utf-8")
        except Exception:
            continue
        rel_path = str(cp.relative_to(repo_root))
        meta = parse_metadata(content)

        # 提取卡 ID
        title_match = re.search(r"^#\s*任务卡\s*(\S+)", content, re.MULTILINE)
        card_id = title_match.group(1) if title_match else cp.stem

        # 断言 2: 卡头关联字段格式 (Governance)
        related = meta.get("关联", "").strip()
        if related and related != "无":
            token = re.split(r"[：:\s（(]", related)[0].strip()
            if not re.match(r"^[a-zA-Z0-9]+-plan-\d+$", token):
                # 找到 关联 所在行号
                line_idx = 1
                for idx, line in enumerate(content.splitlines(), 1):
                    if "关联：" in line or "关联:" in line:
                        line_idx = idx
                        break
                findings.append({
                    "type": "governance",
                    "assertion": 2,
                    "acting_on": card_id,
                    "severity": "YELLOW",
                    "msg": f"卡 {card_id} 的关联字段 '{related}' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。",
                    "evidence": f"{rel_path}:{line_idx}",
                    "cross_confirm": 0.0,
                })

        # 断言 6: 已关闭/已回写的卡缺维护区 (Governance)
        c_state = base_state(meta.get("状态", "未知"))
        if c_state in ("ignore", "已关闭", "已回写"):
            if "## 维护区" not in content:
                findings.append({
                    "type": "governance",
                    "assertion": 6,
                    "acting_on": card_id,
                    "severity": "YELLOW",
                    "msg": f"卡 {card_id} 处于已关闭/已回写状态，但缺失 ## 维护区 章节。",
                    "evidence": f"{rel_path}:1",
                    "cross_confirm": 0.0,
                })
            else:
                # 检查维护区内的占位符 [是/否] 或 [有/无]
                lines = content.splitlines()
                has_placeholder = False
                placeholder_line = 1
                for idx, line in enumerate(lines, 1):
                    if "[是/否]" in line or "[有/无]" in line:
                        has_placeholder = True
                        placeholder_line = idx
                        break
                if has_placeholder:
                    findings.append({
                        "type": "governance",
                        "assertion": 6,
                        "acting_on": card_id,
                        "severity": "YELLOW",
                        "msg": f"卡 {card_id} 的 维护区 包含未回答 of 占位符 [是/否] 或 [有/无]。",
                        "evidence": f"{rel_path}:{placeholder_line}",
                        "cross_confirm": 0.0,
                    })

    # 断言 5: 路线图卡状态一致性 (Governance)
    if roadmap_path.exists():
        roadmap_content = roadmap_path.read_text(encoding="utf-8")
        row_pattern = re.compile(r"^\s*\|\s*\*\*([a-zA-Z0-9_-]+)\*\*\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|", re.MULTILINE)
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
                        findings.append({
                            "type": "governance",
                            "assertion": 5,
                            "acting_on": ref_card_id,
                            "severity": "YELLOW",
                            "msg": f"路线图状态 '{status_cell}' (期望 {expected_state}) 与卡真实状态 '{actual_state}' 漂移。",
                            "evidence": f"docs/roadmap.md:{idx}",
                            "cross_confirm": 0.0,
                        })

    # 方案与卡双向关联及状态巡查
    for plan in plans:
        plan_id = plan["id"]
        plan_status = plan["status"]
        plan_cards_str = plan.get("cards", "").strip()
        plan_path = plan["path"]

        # 关联卡集合
        if not plan_cards_str or plan_cards_str == "无":
            associated_cards = []
        else:
            associated_cards = [c.strip() for c in plan_cards_str.split(",") if c.strip()]

        # 1. 方案已完成但无关联卡 (Reverse View)
        if plan_status == "已完成" and not associated_cards:
            findings.append({
                "type": "reverse",
                "assertion": 3,
                "acting_on": plan_id,
                "severity": "YELLOW",
                "msg": f"方案 {plan_id} 处于已完成状态，但没有关联任何开发卡。",
                "evidence": f"{plan_path}:1",
                "cross_confirm": 0.0,
            })

        # 2. 方案关联不存在的卡 (Governance View Assertion 4)
        for ac in associated_cards:
            if ac not in card_status:
                findings.append({
                    "type": "governance",
                    "assertion": 4,
                    "acting_on": plan_id,
                    "severity": "YELLOW",
                    "msg": f"方案 {plan_id} 引用了不存在的卡 {ac}。",
                    "evidence": f"{plan_path}:1",
                    "cross_confirm": 0.0,
                })

        # 3. 方案已完成但有关联卡未关闭 (Governance View Assertion 3)
        if plan_status == "已完成" and associated_cards:
            unclosed_cards = [ac for ac in associated_cards if ac in card_status and card_status[ac] != "已关闭"]
            if unclosed_cards:
                findings.append({
                    "type": "governance",
                    "assertion": 3,
                    "acting_on": plan_id,
                    "severity": "YELLOW",
                    "msg": f"方案 {plan_id} 已推进至 '已完成'，但其关联卡 {', '.join(unclosed_cards)} 尚未关闭。",
                    "evidence": f"{plan_path}:1",
                    "cross_confirm": 0.0,
                })

        # 4. 卡全关但方案没推进 (Governance / Reverse Double-directional View)
        if plan_status != "已完成" and associated_cards:
            all_closed = True
            for ac in associated_cards:
                if card_status.get(ac) != "已关闭":
                    all_closed = False
                    break
            if all_closed:
                # 治理视角：三层一致性断链 (Governance)
                findings.append({
                    "type": "governance",
                    "assertion": 3,
                    "acting_on": plan_id,
                    "severity": "YELLOW",
                    "msg": f"方案 {plan_id} 关联卡已全部关闭，但方案状态仍为 '{plan_status}' (未推进至 '已完成')。",
                    "evidence": f"{plan_path}:1",
                    "cross_confirm": 0.0,
                })
                # 逆向视角：反推方案可行性 (Reverse)
                findings.append({
                    "type": "reverse",
                    "assertion": 3,
                    "acting_on": plan_id,
                    "severity": "YELLOW",
                    "msg": f"从已关闭卡反推，方案 {plan_id} 应该已完成，但实际状态仍处于 '{plan_status}'。",
                    "evidence": f"{plan_path}:1",
                    "cross_confirm": 0.0,
                })

        # 5. 反向反推：已关闭卡关联的方案未推进到已完成 (Reverse View / Governance View)
        for ac in associated_cards:
            if card_status.get(ac) == "已关闭" and plan_status != "已完成":
                # 针对具体的卡 ac 报告两个视角的异常，使其在 ac 上产生交叉验证！
                findings.append({
                    "type": "reverse",
                    "assertion": 7,
                    "acting_on": ac,
                    "severity": "YELLOW",
                    "msg": f"开发卡 {ac} 已关闭，但其关联方案 {plan_id} 的状态仍为 '{plan_status}' (未完成)。",
                    "evidence": f"docs/dispatch/{ac}.md:1" if (dispatch_dir / f"{ac}.md").exists() else f"{plan_path}:1",
                    "cross_confirm": 0.0,
                })
                # 如果这个卡本身就因为治理原因 (比如缺维护区四问) 被命中
                # 那么 ac 作为 acting_on 就会同时具备 governance 和 reverse 两个独立视角的异常！

    # 3. 交叉验证合并 (Cross Confirm)
    # 同一 acting_on 实体，若同时有 governance 视图 findings 与 reverse 视图 findings，升级为 RED 强红旗并设 cross_confirm = 1.0
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
    """产出巡查报告至 docs/notes/ 目录"""
    today_str = datetime.now().strftime("%Y-%m-%d")
    report_name = f"{today_str}-ccc-patrol.md"
    notes_dir = repo_root / "docs" / "notes"
    notes_dir.mkdir(parents=True, exist_ok=True)
    report_path = notes_dir / report_name

    red_cnt = sum(1 for f in findings if f["severity"] == "RED")
    yel_cnt = sum(1 for f in findings if f["severity"] == "YELLOW")
    blu_cnt = sum(1 for f in findings if f["severity"] == "BLUE")

    content = f"""# CCC 巡查与一致性交叉验证风险报告 ({today_str})

> 自动生成时间：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
> 风险概览：🔴 红旗 {red_cnt} 处 · 🟡 黄旗 {yel_cnt} 处 · 🔵 蓝旗 {blu_cnt} 处

---

## 巡查发现清单

| 严重程度 | 对象 (acting_on) | 发现分类 | 交叉确认 | 证据 (位置) | 详细描述 |
| :---: | :--- | :--- | :---: | :--- | :--- |
"""

    for f in sorted(findings, key=lambda x: (x["severity"] == "RED", x["acting_on"]), reverse=True):
        sev_icon = "🔴 红旗" if f["severity"] == "RED" else "🟡 黄旗" if f["severity"] == "YELLOW" else "🔵 蓝旗"
        cross_cell = "✅ 交叉确认" if f.get("cross_confirm", 0.0) == 1.0 else "—"
        f_type = "逆向巡查" if f["type"] == "reverse" else "治理一致性"
        content += f"| {sev_icon} | `{f['acting_on']}` | {f_type} | {cross_cell} | `{f['evidence']}` | {f['msg']} |\n"

    content += """
---
*本报告由 CCC 逆向巡查 Agent 自动生成并输出。只读，仅记录状态，不修改任何项目数据文件。*
"""
    report_path.write_text(content, encoding="utf-8")
    return report_path


def main():
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


if __name__ == "__main__":
    main()
