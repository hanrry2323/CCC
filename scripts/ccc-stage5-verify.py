#!/usr/bin/env python3
"""ccc-stage5-verify.py — 阶段5 多任务闭环验证汇总器。

收集所有 intent-proposals 的 result.jsonl + board 状态 + Engine 日志，
生成结构化诊断报告，用于识别流程瓶颈与故障点。

Usage:
  ccc-stage5-verify --project qb --proposals-dir ~/program/apps/qb/.ccc/intent-proposals
  ccc-stage5-verify --project qb --engine-log ~/.ccc/logs/ccc-engine.log
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _collect_results(proposals_dir: Path) -> list[dict]:
    results: list[dict] = []
    for result_file in sorted(proposals_dir.glob("*.result.jsonl")):
        proposal_id = result_file.name.removesuffix(".result.jsonl")
        events: list[dict] = []
        for line in result_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                events.append({"status": "corrupt_line", "raw": line[:200]})
        results.append({"proposal_id": proposal_id, "events": events})
    return results


def _proposal_meta(proposals_dir: Path, proposal_id: str) -> dict:
    md = proposals_dir / f"{proposal_id}.md"
    if not md.is_file():
        return {}
    text = md.read_text(encoding="utf-8")
    meta: dict[str, str] = {}
    for line in text.splitlines():
        if line.startswith("---"):
            continue
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip().lower()] = v.strip()
    return meta


def _board_state(ws: Path, proposal_id: str) -> dict:
    """查 epic + work 卡在 board 各列的状态。"""
    epic_id = f"{proposal_id}-epic"
    out: dict[str, str] = {}
    for col in ("backlog", "planned", "in_progress", "testing", "verified", "released", "abnormal"):
        p = ws / ".ccc" / "board" / col / f"{epic_id}.jsonl"
        if p.is_file():
            out[f"epic:{col}"] = _read_card(p)
    # work 子卡
    for col in ("planned", "in_progress", "testing", "verified", "released", "abnormal"):
        for p in (ws / ".ccc" / "board" / col).glob(f"{epic_id}-w*.jsonl"):
            out[f"work:{p.name.removesuffix('.jsonl')}:{col}"] = _read_card(p)
    return out


def _read_card(path: Path) -> str:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("status", "?")
    except Exception:
        return "corrupt"


def _engine_events(engine_log: Path, proposals: list[dict]) -> dict[str, list[str]]:
    """从 Engine 日志提取每个 proposal 的关键事件。"""
    if not engine_log.is_file():
        return {}
    text = engine_log.read_text(encoding="utf-8", errors="replace")
    events: dict[str, list[str]] = {}
    for proposal in proposals:
        pid = proposal["proposal_id"]
        lines = [
            l.strip()
            for l in text.splitlines()
            if pid in l or (pid[:19] in l)  # prop-<ts> 前缀匹配
        ]
        events[pid] = lines[-30:]
    return events


def _main() -> int:
    parser = argparse.ArgumentParser(description="阶段5 多任务闭环验证汇总器")
    parser.add_argument("--project", required=True, help="project_id（qb）")
    parser.add_argument("--proposals-dir", default="", help="intent-proposals 目录")
    parser.add_argument("--workspace", default="", help="业务仓根路径")
    parser.add_argument("--engine-log", default="", help="Engine 日志路径")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()

    ws = Path(args.workspace) if args.workspace else Path.home() / "program" / "apps" / args.project
    proposals_dir = (
        Path(args.proposals_dir)
        if args.proposals_dir
        else ws / ".ccc" / "intent-proposals"
    )
    if not proposals_dir.is_dir():
        print(f"[error] proposals 目录不存在: {proposals_dir}", file=sys.stderr)
        return 1

    results = _collect_results(proposals_dir)
    if not results:
        print(f"[info] 无 result.jsonl（{proposals_dir}）")
        return 0

    engine_log = Path(args.engine_log) if args.engine_log else Path.home() / ".ccc" / "logs" / "ccc-engine.log"
    engine_events = _engine_events(engine_log, results)

    report: list[dict] = []
    for item in results:
        pid = item["proposal_id"]
        events = item["events"]
        meta = _proposal_meta(proposals_dir, pid)
        board = _board_state(ws, pid)

        # 事件流状态
        statuses = [e.get("status") for e in events]
        last_evt = events[-1] if events else {}
        timing = last_evt.get("timing_ms") or {}
        fallback = bool(last_evt.get("fallback"))
        final_status = last_evt.get("status", "unknown")
        error = last_evt.get("error", "")
        cards = int(last_evt.get("cards_produced") or 0)

        # 诊断
        issues: list[str] = []
        if not events:
            issues.append("无 result.jsonl 事件（可能从未触发 splitter）")
        if final_status == "failed":
            issues.append(f"拆卡失败: {error}")
        if final_status == "ok" and not any(":released" in k for k in board):
            issues.append(f"拆卡 ok 但无 released（卡在 {sorted(set(v for k,v in board.items()))}）")
        if fallback:
            issues.append("fallback 拆卡（SDK 不可用）")
        if len(statuses) < 3:
            issues.append(f"事件流不完整: {statuses}")
        if board and not any(v == "released" for k, v in board.items() if k.startswith("epic")):
            issues.append(f"epic 未 done: {board}")

        report.append({
            "proposal_id": pid,
            "title": meta.get("title", "?"),
            "skill_ref": meta.get("skill_ref", "?"),
            "prompt_ref": meta.get("prompt_ref", "?"),
            "status": final_status,
            "cards": cards,
            "fallback": fallback,
            "timing_ms": timing,
            "board": board,
            "engine_events": engine_events.get(pid, []),
            "issues": issues,
        })

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    # 人类可读输出
    for r in report:
        print(f"=== {r['proposal_id']} ===")
        print(f"  title: {r['title']}")
        print(f"  skill: {r['skill_ref']}  prompt: {r['prompt_ref']}")
        print(f"  status: {r['status']}  cards={r['cards']}  fallback={r['fallback']}")
        t = r["timing_ms"]
        if t:
            print(f"  耗时(ms): read={t.get('read')} epic={t.get('create_epic')} "
                  f"fanout={t.get('fanout')} attach={t.get('attach')} wake={t.get('wake')} total={t.get('total')}")
        if r["board"]:
            print(f"  board: {r['board']}")
        if r["engine_events"]:
            print(f"  engine 事件({len(r['engine_events'])}):")
            for line in r["engine_events"][-8:]:
                print(f"    {line[:140]}")
        if r["issues"]:
            print(f"  ⚠ 问题: {r['issues']}")
        print()

    # 汇总统计
    ok = sum(1 for r in report if r["status"] == "ok")
    fail = sum(1 for r in report if r["status"] == "failed")
    released = sum(1 for r in report if any(":released" in k for k in r["board"]))
    fallback_n = sum(1 for r in report if r["fallback"])
    all_issues = [i for r in report for i in r["issues"]]
    print(f"=== 汇总: {len(report)} 任务 | ok={ok} fail={fail} released={released} "
          f"fallback={fallback_n} | 问题数={len(all_issues)} ===")
    for i in all_issues:
        print(f"  ⚠ {i}")
    return 0


if __name__ == "__main__":
    sys.exit(_main())
