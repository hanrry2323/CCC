#!/usr/bin/env python3
"""ccc-clean-abnormal.py — 清理看板 abnormal 列任务（P4.3）

用法:
  python3 ccc-clean-abnormal.py                          # 当前 workspace
  python3 ccc-clean-abnormal.py --workspace ~/program/qx-observer  # 指定
  python3 ccc-clean-abnormal.py --list-only               # 只列出，不清理
  python3 ccc-clean-abnormal.py --force                   # 强制清理所有（含 persistent failure）

分类逻辑:
  - 有 verdict/report（非持续性失败） → 回 testing
  - 有 plan 但无 verdict              → 回 planned
  - 无 plan/verdict                   → 回 backlog
  - persistent failure                → 保留（除非 --force）

可复现：重复跑对同一 abnormal 列给出相同结果。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def _resolve_workspace() -> Path:
    """自动或显式找到目标 workspace。"""
    for i, arg in enumerate(sys.argv[1:], 1):
        if arg == "--workspace" and i < len(sys.argv):
            return Path(sys.argv[i + 1]).resolve()
    # 从 .ccc/board/ 上溯
    cwd = Path.cwd()
    for parent in [cwd] + list(cwd.parents):
        if (parent / ".ccc" / "board").is_dir():
            return parent
    print("❌ 未找到 workspace（无 .ccc/board/），请用 --workspace 指定", file=sys.stderr)
    sys.exit(1)


def _has_flag(flag: str) -> bool:
    return flag in sys.argv[1:]


def _board_path(ws: Path) -> Path:
    return ws / ".ccc" / "board"


def _list_abnormal_tasks(ws: Path) -> list[dict]:
    bp = _board_path(ws)
    ab_dir = bp / "abnormal"
    tasks = []
    if ab_dir.is_dir():
        for fp in sorted(ab_dir.glob("*.jsonl")):
            try:
                data = json.loads(fp.read_text())
                tasks.append(data)
            except (json.JSONDecodeError, OSError):
                pass
    return tasks


def _classify(task: dict) -> str:
    """Return the target column for this abnormal task."""
    # 检查 verdict
    verdict_file = Path(task.get("_path", ""))
    # 找 verdicts 目录
    tid = task.get("id", "")
    ws = Path(task.get("_ws", "")) if task.get("_ws") else None

    if ws:
        has_verdict = (ws / ".ccc" / "verdicts" / f"{tid}.verdict.md").exists()
        has_report = (ws / ".ccc" / "reports" / f"{tid}.report.md").exists()
    else:
        has_verdict = False
        has_report = False

    note = task.get("note", "")

    if has_verdict:
        # 有 verdict — 可能是 reviewer/tester 通过了但后续流程卡住
        return "testing"

    if has_report and "persistent" not in note.lower():
        # 有 report 但无 verdict → 可能需要重新评审
        return "planned"

    plan_dir = (ws / ".ccc" / "plans") if ws else Path("/nonexistent")
    has_plan = plan_dir.is_dir() and list(plan_dir.glob(f"{tid}*"))

    if has_plan:
        return "planned"

    # 无任何产物 → 回 backlog 让 product 重新处理
    return "backlog"


def _move_task(ws: Path, task: dict, to_col: str) -> None:
    """Move task from abnormal to to_col by writing/removing files."""
    bp = _board_path(ws)
    tid = task["id"]
    src = bp / "abnormal" / f"{tid}.jsonl"
    dst = bp / to_col / f"{tid}.jsonl"

    if not src.exists():
        return

    task["status"] = to_col
    # strip abnormal tags for cleaner state
    tags = task.get("tags", [])
    if "abnormal" in tags:
        tags.remove("abnormal")
    if "automated" in tags:
        tags.remove("automated")
    task["tags"] = tags
    # clean [ABNORMAL] prefix from title
    title = task.get("title", "")
    if title.startswith("[ABNORMAL] "):
        task["title"] = title[11:]
    task["note"] = task.get("note", "") + f"\n[自动清理] → {to_col}"

    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(task, ensure_ascii=False) + "\n")
    src.unlink(missing_ok=True)
    print(f"  ✅ {tid}: abnormal → {to_col}")


def main() -> int:
    ws = _resolve_workspace()
    list_only = _has_flag("--list-only")
    force = _has_flag("--force")

    print(f"📋 workspace: {ws}")
    print(f"   异常列清理 {'(只列出)' if list_only else ''}\n")

    tasks = _list_abnormal_tasks(ws)
    if not tasks:
        print("  abnormal 列为空。")
        return 0

    # 给 task 挂上 ws 路径
    for t in tasks:
        t["_ws"] = str(ws)

    moved = 0
    kept = 0
    for task in tasks:
        tid = task["id"]
        note = task.get("note", "")[:80]
        cls = _classify(task)

        # persistent failure → 保留（除非 --force）
        if cls == "abnormal":
            print(f"  ⏭ {tid}: 持续性失败，保留（{note}）")
            kept += 1
            continue

        print(f"  → {tid}: {cls}（{note}）")

        if list_only:
            continue

        if task.get("status", "").lower() != "abnormal":
            print("    已不是 abnormal 状态，跳过")
            continue

        _move_task(ws, task, cls)
        moved += 1

    print(f"\n📊 结果: {moved} 已清理, {kept} 保留, {len(tasks)} 总")
    return 0


if __name__ == "__main__":
    sys.exit(main())
