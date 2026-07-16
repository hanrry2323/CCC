#!/usr/bin/env python3
"""ccc-daily-diff-review.py — 日 diff 全审骨架（v0.41 / P3）

输入：自上次水位线或 --since 的 git diff
输出：决策枚举 A–J → 可选自动建 backlog + wake Engine

用法：
  python3 scripts/ccc-daily-diff-review.py --workspace ~/program/CCC [--dry-run]
  python3 scripts/ccc-daily-diff-review.py --since HEAD~20 --apply

默认 dry-run（只写报告）。--apply 才建卡/唤醒。
Claude 审查：有 CCC_DAILY_REVIEW_LLM=1 时调 claude；否则走启发式规则。
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

DECISIONS = {
    "A": "noop — 无实质 diff",
    "B": "ack — 小改且干净",
    "C": "spawn_fix — 明确 bug/回归 → backlog + wake",
    "D": "quarantine_alert — 安全风险，禁止自动开发",
    "E": "spawn_reconcile — 范围漂移",
    "F": "spawn_fix — 测试红",
    "G": "human_gate — 需人工",
    "H": "abort_review — 工具失败",
    "I": "spawn_evolve — 仅 invent 模式",
    "J": "dedupe — 队列已有同类",
}


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _git(ws: Path, *args: str) -> tuple[int, str]:
    r = subprocess.run(
        ["git", *args], cwd=str(ws), capture_output=True, text=True, timeout=60
    )
    return r.returncode, ((r.stdout or "") + (r.stderr or "")).strip()


def _watermark_path(ws: Path) -> Path:
    return ws / ".ccc" / "stats" / "daily-review-watermark.json"


def load_watermark(ws: Path) -> str | None:
    p = _watermark_path(ws)
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text()).get("sha")
    except (OSError, json.JSONDecodeError):
        return None


def save_watermark(ws: Path, sha: str) -> None:
    p = _watermark_path(ws)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps({"sha": sha, "ts": _now()}, indent=2) + "\n", encoding="utf-8"
    )


def heuristic_decide(diff_stat: str, diff_text: str, mode: str) -> dict:
    """无 LLM 时的保守规则（可被 Claude 覆盖）。"""
    if not diff_stat.strip() and not diff_text.strip():
        return {"decision": "A", "rationale": "empty diff", "spawn": None}
    low = (diff_stat + "\n" + diff_text[:8000]).lower()
    if any(k in low for k in ("api_key", "secret", "password", "private_key", "begin rsa")):
        return {
            "decision": "D",
            "rationale": "possible secret in diff",
            "spawn": None,
        }
    if "test" in low and ("fail" in low or "error" in low or "xfail" in low):
        return {
            "decision": "F",
            "rationale": "test-related failure signals in diff/log",
            "spawn": {
                "title": "daily-fix: test signals in recent diff",
                "description": diff_stat[:2000],
            },
        }
    # 默认 ack 小改；大 diff → human_gate
    lines = 0
    for part in diff_stat.split():
        if part.isdigit():
            lines += int(part)
    if lines > 400:
        return {
            "decision": "G",
            "rationale": f"large diff (~{lines} lines) needs human",
            "spawn": None,
        }
    if mode != "invent" and "evolve" in low:
        return {"decision": "B", "rationale": "non-invent: ack only", "spawn": None}
    return {"decision": "B", "rationale": "heuristic ack", "spawn": None}


def maybe_spawn(ws: Path, spawn: dict | None, decision: str, *, apply: bool) -> dict | None:
    if not spawn or not apply:
        return None
    if decision not in ("C", "E", "F", "I"):
        return None
    if decision == "I":
        from _ccc_control import may_invent

        if not may_invent():
            return {"skipped": True, "reason": "invent not allowed"}

    tid = f"daily-{decision.lower()}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    task = {
        "id": tid,
        "title": spawn.get("title") or tid,
        "description": spawn.get("description") or "",
        "status": "backlog",
        "created_at": _now(),
        "updated_at": _now(),
        "schema_version": "1.2",
        "complexity": "medium",
        "tags": ["daily-review", f"decision-{decision}"],
    }
    from board.context import set_workspace
    from _board_store import FileBoardStore

    set_workspace(ws)
    store = FileBoardStore(ws)
    ok = store.create_task(task, column="backlog")
    wake = None
    if ok:
        from _engine_wake import ensure_engine_for_task

        wake = ensure_engine_for_task(reason="daily_review", task_id=tid)
    return {"created": ok, "task_id": tid, "engine_wake": wake}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="CCC daily diff review")
    ap.add_argument("--workspace", default=str(SCRIPTS.parent))
    ap.add_argument("--since", default="", help="git rev (default: watermark or HEAD~1)")
    ap.add_argument("--apply", action="store_true", help="建卡+wake（默认只报告）")
    ap.add_argument("--dry-run", action="store_true", help="强制只报告")
    args = ap.parse_args(argv)

    ws = Path(args.workspace).resolve()
    apply = bool(args.apply) and not args.dry_run

    rc, head = _git(ws, "rev-parse", "HEAD")
    if rc != 0:
        print(json.dumps({"ok": False, "error": "not a git repo", "decision": "H"}))
        return 1

    since = args.since or load_watermark(ws) or "HEAD~1"
    _, diff_stat = _git(ws, "diff", "--stat", f"{since}..HEAD")
    _, diff_text = _git(ws, "diff", f"{since}..HEAD")

    from _ccc_control import get_mode

    mode = get_mode()
    result = heuristic_decide(diff_stat, diff_text, mode)

    # 可选 LLM（骨架：环境开关；未开则跳过）
    if os.environ.get("CCC_DAILY_REVIEW_LLM", "").strip() in ("1", "true", "yes"):
        result["llm"] = "not_wired_in_skeleton"  # P3 后续接 claude -p JSON

    spawn_out = maybe_spawn(ws, result.get("spawn"), result["decision"], apply=apply)

    report_dir = ws / ".ccc" / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    day = datetime.now().strftime("%Y-%m-%d")
    report_path = report_dir / f"daily-review-{day}.md"
    report_path.write_text(
        f"# Daily Diff Review {day}\n\n"
        f"- ts: {_now()}\n"
        f"- since: `{since}`\n"
        f"- head: `{head}`\n"
        f"- decision: **{result['decision']}** — {DECISIONS.get(result['decision'], '')}\n"
        f"- rationale: {result.get('rationale')}\n"
        f"- apply: {apply}\n"
        f"- spawn: {json.dumps(spawn_out, ensure_ascii=False)}\n\n"
        f"## Diff stat\n```\n{diff_stat[:4000]}\n```\n",
        encoding="utf-8",
    )

    if apply and result["decision"] in ("A", "B"):
        save_watermark(ws, head)

    out = {
        "ok": True,
        "decision": result["decision"],
        "label": DECISIONS.get(result["decision"]),
        "rationale": result.get("rationale"),
        "since": since,
        "head": head,
        "apply": apply,
        "spawn": spawn_out,
        "report": str(report_path),
        "decisions_catalog": DECISIONS,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
